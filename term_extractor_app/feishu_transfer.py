"""Local authenticated proxy for the company file-transfer gateway."""

import hashlib
import json
import ssl
import sys
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager
from uuid import UUID
from .feishu_direct import Feishu
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from .ai_review.memoq_service import (
    DEFAULT_BASE_URL,
    MemoQClient,
    MemoQError,
    _load_credentials,
)

router = APIRouter(prefix="/api/feishu-transfer")
resources = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
_lock = threading.Lock()
_session = {}


def gateway():
    try:
        config = json.loads(
            (resources / "feishu-transfer.json").read_text(encoding="utf-8-sig")
        )
        url = config["gateway_url"].rstrip("/")
        if urlsplit(url).scheme != "https" or not config["bot_app_id"].startswith(
            "cli_"
        ):
            raise ValueError()
        tls = ssl.create_default_context(
            cafile=str(resources / "feishu-transfer-ca.pem")
        )
        return url, tls
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "飞书传输配置缺失，请联系管理员")


def session(request: Request):
    # This desktop API can act on the locally signed-in user's behalf.
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin and origin != str(request.base_url).rstrip("/")
    ):
        raise HTTPException(403, "请从工具合集内访问")
    if request.url.hostname not in ("localhost", "127.0.0.1", "::1", "testserver"):
        raise HTTPException(403, "仅支持本机访问")
    with _lock:
        credentials = _load_credentials()
        if not credentials or credentials["base_url"].rstrip("/") != DEFAULT_BASE_URL:
            _session.clear()
            raise HTTPException(401, "请先登录公司 memoQ 账号")
        key = hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).digest()
        if _session.get("key") != key or time.monotonic() >= _session.get("expires", 0):
            _session.clear()
            client = MemoQClient(credentials)
            try:
                client.login()
                _session.update(
                    key=key, token=client.token, expires=time.monotonic() + 180
                )
            except MemoQError:
                raise HTTPException(401, "memoQ 登录失效，请重新登录")
            except httpx.RequestError:
                raise HTTPException(503, "无法连接公司 memoQ 服务器")
            finally:
                client.close()
        return _session["token"]


async def forward(method, path, token, **kwargs):
    url, tls = gateway()
    try:
        async with httpx.AsyncClient(
            verify=tls, timeout=httpx.Timeout(190, connect=10)
        ) as client:
            response = await client.request(
                method,
                url + path,
                headers={"Authorization": "Bearer " + token},
                **kwargs,
            )
    except httpx.RequestError:
        raise HTTPException(503, "无法连接广州文件传输服务，请检查网络后重试")
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "传输服务响应异常")
    if response.is_error:
        if response.status_code == 401:
            with _lock:
                if _session.get("token") == token:
                    _session.clear()
        raise HTTPException(response.status_code, data.get("detail", "文件传输失败"))
    return data


@asynccontextmanager
async def direct(token):
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=15)) as client:
        yield Feishu(client, lambda: forward("POST", "/access", token))


@router.get("/groups")
async def list_groups(token=Depends(session)):
    async with direct(token) as api:
        return {
            "groups": await api.groups(),
            "username": (_load_credentials() or {}).get("username", ""),
        }


@router.get("/groups/{chat}/membership")
async def membership(chat: str, token=Depends(session)):
    async with direct(token) as api:
        return {"member": await api.member(chat)}


@router.post("/groups/{chat}/prepare")
async def prepare(chat: str, token=Depends(session)):
    async with direct(token) as api:
        return await api.prepare(chat)


_busy = set()
_progress = {}


@router.get("/progress/{file_id}")
async def upload_progress(file_id: UUID, token=Depends(session)):
    return _progress.get(str(file_id), {"state": "waiting", "uploaded": 0})


@router.put("/groups/{chat}/files/{file_id}")
async def send(
    chat: str, file_id: UUID, filename: str, request: Request, token=Depends(session)
):
    try:
        size = int(request.headers.get("content-length", "0"))
    except ValueError:
        size = 0
    if size <= 0 or not filename:
        raise HTTPException(400, "请选择非空文件")
    if file_id in _busy:
        raise HTTPException(409, "文件正在发送")
    _busy.add(file_id)
    key = str(file_id)
    started = time.monotonic()
    _progress[key] = {"state": "uploading", "uploaded": 0, "total": size, "speed": 0}

    def update_progress(uploaded):
        elapsed = max(time.monotonic() - started, 0.001)
        _progress[key] = {"state": "finalizing" if uploaded == size else "uploading",
                          "uploaded": uploaded, "total": size, "speed": uploaded / elapsed}
    try:
        async with direct(token) as api:
            group = next((g for g in await api.groups() if g["id"] == chat), None)
            if not group:
                raise HTTPException(403, "传输账号不在所选群中")

            async def coordinate(record):
                return await forward(
                    "POST", f"/groups/{chat}/document", session(request), json=record
                )

            return await api.deliver(
                chat,
                group["name"],
                filename,
                size,
                str(file_id),
                request.stream(),
                coordinate,
                update_progress,
            )
    finally:
        _busy.discard(file_id)
        _progress.pop(key, None)
