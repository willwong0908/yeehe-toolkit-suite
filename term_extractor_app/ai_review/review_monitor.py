"""Release-only file review snapshots and durable asynchronous delivery."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx

from .database import get_connection
from ..constants import APP_VERSION
from ..telemetry import TELEMETRY_ENDPOINT, is_release_runtime

ENDPOINT = TELEMETRY_ENDPOINT.rsplit("/", 1)[0] + "/review-monitor"
TERMINAL = {"完成", "部分失败", "失败", "中断"}
_lock = threading.RLock()
_wake = threading.Event()
_active: set[str] = set()
_worker_started = False
_last_heartbeat = 0.0


def now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def api_key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest() if api_key else ""


def basename(value: str) -> str:
    return str(value or "").replace("\\", "/").rsplit("/", 1)[-1][:255] or "未命名文件"


def file_group_id(invocation_id: str, source_file: str) -> str:
    # Paths are used locally for disambiguation, never transmitted.
    return uuid.uuid5(uuid.NAMESPACE_URL, invocation_id + ":" + source_file).hex


def _safe_failure() -> None:
    logging.getLogger(__name__).warning("Review monitoring local operation failed (details suppressed)")


def monitor_task_started(task_id: str, batch_id: str, config: dict[str, Any],
                         items: list[dict[str, Any]], api_key: str) -> None:
    if not is_release_runtime() or not config.get("enable_ai_review", True):
        return
    try:
        with _lock, get_connection() as conn:
            if conn.execute("SELECT 1 FROM review_monitor_outbox WHERE task_id=?", (task_id,)).fetchone():
                _active.add(task_id)
                return
            batch = conn.execute("SELECT original_filename FROM file_batches WHERE id=?", (batch_id,)).fetchone()
            files: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for item in items:
                files[str(item.get("source_file") or (batch["original_filename"] if batch else "未命名文件"))].append(item)
            started = now_utc()
            invocation = str(config.get("monitor_group_id") or task_id)
            expected = config.get("monitor_expected_languages") or {}
            for source_file, file_items in files.items():
                group_id = file_group_id(invocation, source_file)
                record_id = uuid.uuid5(uuid.NAMESPACE_URL, task_id + ":" + group_id).hex
                language = str(config.get("target_language") or "auto")
                payload = {
                    "record_id": record_id, "task_id": task_id, "group_id": group_id,
                    "expected_languages": sorted(set(expected.get(source_file) or [language])),
                    "filename": basename(source_file), "pm_fingerprint": api_key_fingerprint(api_key),
                    "status": "运行中", "started_at": started, "finished_at": None,
                    "last_activity_at": started, "target_language": language,
                    "total_count": len(file_items), "requested_count": 0, "cached_count": 0,
                    "failed_count": 0, "model": str(config.get("model") or ""),
                    "app_version": APP_VERSION, "error_category": "", "revision": 1,
                }
                conn.execute(
                    "INSERT INTO review_monitor_outbox(record_id,task_id,group_id,payload_json) VALUES (?,?,?,?)",
                    (record_id, task_id, group_id, json.dumps(payload, ensure_ascii=False)),
                )
                conn.executemany(
                    "INSERT INTO review_monitor_items(task_id,item_id,record_id) VALUES (?,?,?)",
                    [(task_id, item["id"], record_id) for item in file_items],
                )
            _active.add(task_id)
        start_monitor_worker()
        _wake.set()
    except Exception:
        _safe_failure()


def monitor_requested(task_id: str, items: list[dict[str, Any]]) -> None:
    if not is_release_runtime():
        return
    try:
        with _lock, get_connection() as conn:
            conn.executemany(
                "UPDATE review_monitor_items SET requested=1 WHERE task_id=? AND item_id=?",
                [(task_id, item["id"]) for item in items],
            )
    except Exception:
        _safe_failure()


def _snapshot(task_id: str, status: str | None = None, error_category: str = "") -> None:
    with _lock, get_connection() as conn:
        rows = conn.execute("SELECT * FROM review_monitor_outbox WHERE task_id=?", (task_id,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload["status"] in TERMINAL:
                continue
            counts = conn.execute(
                """SELECT COUNT(*) AS total, COALESCE(SUM(m.requested),0) AS requested,
                   COALESCE(SUM(EXISTS(SELECT 1 FROM review_results r
                       WHERE r.task_id=m.task_id AND r.item_id=m.item_id AND r.status='cached')),0) AS cached,
                   COALESCE(SUM(EXISTS(SELECT 1 FROM review_results r
                       WHERE r.task_id=m.task_id AND r.item_id=m.item_id AND r.status='failed')
                       AND NOT EXISTS(SELECT 1 FROM review_results r WHERE r.task_id=m.task_id
                           AND r.item_id=m.item_id AND r.status IN ('completed','cached'))),0) AS failed
                   FROM review_monitor_items m WHERE m.record_id=?""", (row["record_id"],),
            ).fetchone()
            payload.update(total_count=counts["total"], requested_count=counts["requested"],
                           cached_count=counts["cached"], failed_count=counts["failed"])
            if status:
                payload["status"] = status
                if status in {"完成", "部分失败"}:
                    payload["status"] = ("失败" if counts["failed"] == counts["total"] else "部分失败") if counts["failed"] else "完成"
                payload["finished_at"] = now_utc() if status != "中断" else None
                payload["error_category"] = error_category or ("request_failed" if counts["failed"] else "")
            if status != "中断":
                payload["last_activity_at"] = now_utc()
            payload["revision"] = row["revision"] + 1
            conn.execute(
                """UPDATE review_monitor_outbox SET payload_json=?, revision=?, sync_status='pending',
                   next_attempt=0 WHERE record_id=?""",
                (json.dumps(payload, ensure_ascii=False), payload["revision"], row["record_id"]),
            )


def monitor_task_progress(task_id: str, **_counts: Any) -> None:
    if is_release_runtime():
        try:
            _snapshot(task_id)
        except Exception:
            _safe_failure()


def monitor_task_finished(task_id: str, *, status: str, error_category: str = "", **_counts: Any) -> None:
    if not is_release_runtime():
        return
    try:
        _snapshot(task_id, status, error_category)
        with _lock:
            _active.discard(task_id)
        _wake.set()
    except Exception:
        _safe_failure()


def flush_pending_once() -> None:
    if not is_release_runtime():
        return
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM review_monitor_outbox WHERE sync_status='pending' AND next_attempt<=?
               ORDER BY next_attempt, rowid LIMIT 24""", (time.time(),),
        ).fetchall()
    if not rows:
        return
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(ENDPOINT, json={"schema_version": 1,
                "review_records": [json.loads(row["payload_json"]) for row in rows]})
            response.raise_for_status()
            result = response.json()
        if result.get("ok") is not True:
            raise ValueError("delivery_not_confirmed")
        accepted = {(entry["record_id"], entry["revision"]) for entry in result.get("acknowledged", [])}
        if any((row["record_id"], row["revision"]) not in accepted for row in rows):
            raise ValueError("missing_acknowledgement")
        with get_connection() as conn:
            for row in rows:
                conn.execute(
                    """UPDATE review_monitor_outbox SET sync_status='sent',sync_attempts=0,sync_error=''
                       WHERE record_id=? AND revision=?""", (row["record_id"], row["revision"]),
                )
    except Exception:
        # HTTP bodies and exceptions can contain sensitive input; store only a category.
        with get_connection() as conn:
            for row in rows:
                delay = min(1800, 8 * 2 ** min(row["sync_attempts"], 8))
                conn.execute(
                    """UPDATE review_monitor_outbox SET sync_attempts=sync_attempts+1,
                       sync_error='delivery_failed',next_attempt=? WHERE record_id=? AND revision=?""",
                    (time.time() + delay, row["record_id"], row["revision"]),
                )


def _worker_loop() -> None:
    global _last_heartbeat
    while True:
        _wake.wait(8)
        _wake.clear()
        try:
            if time.monotonic() - _last_heartbeat >= 60:
                with _lock:
                    tasks = tuple(_active)
                for task_id in tasks:
                    _snapshot(task_id)
                _last_heartbeat = time.monotonic()
            flush_pending_once()
        except Exception:
            _safe_failure()


def start_monitor_worker() -> None:
    global _worker_started
    if not is_release_runtime():
        return
    with _lock:
        if not _worker_started:
            threading.Thread(target=_worker_loop, name="review-monitor", daemon=True).start()
            _worker_started = True
