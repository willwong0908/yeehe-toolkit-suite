"""Sync the latest GitHub release metadata to the Yeehe Worker update endpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError


DEFAULT_REPO = "willwong0908/yeehe-toolkit-suite"
DEFAULT_WORKER_URL = "https://yeehe-telemetry.willwong0908.workers.dev"
DEFAULT_TOKEN_ENV = "YEEHE_WORKER_ADMIN_TOKEN"
ASSET_HINTS = ("yeehe", "toolkit", "suite", "release", "program")


def run_gh_release_view(repo: str, tag: str) -> dict:
    command = [
        "gh",
        "release",
        "view",
    ]
    if tag:
        command.append(tag)
    command.extend([
        "--repo",
        repo,
        "--json",
        "tagName,name,body,publishedAt,assets",
    ])
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(completed.stdout)


def pick_asset(assets: list[dict]) -> dict:
    zip_assets = [
        item for item in assets
        if str(item.get("name", "")).lower().endswith(".zip") and str(item.get("url", "")).strip()
    ]
    if not zip_assets:
        raise RuntimeError("No downloadable .zip asset found on the release.")
    for hint in ASSET_HINTS:
        for item in zip_assets:
            if hint in str(item.get("name", "")).lower():
                return item
    return zip_assets[0]


def build_payload(release_data: dict) -> dict:
    asset = pick_asset(list(release_data.get("assets") or []))
    return {
        "latest_version": str(release_data.get("tagName") or release_data.get("name") or "").strip(),
        "release_notes": str(release_data.get("body") or "").strip(),
        "published_at": str(release_data.get("publishedAt") or "").strip(),
        "download_url": str(asset.get("url") or "").strip(),
        "asset_name": str(asset.get("name") or "").strip(),
    }


def post_worker_update(worker_url: str, token: str, payload: dict) -> dict:
    endpoint = worker_url.rstrip("/") + "/admin/app-update"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Yeehe-Release-Sync",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Worker sync failed: HTTP {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Worker sync failed: {exc}") from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the latest GitHub release metadata to Cloudflare Worker.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo, for example owner/name.")
    parser.add_argument("--tag", default="", help="Specific release tag. Defaults to latest release.")
    parser.add_argument("--worker-url", default=DEFAULT_WORKER_URL, help="Worker base URL.")
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV, help="Environment variable containing admin token.")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without syncing.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    release_data = run_gh_release_view(args.repo, args.tag)
    payload = build_payload(release_data)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    token = str(os.environ.get(args.token_env, "")).strip()
    if not token:
        raise RuntimeError(f"Missing admin token. Set {args.token_env} before running this script.")
    result = post_worker_update(args.worker_url, token, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
