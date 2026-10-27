"""Small opt-in live regression; at most 8 paid requests, never writes app data."""
from __future__ import annotations
import argparse
import asyncio
import copy
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from term_extractor_app.ai_review import review_service as review
from term_extractor_app.ai_review import evidence_service as evidence
from term_extractor_app.ai_review.learning_service import build_learning_messages
from term_extractor_app.ai_review.learning_protocol import validate_proposal
from term_extractor_app.ai_review.prompt_service import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT
from term_extractor_app.ai_review.shared_provider import _load_provider_settings
from term_extractor_app.models import LLMRequest
from term_extractor_app.providers import ProviderRegistry


CASES=[
 ('符号惯例','攻击力提高25%。','Increases ATK by +25%.',False),
 ('符号惯例中的真错','攻击力提高25%。','Increases ATK by +15%.',True),
 ('角色自然改写','他总能在绝境中找到出路。','He always finds a way when all hope seems lost.',False),
 ('角色身份真错','她是国王的妹妹。','She is the king’s daughter.',True),
 ('技能命名','生命兑换','Health Exchange',False),
 ('否定遗漏','未击败首领时不能领取奖励。','Claim rewards before defeating the boss.',True),
 ('语言频道','简体中文','简体中文',False),
 ('语法','所有随从变身，并保留星级。','All Minions transform (retains their own rank).',True),
 ('名称不必缩写','生命转化','Health Conversion',False),
 ('条件遗漏','生命低于50%时，攻击力提高20%。','Increases ATK by 20%.',True),
]


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--recheck-context',action='store_true');parser.add_argument('--verify-context-only',action='store_true');args=parser.parse_args()
    if not args.live:raise SystemExit('Use --live to authorize up to 8 DeepSeek requests.')
    provider_name,provider=_load_provider_settings()
    if 'deepseek' not in (provider_name+' '+provider.base_url).lower() or not provider.api_key:
        raise SystemExit('Configured DeepSeek credentials are required.')
    out=ROOT/'output'/'qa_evidence_deepseek_20261027';out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists() and not (args.recheck_context or args.verify_context_only):raise SystemExit('Live report exists; inspect it before authorizing another run.')
    if args.verify_context_only and (out/'controlled_context_verification.json').exists():raise SystemExit('Controlled verification already exists.')
    if args.recheck_context and (out/'context_recheck.json').exists():raise SystemExit('Targeted recheck already exists; inspect it before further spending.')
    config={'mode':'normal','system_prompt':DEFAULT_SYSTEM_PROMPT,'user_prompt':DEFAULT_USER_PROMPT,
        'source_language':'中文','target_language':'英语','evidence_enabled':True,'memoq_term_pairs':[{'source':'生命','targets':['HP'],'entry_note':'属性数值的名称'}],
        'memory_snapshot':{'version':1,'rules':[
            {'id':'numeric','active':True,'text':'本项目属性增益允许使用 by +数值，不单独因正号判错；仍检查数值、增减方向与作用对象。'},
            {'id':'character','active':True,'text':'角色介绍允许符合角色定位的自然改写，仍须保留身份、关系与核心设定。'}]}}
    items=[{'id':f'case{i+1}','source_file':'regression.xlsx','sheet_name':'Main','item_order':i+1,'source_text':source,'target_text':target,
            'info_json':json.dumps([{'category':'用途','value':'语言频道名称' if i==6 else '角色介绍' if i in {2,3} else '技能名称' if i in {4,8} else '技能说明'}],ensure_ascii=False)}
           for i,(_,source,target,_) in enumerate(CASES)]
    items.extend([{'id':'reference1','source_file':'regression.xlsx','sheet_name':'Main','item_order':30,'source_text':'Français','target_text':'Français','info_json':json.dumps([{'category':'用途','value':'语言频道名称'}],ensure_ascii=False)},
                  {'id':'reference2','source_file':'regression.xlsx','sheet_name':'Main','item_order':31,'source_text':'日本語','target_text':'日本語','info_json':json.dumps([{'category':'用途','value':'语言频道名称'}],ensure_ascii=False)}])
    index=evidence.EvidenceIndex(items,config)
    adapter=ProviderRegistry.create_adapter(provider_name,provider)
    metrics=json.loads((out/'metrics.json').read_text(encoding='utf8')) if (args.recheck_context or args.verify_context_only) else []
    saved={};logs=[]
    async def send(request,attempt=1):
        if len(metrics)>=8:raise RuntimeError('Live request budget exhausted')
        start=time.perf_counter();metrics.append({'id':request.task_id})
        response=await adapter.send_prompt(request,attempt=1)
        metrics[-1].update(seconds=round(time.perf_counter()-start,2),success=response.success,usage=response.response_metadata.get('usage',{}))
        (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf8')
        if not response.success:raise RuntimeError(response.error_type or 'DeepSeek request failed')
        return response
    try:
        if args.recheck_context or args.verify_context_only:
            package=[items[6]]
            payload=review._build_request_payload(package,config)
            prompt=review._build_user_prompt(config,json.dumps(payload,ensure_ascii=False),True,bool(payload.get('term_pairs')))
            request=LLMRequest(task_id='qa_context_recheck',task_type='candidate_review_batch',prompt=prompt,
                messages=[{'role':'system','content':review._effective_system_prompt(config)},{'role':'user','content':prompt}],
                metadata={'package':package,'enable_thinking':True,'reasoning_effort':'low'})
            if args.verify_context_only:
                from term_extractor_app.models import LLMResponse
                initial=json.loads((out/'context_recheck.json').read_text(encoding='utf8'))['initial']
                initial['context_requests']=[{'item_id':'case7','kind':'search','query':'语言频道名称','field':'info','reason':'核对同用途名称是否保留本语言自称'}]
                response=LLMResponse('qa_controlled','candidate_review_batch',json.dumps(initial,ensure_ascii=False),provider_name,provider.model,0,1,True)
            else:
                response=await send(request)
                initial=review._parse_json_object(response.content)
            response=await evidence.verify_response(request,response,index=index,send=send,config=config,parse=review._parse_json_object,validate=review._validate_response_items,log=logs.append)
            final=review._parse_json_object(response.content)
            record={'initial':initial,'final':final,'metrics':metrics,'logs':logs,'controlled_trigger':args.verify_context_only}
            (out/('controlled_context_verification.json' if args.verify_context_only else 'context_recheck.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps({'total_requests':len(metrics),'initial_issue':initial['items'][0]['has_issue'],'final_issue':final['items'][0]['has_issue'],'requested_context':bool(initial.get('context_requests'))},ensure_ascii=False))
            if final['items'][0]['has_issue']:raise SystemExit('Language-channel false positive remains; inspect evidence before release.')
            return
        for mode in ['baseline','evidence']:
            mode_config={**config,'evidence_enabled':mode=='evidence'}
            combined=[];start=time.perf_counter()
            for number,package in enumerate([items[:5],items[5:10]],1):
                payload=review._build_request_payload(package,mode_config)
                prompt=review._build_user_prompt(mode_config,json.dumps(payload,ensure_ascii=False),True,bool(payload.get('term_pairs')))
                request=LLMRequest(task_id=f'qa_{mode}_{number}',task_type='candidate_review_batch',prompt=prompt,
                    messages=[{'role':'system','content':review._effective_system_prompt(mode_config)},{'role':'user','content':prompt}],
                    metadata={'package':package,'enable_thinking':True,'reasoning_effort':'low'})
                response=await send(request)
                if mode=='evidence':
                    response=await evidence.verify_response(request,response,index=index,send=send,config=mode_config,parse=review._parse_json_object,validate=review._validate_response_items,log=logs.append)
                parsed=review._parse_json_object(response.content);review._validate_response_items(parsed,package,mode_config)
                combined.extend(parsed['items'])
                (out/f'{mode}_{number}.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding='utf8')
            truth={row['id']:CASES[i][3] for i,row in enumerate(items[:10])}
            saved[mode]={'seconds':round(time.perf_counter()-start,2),'false_positives':[r['id'] for r in combined if r['has_issue'] and not truth[r['id']]],
                         'misses':[r['id'] for r in combined if not r['has_issue'] and truth[r['id']]],'items':combined}
            print(mode,{key:value for key,value in saved[mode].items() if key!='items'},flush=True)
        old={'version':0,'rules':[]}
        for case,reason in [('ambiguous','忽略'),('specific','这里是本项目的属性增益固定写法 by +数值，不单独因正号报错；仍检查数值和增减方向。')]:
            feedback=[{'result_id':'qa','source_text':'攻击力提高25%。','target_text':'Increases ATK by +25%.','issue':'by 后不应有正号',
                       'suggestion':'Increases ATK by 25%.','reason':reason,'decision':'disagree'}]
            messages=build_learning_messages(old,feedback)
            request=LLMRequest(task_id='qa_learning_'+case,task_type='ai_review_memory',prompt=messages[-1]['content'],messages=messages,metadata={'enable_thinking':False})
            response=await send(request)
            parsed=review._parse_json_object(response.content);validate_proposal(parsed,old,feedback)
            if case=='ambiguous' and not parsed.get('questions'):raise AssertionError('Unexplained ignore did not ask a question')
            if case=='specific' and not parsed.get('new_rules'):raise AssertionError('Explicit format feedback did not produce a scoped rule')
            saved['learning_'+case]=parsed
            (out/f'learning_{case}.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding='utf8')
    finally:
        await adapter.close()
        (out/'partial.json').write_text(json.dumps({'results':saved,'logs':logs,'metrics':metrics},ensure_ascii=False,indent=2),encoding='utf8')
    report={'model':provider.model,'requests':len(metrics),'cases':len(CASES),'results':saved,'metrics':metrics,'logs':logs,
            'limits':'Small hand-labeled regression only; no guarantee for unknown files; no app data changed.'}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    if saved['evidence']['misses']:raise SystemExit('Live regression found missed known errors; inspect before release.')
    print('LIVE_QA_COMPLETE',json.dumps({'requests':len(metrics),'model':provider.model,'report':str(out/'summary.json')},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
