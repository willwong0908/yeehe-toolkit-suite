"""Non-blocking, session-scoped learning clarification with explicit answers."""
from __future__ import annotations

import uuid
from .database import get_connection, dumps_json, loads_json, utc_now


def questions(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows=conn.execute("SELECT * FROM review_learning_questions WHERE session_id=? AND status='pending' ORDER BY created_at,rowid LIMIT 100",(session_id,)).fetchall()
    return [{'id':row['id'],'event_id':row['event_id'],'status':row['status'],
             **loads_json(row['payload_json'],{})} for row in rows]


def save_questions(conn, event: dict, proposal: dict, feedback: list[dict]) -> None:
    now=utc_now()
    for question in proposal['questions']:
        id_=uuid.uuid4().hex
        payload={**question,'examples':[{'source':feedback[i].get('source_text',''),
                    'target':feedback[i].get('target_text',''),'issue':feedback[i].get('issue',''),
                    'reason':feedback[i].get('reason','')} for i in question['feedback_indexes'][:2]]}
        conn.execute('INSERT INTO review_learning_questions VALUES(?,?,?,?,?,?,?,?,?)',
                     (id_,event['session_id'],event['id'],'pending',dumps_json(payload),'',now,now,''))
    conn.execute("UPDATE review_learning_events SET status='needs_input',error='',updated_at=? WHERE id=?",(now,event['id']))


def answer(session_id: str, question_id: str, *, option: int | None = None, text: str = '') -> dict:
    from .learning_service import options, start_learning
    from .session_store import add_message, emit_event
    if not options()['learning_enabled']:
        raise ValueError('请先开启自主学习，待确认反馈仍已保留')
    answer_text=str(text or '').strip()
    if option is not None and answer_text:
        raise ValueError('请选择一个选项，或自行输入原因')
    if len(answer_text)>2000:
        raise ValueError('补充原因请控制在2000字以内')
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM review_sessions WHERE id=?',(session_id,)).fetchone():
            raise ValueError('审校会话不存在')
        row=conn.execute('SELECT * FROM review_learning_questions WHERE id=? AND session_id=?',(question_id,session_id)).fetchone()
        if not row or row['status']!='pending':
            raise ValueError('该学习问题不存在或已经处理，请刷新聊天')
        event=conn.execute('SELECT * FROM review_learning_events WHERE id=? AND session_id=?',(row['event_id'],session_id)).fetchone()
        if not event or event['status']!='needs_input':
            raise ValueError('该学习反馈状态已变化，请刷新聊天')
        payload=loads_json(row['payload_json'],{})
        feedback=loads_json(event['payload_json'],[])
        if option is not None:
            if type(option) is not int or not 0<=option<len(payload.get('options',[])):
                raise ValueError('学习选项无效')
            choice=payload['options'][option]
            if choice.get('requires_reason'):
                raise ValueError('请在自行输入中补充具体原因，再总结通用规范')
            answer_text=choice['reason'];scope=choice['scope'];label=choice['label']
        else:
            if not answer_text:
                raise ValueError('请输入忽略原因或希望采用的判断原则')
            scope='rule';label=answer_text
        for i in payload['feedback_indexes']:
            item=feedback[i]
            current=conn.execute('SELECT decision,reason FROM review_feedback WHERE result_id=? AND session_id=?',(item['result_id'],session_id)).fetchone()
            if not current or current['decision']!=item.get('decision','disagree') or current['reason']!=str(item.get('reason') or ''):
                raise ValueError('这条反馈已经修改，请使用最新反馈重新学习')
            item.update(reason=answer_text,learning_scope=scope,qa_confirmed=True)
            conn.execute('UPDATE review_feedback SET reason=?,updated_at=? WHERE result_id=? AND session_id=?',(answer_text,utc_now(),item['result_id'],session_id))
        conn.execute("UPDATE review_learning_questions SET status='answered',answer_json=?,updated_at=?,answered_at=? WHERE id=?",
                     (dumps_json({'text':answer_text,'scope':scope}),utc_now(),utc_now(),question_id))
        pending=conn.execute("SELECT 1 FROM review_learning_questions WHERE event_id=? AND status='pending'",(event['id'],)).fetchone()
        conn.execute('UPDATE review_learning_events SET payload_json=?,status=?,updated_at=? WHERE id=?',
                     (dumps_json(feedback),'needs_input' if pending else 'queued',utc_now(),event['id']))
    add_message(session_id,'user','learning_answer',label,{'learning_question_id':question_id})
    add_message(session_id,'assistant','learning_confirmation',
                '已记为当前案例，不扩展为通用规范。' if scope=='case' else '已记录你的解释，将据此重新总结适用范围。',
                {'learning_question_id':question_id})
    emit_event(session_id,'learning.updated',{'event_id':event['id']})
    if not pending:
        start_learning(session_id)
    return {'ok':True,'scope':scope,'pending':bool(pending)}


def save_revision(conn, session_id: str, version: int, rules: list[dict], reason: str) -> None:
    conn.execute('INSERT OR IGNORE INTO review_memory_history VALUES(?,?,?,?,?)',
                 (session_id,version,dumps_json(rules),reason,utc_now()))


def restore_previous(session_id: str, expected_version: int) -> dict:
    from .learning_service import memory_snapshot
    from .session_store import add_message
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current=conn.execute('SELECT * FROM review_memory WHERE session_id=?',(session_id,)).fetchone()
        if not current or current['version']!=expected_version:
            raise ValueError('会话规范已变化，请刷新后重试')
        previous=conn.execute('SELECT * FROM review_memory_history WHERE session_id=? AND version<? ORDER BY version DESC LIMIT 1',(session_id,expected_version)).fetchone()
        if not previous:
            raise ValueError('没有可撤回的历史规范')
        save_revision(conn,session_id,expected_version,loads_json(current['rules_json'],[]),'撤回前')
        conn.execute('UPDATE review_memory SET version=?,rules_json=?,updated_at=? WHERE session_id=?',
                     (expected_version+1,previous['rules_json'],utc_now(),session_id))
    add_message(session_id,'assistant','learning_confirmation',f'已恢复更新前的规范，并保存为 v{expected_version+1}；后续任务和缓存将使用新版本。')
    return memory_snapshot(session_id)
