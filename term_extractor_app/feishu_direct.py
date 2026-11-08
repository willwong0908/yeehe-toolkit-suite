"""Direct Feishu data plane. Credentials and upload bytes stay in process memory."""

import asyncio
import json
from uuid import UUID, uuid5

import httpx
from fastapi import HTTPException

from .ai_review.database import get_connection

LIMIT = 30 * 1024 * 1024
BASE = "https://open.feishu.cn/open-apis/"


class FeishuError(HTTPException):
    def __init__(self, code, message):
        self.code = code
        super().__init__(409, f"飞书返回 {code}：{message}")


class Feishu:
    def __init__(self, client, issue):
        self.client = client
        self.issue = issue
        self.tokens = {}

    async def api(self, method, path, identity="user", **kwargs):
        for attempt in range(2):
            if not self.tokens:
                self.tokens = await self.issue()
            try:
                response = await self.client.request(
                    method,
                    BASE + path,
                    headers={"Authorization": "Bearer " + self.tokens[identity]},
                    **kwargs,
                )
                data = response.json()
            except (ValueError, httpx.RequestError):
                raise HTTPException(502, "无法连接飞书，请重试")
            code = data.get("code", response.status_code)
            if not code:
                return data.get("data", data)
            if code in (99991668, 99991677) and not attempt:
                self.tokens = {}
                continue
            raise FeishuError(code, data.get("msg", "请求失败"))

    async def groups(self):
        result = []
        params = {"page_size": 100}
        while True:
            page = await self.api("GET", "im/v1/chats", params=params)
            result.extend(
                {
                    "id": g["chat_id"],
                    "name": g["name"],
                    "external": g.get("external"),
                    "description": g.get("description", ""),
                }
                for g in page["items"]
                if g.get("name")
            )
            if not page.get("has_more"):
                return result
            params["page_token"] = page["page_token"]

    async def member(self, chat):
        info = await self.api("GET", "bot/v3/info", "bot")
        bots = await self.api("GET", f"im/v1/chats/{chat}/members/bots")
        return any(b["bot_id"] == info["bot"]["open_id"] for b in bots.get("items", []))

    async def prepare(self, chat):
        if await self.member(chat):
            return {"ready": True}
        reply = await self.api(
            "POST",
            f"im/v1/chats/{chat}/members",
            params={"member_id_type": "app_id"},
            json={"id_list": [self.tokens["app_id"]]},
        )
        if reply.get("invalid_id_list") or reply.get("not_existed_id_list"):
            raise HTTPException(409, "信鸽无法加入此群")
        return {
            "ready": await self.member(chat),
            "pending": bool(reply.get("pending_approval_id_list")),
        }

    async def upload(self, filename, size, stream, on_progress=None):
        if size <= LIMIT:
            buf = bytearray()
            async for chunk in stream:
                if len(buf) + len(chunk) > size:
                    raise HTTPException(400, "文件大小发生变化，请重新选择")
                buf.extend(chunk)
            if not buf or len(buf) != size:
                raise HTTPException(400, "文件不完整")
            result = await self.api(
                "POST",
                "im/v1/files",
                "bot",
                data={"file_type": "stream", "file_name": filename},
                files={"file": (filename, bytes(buf), "application/octet-stream")},
            )
            if on_progress:
                on_progress(size)
            return result["file_key"]
        root = await self.api("GET", "drive/explorer/v2/root_folder/meta")
        setup = await self.api(
            "POST",
            "drive/v1/files/upload_prepare",
            json={
                "file_name": filename,
                "parent_type": "explorer",
                "parent_node": root["token"],
                "size": size,
            },
        )
        upload_id, block = setup["upload_id"], setup["block_size"]
        seq = total = 0
        buf = bytearray()

        async def part():
            await self.api(
                "POST",
                "drive/v1/files/upload_part",
                data={"upload_id": upload_id, "seq": str(seq), "size": str(len(buf))},
                files={"file": (filename, bytes(buf), "application/octet-stream")},
            )

        async for chunk in stream:
            total += len(chunk)
            if total > size:
                raise HTTPException(400, "文件大小发生变化，请重新选择")
            view = memoryview(chunk)
            while view:
                n = min(len(view), block - len(buf))
                buf.extend(view[:n])
                view = view[n:]
                if len(buf) == block:
                    await part()
                    seq += 1
                    if on_progress:
                        on_progress(min(seq * block, size))
                    buf.clear()
        if total != size:
            raise HTTPException(400, "文件不完整，请重试")
        if buf:
            await part()
            seq += 1
            if on_progress:
                on_progress(size)
        result = await self.api(
            "POST",
            "drive/v1/files/upload_finish",
            json={"upload_id": upload_id, "block_num": seq},
        )
        return result["file_token"]

    async def group_document(self, chat, name, operation, coordinate):
        previous = ""
        for _ in range(90):
            result = await coordinate({"operation": operation, "previous": previous})
            if result.get("wait"):
                await asyncio.sleep(1)
                continue
            doc = result.get("document")
            if doc:
                try:
                    await self.api("GET", f"docx/v1/documents/{doc}")
                except FeishuError as ex:
                    if ex.code != 1770003:  # explicit resource deleted
                        raise
                    previous = doc
                    continue
                return doc
            created = await self.api(
                "POST",
                "docx/v1/documents",
                params={
                    "client_token": str(uuid5(UUID(operation), "create:" + previous))
                },
                json={"title": name + " · 群文件"},
            )
            doc = created["document"]["document_id"]
            saved = await coordinate(
                {"operation": operation, "previous": previous, "created": doc}
            )
            if saved.get("document") == doc:
                return doc
        raise HTTPException(503, "正在创建群文档，请稍后重试")

    async def share(self, token, kind, chat):
        await self.api(
            "POST",
            f"drive/v1/permissions/{token}/members",
            params={"type": kind, "need_notification": "false"},
            json={"member_type": "openchat", "member_id": chat, "perm": "edit" if kind == "docx" else "view"},
        )

    async def links(self, uploaded, doc):
        result = await self.api(
            "POST",
            "drive/v1/metas/batch_query",
            json={
                "with_url": True,
                "request_docs": [
                    {"doc_type": "docx", "doc_token": doc},
                    {"doc_type": "file", "doc_token": uploaded},
                ],
            },
        )
        links = {m["doc_token"]: m["url"] for m in result.get("metas", [])}
        if not all(t in links for t in (uploaded, doc)):
            raise HTTPException(409, "飞书未返回文档或文件链接，请重试")
        return links

    async def deliver(self, chat, name, filename, size, key, stream, coordinate, on_progress=None):
        with get_connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS feishu_delivery(id TEXT PRIMARY KEY,chat TEXT,name TEXT,size INTEGER,uploaded TEXT,appended TEXT,message TEXT)"
            )
            db.execute(
                "INSERT OR IGNORE INTO feishu_delivery VALUES(?,?,?,?, '', '', '')",
                (key, chat, filename, size),
            )
            row = db.execute(
                "SELECT * FROM feishu_delivery WHERE id=?", (key,)
            ).fetchone()
        if (row["chat"], row["name"], row["size"]) != (chat, filename, size):
            raise HTTPException(409, "文件任务信息不一致")
        if row["message"]:
            return {"message_id": row["message"]}
        uploaded = row["uploaded"]
        if not uploaded:
            uploaded = await self.upload(filename, size, stream, on_progress)
            with get_connection() as db:
                db.execute(
                    "UPDATE feishu_delivery SET uploaded=? WHERE id=?", (uploaded, key)
                )
        if on_progress:
            on_progress(size)
        if size <= LIMIT:
            kind, content = "file", {"file_key": uploaded}
        else:
            doc = await self.group_document(chat, name, key, coordinate)
            links = await self.links(uploaded, doc)
            await self.share(doc, "docx", chat)
            await self.share(uploaded, "file", chat)
            if row["appended"] != doc:
                element = {
                    "text_run": {
                        "content": filename,
                        "text_element_style": {"link": {"url": links[uploaded]}},
                    }
                }
                await self.api(
                    "POST",
                    f"docx/v1/documents/{doc}/blocks/{doc}/children",
                    params={"client_token": str(uuid5(UUID(key), doc))},
                    json={
                        "children": [{"block_type": 2, "text": {"elements": [element]}}]
                    },
                )
                with get_connection() as db:
                    db.execute(
                        "UPDATE feishu_delivery SET appended=? WHERE id=?", (doc, key)
                    )
            kind, content = (
                "text",
                {"text": filename + " 已添加到群文件文档\n" + links[doc]},
            )
        sent = await self.api(
            "POST",
            "im/v1/messages",
            "bot",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat,
                "uuid": key,
                "msg_type": kind,
                "content": json.dumps(content, ensure_ascii=False),
            },
        )
        message = sent["message_id"]
        with get_connection() as db:
            db.execute(
                "UPDATE feishu_delivery SET message=? WHERE id=?", (message, key)
            )
        return {"message_id": message}
