"""Anonymous usage telemetry for packaged releases only."""

from __future__ import annotations

import atexit
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .constants import APP_NAME, APP_VERSION
from .storage import SettingsStore, get_app_paths

TELEMETRY_ENDPOINT = "https://yeehe-telemetry.willwong0908.workers.dev/collect"
TELEMETRY_SCHEMA_VERSION = 1
TELEMETRY_FLUSH_INTERVAL_SECONDS = 8.0
TELEMETRY_BATCH_SIZE = 24
TELEMETRY_QUEUE_LIMIT = 256
TELEMETRY_TIMEOUT_SECONDS = 2.5


@dataclass
class TelemetryEvent:
    name: str
    count: int = 1
    timestamp: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": int(self.count or 1),
            "ts": int(self.timestamp or time.time()),
        }


def is_release_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def infer_model_tier(model_name: str) -> str:
    normalized = str(model_name or "").strip().lower()
    if "flash" in normalized:
        return "flash"
    if "pro" in normalized:
        return "pro"
    return ""


class TelemetryClient:
    def __init__(self) -> None:
        self.enabled = is_release_runtime()
        self.endpoint = TELEMETRY_ENDPOINT
        self._queue: "queue.Queue[TelemetryEvent]" = queue.Queue(maxsize=TELEMETRY_QUEUE_LIMIT)
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._worker_started = False
        self._worker_lock = threading.Lock()
        self._install_id = ""
        if self.enabled:
            self._install_id = self._ensure_install_id()
            self._start_worker()
            atexit.register(self.close)

    def track(self, name: str, *, count: int = 1) -> None:
        if not self.enabled:
            return
        event_name = str(name or "").strip()
        if not event_name:
            return
        event = TelemetryEvent(name=event_name, count=max(1, int(count or 1)), timestamp=int(time.time()))
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            return
        if self._queue.qsize() >= TELEMETRY_BATCH_SIZE:
            self._flush_event.set()

    def close(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        self._flush_event.set()

    def _ensure_install_id(self) -> str:
        try:
            store = SettingsStore(get_app_paths())
            settings = store.load()
            install_id = str(settings.ui_preferences.get("telemetry_install_id", "") or "").strip()
            if install_id:
                return install_id
            install_id = uuid.uuid4().hex
            settings.ui_preferences["telemetry_install_id"] = install_id
            store.save(settings)
            return install_id
        except Exception:
            return ""

    def _start_worker(self) -> None:
        with self._worker_lock:
            if self._worker_started:
                return
            thread = threading.Thread(target=self._worker_loop, name="telemetry-worker", daemon=True)
            thread.start()
            self._worker_started = True

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            self._flush_event.wait(TELEMETRY_FLUSH_INTERVAL_SECONDS)
            self._flush_event.clear()
            self._flush_once()
        self._flush_once()

    def _drain_batch(self) -> list[TelemetryEvent]:
        items: list[TelemetryEvent] = []
        while len(items) < TELEMETRY_BATCH_SIZE:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _flush_once(self) -> None:
        batch = self._drain_batch()
        if not batch:
            return
        payload = {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "install_id": self._install_id,
            "events": [item.to_dict() for item in batch],
        }
        try:
            with httpx.Client(timeout=TELEMETRY_TIMEOUT_SECONDS, follow_redirects=True) as client:
                client.post(self.endpoint, json=payload)
        except Exception:
            return


_telemetry_client: Optional[TelemetryClient] = None


def get_telemetry_client() -> TelemetryClient:
    global _telemetry_client
    if _telemetry_client is None:
        _telemetry_client = TelemetryClient()
    return _telemetry_client


def track_event(name: str, *, count: int = 1) -> None:
    get_telemetry_client().track(name, count=count)
