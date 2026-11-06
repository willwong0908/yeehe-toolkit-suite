from __future__ import annotations
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from term_extractor_app.ai_review import database

class DatabaseConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'review.sqlite3'
        self.patch = patch.object(database, 'DB_PATH', self.path)
        self.patch.start(); database.init_db()
    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def test_long_snapshot_allows_other_writer_and_remains_consistent(self):
        with database.get_connection() as conn:
            conn.execute("INSERT INTO settings VALUES ('snapshot', '1', 'now')")
        reader = sqlite3.connect(self.path, timeout=1)
        try:
            reader.execute('BEGIN')
            self.assertEqual(reader.execute("SELECT value_json FROM settings WHERE key='snapshot'").fetchone()[0], '1')
            def write():
                with database.get_connection() as conn:
                    conn.execute("UPDATE settings SET value_json='2' WHERE key='snapshot'")
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(write).result(timeout=2)
            self.assertEqual(reader.execute("SELECT value_json FROM settings WHERE key='snapshot'").fetchone()[0], '1')
            reader.commit()
            self.assertEqual(reader.execute("SELECT value_json FROM settings WHERE key='snapshot'").fetchone()[0], '2')
        finally:
            reader.close()

    def test_existing_snapshot_refresh_does_not_rerun_schema_under_writer(self):
        with database.get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("INSERT INTO settings VALUES ('held','1','now')")
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(database.init_db).result(timeout=1)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            indexes={r[1] for r in conn.execute("PRAGMA index_list('review_results')")}
            self.assertIn('idx_review_results_task_item_status', indexes)
            plan=' '.join(str(r) for r in conn.execute("EXPLAIN QUERY PLAN DELETE FROM review_results WHERE task_id=? AND item_id=? AND status='failed'", ('t','i')))
            self.assertIn('idx_review_results_task_item_status', plan)

    def test_concurrent_languages_and_snapshots_preserve_all_commits(self):
        barrier=threading.Barrier(5)
        def writer(language):
            barrier.wait()
            for i in range(160):
                with database.get_connection() as conn:
                    conn.execute('INSERT INTO settings VALUES (?, ?, ?)', (f'{language}-{i}',str(i),'now'))
        def reader():
            barrier.wait()
            for _ in range(250):
                database.init_db()
                with database.get_connection() as conn:
                    conn.execute('BEGIN')
                    conn.execute('SELECT count(*) FROM settings').fetchone()
                    conn.execute('SELECT count(*) FROM review_results').fetchone()
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures=[pool.submit(writer,language) for language in ('ja','zh','pt')]+[pool.submit(reader) for _ in range(2)]
            for future in futures: future.result(timeout=25)
        with database.get_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM settings').fetchone()[0], 480)

    def test_two_review_languages_save_results_during_conversation_refresh(self):
        from term_extractor_app.ai_review import review_service, session_store, workflow_service
        sid = session_store.create_session(title="并发回归")["id"]
        with database.get_connection() as conn:
            for lang in ("zh", "ja"):
                conn.execute("INSERT INTO file_batches(id,original_filename,stored_path,file_type,status,created_at,updated_at) VALUES(?,?,?, 'workspace','ready','now','now')", (lang,lang,""))
                conn.execute("INSERT INTO review_tasks(id,batch_id,session_id,target_language,status,config_json,created_at,updated_at) VALUES(?,?,?,?, 'running','{}','now','now')", (lang,lang,sid,lang))
                conn.execute("INSERT INTO review_session_tasks VALUES(?,?,?,'now')", (sid,lang,lang))
                conn.executemany("INSERT INTO file_items(id,batch_id,source_file,source_text,target_text,item_order,created_at) VALUES(?,?, 'test.xlsx','source','target',?,'now')", [(f"{lang}-{i}",lang,i) for i in range(1800)])
        barrier = threading.Barrier(4)
        def reviewer(lang):
            barrier.wait()
            for start in range(0,1800,3):
                items=[{"id":f"{lang}-{i}","source_text":"source","target_text":"target"} for i in range(start,start+3)]
                if start == 0: review_service._save_review_errors_bulk(lang,items,"模拟重试")
                results=[(item,{"id":item["id"],"has_issue":False,"issue_type":"","issue":"","suggestion":""}) for item in items]
                review_service._save_review_results_bulk(lang,results)
                review_service._update_task(lang,completed_count=start+3)
                if start % 30 == 0: session_store.emit_event(sid,"review.progress",{"task_id":lang,"completed_count":start+3})
        def refresh():
            barrier.wait()
            for _ in range(80):
                snapshot=session_store.get_session_snapshot(sid)
                results=workflow_service.get_session_task_results(sid,snapshot=snapshot)
                self.assertEqual(len(results),2)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(reviewer,lang) for lang in ("zh","ja")]+[pool.submit(refresh) for _ in range(2)]
            for future in futures: future.result(timeout=45)
        with database.get_connection() as conn:
            for lang in ("zh","ja"):
                row=conn.execute("SELECT count(*),count(DISTINCT item_id),sum(status='failed') FROM review_results WHERE task_id=?",(lang,)).fetchone()
                self.assertEqual(tuple(row),(1800,1800,0))
                self.assertEqual(conn.execute("SELECT completed_count FROM review_tasks WHERE id=?",(lang,)).fetchone()[0],1800)

    def test_progress_lock_does_not_retry_paid_request_or_lose_result(self):
        import asyncio, json
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from term_extractor_app.ai_review import review_service as review
        from term_extractor_app.models import LLMResponse
        with database.get_connection() as conn:
            conn.execute("INSERT INTO file_batches(id,original_filename,stored_path,file_type,status,created_at,updated_at) VALUES('b','qa','','workspace','ready','now','now')")
            conn.execute("INSERT INTO review_tasks(id,batch_id,status,config_json,created_at,updated_at) VALUES('t','b','running','{}','now','now')")
            conn.execute("INSERT INTO file_items(id,batch_id,source_file,source_text,target_text,item_order,created_at) VALUES('i','b','qa','source','target',1,'now')")
        item={'id':'i','source_text':'source','target_text':'target'}
        review._replace_review_request_states('t',[[item]])
        original_status=review._set_review_request_status
        def status(task_id,index,value,*args):
            if value == 'thinking': raise sqlite3.OperationalError('database is locked')
            return original_status(task_id,index,value,*args)
        class FakeAdapter:
            provider_name='deepseek'
            calls=0
            async def send_prompt(self,request,attempt=1):
                self.calls += 1
                request.metadata['stream_phase_callback']('thinking')
                result={'items':[{'id':'i','has_issue':False,'issue_type':'','issue':'','suggestion':''}]}
                return LLMResponse(request.task_id,request.task_type,json.dumps(result),'deepseek','mock',1,attempt,True)
            async def close(self): pass
        adapter=FakeAdapter();settings=SimpleNamespace(base_url='https://mock.invalid',max_concurrency=1,timeout_seconds=10)
        logger=MagicMock();logger.handlers=[object()]
        config={'mode':'normal','system_prompt':'review','user_prompt':'{text}','max_concurrency':1}
        with patch.object(review,'_load_review_provider',return_value=('deepseek',settings)), patch.object(review.ProviderRegistry,'create_adapter',return_value=adapter), patch.object(review,'_set_review_request_status',side_effect=status), patch.object(review,'_add_log'), patch.object(review,'monitor_requested'), patch.object(review.logging,'getLogger',return_value=logger):
            result=asyncio.run(review._run_review_packages('t','dummy','mock',config,[[item]]))
        self.assertEqual(adapter.calls,1)
        self.assertEqual(result,(1,1,0))
        with database.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM review_results WHERE task_id='t' AND item_id='i' AND status='completed'").fetchone()[0],1)
            self.assertEqual(conn.execute("SELECT status FROM review_request_states WHERE task_id='t'").fetchone()[0],'completed')
        logger.warning.assert_called_once()

    def test_file_logging_survives_database_lock_without_masking_other_errors(self):
        from unittest.mock import MagicMock
        from term_extractor_app.ai_review import review_service
        logger = MagicMock(); logger.handlers = [object()]
        with patch.object(review_service.logging, 'getLogger', return_value=logger):
            with patch.object(review_service, 'get_connection', side_effect=sqlite3.OperationalError('database is locked')):
                review_service._add_log('task-1','error','original failure')
            logger.error.assert_called_with('[AI_REVIEW][%s] %s','task-1','original failure')
            logger.warning.assert_called_once()
            with patch.object(review_service, 'get_connection', side_effect=sqlite3.OperationalError('disk I/O error')):
                with self.assertRaises(sqlite3.OperationalError):
                    review_service._add_log('task-1','error','disk failure')

    def test_waits_past_old_five_second_limit_without_losing_write(self):
        started=threading.Event()
        def writer():
            started.set()
            with database.get_connection() as conn:
                conn.execute("INSERT INTO settings VALUES ('waited','ok','now')")
        with database.get_connection() as held:
            held.execute('BEGIN IMMEDIATE')
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(writer)
                self.assertTrue(started.wait(1))
                time.sleep(5.3)
                self.assertFalse(future.done())
                held.commit()
                future.result(timeout=3)
        with database.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT value_json FROM settings WHERE key='waited'").fetchone()[0], 'ok')

    def test_recreated_database_at_same_path_is_initialized(self):
        self.path.unlink()
        self.path.touch()
        database.init_db()
        with database.get_connection() as conn:
            self.assertIsNotNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='review_results'").fetchone())

if __name__ == '__main__': unittest.main()
