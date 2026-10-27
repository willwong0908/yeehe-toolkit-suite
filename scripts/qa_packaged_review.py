"""Validate the release ZIP in an isolated directory and on a private test port."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'release_bundle'
ZIP=ROOT/'Yeehe_Toolkit_Suite_v2.2.11.zip'
SMOKE=ROOT/'output'/'package_smoke_2.2.11'
for file in BUNDLE.rglob('settings.json'):
    settings=json.loads(file.read_text(encoding='utf8'))
    assert all(not item.get('api_key') for item in settings.get('provider_settings',{}).values())
files=[p for p in BUNDLE.rglob('*') if p.is_file()]
assert not any(p.suffix in {'.sqlite3','.db','.sqlite'} for p in files)
if not ZIP.exists() or any(file.stat().st_mtime>ZIP.stat().st_mtime for file in files):
    with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in files:archive.write(file,file.relative_to(BUNDLE))
        archive.writestr('更新说明.txt',(ROOT/'release_notes_2.2.11.txt').read_bytes())
with zipfile.ZipFile(ZIP) as archive:
    assert archive.testzip() is None
    assert 'program/Yeehe_Toolkit_Suite.exe' in archive.namelist()
    SMOKE.mkdir(parents=True,exist_ok=True)
    archive.extractall(SMOKE)

with socket.socket() as probe:
    probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
base=f'http://127.0.0.1:{port}'
def api(route,method='GET',data=None):
    request=urllib.request.Request(base+route,data=json.dumps(data).encode('utf8') if data is not None else None,
        method=method,headers={'Content-Type':'application/json','User-Agent':'Yeehe-Packaged-QA'})
    with urllib.request.urlopen(request,timeout=10) as response:
        raw=response.read().decode('utf8')
        return json.loads(raw) if response.headers.get_content_type()=='application/json' else raw

log=open(ROOT/'output'/'package_smoke_2.2.11.log','w',encoding='utf8')
process=subprocess.Popen([str(SMOKE/'program'/'Yeehe_Toolkit_Suite.exe')],cwd=SMOKE,
    env={**os.environ,'YEEHE_WEBUI_PORT':str(port),'YEEHE_DISABLE_BROWSER_AUTOOPEN':'1'},
    stdin=subprocess.PIPE,stdout=log,stderr=log,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW)
try:
    deadline=time.monotonic()+40
    while True:
        if process.poll() is not None:raise RuntimeError('Packaged app exited during startup')
        try:
            status=api('/api/status')
            break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.25)
    html=api('/')
    javascript=api('/assets/app.js')
    assert '2.2.11' in html and 'renderLearningQuestion' in javascript and 'verification_pending' in javascript
    sid=api('/api/ai-review/conversations','POST',{'title':'Packaged QA'})['session']['id']
    database=next(SMOKE.rglob('app.sqlite3'))
    assert database.resolve().is_relative_to(SMOKE.resolve())
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO file_batches(id,original_filename,stored_path,file_type,status,created_at,updated_at) VALUES('smoke-b','smoke.xlsx','','xlsx','ready','now','now')")
        conn.execute("INSERT INTO file_items(id,batch_id,source_file,source_text,target_text,item_order,created_at) VALUES('smoke-i','smoke-b','smoke.xlsx','生命兑换','Health Exchange',1,'now')")
        conn.execute("INSERT INTO review_tasks(id,batch_id,session_id,status,config_json,created_at,updated_at) VALUES('smoke-t','smoke-b',?,'completed',?,'now','now')",(sid,json.dumps({'mode':'normal','session_id':sid})))
        conn.execute("INSERT INTO review_results(id,task_id,item_id,cache_key,status,has_issue,issue_type,issue,suggestion,raw_result_json,created_at,updated_at) VALUES('smoke-r','smoke-t','smoke-i','','completed',1,'术语','应使用HP','HP Exchange','{}','now','now')")
    api(f'/api/ai-review/conversations/{sid}/feedback','POST',{'task_id':'smoke-t','entries':[{'result_id':'smoke-r','decision':'disagree','reason':''}]})
    deadline=time.monotonic()+10
    while True:
        learning=api(f'/api/ai-review/conversations/{sid}/learning')
        if learning['questions']:break
        if time.monotonic()>deadline:raise RuntimeError('Packaged QA did not create clarification')
        time.sleep(.1)
    question=learning['questions'][0]
    assert question['options'][1]['requires_reason']
    api(f'/api/ai-review/conversations/{sid}/learning-questions/{question["id"]}/answer','POST',{'option':0})
    assert api(f'/api/ai-review/conversations/{sid}/memory')['version']==0
    api(f'/api/ai-review/conversations/{sid}','DELETE',{'confirm':True})
    print(json.dumps({'version':'2.2.11','startup':True,'qa_flow':True,'paid_calls':0,
        'bytes':ZIP.stat().st_size,'sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest()},ensure_ascii=False))
finally:
    if process.poll() is None:
        process.stdin.write('q\n');process.stdin.flush()
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.terminate();process.wait(timeout=5)
    log.close()
assert process.returncode==0,process.returncode
print('Packaged process exited cleanly')
