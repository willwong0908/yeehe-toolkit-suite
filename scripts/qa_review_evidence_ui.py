"""Isolated QA host with real persistence and simulated model responses."""
from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
QA=ROOT/'output'/'playwright'/'review-evidence-qa'
QA.mkdir(parents=True,exist_ok=True)
from term_extractor_app import storage, telemetry
patch.object(storage,'get_app_root',return_value=QA).start()
patch.object(telemetry,'track_event').start()
store=storage.SettingsStore(storage.get_app_paths());settings=store.load()
settings.provider_settings[settings.provider_name].api_key='qa-placeholder'
settings.provider_settings[settings.provider_name].model='qa-simulated'
store.save(settings)
from term_extractor_app.ai_review import database as db,learning_service as learning,shared_provider,review_service
from term_extractor_app.ai_review.session_store import create_session
from test_ai_review_learning import learning_reply

def learn(task_id,messages,**kwargs):
    payload=json.loads(messages[-1]['content'])
    if payload['feedback'][0].get('qa_confirmed'):
        return learning_reply(['技能名称允许使用自然完整词，属性数值术语仍单独检查。'])
    return json.dumps({'protocol':2,'new_rules':[],'triggered_ids':[],'questions':[
        {'feedback_indexes':[0],'prompt':'你忽略这条报错，是仅接受当前技能名称，还是希望同类名称都避免机械使用属性缩写？',
         'options':[{'label':'仅确认当前名称可接受','reason':'当前是技能名称，Health Exchange 可以接受；不扩展到其他名称。','scope':'case'},
                    {'label':'作为项目技能命名原则','reason':'本项目技能名称允许自然完整词；属性数值仍按术语检查。','scope':'rule'}]}]},ensure_ascii=False)

patch.object(shared_provider,'followup_chat',side_effect=learn).start()
db.init_db()
session=create_session(title='学习范围确认 QA',source_language='中文',target_languages=['英语'])
sid=session['id'];bid='qa_'+sid;tid='qa_task_'+sid
config={'mode':'normal','model':'qa-simulated','session_id':sid,'system_prompt':'检查语义与语言，不因名称偏好报错','user_prompt':'{text}',
        'source_language':'中文','target_language':'英语','enable_ai_review':True}
with db.get_connection() as conn:
    conn.execute('INSERT INTO file_batches(id,original_filename,stored_path,file_type,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(bid,'QA.xlsx','','xlsx','ready','now','now'))
    conn.execute('INSERT INTO file_items(id,batch_id,source_file,source_text,target_text,item_order,created_at) VALUES(?,?,?,?,?,?,?)',('item_'+sid,bid,'QA.xlsx','生命兑换','Health Exchange',1,'now'))
    conn.execute('INSERT INTO review_tasks(id,batch_id,session_id,status,config_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(tid,bid,sid,'completed',db.dumps_json(config),'now','now'))
    conn.execute('INSERT INTO review_session_tasks VALUES(?,?,?,?)',(sid,'英语',tid,'now'))
review_service._save_review_results_bulk(tid,[({'id':'item_'+sid,'cache_key':'qa'}, {'id':'item_'+sid,'has_issue':True,'issue_type':'术语','issue':'生命必须使用HP','suggestion':'HP Exchange'})])
rid=review_service.get_review_results(tid,None)[0]['id']
learning.submit_feedback(sid,tid,[{'result_id':rid,'decision':'disagree','reason':''}])
(QA/'session.json').write_text(json.dumps({'session_id':sid,'task_id':tid}),encoding='utf8')
from term_extractor_app.web_app import app
if __name__=='__main__':
    import uvicorn
    print('QA_SESSION='+sid,flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8877,access_log=False)
