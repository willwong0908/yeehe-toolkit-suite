"""Expose expiring Feishu access tokens after the gateway's memoQ check."""

import json
import re
from pathlib import Path

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException


def stored(account):
    # Linux credential format of the pinned lark-cli 1.0.48.
    directory = Path.home() / ".local/share/lark-cli"
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", account) + ".enc"
    encrypted = (directory / filename).read_bytes()
    return (
        AESGCM((directory / "master.key").read_bytes())
        .decrypt(encrypted[:12], encrypted[12:], None)
        .decode()
    )


def temporary_tokens(cli, app_id):
    # A user API call lets the CLI refresh under its own token lifecycle.
    user = cli("api", "GET", "/open-apis/authen/v1/user_info", "--as", "user")
    try:
        account = json.loads(stored(app_id + ":" + user["open_id"]))
        response = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": stored("appsecret:" + app_id)},
            timeout=12,
        )
        return {
            "user": account["accessToken"],
            "bot": response.json()["tenant_access_token"],
            "expires": account["expiresAt"],
        }
    except (KeyError, OSError, ValueError, httpx.HTTPError):
        raise HTTPException(503, "获取飞书临时凭据失败，请联系管理员")
