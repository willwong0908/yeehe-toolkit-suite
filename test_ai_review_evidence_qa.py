from __future__ import annotations

import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

from term_extractor_app.ai_review import evidence_service as evidence, learning_service as learning
from term_extractor_app.ai_review import database as db
from term_extractor_app.ai_review import review_service as review
from term_extractor_app.ai_review.learning_protocol import validate_proposal, enrich_rules
from term_extractor_app.ai_review.learning_qa import questions
from term_extractor_app.models import LLMRequest, LLMResponse
import test_ai_review_learning as fixtures


def result(id_, issue=False, **extra):
    return {'id':id_,'has_issue':issue,'issue_type':'语法' if issue else '',
            'issue':'发现错误' if issue else '', 'suggestion':'Correct translation.' if issue else '',**extra}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.items=[{'id':'a','source_file':'first.xlsx','sheet_name':'Sheet1','item_order':1,'source_text':'简体中文','target_text':'简体中文'},
                    {'id':'b','source_file':'first.xlsx','sheet_name':'Sheet1','item_order':2,'source_text':'Français','target_text':'Français'},
                    {'id':'c','source_file':'other.xlsx','sheet_name':'Sheet1','item_order':3,'source_text':'Français','target_text':'French'}]
        self.config={'mode':'normal','evidence_enabled':True,'memoq_term_pairs':[]}
        self.index=evidence.EvidenceIndex(self.items,self.config)

    def test_search_is_current_file_only_and_cache_tracks_result_membership(self):
        selector={'kind':'search','query':'Français','field':'all'}
        records,dependency=self.index.lookup(self.items[0],selector)
        self.assertEqual(records['total'],1)
        cached={'_verification':{'dependencies':[dependency]}}
        self.assertTrue(self.index.cache_valid(self.items[0],cached))
        self.items[2]['target_text']='changed unrelated file'
        self.assertTrue(self.index.cache_valid(self.items[0],cached))
        self.items[1]['target_text']='French'
        self.assertFalse(self.index.cache_valid(self.items[0],cached))

    def test_cached_evidence_survives_reimported_ids_but_not_new_matches(self):
        selector={'kind':'search','query':'Français','field':'source'}
        _,dependency=self.index.lookup(self.items[0],selector)
        imported=copy.deepcopy(self.items)
        for row in imported:row['id']='new-'+row['id']
        index=evidence.EvidenceIndex(imported,self.config)
        self.assertTrue(index.cache_valid(imported[0],{'_verification':{'dependencies':[dependency]}}))
        imported.append({**imported[1],'id':'added'})
        self.assertFalse(evidence.EvidenceIndex(imported,self.config).cache_valid(imported[0],{'_verification':{'dependencies':[dependency]}}))

    def test_request_budget_ids_and_no_new_file_access(self):
        parsed={'context_requests':[{'item_id':'a','kind':'search','query':'x','reason':'why'}]*20+[{'item_id':'foreign','reason':'why'}]}
        self.assertEqual(len(evidence.collect_requests(parsed,self.items)['a']),2)
        with self.assertRaises(ValueError):self.index.lookup(self.items[0],{'kind':'open_file','query':'secret'})

    def test_duplicate_filenames_do_not_mix_attachments(self):
        a={**self.items[0],'location_json':json.dumps({'attachment_id':'one'})}
        b={**self.items[1],'location_json':json.dumps({'attachment_id':'two'})}
        records,_=evidence.EvidenceIndex([a,b],self.config).lookup(a,{'kind':'search','query':'Français'})
        self.assertEqual(records['total'],0)

    def run_verify(self, initial, checked, selector=None):
        selector=selector or {'item_id':'a','kind':'search','query':'Français','field':'all','reason':'语言频道是否应自称'}
        request=LLMRequest(task_id='qa',task_type='candidate_review_batch',prompt='',messages=[{'role':'system','content':'Review all errors.'}],metadata={'package':[self.items[0]]})
        response=LLMResponse('qa','candidate_review_batch',json.dumps({'items':[initial],'context_requests':[selector]}),'mock','mock',1,1,True)
        send=AsyncMock(return_value=LLMResponse('qa','candidate_review_batch',json.dumps({'items':[checked]}),'mock','mock',1,1,True))
        value=asyncio.run(evidence.verify_response(request,response,index=self.index,send=send,config=self.config,parse=review._parse_json_object,validate=review._validate_response_items))
        self.assertEqual(send.await_count,1)
        return json.loads(value.content)['items'][0]

    def test_withdrawal_without_real_evidence_is_rejected(self):
        value=self.run_verify(result('a',True),result('a',False,evidence_refs=['invented'],verification_reason='自然表达'))
        self.assertTrue(value['has_issue']);self.assertTrue(value['_verification']['unresolved'])

    def test_grounded_withdrawal_and_new_detection_both_allowed(self):
        block,_=self.index.lookup(self.items[0],{'kind':'search','query':'Français','field':'all'})
        refs=[block['records'][0]['ref']]
        value=self.run_verify(result('a',True),result('a',False,evidence_refs=refs,verification_reason='同一语言频道采用本语言自称'))
        self.assertFalse(value['has_issue']);self.assertFalse(value['_verification']['unresolved'])
        value=self.run_verify(result('a',False),result('a',True,evidence_refs=refs,verification_reason='查到支持具体问题的证据'))
        self.assertTrue(value['has_issue'])

    def test_failed_lookup_cannot_become_healthy_cache(self):
        value=self.run_verify(result('a',False),result('a',False),{'item_id':'a','kind':'search','query':'absent','reason':'是否有例外'})
        self.assertTrue(value['_verification']['unresolved'])
        self.assertFalse(self.index.cache_valid(self.items[0],value))

    def test_suggestion_integrity_without_assuming_marker_grammar(self):
        row={'source_text':'{Ready} 原文','target_text':'{Ready} '+('First paragraph. '*20)+'\nSecond paragraph.'}
        self.assertTrue(evidence.suggestion_problem(row,result('a',True,suggestion='Second paragraph.')))
        row={'source_text':'不可{Sell}','target_text':"can't be {Sell=sold}"}
        self.assertFalse(evidence.suggestion_problem(row,result('a',True,suggestion="cannot be {Sell=sold}")))
        row={'source_text':'{0} {1}','target_text':'{0} plus {1}'}
        self.assertIn('变量',evidence.suggestion_problem(row,result('a',True,suggestion='{0} only')))
        row={'source_text':'First paragraph.\n\nSecond paragraph.','target_text':'x'*280+'\n\n'+'y'*450}
        self.assertIn('遗漏段落',evidence.suggestion_problem(row,result('a',True,suggestion='y'*450)))


class LearningQATests(unittest.TestCase):
    setUp=fixtures.ReviewLearningTests.setUp
    tearDown=fixtures.ReviewLearningTests.tearDown
    feedback=fixtures.ReviewLearningTests.feedback

    def test_unresolved_clean_result_is_not_cached_and_is_exported_as_pending(self):
        from term_extractor_app.ai_review import output_service
        from openpyxl import load_workbook
        row=result('i0',False,_verification={'unresolved':True,'dependencies':[]})
        with db.get_connection() as conn:
            conn.execute("DELETE FROM review_results WHERE task_id='t' AND item_id='i0'")
        review._save_review_results_bulk('t',[(self.items[0],row)])
        learning.cache_results(self.session,[(self.items[0],row)])
        self.assertEqual(learning.cached_results(self.session,['k0']),{})
        self.assertTrue(review.get_review_results('t')[0]['verification_pending'])
        book=load_workbook(output_service.generate_review_excel('t'))
        self.assertEqual(book['审校结果']['F2'].value,'待核实');book.close()

    def question_reply(self):
        return db.dumps_json({'protocol':2,'new_rules':[],'triggered_ids':[],
            'questions':[{'feedback_indexes':[0],'prompt':'仅本条可接受，还是相同语境也适用？','options':[
                {'label':'仅当前案例','reason':'只确认本条可接受，范围不扩展','scope':'case'},
                {'label':'同类角色介绍','reason':'角色介绍允许自然改写，但不能改变身份','scope':'rule'}]}]})

    def prepare_question(self):
        event=self.feedback(reason='忽略')
        with patch('term_extractor_app.ai_review.shared_provider.followup_chat',return_value=self.question_reply()):
            learning._learning_worker(self.session)
        pending=questions(self.session)
        self.assertEqual(len(pending),1)
        self.assertEqual(learning.memory_snapshot(self.session)['version'],0)
        self.assertEqual(learning.learning_status(self.session)['events'][0]['status'],'needs_input')
        return pending[0],event

    def answer(self, question, payload, session=None):
        return self.client.post(f'/api/ai-review/conversations/{session or self.session}/learning-questions/{question["id"]}/answer',json=payload)

    def test_case_answer_never_calls_model_or_generalizes_and_cannot_replay(self):
        question,_=self.prepare_question()
        self.assertEqual(self.answer(question,{'option':0},self.other).status_code,400)
        self.assertEqual(self.answer(question,{'option':0}).status_code,200)
        with patch('term_extractor_app.ai_review.shared_provider.followup_chat') as call:
            learning._learning_worker(self.session);call.assert_not_called()
        self.assertEqual(learning.memory_snapshot(self.session)['version'],0)
        self.assertEqual(self.answer(question,{'option':0}).status_code,400)
        self.assertFalse(questions(self.session))

    def test_rule_answer_resumes_learning_with_explicit_scope(self):
        question,_=self.prepare_question()
        self.assertEqual(self.answer(question,{'option':1}).status_code,400)
        self.assertEqual(self.answer(question,{'text':'角色介绍允许自然改写，但不能改变身份'}).status_code,200)
        with patch('term_extractor_app.ai_review.shared_provider.followup_chat',return_value=fixtures.learning_reply(['角色介绍允许自然改写，保留身份信息'])) as call:
            learning._learning_worker(self.session)
        payload=db.loads_json(call.call_args.kwargs['messages'][-1]['content'],{})
        self.assertTrue(payload['feedback'][0]['qa_confirmed'])
        self.assertEqual(learning.memory_snapshot(self.session)['version'],1)
        self.assertIn('feedback_sources',learning.memory_snapshot(self.session)['rules'][0])

    def test_free_text_does_not_auto_submit_and_latest_feedback_wins(self):
        question,_=self.prepare_question()
        self.assertEqual(self.answer(question,{'text':''}).status_code,400)
        self.assertEqual(self.answer(question,{'option':0,'text':'both'}).status_code,400)
        self.feedback(reason='这里仅当前技能名接受')
        self.assertFalse(questions(self.session))
        self.assertEqual(self.answer(question,{'text':'推广到其他技能'}).status_code,400)

    def test_manual_case_and_rule_survive_automatic_update_and_undo(self):
        rules=[{'id':'a','text':'规范','weight':1.,'active':True,'few_shot':{'source_text':'old','target_text':'旧'}}]
        with db.get_connection() as conn:conn.execute('INSERT INTO review_memory VALUES(?,?,?,?)',(self.session,1,db.dumps_json(rules),'now'))
        memory=learning.update_memory(self.session,1,[{'id':'a','text':'手动规范','few_shot':{'source_text':'manual','target_text':'手动'}}])
        self.assertTrue(memory['rules'][0]['manual_edited']);self.assertTrue(memory['rules'][0]['manual_example'])
        self.feedback()
        reply=json.loads(fixtures.learning_reply(triggered_ids=['a'],few_shot_updates=[{'id':'a','few_shot':{'feedback_index':0,'source_text':'source0','target_text':'target0'}}]))
        with patch('term_extractor_app.ai_review.shared_provider.followup_chat',return_value=db.dumps_json(reply)):
            learning._learning_worker(self.session)
        rule=learning.memory_snapshot(self.session)['rules'][0]
        self.assertEqual(rule['text'],'手动规范');self.assertEqual(rule['few_shot']['source_text'],'manual')
        version=learning.memory_snapshot(self.session)['version']
        restored=self.client.post(f'/api/ai-review/conversations/{self.session}/memory/restore',json={'version':version})
        self.assertEqual(restored.status_code,200)
        self.assertEqual(restored.json()['version'],version+1)

    def test_case_feedback_and_unexplained_feedback_cannot_create_rules(self):
        proposal=json.loads(fixtures.learning_reply(['新规范']))
        for feedback in [[{'reason':'忽略'}],[{'reason':'明确理由','learning_scope':'case'}]]:
            with self.assertRaises(ValueError):validate_proposal(proposal,{'version':0,'rules':[]},feedback)

    def test_agree_feedback_cannot_become_an_acceptable_example(self):
        proposal=json.loads(fixtures.learning_reply([{'text':'数字必须对应','few_shot':{'feedback_index':0,'source_text':'25','target_text':'15'}}]))
        with self.assertRaises(ValueError):validate_proposal(proposal,{'version':0,'rules':[]},[{'reason':'原文25译为15确实错误','decision':'agree'}])

    def test_session_delete_removes_pending_qa_and_history(self):
        self.prepare_question()
        from term_extractor_app.ai_review.session_store import delete_session
        delete_session(self.session)
        self.assertFalse(questions(self.session))
        with db.get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM review_memory_history WHERE session_id=?',(self.session,)).fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
