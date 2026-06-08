"""Feedback submission helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from .constants import APP_VERSION
from .storage import AppPaths, get_app_paths

DEFAULT_FEEDBACK_ENDPOINT = "https://yeehe-telemetry.willwong0908.workers.dev/feedback"
MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 1500 * 1024
HTTP_TIMEOUT_SECONDS = 25.0


class FeedbackError(RuntimeError):
    """Raised when feedback submission cannot be completed."""


@dataclass
class FeedbackAttachment:
    filename: str
    mime_type: str
    content_base64: str
    size_bytes: int

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "content_base64": self.content_base64,
            "size_bytes": self.size_bytes,
        }


def feedback_service_enabled() -> bool:
    return bool(str(DEFAULT_FEEDBACK_ENDPOINT or "").strip())


def feedback_status(paths: Optional[AppPaths] = None) -> dict:
    paths = paths or get_app_paths()
    return {
        "enabled": feedback_service_enabled(),
        "log_path": str(paths.log_file),
        "has_log_file": bool(paths.log_file.exists() and paths.log_file.is_file()),
    }


def _encode_bytes(filename: str, mime_type: str, payload: bytes) -> FeedbackAttachment:
    return FeedbackAttachment(
        filename=filename,
        mime_type=mime_type,
        content_base64=base64.b64encode(payload).decode("ascii"),
        size_bytes=len(payload),
    )


def _build_log_attachment(log_path: Path) -> Optional[FeedbackAttachment]:
    if not log_path.exists() or not log_path.is_file():
        return None
    data = log_path.read_bytes()
    if len(data) > MAX_LOG_BYTES:
        prefix = (
            "[log truncated]\n"
            "The original log exceeded the size limit, so only the latest portion is attached.\n\n"
        ).encode("utf-8")
        tail_budget = max(0, MAX_LOG_BYTES - len(prefix))
        data = prefix + data[-tail_budget:]
    return _encode_bytes("log.txt", "text/plain; charset=utf-8", data)


def _build_screenshot_attachment(filename: str, content_type: str, payload: bytes) -> FeedbackAttachment:
    if len(payload) > MAX_SCREENSHOT_BYTES:
        raise FeedbackError("截图太大了，请控制在 4MB 以内。")
    normalized_name = str(filename or "").strip() or "screenshot.png"
    normalized_type = str(content_type or "").strip() or "application/octet-stream"
    return _encode_bytes(normalized_name, normalized_type, payload)


def submit_feedback(
    message: str,
    *,
    screenshot_name: str = "",
    screenshot_type: str = "",
    screenshot_bytes: Optional[bytes] = None,
    paths: Optional[AppPaths] = None,
) -> dict:
    paths = paths or get_app_paths()
    text = str(message or "").strip()
    if not text:
        raise FeedbackError("请先填写问题。")
    if not feedback_service_enabled():
        raise FeedbackError("反馈服务当前不可用。")

    payload = {
        "app_version": APP_VERSION,
        "feedback": text,
        "log_path": str(paths.log_file),
    }

    log_attachment = _build_log_attachment(paths.log_file)
    if log_attachment is not None:
        payload["log_attachment"] = log_attachment.to_dict()

    if screenshot_bytes:
        payload["screenshot_attachment"] = _build_screenshot_attachment(
            screenshot_name,
            screenshot_type,
            screenshot_bytes,
        ).to_dict()

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.post(DEFAULT_FEEDBACK_ENDPOINT, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail_data = exc.response.json()
            detail = str(detail_data.get("message", "") or detail_data.get("error", "") or "").strip()
        except Exception:
            detail = ""
        raise FeedbackError(detail or "反馈发送失败，请稍后重试。") from exc
    except Exception as exc:
        raise FeedbackError("反馈发送失败，请检查网络后重试。") from exc

    if not bool(data.get("ok")):
        raise FeedbackError(str(data.get("message", "") or "反馈发送失败，请稍后重试。"))
    return data
