"""Yeehe file transfer gateway. Run with one uvicorn worker."""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

ROOT = Path(os.environ.get("TRANSFER_HOME", ".")).resolve()
CLI = str(ROOT / "bin/lark-cli")
PROFILE = "file-transfer"
MEMOQ = "https://memoq.iyeehe.com:8080/memoqserverhttpapi/v1"
LIMIT = 30 * 1024 * 1024
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
cache = {}
lock = threading.RLock()
send_slots = threading.BoundedSemaphore(4)
inflight = set()


def authenticated(authorization: str = Header(default="")):
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(401, "请先登录 memoQ")
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    with lock:
        if cache.get(fingerprint, 0) > time.monotonic():
            return
    try:
        with httpx.stream(
            "GET",
            MEMOQ + "/tbs",
            headers={"Authorization": "MQS-API " + token},
            timeout=15,
        ) as result:
            if result.status_code in (401, 403):
                raise HTTPException(401, "memoQ 登录已过期，请重新登录")
            if result.status_code != 200:
                raise HTTPException(503, "暂时无法验证 memoQ 登录")
    except httpx.RequestError:
        raise HTTPException(503, "无法连接 memoQ 服务器")
    with lock:
        now = time.monotonic()
        for key in [key for key, until in cache.items() if until <= now]:
            cache.pop(key)
        cache[fingerprint] = now + 60


def cli(*args, cwd=None):
    try:
        proc = subprocess.run(
            [CLI, "--profile", PROFILE, *args],
            cwd=cwd,
            capture_output=True,
            timeout=160,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(503, "飞书服务暂时不可用")
    try:
        # Progress goes to stderr. Some CLI errors are emitted there as JSON.
        raw = proc.stdout.strip() or proc.stderr.strip()
        result = json.loads(raw[raw.index(b"{") :])
    except (ValueError, UnicodeError):
        raise HTTPException(502, "飞书响应异常，请联系管理员检查传输账号授权")
    if proc.returncode or result.get("code", 0) or result.get("ok") is False:
        err = result.get("error") or {}
        code = err.get("code") or result.get("code") or ""
        messages = {
            230002: "信鸽尚未加入该群",
            230027: "当前账号无权在此群执行该操作",
            99991679: "飞书传输账号需要管理员重新授权",
            230038: "飞书限制了跨企业会话操作",
        }
        raise HTTPException(
            409, messages.get(code, f"飞书操作失败（{code or '请检查传输账号授权'}）")
        )
    return result.get("data", result)


def groups(details=False):
    rows, page, seen = [], "", set()
    while True:
        args = ["im", "+chat-list", "--as", "user", "--page-size", "100"]
        if page:
            args += ["--page-token", page]
        data = cli(*args)
        for row in data["chats"]:
            if row.get("name"):
                rows.append(
                    {
                        "id": row["chat_id"],
                        "name": row["name"],
                        "external": bool(row.get("external")),
                        "description": row.get("description") or "",
                    }
                )
        if not data.get("has_more"):
            break
        page = data.get("page_token")
        if not page or page in seen:
            raise HTTPException(502, "群列表分页异常，请刷新")
        seen.add(page)
    if details:
        from collections import Counter

        names = Counter(row["name"] for row in rows)
        for row in rows:
            if names[row["name"]] > 1:
                members = cli(
                    "im",
                    "chat.members",
                    "get",
                    "--as",
                    "user",
                    "--params",
                    json.dumps({"chat_id": row["id"], "page_size": 5}),
                )
                peers = [m["name"] for m in members.get("items", []) if m.get("name")]
                if peers:
                    row["members_hint"] = "群成员：" + "、".join(peers[:3])
    return rows


def check_group(chat):
    if not re.fullmatch(r"oc_[a-zA-Z0-9]+", chat) or not any(
        r["id"] == chat for r in groups()
    ):
        raise HTTPException(403, "传输账号已不在这个群中")


def bot_present(chat):
    # Match the bot open_id, since different applications can share a display name.
    info = cli("api", "GET", "/open-apis/bot/v3/info", "--as", "bot")
    bot_id = info["bot"]["open_id"]
    members = cli(
        "im",
        "chat.members",
        "bots",
        "--as",
        "user",
        "--params",
        json.dumps({"chat_id": chat}),
    )
    return any(item["bot_id"] == bot_id for item in members.get("items", []))


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/groups", dependencies=[Depends(authenticated)])
def list_groups():
    return {"groups": groups(details=True)}


@app.get("/groups/{chat}/membership", dependencies=[Depends(authenticated)])
def membership(chat: str):
    check_group(chat)
    return {"member": bot_present(chat)}


@app.post("/groups/{chat}/prepare", dependencies=[Depends(authenticated)])
def prepare(chat: str):
    check_group(chat)
    if bot_present(chat):
        return {"ready": True}
    app_id = json.loads((ROOT / "feishu-transfer.json").read_text())["bot_app_id"]
    data = cli(
        "im",
        "chat.members",
        "create",
        "--as",
        "user",
        "--params",
        json.dumps({"chat_id": chat, "member_id_type": "app_id"}),
        "--data",
        json.dumps({"id_list": [app_id]}),
    )
    if data.get("pending_approval_id_list"):
        return {"ready": False, "pending": True}
    if data.get("invalid_id_list") or data.get("not_existed_id_list"):
        raise HTTPException(409, "信鸽无法加入该群，请检查邀请权限和应用可用范围")
    return {"ready": bot_present(chat)}


def receipts():
    db = sqlite3.connect(ROOT / "receipts.sqlite3")
    db.execute(
        "CREATE TABLE IF NOT EXISTS sent (id TEXT PRIMARY KEY,chat TEXT NOT NULL,message TEXT NOT NULL)"
    )
    return db


@app.put("/groups/{chat}/files/{file_id}", dependencies=[Depends(authenticated)])
async def send(chat: str, file_id: UUID, filename: str, request: Request):
    raise HTTPException(410, "请使用本机直传版工具合集")


@app.post("/access", dependencies=[Depends(authenticated)])
def access():
    from direct_auth import temporary_tokens
    from fastapi.responses import JSONResponse

    config = json.loads((ROOT / "feishu-transfer.json").read_text())
    with lock:
        value = temporary_tokens(cli, config["bot_app_id"])
    return JSONResponse(
        {**value, "app_id": config["bot_app_id"]}, headers={"Cache-Control": "no-store"}
    )


@app.post("/groups/{chat}/document", dependencies=[Depends(authenticated)])
def coordinate(chat: str, record: dict):
    """The gateway stores only mapping metadata shared by all desktop users."""
    from contextlib import closing

    if not re.fullmatch(r"oc_[A-Za-z0-9]+", chat):
        raise HTTPException(400, "无效群号")
    known = str(record.get("previous", ""))
    candidate = str(record.get("created", ""))
    operation = UUID(str(record["operation"])).hex
    if any(not re.fullmatch("[a-zA-Z0-9]{0,100}", v) for v in (known, candidate)):
        raise HTTPException(400, "无效文档标识")
    with closing(receipts()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS group_docs(chat TEXT PRIMARY KEY, doc TEXT, owner TEXT, until REAL)"
        )
        doc, owner, until = db.execute(
            "SELECT doc,owner,until FROM group_docs WHERE chat=?", (chat,)
        ).fetchone() or ("", "", 0)
        if doc != known:
            return {"document": doc}
        if owner != operation and until > time.time():
            return {"wait": True}
        if candidate and owner != operation:
            raise HTTPException(409, "文档创建任务已过期，请重试")
        db.execute(
            "INSERT OR REPLACE INTO group_docs VALUES(?,?,?,?)",
            (
                chat,
                candidate or doc,
                "" if candidate else operation,
                0 if candidate else time.time() + 60,
            ),
        )
        return {"document": candidate, "create": not candidate}
