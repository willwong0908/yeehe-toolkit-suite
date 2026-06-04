"""FastAPI WebUI entry point."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, ConfigDict

if __package__:
    from .constants import APP_VERSION, UPDATE_ASSET_NAME_HINTS, UPDATE_RELEASE_API
    from .core import scan_folder
    from .models import TaskInput, normalize_extraction_mode, sync_extraction_flags
    from .nontrans import (
        NONTRANS_ELEMENT_TYPE_LABELS,
        NONTRANS_ROLE_LABELS,
        BUILTIN_NONTRANS_LIBRARY_FILE,
        deduplicate_nontrans_regex_rows,
        expand_nontrans_regex_rows,
        load_builtin_nontrans_rules,
        validate_nontrans_rule,
    )
    from .providers import ProviderRegistry
    from .service_layer import ExtractionTaskFacade
    from .storage import (
        append_pending_nontrans_rule_imports,
        build_default_settings,
        clear_pending_nontrans_rule_imports,
        get_app_root,
        load_pending_nontrans_rule_imports,
        mark_pending_nontrans_rule_notice,
    )
else:
    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from term_extractor_app.constants import APP_VERSION, UPDATE_ASSET_NAME_HINTS, UPDATE_RELEASE_API
    from term_extractor_app.core import scan_folder
    from term_extractor_app.models import TaskInput, normalize_extraction_mode, sync_extraction_flags
    from term_extractor_app.nontrans import (
        NONTRANS_ELEMENT_TYPE_LABELS,
        NONTRANS_ROLE_LABELS,
        BUILTIN_NONTRANS_LIBRARY_FILE,
        deduplicate_nontrans_regex_rows,
        expand_nontrans_regex_rows,
        load_builtin_nontrans_rules,
        validate_nontrans_rule,
    )
    from term_extractor_app.providers import ProviderRegistry
    from term_extractor_app.service_layer import ExtractionTaskFacade
    from term_extractor_app.storage import (
        append_pending_nontrans_rule_imports,
        build_default_settings,
        clear_pending_nontrans_rule_imports,
        get_app_root,
        load_pending_nontrans_rule_imports,
        mark_pending_nontrans_rule_notice,
    )


class StartTaskPayload(BaseModel):
    folder_path: str
    header_name: str = ""
    source_language: str = "中文"
    file_type: str = ""
    export_review_sheet: bool = False
    extraction_mode: str = "terms"
    single_item_char_limit: int = 500
    batch_request_char_limit: int = 3000
    resume: bool = False


class SettingsPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_name: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_concurrency: Optional[int] = None
    disable_system_proxy: Optional[bool] = None
    extraction_mode: Optional[str] = None
    source_language: Optional[str] = None
    nontrans_chunk_char_limit: Optional[int] = None
    nontrans_placeholder_format: Optional[str] = None
    term_recall_batch_char_limit: Optional[int] = None
    term_review_batch_char_limit: Optional[int] = None
    term_review_max_context_chars: Optional[int] = None
    nontrans_enable_thinking: Optional[bool] = None
    term_recall_enable_thinking: Optional[bool] = None
    term_review_enable_thinking: Optional[bool] = None
    builtin_regex_enabled: Optional[bool] = None
    ai_discovery_enabled: Optional[bool] = None
    ai_regex_generation_enabled: Optional[bool] = None
    numeric_normalization_enabled: Optional[bool] = None


class AsciiCandidatePatternPayload(BaseModel):
    name: str = ""
    pattern: str
    enabled: bool = True
    order_index: int = 0


class AsciiCandidatePatternsPayload(BaseModel):
    patterns: list[AsciiCandidatePatternPayload]


class BuiltinNonTransRulePayload(BaseModel):
    rule_id: str = ""
    name: str = ""
    role: str = "empty"
    element_type: str = ""
    pattern: str = ""
    open_pattern: str = ""
    close_pattern: str = ""
    empty_pattern: str = ""
    enabled: bool = True
    examples: list[str] = []


class BuiltinNonTransRulesPayload(BaseModel):
    rules: list[BuiltinNonTransRulePayload]


class PendingNonTransRuleItemPayload(BaseModel):
    cache_id: str = ""
    rule_id: str = ""
    name: str = ""
    role: str = "empty"
    element_type: str = "other"
    pattern: str = ""
    enabled: bool = True
    examples: list[str] = []


class PendingNonTransRuleImportPayload(BaseModel):
    rules: list[PendingNonTransRuleItemPayload]


class PendingNonTransRuleSeenPayload(BaseModel):
    notice_seen: Optional[bool] = None
    library_seen: Optional[bool] = None


class PromptTemplatesPayload(BaseModel):
    templates: dict[str, str]


class PromptTemplateResetPayload(BaseModel):
    keys: list[str] = []


class AppUpdateStartPayload(BaseModel):
    force: bool = False


PROMPT_TEMPLATE_META = [
    {
        "key": "candidate_system_prompt_template",
        "label": "术语召回提示词（系统）",
        "description": "",
    },
    {
        "key": "candidate_user_prompt_template",
        "label": "术语召回提示词（用户）",
        "description": "",
    },
    {
        "key": "classification_system_prompt_template",
        "label": "术语校验提示词（系统）",
        "description": "",
    },
    {
        "key": "classification_user_prompt_template",
        "label": "术语校验提示词（用户）",
        "description": "",
    },
    {
        "key": "nontrans_discovery_system_prompt_template",
        "label": "非译发现提示词（系统）",
        "description": "",
    },
    {
        "key": "nontrans_discovery_user_prompt_template",
        "label": "非译发现提示词（用户）",
        "description": "",
    },
    {
        "key": "nontrans_regex_system_prompt_template",
        "label": "非译正则提示词（系统）",
        "description": "",
    },
    {
        "key": "nontrans_regex_user_prompt_template",
        "label": "非译正则提示词（用户）",
        "description": "",
    },
]


def allowed_prompt_template_keys() -> set[str]:
    return {str(item["key"]) for item in PROMPT_TEMPLATE_META}


def prompt_templates_response(settings):
    defaults = build_default_settings().prompt_templates
    templates = []
    for item in PROMPT_TEMPLATE_META:
        key = str(item["key"])
        value = str(settings.prompt_templates.get(key, defaults.get(key, "")) or "")
        default_value = str(defaults.get(key, "") or "")
        templates.append(
            {
                "key": key,
                "label": item["label"],
                "description": item["description"],
                "value": value,
                "is_default": value == default_value,
            }
        )
    return {"templates": templates}


def builtin_nontrans_rules_response():
    rules = load_builtin_nontrans_rules()
    rows = deduplicate_nontrans_regex_rows(expand_nontrans_regex_rows(rules))
    return {
        "rule_count": len(rules),
        "row_count": len(rows),
        "rows": [
            {
                "row_id": row.row_id,
                "rule_id": row.rule_id,
                "name": row.name,
                "regex": row.regex,
                "role": row.role,
                "role_label": NONTRANS_ROLE_LABELS.get(row.role, row.role),
                "element_type": row.element_type,
                "element_type_label": NONTRANS_ELEMENT_TYPE_LABELS.get(row.element_type, row.element_type),
                "order_index": index,
                "examples": list(row.examples or []),
            }
            for index, row in enumerate(rows, start=1)
        ],
        "rules": [
            {
                **rule.to_dict(),
                "role": (
                    "open"
                    if str(rule.open_pattern or "").strip()
                    else "close"
                    if str(rule.close_pattern or "").strip()
                    else "empty"
                ),
                "regex": (
                    str(rule.open_pattern or "").strip()
                    or str(rule.close_pattern or "").strip()
                    or str(rule.empty_pattern or "").strip()
                    or str(rule.pattern or "").strip()
                ),
            }
            for rule in rules
        ],
    }


def pending_nontrans_rules_response(settings) -> dict:
    items = load_pending_nontrans_rule_imports(settings)
    notice_seen = bool(settings.ui_preferences.get("pending_nontrans_rule_notice_seen", False))
    library_seen = bool(settings.ui_preferences.get("pending_nontrans_rule_library_seen", False))
    return {
        "count": len(items),
        "has_pending": bool(items),
        "notice_seen": notice_seen,
        "library_seen": library_seen,
        "show_notice_dot": bool(items) and not notice_seen,
        "show_library_dot": bool(items) and not library_seen,
        "show_notice_button": bool(items) and not notice_seen,
        "rules": items,
    }


def _normalize_version_parts(version_text: str) -> list[int]:
    normalized = str(version_text or "").strip().lower()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    parts = []
    for chunk in normalized.split("."):
        chunk = chunk.strip()
        if not chunk:
            continue
        digits = "".join(char for char in chunk if char.isdigit())
        parts.append(int(digits or 0))
    return parts


def _is_remote_version_newer(current_version: str, remote_version: str) -> bool:
    left = _normalize_version_parts(current_version)
    right = _normalize_version_parts(remote_version)
    length = max(len(left), len(right), 1)
    left.extend([0] * (length - len(left)))
    right.extend([0] * (length - len(right)))
    return tuple(right) > tuple(left)


def _pick_update_asset(release_data: dict) -> Optional[dict]:
    assets = list(release_data.get("assets", []) or [])
    zip_assets = [
        item for item in assets
        if str(item.get("name", "") or "").lower().endswith(".zip")
        and str(item.get("browser_download_url", "") or "").strip()
    ]
    if not zip_assets:
        return None
    for hint in UPDATE_ASSET_NAME_HINTS:
        matched = next(
            (
                item for item in zip_assets
                if hint in str(item.get("name", "") or "").lower()
            ),
            None,
        )
        if matched is not None:
            return matched
    return zip_assets[0]


def _resolve_logo_path() -> Path:
    candidate_paths = [
        get_app_root() / "logo.png",
        get_app_root() / "_internal" / "logo.png",
        get_app_root().parent / "logo.png",
        Path(__file__).resolve().parent.parent / "logo.png",
    ]
    for path in candidate_paths:
        if path.exists() and path.is_file():
            return path
    raise FileNotFoundError("未找到 logo.png")


async def fetch_app_update_info() -> dict:
    current_version = APP_VERSION
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                UPDATE_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "TextForge-Toolkit-Updater",
                },
            )
            response.raise_for_status()
            release_data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {
                "supported": bool(getattr(sys, "frozen", False)),
                "current_version": current_version,
                "latest_version": current_version,
                "update_available": False,
                "release_notes": "",
                "published_at": "",
                "download_url": "",
                "asset_name": "",
                "message": "当前还没有可用的发布版本。",
            }
        return {
            "supported": bool(getattr(sys, "frozen", False)),
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "release_notes": "",
            "published_at": "",
            "download_url": "",
            "asset_name": "",
            "message": "检查更新失败：{0}".format(exc),
        }
    except Exception as exc:
        return {
            "supported": bool(getattr(sys, "frozen", False)),
            "current_version": current_version,
            "latest_version": current_version,
            "update_available": False,
            "release_notes": "",
            "published_at": "",
            "download_url": "",
            "asset_name": "",
            "message": "检查更新失败：{0}".format(exc),
        }

    latest_version = str(
        release_data.get("tag_name")
        or release_data.get("name")
        or current_version
    ).strip() or current_version
    asset = _pick_update_asset(release_data) or {}
    return {
        "supported": bool(getattr(sys, "frozen", False)),
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": _is_remote_version_newer(current_version, latest_version),
        "release_notes": str(release_data.get("body", "") or "").strip(),
        "published_at": str(release_data.get("published_at", "") or "").strip(),
        "download_url": str(asset.get("browser_download_url", "") or "").strip(),
        "asset_name": str(asset.get("name", "") or "").strip(),
        "message": "",
    }


def _build_update_powershell_script() -> str:
    return r"""
param(
  [string]$DownloadUrl,
  [string]$BundleRoot,
  [string]$LauncherName,
  [string]$ExeName,
  [int]$ParentPid
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Cyan
}

function Find-BundlePayloadRoot {
  param([string]$ExtractRoot, [string]$ExeName, [string]$LauncherName)
  $roots = @($ExtractRoot)
  $dirs = Get-ChildItem -LiteralPath $ExtractRoot -Directory -Recurse -ErrorAction SilentlyContinue
  foreach ($dir in $dirs) {
    $roots += $dir.FullName
  }
  foreach ($root in $roots) {
    $launcherPath = Join-Path $root $LauncherName
    $programExe = Join-Path (Join-Path $root "program") $ExeName
    $directExe = Join-Path $root $ExeName
    if ((Test-Path -LiteralPath $launcherPath) -and (Test-Path -LiteralPath $programExe)) {
      return $root
    }
    if (Test-Path -LiteralPath $launcherPath) {
      return $root
    }
    if (Test-Path -LiteralPath $programExe) {
      return $root
    }
    if (Test-Path -LiteralPath $directExe) {
      return $root
    }
  }
  throw "未找到更新包中的启动文件。"
}

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("textforge_update_" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $workDir "update.zip"
$extractDir = Join-Path $workDir "extract"
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
  $host.UI.RawUI.WindowTitle = "文本预处理工具 更新中"
  Write-Host "==============================================" -ForegroundColor DarkGray
  Write-Host "文本预处理工具 正在更新" -ForegroundColor Yellow
  Write-Host "请不要关闭此窗口，更新完成后会自动重新打开程序。" -ForegroundColor Gray
  Write-Host "==============================================" -ForegroundColor DarkGray
  Write-Host ""
  Write-Step "开始下载更新包"
  Invoke-WebRequest -Uri $DownloadUrl -OutFile $zipPath -UseBasicParsing
  Write-Step "下载完成，正在解压"
  Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
  $payloadRoot = Find-BundlePayloadRoot -ExtractRoot $extractDir -ExeName $ExeName -LauncherName $LauncherName

  if ($ParentPid -gt 0) {
    Write-Step "正在关闭旧进程"
    try {
      Stop-Process -Id $ParentPid -Force -ErrorAction SilentlyContinue
    }
    catch {}
    for ($i = 0; $i -lt 120; $i++) {
      $proc = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
      if ($null -eq $proc) { break }
      Start-Sleep -Milliseconds 500
    }
  }

  Write-Step "正在替换程序文件"
  $programDir = Join-Path $BundleRoot "program"
  if (Test-Path -LiteralPath $programDir) {
    Remove-Item -LiteralPath $programDir -Recurse -Force -ErrorAction SilentlyContinue
  }
  Get-ChildItem -LiteralPath $payloadRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $BundleRoot -Recurse -Force
  }

  $launcherPath = Join-Path $BundleRoot $LauncherName
  Write-Step "更新完成，正在重新启动"
  if (Test-Path -LiteralPath $launcherPath) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", ('"{0}"' -f $launcherPath) -WorkingDirectory $BundleRoot | Out-Null
  }
  else {
    Start-Process -FilePath (Join-Path $BundleRoot "program\$ExeName") -WorkingDirectory (Join-Path $BundleRoot "program") | Out-Null
  }
  Write-Host ""
  Write-Host "更新完成，程序已重新启动。" -ForegroundColor Green
  Start-Sleep -Seconds 2
}
finally {
  Start-Sleep -Seconds 2
  Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
}
"""


def start_app_update(download_url: str) -> dict:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("当前是源码运行模式，自动更新只支持发布版。")
    url = str(download_url or "").strip()
    if not url:
        raise RuntimeError("没有可用的更新下载地址。")

    app_root = Path(get_app_root()).resolve()
    exe_path = Path(sys.executable).resolve()
    bundle_root = app_root.parent if exe_path.parent.name.lower() == "program" else app_root
    launcher_name = "start_webui.bat"
    script_dir = Path(tempfile.mkdtemp(prefix="textforge_update_"))
    script_path = script_dir / "run_update.ps1"
    # Windows PowerShell 5.x reads UTF-8 scripts reliably when BOM is present.
    # Without BOM, non-ASCII text in the updater script can be misparsed.
    script_path.write_text(_build_update_powershell_script(), encoding="utf-8-sig")

    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-DownloadUrl",
            url,
            "-BundleRoot",
            str(bundle_root),
            "-LauncherName",
            launcher_name,
            "-ExeName",
            exe_path.name,
            "-ParentPid",
            str(os.getpid()),
        ],
        cwd=str(bundle_root),
        creationflags=(
            getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        ),
    )
    return {
        "ok": True,
        "message": "更新已开始，当前页面会关闭，并弹出更新窗口显示进度。",
    }


def _save_builtin_nontrans_rules_to_library(rules_payload: list[BuiltinNonTransRulePayload]) -> dict:
    normalized_rules = []
    seen_rule_ids = set()

    for index, item in enumerate(rules_payload, start=1):
        rule_id = str(item.rule_id or "").strip() or "custom_rule_{0:03d}".format(index)
        if rule_id in seen_rule_ids:
            raise HTTPException(status_code=400, detail="规则 ID 重复：{0}".format(rule_id))
        seen_rule_ids.add(rule_id)

        examples = [str(example or "").strip() for example in list(item.examples or []) if str(example or "").strip()]
        role = str(item.role or "empty").strip() or "empty"
        regex_text = (
            str(item.pattern or "").strip()
            or str(item.open_pattern or "").strip()
            or str(item.close_pattern or "").strip()
            or str(item.empty_pattern or "").strip()
        )
        rule = item.model_dump()
        rule.update(
            {
                "rule_id": rule_id,
                "name": str(item.name or "").strip() or rule_id,
                "element_type": str(item.element_type or "").strip() or "other",
                "pattern": regex_text,
                "open_pattern": regex_text if role == "open" else "",
                "close_pattern": regex_text if role == "close" else "",
                "empty_pattern": regex_text if role == "empty" else "",
                "enabled": bool(item.enabled),
                "order_index": index,
                "examples": examples,
                "source": "builtin",
            }
        )
        model_rule = load_builtin_nontrans_rules()[0].from_dict(rule)
        issues = []
        if role not in {"open", "close", "empty"}:
            issues.append("命中方式无效")
        if not regex_text:
            issues.append("至少要填写一个正则")
        try:
            re.compile(regex_text)
        except re.error as exc:
            issues.append("正则编译失败：{0}".format(exc))
        if issues:
            raise HTTPException(
                status_code=400,
                detail="规则 {0} 校验失败：{1}".format(model_rule.name or model_rule.rule_id, "；".join(issues)),
            )
        normalized_rules.append(model_rule.to_dict())

    BUILTIN_NONTRANS_LIBRARY_FILE.write_text(
        json.dumps({"version": 1, "rules": normalized_rules}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return builtin_nontrans_rules_response()


def create_app(facade: Optional[ExtractionTaskFacade] = None) -> FastAPI:
    task_facade = facade or ExtractionTaskFacade()
    app = FastAPI(title="AI Term Extractor WebUI")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return build_index_html()

    @app.get("/assets/app.css")
    async def css() -> Response:
        return Response(APP_CSS, media_type="text/css")

    @app.get("/assets/app.js")
    async def js() -> Response:
        return Response(APP_JS, media_type="application/javascript")

    @app.get("/assets/logo.png")
    async def logo() -> FileResponse:
        try:
            logo_path = _resolve_logo_path()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(logo_path, media_type="image/png")

    @app.get("/api/app-update")
    async def get_app_update():
        return await fetch_app_update_info()

    @app.post("/api/app-update/start")
    async def start_app_update_endpoint(payload: AppUpdateStartPayload):
        snapshot = task_facade.snapshot()
        if snapshot.is_running and not payload.force:
            raise HTTPException(status_code=409, detail="任务运行中，暂时不能更新。")
        update_info = await fetch_app_update_info()
        if not update_info.get("supported"):
            raise HTTPException(status_code=400, detail="当前运行方式不支持自动更新。")
        if not update_info.get("update_available"):
            raise HTTPException(status_code=400, detail="当前已经是最新版本。")
        if not str(update_info.get("download_url", "") or "").strip():
            raise HTTPException(status_code=400, detail="当前版本缺少可下载的更新包。")
        try:
            return start_app_update(str(update_info.get("download_url", "") or ""))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/settings")
    async def get_settings():
        settings = task_facade.load_settings()
        provider_settings = settings.provider_settings.get(settings.provider_name)
        nontrans = dict(settings.input_defaults.get("nontrans_stage_settings", {}) or {})
        recall = dict(settings.input_defaults.get("term_recall_stage_settings", {}) or {})
        review = dict(settings.input_defaults.get("term_review_stage_settings", {}) or {})
        return {
            "provider_name": settings.provider_name,
            "model_name": provider_settings.model if provider_settings else "",
            "api_key": provider_settings.api_key if provider_settings else "",
            "base_url": provider_settings.base_url if provider_settings else "",
            "timeout_seconds": provider_settings.timeout_seconds if provider_settings else 90,
            "max_concurrency": provider_settings.max_concurrency if provider_settings else 1,
            "disable_system_proxy": provider_settings.disable_system_proxy if provider_settings else True,
            "source_language": settings.input_defaults.get("source_language", "中文"),
            "extraction_mode": settings.input_defaults.get("extraction_mode", "terms"),
            "enable_nontrans_extraction": settings.input_defaults.get("enable_nontrans_extraction", True),
            "enable_term_extraction": settings.input_defaults.get("enable_term_extraction", True),
            "nontrans_placeholder_format": settings.input_defaults.get("nontrans_placeholder_format", "<{n}>"),
            "numeric_normalization_enabled": settings.input_defaults.get(
                "numeric_normalization_enabled", True
            ),
            "numeric_normalization_mode": settings.input_defaults.get(
                "numeric_normalization_mode", "duplicate_group_only"
            ),
            "nontrans_stage_settings": nontrans,
            "term_recall_stage_settings": recall,
            "term_review_stage_settings": review,
            "providers": list(settings.provider_settings.keys()),
            "pending_nontrans_rules": pending_nontrans_rules_response(settings),
        }

    @app.post("/api/settings")
    async def save_settings(payload: SettingsPayload):
        settings = task_facade.load_settings()
        if payload.provider_name and payload.provider_name in settings.provider_settings:
            settings.provider_name = payload.provider_name
        provider_settings = settings.provider_settings.get(settings.provider_name)
        if provider_settings:
            if payload.model_name is not None:
                provider_settings.model = payload.model_name
            if payload.api_key is not None:
                provider_settings.api_key = payload.api_key
            if payload.base_url is not None:
                provider_settings.base_url = payload.base_url
            if payload.timeout_seconds is not None:
                provider_settings.timeout_seconds = max(1, int(payload.timeout_seconds))
            if payload.max_concurrency is not None:
                provider_settings.max_concurrency = max(1, int(payload.max_concurrency))
            if payload.disable_system_proxy is not None:
                provider_settings.disable_system_proxy = bool(payload.disable_system_proxy)
            settings.provider_settings[settings.provider_name] = provider_settings
        if payload.extraction_mode:
            settings.input_defaults["extraction_mode"] = normalize_extraction_mode(payload.extraction_mode)
            sync_extraction_flags(settings.input_defaults)
        if payload.source_language:
            settings.input_defaults["source_language"] = payload.source_language
        if payload.nontrans_placeholder_format is not None:
            settings.input_defaults["nontrans_placeholder_format"] = payload.nontrans_placeholder_format.strip() or "<{n}>"
        settings.input_defaults["single_occurrence_approved_policy"] = "allow_to_library"
        if payload.numeric_normalization_enabled is not None:
            settings.input_defaults["numeric_normalization_enabled"] = bool(
                payload.numeric_normalization_enabled
            )
            settings.input_defaults.setdefault("numeric_normalization_mode", "duplicate_group_only")

        nontrans = dict(settings.input_defaults.get("nontrans_stage_settings", {}) or {})
        if payload.nontrans_chunk_char_limit is not None:
            nontrans["chunk_char_limit"] = int(payload.nontrans_chunk_char_limit)
        if payload.nontrans_enable_thinking is not None:
            nontrans["enable_thinking"] = bool(payload.nontrans_enable_thinking)
        if payload.builtin_regex_enabled is not None:
            nontrans["builtin_regex_enabled"] = bool(payload.builtin_regex_enabled)
        if payload.ai_discovery_enabled is not None:
            nontrans["ai_discovery_enabled"] = bool(payload.ai_discovery_enabled)
        if payload.ai_regex_generation_enabled is not None:
            nontrans["ai_regex_generation_enabled"] = bool(payload.ai_regex_generation_enabled)
        settings.input_defaults["nontrans_stage_settings"] = nontrans

        recall = dict(settings.input_defaults.get("term_recall_stage_settings", {}) or {})
        if payload.term_recall_batch_char_limit is not None:
            recall["batch_request_char_limit"] = int(payload.term_recall_batch_char_limit)
        if payload.term_recall_enable_thinking is not None:
            recall["enable_thinking"] = bool(payload.term_recall_enable_thinking)
        settings.input_defaults["term_recall_stage_settings"] = recall

        review = dict(settings.input_defaults.get("term_review_stage_settings", {}) or {})
        if payload.term_review_batch_char_limit is not None:
            review["batch_request_char_limit"] = int(payload.term_review_batch_char_limit)
        if payload.term_review_max_context_chars is not None:
            review["max_context_chars"] = int(payload.term_review_max_context_chars)
        if payload.term_review_enable_thinking is not None:
            review["enable_thinking"] = bool(payload.term_review_enable_thinking)
        settings.input_defaults["term_review_stage_settings"] = review

        task_facade.save_settings(settings)
        return {"ok": True}

    @app.post("/api/providers/models")
    async def load_provider_models(payload: SettingsPayload):
        settings = task_facade.load_settings()
        provider_name = payload.provider_name or settings.provider_name
        if provider_name not in settings.provider_settings:
            raise HTTPException(status_code=400, detail="Unknown provider.")

        provider_settings = settings.provider_settings[provider_name]
        if payload.model_name is not None:
            provider_settings.model = payload.model_name
        if payload.api_key is not None:
            provider_settings.api_key = payload.api_key
        if payload.base_url is not None:
            provider_settings.base_url = payload.base_url
        if payload.timeout_seconds is not None:
            provider_settings.timeout_seconds = max(1, int(payload.timeout_seconds))
        if payload.max_concurrency is not None:
            provider_settings.max_concurrency = max(1, int(payload.max_concurrency))
        if payload.disable_system_proxy is not None:
            provider_settings.disable_system_proxy = bool(payload.disable_system_proxy)

        adapter = ProviderRegistry.create_adapter(provider_name, provider_settings)
        try:
            success, message, models = await adapter.list_models()
        finally:
            await adapter.close()

        if not success:
            raise HTTPException(status_code=400, detail=message or "加载模型失败")

        return {
            "provider_name": provider_name,
            "models": models,
            "message": message or "已刷新模型列表",
            "selected_model": provider_settings.model,
        }

    @app.get("/api/ascii-candidate-patterns")
    async def get_ascii_candidate_patterns():
        settings = task_facade.load_settings()
        patterns = list(settings.input_defaults.get("ascii_candidate_patterns", []) or [])
        return {"patterns": patterns}

    @app.post("/api/ascii-candidate-patterns")
    async def save_ascii_candidate_patterns(payload: AsciiCandidatePatternsPayload):
        normalized = []
        for index, item in enumerate(payload.patterns, start=1):
            pattern = item.pattern.strip()
            if not pattern:
                raise HTTPException(status_code=400, detail="Regex pattern cannot be empty.")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise HTTPException(status_code=400, detail="Invalid regex: {0}".format(exc)) from exc
            name = item.name.strip() or pattern
            normalized.append(
                {
                    "name": name,
                    "pattern": pattern,
                    "enabled": bool(item.enabled),
                    "order_index": index,
                }
            )
        settings = task_facade.load_settings()
        settings.input_defaults["ascii_candidate_patterns"] = normalized
        task_facade.save_settings(settings)
        return {"ok": True, "patterns": normalized}

    @app.get("/api/nontrans-builtin-rules")
    async def get_nontrans_builtin_rules():
        return builtin_nontrans_rules_response()

    @app.post("/api/nontrans-builtin-rules")
    async def save_nontrans_builtin_rules(payload: BuiltinNonTransRulesPayload):
        response = _save_builtin_nontrans_rules_to_library(payload.rules)
        return {"ok": True, **response}

    @app.get("/api/nontrans-pending-rules")
    async def get_pending_nontrans_rules():
        settings = task_facade.load_settings()
        return pending_nontrans_rules_response(settings)

    @app.post("/api/nontrans-pending-rules/seen")
    async def save_pending_nontrans_rule_seen(payload: PendingNonTransRuleSeenPayload):
        settings = task_facade.load_settings()
        mark_pending_nontrans_rule_notice(
            settings,
            notice_seen=payload.notice_seen,
            library_seen=payload.library_seen,
        )
        task_facade.save_settings(settings)
        return {"ok": True, **pending_nontrans_rules_response(settings)}

    @app.post("/api/nontrans-pending-rules/import")
    async def import_pending_nontrans_rules(payload: PendingNonTransRuleImportPayload):
        if not payload.rules:
            raise HTTPException(status_code=400, detail="没有可导入的规则。")
        pending_rules = load_pending_nontrans_rule_imports(task_facade.load_settings())
        pending_by_cache_id = {
            str(item.get("cache_id", "")).strip(): item
            for item in pending_rules
            if str(item.get("cache_id", "")).strip()
        }
        if not pending_by_cache_id:
            raise HTTPException(status_code=400, detail="当前没有待导入的规则。")

        selected_cache_ids = []
        import_rows = []
        for index, item in enumerate(payload.rules, start=1):
            cache_id = str(item.cache_id or "").strip()
            if not cache_id or cache_id not in pending_by_cache_id:
                raise HTTPException(status_code=400, detail="存在无效的缓存规则，无法导入。")
            selected_cache_ids.append(cache_id)
            import_rows.append(
                BuiltinNonTransRulePayload(
                    rule_id=str(item.rule_id or "").strip() or cache_id,
                    name=str(item.name or "").strip() or cache_id,
                    role=str(item.role or "empty").strip() or "empty",
                    element_type=str(item.element_type or "other").strip() or "other",
                    pattern=str(item.pattern or "").strip(),
                    enabled=bool(item.enabled),
                    examples=[str(example or "").strip() for example in list(item.examples or []) if str(example or "").strip()],
                )
            )

        builtin_rules = load_builtin_nontrans_rules()
        builtin_by_key = {}
        merged_payload = []
        for rule in builtin_rules:
            role = (
                "open"
                if str(rule.open_pattern or "").strip()
                else "close"
                if str(rule.close_pattern or "").strip()
                else "empty"
            )
            regex = (
                str(rule.open_pattern or "").strip()
                or str(rule.close_pattern or "").strip()
                or str(rule.empty_pattern or "").strip()
                or str(rule.pattern or "").strip()
            )
            key = (role, str(rule.element_type or "").strip() or "other", regex)
            builtin_by_key[key] = rule
            merged_payload.append(
                BuiltinNonTransRulePayload(
                    rule_id=rule.rule_id,
                    name=rule.name,
                    role=role,
                    element_type=rule.element_type,
                    pattern=regex,
                    enabled=rule.enabled,
                    examples=list(rule.examples or []),
                )
            )

        for item in import_rows:
            key = (str(item.role), str(item.element_type), str(item.pattern))
            existing = builtin_by_key.get(key)
            if existing is None:
                merged_payload.append(item)
                continue
            merged_examples = [str(example or "").strip() for example in list(existing.examples or []) if str(example or "").strip()]
            for example in list(item.examples or []):
                cleaned = str(example or "").strip()
                if cleaned and cleaned not in merged_examples:
                    merged_examples.append(cleaned)
            for target in merged_payload:
                target_key = (str(target.role), str(target.element_type), str(target.pattern))
                if target_key == key:
                    target.examples = merged_examples[:3]
                    if not str(target.name or "").strip() and str(item.name or "").strip():
                        target.name = str(item.name)
                    break

        response = _save_builtin_nontrans_rules_to_library(merged_payload)
        settings = task_facade.load_settings()
        clear_pending_nontrans_rule_imports(settings)
        task_facade.save_settings(settings)
        return {
            "ok": True,
            **response,
            "pending_nontrans_rules": pending_nontrans_rules_response(settings),
        }

    @app.post("/api/nontrans-pending-rules/clear")
    async def clear_pending_nontrans_rules():
        settings = task_facade.load_settings()
        clear_pending_nontrans_rule_imports(settings)
        task_facade.save_settings(settings)
        return {"ok": True, **pending_nontrans_rules_response(settings)}

    @app.get("/api/prompt-templates")
    async def get_prompt_templates():
        settings = task_facade.load_settings()
        return prompt_templates_response(settings)

    @app.post("/api/prompt-templates")
    async def save_prompt_templates(payload: PromptTemplatesPayload):
        allowed_keys = allowed_prompt_template_keys()
        unknown_keys = sorted(set(payload.templates.keys()) - allowed_keys)
        if unknown_keys:
            raise HTTPException(
                status_code=400,
                detail="Unknown prompt template key: {0}".format(", ".join(unknown_keys)),
            )
        settings = task_facade.load_settings()
        for key, value in payload.templates.items():
            text = str(value)
            if not text.strip():
                raise HTTPException(status_code=400, detail="Prompt template cannot be empty: {0}".format(key))
            settings.prompt_templates[key] = text
        task_facade.save_settings(settings)
        return {"ok": True, **prompt_templates_response(settings)}

    @app.post("/api/prompt-templates/reset")
    async def reset_prompt_templates(payload: PromptTemplateResetPayload):
        allowed_keys = allowed_prompt_template_keys()
        keys = payload.keys or sorted(allowed_keys)
        unknown_keys = sorted(set(keys) - allowed_keys)
        if unknown_keys:
            raise HTTPException(
                status_code=400,
                detail="Unknown prompt template key: {0}".format(", ".join(unknown_keys)),
            )
        defaults = build_default_settings().prompt_templates
        settings = task_facade.load_settings()
        for key in keys:
            settings.prompt_templates[key] = defaults.get(key, "")
        task_facade.save_settings(settings)
        return {"ok": True, **prompt_templates_response(settings)}

    @app.get("/api/scan")
    async def scan(folder_path: str):
        try:
            result = scan_folder(folder_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.to_dict()

    @app.post("/api/dialog/select-folder")
    async def select_folder():
        try:
            folder_path = select_folder_dialog()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"folder_path": folder_path, "cancelled": not bool(folder_path)}

    @app.post("/api/tasks/start")
    async def start_task(payload: StartTaskPayload):
        settings = task_facade.load_settings()
        task_input = None
        if not payload.resume:
            task_input = TaskInput(
                folder_path=payload.folder_path,
                header_name=payload.header_name,
                source_language=payload.source_language,
                single_item_char_limit=payload.single_item_char_limit,
                batch_request_char_limit=payload.batch_request_char_limit,
                file_type=payload.file_type,
                export_review_sheet=payload.export_review_sheet,
                extraction_mode=payload.extraction_mode,
            )
        try:
            task_facade.start(task_input, resume=payload.resume, settings=settings)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/tasks/resume")
    async def resume_task():
        settings = task_facade.load_settings()
        try:
            task_facade.resume(settings=settings)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/api/tasks/stop")
    async def stop_task():
        task_facade.stop()
        return {"ok": True}

    @app.post("/api/tasks/clear-cache")
    async def clear_task_cache():
        try:
            task_facade.clear_runtime_cache()
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/api/status")
    async def status():
        return task_facade.snapshot().to_dict()

    @app.get("/api/results/summary")
    async def results_summary(output_file: Optional[str] = None):
        return task_facade.result_summary(output_file).to_dict()

    @app.get("/api/results/download")
    async def download_result(output_file: str):
        path = Path(output_file)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Output file does not exist.")
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/api/results/open-folder")
    async def open_result_folder(output_file: str):
        path = Path(output_file)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Output file does not exist.")
        try:
            open_file_location(path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "folder": str(path.parent)}

    return app


app = create_app()


def settings_to_json_for_debug() -> str:
    return json.dumps(build_default_settings().to_dict(), ensure_ascii=False, indent=2)


def open_file_location(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path.parent))  # type: ignore[attr-defined]
    elif os.name == "posix":
        opener = "open" if sys_platform_is_darwin() else "xdg-open"
        subprocess.Popen([opener, str(path.parent)])
    else:
        raise RuntimeError("Opening folders is not supported on this platform.")


def sys_platform_is_darwin() -> bool:
    return os.sys.platform == "darwin"


def select_folder_dialog() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError("当前环境不支持原生文件夹选择窗口。") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(title="选择待处理文件夹", mustexist=True)
    finally:
        root.destroy()
    return str(selected or "")


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>文本预处理工具</title>
  <link rel="stylesheet" href="/assets/app.css" />
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-mark" src="/assets/logo.png" alt="文本预处理工具" />
        <div class="brand-copy">
          <span class="brand-version">v__APP_VERSION__</span>
          <strong>文本预处理工具</strong>
          <small>术语与非译元素</small>
        </div>
      </div>
      <nav class="sidebar-nav">
        <button class="nav-link nav-link-top" data-page-target="modelSettingsPage">模型设置</button>

        <details class="nav-accordion" open data-accordion-key="text-preprocess">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">文本预处理工具</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub active" data-page-target="overviewPage">总览</button>
            <button class="nav-link nav-link-sub" data-page-target="modelStageSettingsPage">模型阶段设置</button>
            <button class="nav-link nav-link-sub" data-page-target="nontransSettingsPage">非译元素设置</button>
            <button class="nav-link nav-link-sub" data-page-target="promptSettingsPage">提示词设置</button>
            <button class="nav-link nav-link-sub" data-page-target="runDetailsPage">运行详情</button>
            <button class="nav-link nav-link-sub" data-page-target="resultsPage">结果</button>
          </div>
        </details>

        <details class="nav-accordion" data-accordion-key="diff-tool">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">Diff 工具</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub nav-link-placeholder" type="button" disabled>功能预留</button>
          </div>
        </details>

        <details class="nav-accordion" data-accordion-key="ai-review-tool">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">AI 审校工具</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub nav-link-placeholder" type="button" disabled>功能预留</button>
          </div>
        </details>

        <details class="nav-accordion" data-accordion-key="cross-excel-search">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">跨Excel搜索与合并</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub nav-link-placeholder" type="button" disabled>功能预留</button>
          </div>
        </details>
      </nav>
      <div class="sidebar-status">
        <div class="status-block">
          <small class="status-caption">当前任务</small>
          <strong id="taskTypeLabel">文本预处理工具</strong>
        </div>
        <div class="status-block">
          <small class="status-caption">任务状态</small>
          <span id="statusPill" class="pill">空闲</span>
          <strong id="stageLabel">未启动</strong>
          <small id="statusMessage">等待开始任务</small>
        </div>
        <small class="service-tip">服务地址：<code>http://127.0.0.1:8765</code></small>
      </div>
    </aside>

    <main class="content">
      <header class="hero">
        <div>
          <p class="eyebrow">WebUI</p>
          <h1>开始任务</h1>
          <p class="lede">先选择目录，再开始提取。</p>
        </div>
        <div class="hero-side">
          <button id="updateNoticeButton" class="notice-button update-notice-button" type="button" hidden>
            <span class="notice-dot"></span>
            <span>发现新版本</span>
          </button>
          <button id="pendingRuleNoticeButton" class="notice-button" type="button" hidden>
            <span class="notice-dot"></span>
            <span>发现新的非译规则</span>
          </button>
          <div class="hero-card">
            <div class="hero-card-label">当前状态</div>
            <strong id="heroStateText">未启动</strong>
            <small>服务启动后可以随时回到这里查看状态。</small>
          </div>
        </div>
      </header>

      <section id="overviewPage" class="page-section active">
        <div class="section-header">
          <div>
            <h2>总览</h2>
            <p></p>
          </div>
        </div>
        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>新建任务</h3>
              <p>选择目录和模式。</p>
            </div>
            <div class="grid two">
              <label>输入目录<span class="secret-field"><input id="folderPath" placeholder="D:\\项目\\文本表" /><button id="chooseFolderButton" class="mini-button" type="button">选择文件夹</button></span></label>
              <label>待提取列<select id="headerName"><option value="">请选择待提取列</option></select></label>
              <label>源语言<input id="sourceLanguage" value="Chinese" /></label>
              <label>运行模式<select id="extractionMode"><option value="terms">提取术语</option><option value="nontrans_only">仅提取非译元素</option></select></label>
            </div>
            <div class="actions">
              <button id="scanButton" class="secondary">扫描目录</button>
              <button id="startButton" class="primary">开始提取</button>
            </div>
            <pre id="scanResult" class="result-box">尚未扫描</pre>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>当前状态</h3>
              <p></p>
            </div>
            <div class="metrics hero-metrics">
              <div><span>进度</span><strong id="progressText">0 / 0</strong></div>
              <div><span>批次</span><strong id="batchText">0 / 0</strong></div>
              <div><span>成功</span><strong id="successText">0</strong></div>
              <div><span>失败</span><strong id="failureText">0</strong></div>
              <div><span>重试</span><strong id="retryText">0</strong></div>
              <div><span>并发</span><strong id="concurrencyText">0</strong></div>
            </div>
            <div class="progress"><span id="progressBar"></span></div>
            <div class="actions">
              <button id="resumeButton" class="secondary">继续任务</button>
              <button id="stopButton" class="danger">停止任务</button>
              <button id="clearCacheButton" class="danger">清空缓存</button>
            </div>
            <div id="errorPanel" class="error-panel" hidden>
              <strong>任务需要处理</strong>
              <span id="errorPanelText"></span>
            </div>
          </section>
        </div>

        <div class="grid two">
          <section class="card">
            <div class="card-title">
              <h3>最近输出</h3>
              <p></p>
            </div>
            <div class="result-file">
              <span>输出文件</span>
              <strong id="resultOutputFile">暂无输出</strong>
              <small id="resultState">等待任务完成。</small>
            </div>
            <div class="actions">
              <button id="downloadResultButton" class="secondary" disabled>下载结果文件</button>
              <button id="openResultFolderButton" class="secondary" disabled>打开输出目录</button>
            </div>
            <label>输出文件路径<input id="outputFile" readonly /></label>
            <label>最近错误<input id="lastError" readonly /></label>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>本次结果</h3>
              <p></p>
            </div>
            <div class="metrics result-metrics">
              <div><span>术语库</span><strong id="resultTermCount">0</strong></div>
              <div><span>失败记录</span><strong id="resultFailureCount">0</strong></div>
              <div><span>非译元素正则</span><strong id="resultRegexCount">0</strong></div>
            </div>
          </section>
        </div>
      </section>

      <section id="modelSettingsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>模型设置</h2>
            <p></p>
          </div>
        </div>
        <section class="card">
          <div class="card-title">
            <h3>通用模型</h3>
            <p>统一设置当前任务使用的模型连接。</p>
          </div>
          <div class="grid two">
            <label>供应商<input value="DeepSeek" readonly /></label>
            <label>模型列表<select id="modelName"></select></label>
            <label>API Key<span class="secret-field"><input id="apiKey" type="password" autocomplete="off" placeholder="sk-..." /><button id="saveModelConnectionButton" class="mini-button" type="button">加载模型</button></span></label>
            <label>超时秒数<input id="timeoutSeconds" type="number" min="1" value="90" /></label>
            <label>最大并发<input id="maxConcurrency" type="number" min="1" value="6" /></label>
            <label class="check"><input id="disableSystemProxy" type="checkbox" checked /> 禁用系统代理</label>
          </div>
          <div class="actions">
            <span id="modelConnectionHint" class="hint"></span>
          </div>
        </section>
      </section>

      <section id="modelStageSettingsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>模型阶段设置</h2>
            <p>分别控制非译元素、术语召回和术语校验阶段。</p>
          </div>
        </div>
        <div class="stage-grid">
          <section class="card compact-card">
            <div class="card-title">
              <h3>非译元素阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="nontransLimit" type="number" min="200" value="3000" /></label>
            <label class="check"><input id="nontransThinking" type="checkbox" /> 深度思考</label>
          </section>
          <section class="card compact-card">
            <div class="card-title">
              <h3>术语召回阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="recallLimit" type="number" min="200" value="3000" /></label>
            <label class="check"><input id="recallThinking" type="checkbox" /> 深度思考</label>
          </section>
          <section class="card compact-card">
            <div class="card-title">
              <h3>术语校验阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="reviewLimit" type="number" min="200" value="3000" /></label>
            <label>上下文长度<input id="reviewContextLimit" type="number" min="50" max="2000" value="220" /></label>
            <label class="check"><input id="reviewThinking" type="checkbox" /> 深度思考</label>
          </section>
        </div>

        <div class="sticky-actions">
          <button id="saveSettingsButton" class="primary">保存设置</button>
          <span id="saveHint" class="hint"></span>
        </div>
      </section>

      <section id="nontransSettingsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>非译元素设置</h2>
            <p></p>
          </div>
        </div>
        <div class="subnav">
          <button class="subnav-link active" data-subtab-group="nontrans" data-subtab-target="nontransRulePanel">宽泛检测规则</button>
          <button class="subnav-link" data-subtab-group="nontrans" data-subtab-target="nontransBuiltinPanel">内置规则库</button>
          <button class="subnav-link" data-subtab-group="nontrans" data-subtab-target="nontransProtectPanel">保护设置</button>
        </div>

        <div id="nontransRulePanel" class="subtab-panel active" data-subtab-panel-group="nontrans">
          <section class="card">
            <div class="card-title">
              <h3>宽泛检测规则</h3>
              <p>顺序可调整。</p>
            </div>
            <div class="pattern-table-wrap">
              <table class="pattern-table">
                <thead>
                  <tr><th>启用</th><th>名称</th><th>正则表达式</th><th>顺序</th><th>操作</th></tr>
                </thead>
                <tbody id="asciiPatternBody"></tbody>
              </table>
            </div>
            <div class="actions">
              <button id="addAsciiPatternButton" class="secondary">新增规则</button>
              <button id="saveAsciiPatternsButton" class="secondary">保存规则</button>
              <span id="asciiPatternHint" class="hint"></span>
            </div>
          </section>
        </div>

        <div id="nontransBuiltinPanel" class="subtab-panel" data-subtab-panel-group="nontrans">
          <section class="card">
            <div class="card-title">
              <h3>内置规则库</h3>
              <p></p>
            </div>
            <div class="summary-line">
              <span>规则家族：<strong id="builtinRuleCount">0</strong></span>
              <span>可执行正则：<strong id="builtinRuleRowCount">0</strong></span>
            </div>
            <div class="actions">
              <button id="addBuiltinRuleButton" class="secondary">新增规则</button>
              <button id="saveBuiltinRulesButton" class="secondary">保存规则库</button>
              <span id="builtinRuleHint" class="hint"></span>
            </div>
            <div class="pattern-table-wrap">
              <table class="pattern-table compact-rule-table builtin-editor-table">
                <thead>
                  <tr><th>启用</th><th>标题</th><th>正则表达式</th><th>命中方式</th><th>操作</th></tr>
                </thead>
                <tbody id="builtinRuleEditorBody"></tbody>
              </table>
            </div>
            <div class="pattern-table-wrap">
              <table class="pattern-table builtin-preview-table">
                <thead>
                  <tr><th>顺序</th><th>名称</th><th>开始/结束/空</th><th>类型</th><th>正则表达式</th><th>样例</th></tr>
                </thead>
                <tbody id="builtinRuleBody"></tbody>
              </table>
            </div>
            <div class="actions">
              <span class="hint">下方是保存后的执行预览。样例不会手动填写，规则实际命中后会自动记录，最多保留最新 3 个。</span>
            </div>
          </section>
        </div>

        <div id="nontransProtectPanel" class="subtab-panel" data-subtab-panel-group="nontrans">
          <div class="grid two">
            <section class="card">
              <div class="card-title">
                <h3>保护方式</h3>
                <p></p>
              </div>
              <label>占位符格式<input id="nontransPlaceholderFormat" value="<{n}>" /></label>
              <label class="check"><input id="numericNormalization" type="checkbox" checked /> 启用数值归一</label>
            </section>
            <section class="card">
              <div class="card-title">
                <h3>发现方式</h3>
                <p></p>
              </div>
              <label class="check"><input id="builtinRegex" type="checkbox" checked /> 启用内置规则库</label>
              <label class="check"><input id="aiDiscovery" type="checkbox" checked /> 启用 AI 发现</label>
              <label class="check"><input id="aiRegex" type="checkbox" checked /> 启用 AI 生成规则</label>
            </section>
          </div>
        </div>
      </section>

      <section id="promptSettingsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>提示词设置</h2>
            <p></p>
          </div>
        </div>
        <div class="subnav">
          <button class="subnav-link active" data-subtab-group="prompt" data-subtab-target="promptRecallPanel">术语召回</button>
          <button class="subnav-link" data-subtab-group="prompt" data-subtab-target="promptReviewPanel">术语校验</button>
          <button class="subnav-link" data-subtab-group="prompt" data-subtab-target="promptNontransPanel">非译元素</button>
        </div>
        <div id="promptTemplateList">
          <div id="promptRecallPanel" class="subtab-panel active" data-subtab-panel-group="prompt"></div>
          <div id="promptReviewPanel" class="subtab-panel" data-subtab-panel-group="prompt"></div>
          <div id="promptNontransPanel" class="subtab-panel" data-subtab-panel-group="prompt"></div>
        </div>
        <div class="actions">
          <button id="savePromptTemplatesButton" class="secondary">保存提示词</button>
          <button id="resetPromptTemplatesButton" class="danger">恢复默认提示词</button>
          <span id="promptTemplateHint" class="hint"></span>
        </div>
      </section>

      <section id="runDetailsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>运行详情</h2>
            <p></p>
          </div>
        </div>
        <section class="card">
          <div class="stats-panel">
            <div class="stats-title">任务统计</div>
            <div class="metrics compact-metrics">
              <div><span>源文本</span><strong id="statSourceRecords">0</strong></div>
              <div><span>非译候选条目</span><strong id="statNontransCandidateRecords">0</strong></div>
              <div><span>非译元素</span><strong id="statNontransElements">0</strong></div>
              <div><span>非译正则</span><strong id="statNontransRegexRows">0</strong></div>
              <div><span>文本片段</span><strong id="statSegments">0</strong></div>
              <div><span>候选术语</span><strong id="statCandidates">0</strong></div>
              <div><span>正式术语</span><strong id="statApproved">0</strong></div>
              <div><span>可召回文本</span><strong id="statRecallableRecords">0</strong></div>
              <div><span>唯一召回文本</span><strong id="statUniqueRecallTexts">0</strong></div>
              <div><span>去重节省</span><strong id="statDedupedRecords">0</strong></div>
              <div><span>节省比例</span><strong id="statDedupeSavingsPercent">0%</strong></div>
              <div><span>召回批次</span><strong id="statRecallChunkBatches">0</strong></div>
              <div><span>保护改写</span><strong id="statProtectedChanged">0</strong></div>
              <div><span>清洗为空</span><strong id="statCleanLostMeaningful">0</strong></div>
              <div><span>数值归一</span><strong id="statNumericNormalized">0</strong></div>
            </div>
          </div>

          <div class="stats-panel">
            <div class="stats-title">AI 消耗</div>
            <div class="metrics compact-metrics">
              <div><span>AI 请求</span><strong id="statLlmRequests">0</strong></div>
              <div><span>总耗时(ms)</span><strong id="statLlmLatencyTotal">0</strong></div>
              <div><span>平均耗时(ms)</span><strong id="statLlmLatencyAvg">0</strong></div>
              <div><span>提示字符</span><strong id="statLlmPromptChars">0</strong></div>
              <div><span>Token 合计</span><strong id="statLlmTokens">0</strong></div>
            </div>
          </div>

          <pre id="logBox" class="log-box">暂无日志</pre>
        </section>
      </section>

      <section id="resultsPage" class="page-section">
        <div class="section-header">
          <div>
            <h2>结果</h2>
            <p></p>
          </div>
        </div>
        <div class="grid two">
          <section class="card">
            <div class="card-title">
              <h3>导出结果</h3>
              <p></p>
            </div>
            <div class="result-file">
              <span>输出文件</span>
              <strong id="resultOutputFileMirror">暂无输出</strong>
              <small id="resultStateMirror">等待任务完成。</small>
            </div>
            <div class="notice-list">
              <div>术语提取模式：输出术语库、失败记录、非译元素正则。</div>
              <div>仅提取非译元素模式：只输出非译元素正则。</div>
            </div>
          </section>
          <section class="card">
            <div class="card-title">
              <h3>数量概览</h3>
              <p></p>
            </div>
            <div class="metrics result-metrics">
              <div><span>术语库</span><strong id="resultTermCountMirror">0</strong></div>
              <div><span>失败记录</span><strong id="resultFailureCountMirror">0</strong></div>
              <div><span>非译元素正则</span><strong id="resultRegexCountMirror">0</strong></div>
            </div>
          </section>
        </div>
      </section>

    </main>
  </div>

  <div id="pendingRuleOverlay" class="modal-overlay" hidden>
    <div class="modal-card notice-modal">
      <div class="modal-header">
        <div>
          <h3>发现新的非译规则</h3>
          <p>这些规则来自最近的任务结果。确认后会写入内置规则库。</p>
        </div>
        <button id="closePendingRuleModalButton" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div class="modal-actions">
        <button id="pendingRuleSelectAllButton" class="secondary" type="button">全选</button>
        <button id="pendingRuleClearSelectionButton" class="secondary" type="button">取消全选</button>
      </div>
      <div class="pattern-table-wrap">
        <table class="pattern-table compact-rule-table pending-rule-table">
          <thead>
            <tr><th>导入</th><th>标题</th><th>正则表达式</th><th>命中方式</th><th>样例</th></tr>
          </thead>
          <tbody id="pendingRuleEditorBody"></tbody>
        </table>
      </div>
      <div class="modal-footer">
        <span id="pendingRuleHint" class="hint"></span>
        <button id="confirmPendingRuleImportButton" class="primary" type="button">导入到内置规则库</button>
      </div>
    </div>
  </div>
  <div id="appUpdateOverlay" class="modal-overlay" hidden>
    <div class="modal-card notice-modal update-modal">
      <div class="modal-header">
        <div>
          <h3>发现新版本</h3>
          <p id="appUpdateSummary">当前版本与最新版本不一致。</p>
        </div>
        <button id="closeAppUpdateModalButton" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div class="summary-line">
        <span>当前版本 <strong id="appUpdateCurrentVersion">-</strong></span>
        <span>最新版本 <strong id="appUpdateLatestVersion">-</strong></span>
      </div>
      <div class="pattern-table-wrap">
        <div id="appUpdateReleaseNotes" class="update-release-notes">暂无更新日志</div>
      </div>
      <div class="modal-footer">
        <span id="appUpdateHint" class="hint"></span>
        <div class="modal-footer-actions">
          <button id="cancelAppUpdateButton" class="secondary" type="button">取消</button>
          <button id="confirmAppUpdateButton" class="primary" type="button">立即更新</button>
        </div>
      </div>
    </div>
  </div>
  <script src="/assets/app.js"></script>
</body>
</html>
"""


def build_index_html() -> str:
    return INDEX_HTML.replace("__APP_VERSION__", APP_VERSION)


APP_CSS = r"""
:root {
  --bg: #eef3f8;
  --panel: #ffffff;
  --ink: #162033;
  --muted: #66748a;
  --line: #dbe4ef;
  --primary: #1f6f68;
  --primary-strong: #16564f;
  --danger: #b4443f;
  --shadow: 0 18px 45px rgba(22, 32, 51, 0.10);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(31,111,104,.18), transparent 34rem),
    linear-gradient(135deg, #f8fbfd 0%, var(--bg) 55%, #e7eef6 100%);
  color: var(--ink);
  font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
  font-size: 15px;
}
.shell { display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; }
.sidebar {
  padding: 28px 22px;
  background: rgba(255,255,255,.74);
  border-right: 1px solid var(--line);
  backdrop-filter: blur(18px);
}
.brand { display: flex; gap: 12px; align-items: center; margin-bottom: 36px; }
.brand-mark { width: 38px; height: 38px; border-radius: 13px; object-fit: cover; display: block; box-shadow: var(--shadow); background: #ffffff; }
.brand-copy { min-width: 0; display: grid; gap: 2px; }
.brand-version {
  display: inline-flex;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e7f1ef;
  color: var(--primary-strong);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
}
.brand strong { display:block; font-size: 18px; line-height: 1.2; }
.brand small { color: var(--muted); line-height: 1.3; }
.sidebar-nav { display: grid; gap: 12px; margin-bottom: 22px; }
.nav-group { display: grid; gap: 8px; }
.nav-group-title {
  padding: 0;
  color: var(--ink);
  font-size: 18px;
  font-weight: 800;
  line-height: 1.25;
}
.nav-accordion {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255,255,255,.52);
  overflow: hidden;
}
.nav-accordion[open] {
  background: rgba(255,255,255,.82);
  box-shadow: 0 10px 24px rgba(22, 32, 51, 0.08);
}
.nav-accordion-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  list-style: none;
}
.nav-accordion-summary::-webkit-details-marker { display: none; }
.nav-accordion-summary::after {
  content: "+";
  color: var(--muted);
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}
.nav-accordion[open] .nav-accordion-summary::after { content: "-"; }
.nav-submenu {
  display: grid;
  gap: 8px;
  padding: 0 12px 12px;
}
.nav-link {
  width: 100%;
  justify-content: flex-start;
  min-height: 44px;
  background: transparent;
  color: var(--muted);
  border: 0;
  text-align: left;
  padding: 0 14px;
  border-radius: 12px;
  font-weight: 700;
}
.nav-link-top {
  min-height: 52px;
  padding: 0 16px;
  font-size: 22px;
  font-weight: 800;
  color: var(--ink);
  background: rgba(255,255,255,.78);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}
.nav-link-sub { padding-left: 18px; font-size: 15px; }
.nav-link-placeholder {
  opacity: 0.58;
  border: 1px dashed #cbd8e6;
  background: rgba(237,243,248,.45);
}
.nav-link.active, .nav-link:hover { background: #e7f1ef; color: var(--primary-strong); }
.sidebar-status {
  display: grid;
  gap: 12px;
  padding: 16px;
  background: rgba(255,255,255,.78);
  border: 1px solid var(--line);
  border-radius: 18px;
}
.status-block {
  display: grid;
  gap: 6px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(219,228,239,.9);
}
.status-block:last-of-type {
  padding-bottom: 0;
  border-bottom: 0;
}
.status-caption {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.service-tip { color: var(--muted); line-height: 1.5; }
.service-tip code { font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; }
.content { padding: 28px; max-width: 1280px; width: 100%; }
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 20px;
  align-items: stretch;
  margin-bottom: 20px;
}
.hero h1 { margin: 0; font-size: clamp(28px, 3vw, 44px); line-height: 1.12; letter-spacing: -0.04em; max-width: 840px; }
.eyebrow { margin: 0 0 10px; color: var(--primary); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.lede { color: var(--muted); font-size: 16px; max-width: 760px; }
.hero-card, .card, .advanced-card {
  background: rgba(255,255,255,.88);
  border: 1px solid rgba(219,228,239,.9);
  border-radius: 24px;
  box-shadow: var(--shadow);
}
.hero-card { padding: 22px; display: grid; align-content: center; gap: 10px; }
.hero-card strong { font-size: 26px; }
.hero-card-label { color: var(--muted); font-weight: 700; }
.pill { width: max-content; padding: 7px 11px; border-radius: 999px; background: #e7f1ef; color: var(--primary-strong); font-weight: 800; }
.pill.running { background: #fff2cc; color: #865d10; }
.pill.failed { background: #fde5e2; color: var(--danger); }
.card { padding: 22px; margin-bottom: 18px; }
.advanced-card { padding: 0; margin-bottom: 18px; overflow: hidden; }
.advanced-card summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  cursor: pointer;
  list-style: none;
}
.advanced-card summary::-webkit-details-marker { display: none; }
.advanced-card summary::after {
  content: "灞曞紑";
  min-height: 34px;
  padding: 7px 12px;
  border-radius: 999px;
  background: #e6edf5;
  color: #25364c;
  font-weight: 800;
}
.advanced-card[open] summary::after { content: "鏀惰捣"; }
.advanced-card summary strong { display: block; font-size: 20px; }
.advanced-card summary small { display: block; margin-top: 4px; color: var(--muted); }
.advanced-shortcuts { display: flex; gap: 12px; flex-wrap: wrap; padding: 0 22px 22px; }
.shortcut-button { min-height: 40px; }
.page-section { display: none; }
.page-section.active { display: block; }
.section-header { margin: 0 0 16px; }
.section-header h2 { margin: 0; font-size: 26px; }
.section-header p { margin: 6px 0 0; color: var(--muted); }
.subnav { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.subnav-link {
  min-height: 38px;
  padding: 0 14px;
  background: #edf3f8;
  color: var(--muted);
  border-radius: 999px;
}
.subnav-link.active { background: #e7f1ef; color: var(--primary-strong); }
.link-with-dot,
.section-title-with-dot {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.badge-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #e14b4b;
  box-shadow: 0 0 0 3px rgba(225, 75, 75, 0.14);
}
.subtab-panel { display: none; }
.subtab-panel.active { display: block; }
.dashboard-grid { grid-template-columns: 1.2fr .8fr; align-items: start; }
.card-title { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.card-title h2 { margin: 0; font-size: 22px; }
.card-title h3 { margin: 0; font-size: 20px; }
.card-title p { margin: 0; color: var(--muted); max-width: 620px; }
.card-title p:empty, .section-header p:empty { display: none; }
.grid.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.stage-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.compact-card { margin-bottom: 0; }
.stage-panel { background: #f7fafc; border: 1px solid var(--line); border-radius: 18px; padding: 16px; display: grid; gap: 12px; }
.stage-panel h3 { margin: 0; font-size: 17px; }
label { display: grid; gap: 7px; color: var(--muted); font-weight: 700; }
input, select {
  width: 100%;
  min-height: 42px;
  border: 1px solid #cbd8e6;
  border-radius: 12px;
  padding: 9px 11px;
  background: #fff;
  color: var(--ink);
  font: inherit;
}
.secret-field { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.secret-field input { min-width: 0; }
.mini-button { min-height: 42px; padding: 0 14px; background: #e6edf5; color: #25364c; border: 1px solid #cbd8e6; }
.check { display: flex; align-items: center; gap: 9px; color: var(--ink); }
.check input { width: 18px; min-height: 18px; }
.actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
.sticky-actions {
  position: sticky;
  bottom: 18px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 18px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255,255,255,.92);
  box-shadow: var(--shadow);
}
button {
  min-height: 42px;
  border: 0;
  border-radius: 13px;
  padding: 0 18px;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}
button.primary { background: var(--primary); color: white; }
button.secondary { background: #e6edf5; color: #25364c; }
button.danger { background: #fde5e2; color: var(--danger); }
button:disabled { opacity: .58; cursor: not-allowed; }
.error-panel {
  display: grid;
  gap: 4px;
  margin: 0 0 14px;
  padding: 13px 14px;
  border: 1px solid #f2b8b5;
  border-radius: 14px;
  background: #fff1ef;
  color: var(--danger);
}
.error-panel[hidden] { display: none; }
.pattern-table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 16px; }
.pattern-table { width: 100%; border-collapse: collapse; background: #fff; }
.pattern-table th, .pattern-table td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
.pattern-table th { color: var(--muted); font-size: 13px; background: #f7fafc; }
.pattern-table tr:last-child td { border-bottom: 0; }
.pattern-table input[type="text"] { min-height: 36px; }
.pattern-table input[type="checkbox"] { width: 18px; min-height: 18px; }
.compact-rule-table th, .compact-rule-table td { padding: 8px; }
.compact-rule-table input[type="text"],
.compact-rule-table select {
  min-height: 34px;
  padding: 6px 9px;
  border-radius: 10px;
  font-size: 14px;
}
.compact-rule-table { table-layout: fixed; }
.builtin-editor-table th:nth-child(1),
.builtin-editor-table td:nth-child(1),
.pending-rule-table th:nth-child(1),
.pending-rule-table td:nth-child(1) { width: 54px; }
.builtin-editor-table th:nth-child(2),
.builtin-editor-table td:nth-child(2),
.pending-rule-table th:nth-child(2),
.pending-rule-table td:nth-child(2) { width: 120px; }
.builtin-editor-table th:nth-child(4),
.builtin-editor-table td:nth-child(4),
.pending-rule-table th:nth-child(4),
.pending-rule-table td:nth-child(4) { width: 92px; }
.pending-rule-table th:nth-child(5),
.pending-rule-table td:nth-child(5) { width: 360px; }
.builtin-preview-table { table-layout: fixed; }
.builtin-preview-table th:nth-child(1),
.builtin-preview-table td:nth-child(1) { width: 68px; }
.builtin-preview-table th:nth-child(2),
.builtin-preview-table td:nth-child(2) { width: 150px; }
.builtin-preview-table th:nth-child(3),
.builtin-preview-table td:nth-child(3) { width: 120px; }
.builtin-preview-table th:nth-child(4),
.builtin-preview-table td:nth-child(4) { width: 120px; }
.builtin-preview-table th:nth-child(6),
.builtin-preview-table td:nth-child(6) { width: 360px; }
.compact-rule-table .pattern-actions button {
  min-height: 32px;
  padding: 0 10px;
}
.empty-cell { color: var(--muted); text-align: center; padding: 22px !important; }
.pattern-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.pattern-actions button { min-height: 34px; padding: 0 10px; }
.summary-line { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 14px; color: var(--muted); font-weight: 700; }
.summary-line span { padding: 9px 12px; border: 1px solid var(--line); border-radius: 999px; background: #f7fafc; }
.summary-line strong { color: var(--ink); }
.update-leaving-screen {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px;
}
.update-leaving-card {
  width: min(460px, 100%);
  padding: 28px;
  border-radius: 22px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.92);
  box-shadow: var(--shadow);
  text-align: center;
}
.update-leaving-card h2 { margin: 0 0 10px; font-size: 26px; }
.update-leaving-card p { margin: 0; color: var(--muted); line-height: 1.7; }
.regex-cell { font: 13px/1.45 "Cascadia Mono", "Consolas", monospace; overflow-wrap: anywhere; color: var(--ink); }
.examples-cell { min-width: 0; }
.examples-scroll {
  max-height: 88px;
  overflow-y: auto;
  padding-right: 4px;
  line-height: 1.45;
  white-space: normal;
  overflow-wrap: anywhere;
}
.examples-item + .examples-item { margin-top: 6px; }
.scope-toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.scope-list { display: grid; gap: 12px; }
.scope-item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px 12px; align-items: start; padding: 14px; border: 1px solid var(--line); border-radius: 16px; background: #f7fafc; }
.scope-toggle { display: flex; align-items: center; justify-content: center; min-height: 42px; }
.scope-item input[type="checkbox"] { width: 18px; min-height: 18px; margin: 0; }
.scope-fields { display: grid; gap: 8px; min-width: 0; }
.scope-fields textarea { min-height: 46px; resize: vertical; border: 1px solid #cbd8e6; border-radius: 12px; padding: 9px 11px; font: inherit; }
.scope-delete { min-height: 42px; padding: 0 14px; background: #fde5e2; color: var(--danger); }
.scope-empty { padding: 18px; border: 1px dashed #cbd8e6; border-radius: 16px; background: #f7fafc; color: var(--muted); text-align: center; }
.prompt-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }
.prompt-card { display: grid; gap: 9px; padding: 14px; border: 1px solid var(--line); border-radius: 16px; background: #f7fafc; }
.prompt-card header { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
.prompt-card strong { color: var(--ink); }
.prompt-card small { color: var(--muted); line-height: 1.45; }
.prompt-card-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.prompt-reset-button {
  min-height: 30px;
  padding: 0 10px;
  border-radius: 10px;
}
.prompt-card textarea {
  min-height: 220px;
  resize: vertical;
  border: 1px solid #cbd8e6;
  border-radius: 12px;
  padding: 11px;
  font: 13px/1.55 "Cascadia Mono", "Consolas", monospace;
  color: var(--ink);
}
.prompt-badge { white-space: nowrap; border-radius: 999px; padding: 4px 9px; background: #e6edf5; color: var(--muted); font-size: 12px; font-weight: 800; }
.prompt-badge.modified { background: #fff0cd; color: #8a5d00; }
.result-box, .log-box {
  margin: 16px 0 0;
  padding: 14px;
  border-radius: 14px;
  background: #111827;
  color: #d7e4f5;
  overflow: auto;
  font-size: 13px;
}
.metrics { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 12px; margin-bottom: 14px; }
.metrics div { padding: 14px; background: #f7fafc; border: 1px solid var(--line); border-radius: 16px; }
.metrics span { display:block; color: var(--muted); font-size: 13px; }
.metrics strong { font-size: 22px; }
.stats-panel { margin: 0 0 14px; padding: 14px; border: 1px solid var(--line); border-radius: 18px; background: rgba(247,250,252,.72); }
.stats-title { margin-bottom: 10px; color: var(--muted); font-weight: 800; }
.compact-metrics { grid-template-columns: repeat(4, minmax(0,1fr)); margin-bottom: 0; }
.compact-metrics div { background: #fff; }
.compact-metrics strong { font-size: 18px; }
.result-file {
  display: grid;
  gap: 5px;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: #f7fafc;
}
.result-file span, .result-file small { color: var(--muted); }
.result-file strong { overflow-wrap: anywhere; }
.result-metrics { grid-template-columns: repeat(4, minmax(0,1fr)); }
.hero-metrics { margin-bottom: 10px; }
.notice-list { display: grid; gap: 10px; color: var(--ink); }
.notice-list div { padding: 12px 14px; border: 1px solid var(--line); border-radius: 14px; background: #f7fafc; }
.progress { height: 12px; border-radius: 999px; background: #dfe8f2; overflow: hidden; margin-bottom: 14px; }
.progress span { display:block; height: 100%; width: 0; background: linear-gradient(90deg, var(--primary), #e7b95e); transition: width .25s ease; }
.hint { color: var(--primary-strong); font-weight: 700; }
.hero-side {
  display: grid;
  gap: 12px;
  justify-items: end;
}
.notice-button {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 16px;
  border: 1px solid #f5d2a4;
  border-radius: 999px;
  background: #fff6e7;
  color: #8a5d00;
  box-shadow: 0 10px 26px rgba(138, 93, 0, 0.12);
}
.update-notice-button {
  border-color: #c7d6ea;
  background: #eef5ff;
  color: #194b7a;
  box-shadow: 0 10px 26px rgba(25, 75, 122, 0.10);
}
.notice-button[hidden] { display: none !important; }
.notice-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #e14b4b;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.36);
  z-index: 1000;
}
.modal-overlay[hidden] { display: none; }
.modal-card {
  width: min(1120px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 22px;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.24);
}
.modal-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.modal-header h3 {
  margin: 0;
  font-size: 24px;
}
.modal-header p {
  margin: 8px 0 0;
  color: var(--muted);
}
.modal-close {
  min-height: 38px;
  min-width: 38px;
  padding: 0;
  border-radius: 999px;
  background: #edf3f8;
  color: #25364c;
}
.modal-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}
.modal-footer-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.update-release-notes {
  min-height: 180px;
  max-height: 360px;
  overflow-y: auto;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #f7fafc;
  color: var(--ink);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.update-modal .summary-line {
  margin-bottom: 16px;
}
@media (max-width: 980px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { position: static; }
  .hero, .grid.two, .stage-grid, .metrics, .prompt-grid, .dashboard-grid, .scope-list, .compact-metrics, .result-metrics { grid-template-columns: 1fr; }
  .sticky-actions { position: static; }
  .content { padding: 18px; }
  .hero-side { justify-items: stretch; }
  .modal-card { padding: 18px; }
  .modal-footer { align-items: stretch; }
}
"""


APP_JS = r"""
const $ = (id) => document.getElementById(id);
let asciiPatterns = [];
let promptTemplates = [];
let builtinRuleRows = [];
let builtinRuleDefinitions = [];
let pendingRuleDefinitions = [];
let pendingRuleState = { count: 0, has_pending: false, notice_seen: true, library_seen: true, show_notice_dot: false, show_library_dot: false };
let appUpdateState = {
  supported: false,
  current_version: "",
  latest_version: "",
  update_available: false,
  release_notes: "",
  published_at: "",
  download_url: "",
  asset_name: "",
  message: "",
};
let latestResultFile = "";
let availableModels = [];
let currentProviderName = "DeepSeek";
let currentBaseUrl = "";
let lastScanResult = null;
const PAGE_TASK_LABELS = {
  overviewPage: "文本预处理工具",
  modelSettingsPage: "模型设置",
  modelStageSettingsPage: "文本预处理工具",
  nontransSettingsPage: "文本预处理工具",
  promptSettingsPage: "文本预处理工具",
  runDetailsPage: "文本预处理工具",
  resultsPage: "文本预处理工具",
};
const PAGE_ACCORDION_KEYS = {
  overviewPage: "text-preprocess",
  modelStageSettingsPage: "text-preprocess",
  nontransSettingsPage: "text-preprocess",
  promptSettingsPage: "text-preprocess",
  runDetailsPage: "text-preprocess",
  resultsPage: "text-preprocess",
};

function setPage(pageId) {
  document.querySelectorAll(".page-section").forEach((section) => {
    section.classList.toggle("active", section.id === pageId);
  });
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.pageTarget === pageId);
  });
  $("taskTypeLabel").textContent = PAGE_TASK_LABELS[pageId] || "文本预处理工具";
  const activeAccordionKey = PAGE_ACCORDION_KEYS[pageId] || "";
  document.querySelectorAll(".nav-accordion").forEach((accordion) => {
    if (!accordion.dataset.accordionKey) return;
    accordion.open = accordion.dataset.accordionKey === activeAccordionKey;
  });
  if (pageId === "nontransSettingsPage" && pendingRuleState.show_library_dot) {
    markPendingRuleSeen({ library_seen: true }).catch(() => {});
  }
}

function setSubtab(group, targetId) {
  document.querySelectorAll(`[data-subtab-group="${group}"]`).forEach((button) => {
    button.classList.toggle("active", button.dataset.subtabTarget === targetId);
  });
  document.querySelectorAll(`[data-subtab-panel-group="${group}"]`).forEach((panel) => {
    panel.classList.toggle("active", panel.id === targetId);
  });
  if (group === "nontrans" && targetId === "nontransBuiltinPanel" && pendingRuleState.show_library_dot) {
    markPendingRuleSeen({ library_seen: true }).catch(() => {});
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function settingsPayload() {
  return {
    provider_name: currentProviderName,
    model_name: $("modelName").value,
    api_key: $("apiKey").value,
    base_url: currentBaseUrl,
    timeout_seconds: Number($("timeoutSeconds").value || 90),
    max_concurrency: Number($("maxConcurrency").value || 1),
    disable_system_proxy: $("disableSystemProxy").checked,
    extraction_mode: $("extractionMode").value,
    source_language: $("sourceLanguage").value,
    nontrans_chunk_char_limit: Number($("nontransLimit").value || 3000),
    nontrans_placeholder_format: $("nontransPlaceholderFormat").value || "<{n}>",
    term_recall_batch_char_limit: Number($("recallLimit").value || 3000),
    term_review_batch_char_limit: Number($("reviewLimit").value || 3000),
    term_review_max_context_chars: Number($("reviewContextLimit").value || 220),
    nontrans_enable_thinking: $("nontransThinking").checked,
    term_recall_enable_thinking: $("recallThinking").checked,
    term_review_enable_thinking: $("reviewThinking").checked,
    builtin_regex_enabled: $("builtinRegex").checked,
    ai_discovery_enabled: $("aiDiscovery").checked,
    ai_regex_generation_enabled: $("aiRegex").checked,
    numeric_normalization_enabled: $("numericNormalization").checked,
  };
}

function modelConnectionPayload() {
  return {
    provider_name: currentProviderName,
    model_name: $("modelName").value,
    api_key: $("apiKey").value,
    base_url: currentBaseUrl,
    timeout_seconds: Number($("timeoutSeconds").value || 90),
    max_concurrency: Number($("maxConcurrency").value || 1),
    disable_system_proxy: $("disableSystemProxy").checked,
  };
}

function setHeaderOptions(headers, preferredValue = "") {
  const select = $("headerName");
  const values = Array.isArray(headers) ? headers.map((item) => String(item || "").trim()).filter(Boolean) : [];
  const currentValue = String(preferredValue || select.value || "").trim();
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = values.length ? "请选择待提取列" : "请先选择文件夹";
  placeholder.selected = !currentValue;
  select.appendChild(placeholder);

  values.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (name === currentValue) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

function applyScanResult(data) {
  lastScanResult = data || null;
  $("scanResult").textContent = JSON.stringify(data, null, 2);

  if ((data?.file_type || "") === "xliff") {
    setHeaderOptions(["source"], "source");
    $("headerName").value = "source";
    $("headerName").disabled = true;
    return;
  }

  $("headerName").disabled = false;
  setHeaderOptions(data?.headers || [], $("headerName").value || (data?.headers || [])[0] || "");
}

async function loadSettings() {
  const data = await api("/api/settings");
  currentProviderName = data.provider_name || "DeepSeek";
  renderModelOptions([], data.model_name || "");
  $("apiKey").value = data.api_key || "";
  currentBaseUrl = data.base_url || "";
  $("timeoutSeconds").value = data.timeout_seconds || 90;
  $("maxConcurrency").value = data.max_concurrency || 1;
  $("disableSystemProxy").checked = data.disable_system_proxy !== false;
  $("sourceLanguage").value = data.source_language || "中文";
  $("extractionMode").value = data.extraction_mode || "terms";
  $("nontransPlaceholderFormat").value = data.nontrans_placeholder_format || "<{n}>";
  const nontrans = data.nontrans_stage_settings || {};
  const recall = data.term_recall_stage_settings || {};
  const review = data.term_review_stage_settings || {};
  $("nontransLimit").value = nontrans.chunk_char_limit || 3000;
  $("recallLimit").value = recall.batch_request_char_limit || 3000;
  $("reviewLimit").value = review.batch_request_char_limit || 3000;
  $("reviewContextLimit").value = review.max_context_chars || 220;
  $("nontransThinking").checked = Boolean(nontrans.enable_thinking);
  $("recallThinking").checked = Boolean(recall.enable_thinking);
  $("reviewThinking").checked = Boolean(review.enable_thinking);
  $("builtinRegex").checked = nontrans.builtin_regex_enabled !== false;
  $("aiDiscovery").checked = nontrans.ai_discovery_enabled !== false;
  $("aiRegex").checked = nontrans.ai_regex_generation_enabled !== false;
  $("numericNormalization").checked = data.numeric_normalization_enabled !== false;
  applyPendingRuleState(data.pending_nontrans_rules || {});
  setHeaderOptions([], "");
}

function renderModelOptions(models, preferredModel = "") {
  availableModels = Array.isArray(models) ? [...models] : [];
  const select = $("modelName");
  const currentValue = String(preferredModel || select.value || "").trim();
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = availableModels.length ? "请选择模型" : "保存 API Key 后加载模型";
  placeholder.disabled = availableModels.length > 0;
  placeholder.selected = !currentValue;
  select.appendChild(placeholder);

  const finalModels = [...availableModels];
  if (currentValue && !finalModels.includes(currentValue)) {
    finalModels.unshift(currentValue);
  }

  finalModels.forEach((name) => {
    const option = document.createElement("option");
    option.value = String(name || "");
    option.textContent = String(name || "");
    if (String(name || "") === currentValue) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

async function refreshModelList() {
  const data = await api("/api/providers/models", {
    method: "POST",
    body: JSON.stringify(modelConnectionPayload()),
  });
  const currentModel = $("modelName").value.trim();
  const nextModel = currentModel && (data.models || []).includes(currentModel)
    ? currentModel
    : data.selected_model && (data.models || []).includes(data.selected_model)
      ? data.selected_model
      : (data.models || [])[0] || "";
  renderModelOptions(data.models || [], nextModel);
  return data;
}

async function saveModelConnection() {
  try {
    await api("/api/settings", { method: "POST", body: JSON.stringify(modelConnectionPayload()) });
    const modelData = await refreshModelList();
    await api("/api/settings", { method: "POST", body: JSON.stringify(modelConnectionPayload()) });
    $("modelConnectionHint").textContent = modelData.message || "已保存并刷新模型列表";
  } catch (error) {
    renderModelOptions([], $("modelName").value);
    $("modelConnectionHint").textContent = `保存成功，但模型列表刷新失败：${error.message}`;
  }
  setTimeout(() => ($("modelConnectionHint").textContent = ""), 2600);
}

async function saveSettings() {
  await api("/api/settings", { method: "POST", body: JSON.stringify(settingsPayload()) });
  $("saveHint").textContent = "设置已保存";
  setTimeout(() => ($("saveHint").textContent = ""), 1800);
}

function renderPromptTemplates() {
  const groups = {
    recall: $("promptRecallPanel"),
    review: $("promptReviewPanel"),
    nontrans: $("promptNontransPanel"),
  };
  Object.values(groups).forEach((panel) => {
    panel.innerHTML = "";
  });
  promptTemplates.forEach((item) => {
    const key = String(item.key || "");
    let groupKey = "nontrans";
    if (key.startsWith("candidate_")) {
      groupKey = "recall";
    } else if (key.startsWith("classification_")) {
      groupKey = "review";
    }
    const list = groups[groupKey];
    const card = document.createElement("div");
    card.className = "prompt-card";
    card.innerHTML = `
      <header>
        <div>
          <strong>${escapeHtml(item.label || item.key || "")}</strong>
          ${item.description ? `<small>${escapeHtml(item.description || "")}</small>` : ""}
        </div>
        <div class="prompt-card-actions">
          <button type="button" class="secondary mini-button prompt-reset-button" data-key="${escapeHtml(item.key || "")}">恢复默认</button>
          <span class="prompt-badge ${item.is_default ? "" : "modified"}">${item.is_default ? "默认" : "已修改"}</span>
        </div>
      </header>
      <textarea data-key="${escapeHtml(item.key || "")}" spellcheck="false">${escapeHtml(item.value || "")}</textarea>`;
    card.querySelector("textarea").addEventListener("input", (event) => {
      item.value = event.target.value;
      item.is_default = false;
      const badge = card.querySelector(".prompt-badge");
      badge.textContent = "已修改";
      badge.classList.add("modified");
    });
    card.querySelector(".prompt-reset-button").addEventListener("click", () => resetSinglePromptTemplate(item.key));
    list.appendChild(card);
  });
}

async function loadPromptTemplates() {
  const data = await api("/api/prompt-templates");
  promptTemplates = data.templates || [];
  renderPromptTemplates();
}

async function savePromptTemplates() {
  const templates = {};
  promptTemplates.forEach((item) => {
    templates[item.key] = item.value || "";
  });
  await api("/api/prompt-templates", {
    method: "POST",
    body: JSON.stringify({ templates }),
  });
  $("promptTemplateHint").textContent = "提示词已保存";
  setTimeout(() => ($("promptTemplateHint").textContent = ""), 1800);
  await loadPromptTemplates();
}

async function resetPromptTemplates() {
  if (!window.confirm("恢复默认提示词会覆盖当前编辑内容，确定继续吗？")) return;
  await api("/api/prompt-templates/reset", {
    method: "POST",
    body: JSON.stringify({ keys: promptTemplates.map((item) => item.key) }),
  });
  $("promptTemplateHint").textContent = "默认提示词已恢复";
  setTimeout(() => ($("promptTemplateHint").textContent = ""), 1800);
  await loadPromptTemplates();
}

async function resetSinglePromptTemplate(key) {
  const localSnapshot = new Map(
    promptTemplates.map((item) => [
      item.key,
      {
        ...item,
        value: item.value || "",
        is_default: Boolean(item.is_default),
      },
    ]),
  );
  const data = await api("/api/prompt-templates/reset", {
    method: "POST",
    body: JSON.stringify({ keys: [key] }),
  });
  const resetItem = (data.templates || []).find((item) => item.key === key) || null;
  promptTemplates = promptTemplates.map((item) => {
    if (item.key === key) {
      return resetItem || item;
    }
    return localSnapshot.get(item.key) || item;
  });
  $("promptTemplateHint").textContent = "该提示词已恢复默认";
  setTimeout(() => ($("promptTemplateHint").textContent = ""), 1800);
  renderPromptTemplates();
}

function renderAsciiPatterns() {
  const body = $("asciiPatternBody");
  body.innerHTML = "";
  if (!asciiPatterns.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">暂无规则</td></tr>';
    return;
  }
  asciiPatterns.forEach((item, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><input type="checkbox" data-field="enabled" ${item.enabled !== false ? "checked" : ""}></td>
      <td><input type="text" data-field="name" value="${escapeHtml(item.name || "")}"></td>
      <td><input type="text" data-field="pattern" value="${escapeHtml(item.pattern || "")}"></td>
      <td>${index + 1}</td>
      <td class="pattern-actions">
        <button type="button" data-action="up">上移</button>
        <button type="button" data-action="down">下移</button>
        <button type="button" data-action="delete">删除</button>
      </td>`;
    row.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => syncAsciiPatternFromRow(index, row));
      input.addEventListener("input", () => syncAsciiPatternFromRow(index, row));
    });
    row.querySelector('[data-action="up"]').addEventListener("click", () => moveAsciiPattern(index, -1));
    row.querySelector('[data-action="down"]').addEventListener("click", () => moveAsciiPattern(index, 1));
    row.querySelector('[data-action="delete"]').addEventListener("click", () => {
      asciiPatterns.splice(index, 1);
      renderAsciiPatterns();
    });
    body.appendChild(row);
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function syncAsciiPatternFromRow(index, row) {
  asciiPatterns[index] = {
    name: row.querySelector('[data-field="name"]').value,
    pattern: row.querySelector('[data-field="pattern"]').value,
    enabled: row.querySelector('[data-field="enabled"]').checked,
    order_index: index + 1,
  };
}

function moveAsciiPattern(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= asciiPatterns.length) return;
  const [item] = asciiPatterns.splice(index, 1);
  asciiPatterns.splice(target, 0, item);
  renderAsciiPatterns();
}

async function loadAsciiPatterns() {
  const data = await api("/api/ascii-candidate-patterns");
  asciiPatterns = (data.patterns || []).map((item, index) => ({
    name: item.name || item.pattern || "",
    pattern: item.pattern || "",
    enabled: item.enabled !== false,
    order_index: item.order_index || index + 1,
  })).sort((a, b) => Number(a.order_index || 0) - Number(b.order_index || 0));
  renderAsciiPatterns();
}

function addAsciiPattern() {
  asciiPatterns.push({ name: "新规则", pattern: "", enabled: true, order_index: asciiPatterns.length + 1 });
  renderAsciiPatterns();
}

async function saveAsciiPatterns() {
  await api("/api/ascii-candidate-patterns", {
    method: "POST",
    body: JSON.stringify({ patterns: asciiPatterns }),
  });
  $("asciiPatternHint").textContent = "规则已保存";
  setTimeout(() => ($("asciiPatternHint").textContent = ""), 1800);
  await loadAsciiPatterns();
}

function normalizeBuiltinRule(item = {}, index = 0) {
  return {
    rule_id: String(item.rule_id || `custom_rule_${String(index + 1).padStart(3, "0")}`),
    name: String(item.name || ""),
    role: String(item.role || "empty"),
    regex: String(item.regex || item.pattern || ""),
    element_type: String(item.element_type || "other"),
    enabled: item.enabled !== false,
    examples: Array.isArray(item.examples) ? item.examples.map((value) => String(value || "")).filter(Boolean) : [],
  };
}

function normalizePendingRule(item = {}, index = 0) {
  return {
    cache_id: String(item.cache_id || `pending_rule_${String(index + 1).padStart(4, "0")}`),
    rule_id: String(item.rule_id || item.cache_id || `pending_rule_${String(index + 1).padStart(4, "0")}`),
    name: String(item.name || item.rule_id || item.cache_id || ""),
    role: String(item.role || "empty"),
    regex: String(item.regex || item.pattern || ""),
    element_type: String(item.element_type || "other"),
    enabled: item.enabled !== false,
    selected: item.selected !== false,
    examples: Array.isArray(item.examples) ? item.examples.map((value) => String(value || "")).filter(Boolean) : [],
  };
}

function renderBuiltinRuleEditors() {
  const body = $("builtinRuleEditorBody");
  body.innerHTML = "";
  if (!builtinRuleDefinitions.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">暂无规则</td></tr>';
    return;
  }
  builtinRuleDefinitions.forEach((item, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><input type="checkbox" data-field="enabled" ${item.enabled !== false ? "checked" : ""}></td>
      <td><input type="text" data-field="name" value="${escapeHtml(item.name || "")}" placeholder="规则标题"></td>
      <td><input type="text" data-field="regex" value="${escapeHtml(item.regex || "")}" placeholder="正则表达式"></td>
      <td>
        <select data-field="role">
          <option value="open" ${item.role === "open" ? "selected" : ""}>开始</option>
          <option value="close" ${item.role === "close" ? "selected" : ""}>结束</option>
          <option value="empty" ${item.role === "empty" ? "selected" : ""}>空</option>
        </select>
      </td>
      <td class="pattern-actions"><button type="button" data-action="delete">删除</button></td>`;
    row.querySelectorAll("input, select").forEach((input) => {
      input.addEventListener("change", () => syncBuiltinRuleFromEditor(index, row));
      input.addEventListener("input", () => syncBuiltinRuleFromEditor(index, row));
    });
    row.querySelector('[data-action="delete"]').addEventListener("click", () => {
      builtinRuleDefinitions.splice(index, 1);
      renderBuiltinRuleEditors();
    });
    body.appendChild(row);
  });
}

function syncBuiltinRuleFromEditor(index, row) {
  builtinRuleDefinitions[index] = {
    ...builtinRuleDefinitions[index],
    name: row.querySelector('[data-field="name"]').value.trim(),
    role: row.querySelector('[data-field="role"]').value,
    regex: row.querySelector('[data-field="regex"]').value.trim(),
    enabled: row.querySelector('[data-field="enabled"]').checked,
  };
}

function addBuiltinRule() {
  builtinRuleDefinitions.push(normalizeBuiltinRule({}, builtinRuleDefinitions.length));
  renderBuiltinRuleEditors();
}

function renderBuiltinRules(ruleCount, rowCount) {
  $("builtinRuleCount").textContent = ruleCount || 0;
  $("builtinRuleRowCount").textContent = rowCount || 0;
  const body = $("builtinRuleBody");
  body.innerHTML = "";
  if (!builtinRuleRows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">暂无内置规则</td></tr>';
    return;
  }
  builtinRuleRows.forEach((item, index) => {
    const row = document.createElement("tr");
    const examples = (item.examples || []).slice(0, 3);
    const examplesHtml = examples.length
      ? `<div class="examples-scroll">${examples.map((value) => `<div class="examples-item">${escapeHtml(value || "")}</div>`).join("")}</div>`
      : "";
    row.innerHTML = `
      <td>${item.order_index || index + 1}</td>
      <td>${escapeHtml(item.name || "")}</td>
      <td>${escapeHtml(item.role_label || item.role || "")}</td>
      <td>${escapeHtml(item.element_type_label || item.element_type || "")}</td>
      <td class="regex-cell">${escapeHtml(item.regex || "")}</td>
      <td class="examples-cell">${examplesHtml}</td>`;
    body.appendChild(row);
  });
}

async function loadBuiltinRules() {
  const data = await api("/api/nontrans-builtin-rules");
  builtinRuleDefinitions = (data.rules || []).map((item, index) => normalizeBuiltinRule(item, index));
  builtinRuleRows = data.rows || [];
  renderBuiltinRuleEditors();
  renderBuiltinRules(data.rule_count || 0, data.row_count || builtinRuleRows.length);
}

function renderPendingRuleEditors() {
  const body = $("pendingRuleEditorBody");
  if (!body) return;
  body.innerHTML = "";
  if (!pendingRuleDefinitions.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">当前没有待导入的规则</td></tr>';
    return;
  }
  pendingRuleDefinitions.forEach((item, index) => {
    const row = document.createElement("tr");
    const examples = (item.examples || []).slice(0, 3);
    const examplesHtml = examples.length
      ? `<div class="examples-scroll">${examples.map((value) => `<div class="examples-item">${escapeHtml(value || "")}</div>`).join("")}</div>`
      : "";
    row.innerHTML = `
      <td><input type="checkbox" data-field="selected" ${item.selected !== false ? "checked" : ""}></td>
      <td><input type="text" data-field="name" value="${escapeHtml(item.name || "")}" placeholder="规则标题"></td>
      <td><input type="text" data-field="regex" value="${escapeHtml(item.regex || "")}" placeholder="正则表达式"></td>
      <td>
        <select data-field="role">
          <option value="open" ${item.role === "open" ? "selected" : ""}>开始</option>
          <option value="close" ${item.role === "close" ? "selected" : ""}>结束</option>
          <option value="empty" ${item.role === "empty" ? "selected" : ""}>空</option>
        </select>
      </td>
      <td class="examples-cell">${examplesHtml}</td>`;
    row.querySelectorAll("input, select").forEach((input) => {
      input.addEventListener("change", () => syncPendingRuleFromEditor(index, row));
      input.addEventListener("input", () => syncPendingRuleFromEditor(index, row));
    });
    body.appendChild(row);
  });
}

function syncPendingRuleFromEditor(index, row) {
  pendingRuleDefinitions[index] = {
    ...pendingRuleDefinitions[index],
    selected: row.querySelector('[data-field="selected"]').checked,
    name: row.querySelector('[data-field="name"]').value.trim(),
    role: row.querySelector('[data-field="role"]').value,
    regex: row.querySelector('[data-field="regex"]').value.trim(),
  };
}

function setAllPendingRuleSelection(selected) {
  pendingRuleDefinitions = pendingRuleDefinitions.map((item) => ({ ...item, selected: Boolean(selected) }));
  renderPendingRuleEditors();
}

function ensurePendingRuleNavDot(pageTarget, visible) {
  const button = document.querySelector(`.nav-link[data-page-target="${pageTarget}"]`);
  if (!button) return;
  let wrapper = button.querySelector(".link-with-dot");
  let label = button.dataset.labelText;
  if (!label) {
    label = button.textContent.trim();
    button.dataset.labelText = label;
  }
  if (!wrapper) {
    button.textContent = "";
    wrapper = document.createElement("span");
    wrapper.className = "link-with-dot";
    const text = document.createElement("span");
    text.className = "link-text";
    text.textContent = label;
    const dot = document.createElement("span");
    dot.className = "badge-dot";
    dot.hidden = true;
    wrapper.appendChild(text);
    wrapper.appendChild(dot);
    button.appendChild(wrapper);
  }
  const dot = wrapper.querySelector(".badge-dot");
  if (dot) dot.hidden = !visible;
}

function ensurePendingRuleSubtabDot(targetId, visible) {
  const button = document.querySelector(`.subnav-link[data-subtab-target="${targetId}"]`);
  if (!button) return;
  let wrapper = button.querySelector(".link-with-dot");
  let label = button.dataset.labelText;
  if (!label) {
    label = button.textContent.trim();
    button.dataset.labelText = label;
  }
  if (!wrapper) {
    button.textContent = "";
    wrapper = document.createElement("span");
    wrapper.className = "link-with-dot";
    const text = document.createElement("span");
    text.className = "link-text";
    text.textContent = label;
    const dot = document.createElement("span");
    dot.className = "badge-dot";
    dot.hidden = true;
    wrapper.appendChild(text);
    wrapper.appendChild(dot);
    button.appendChild(wrapper);
  }
  const dot = wrapper.querySelector(".badge-dot");
  if (dot) dot.hidden = !visible;
}

function renderPendingRuleIndicators() {
  const noticeButton = $("pendingRuleNoticeButton");
  if (noticeButton) {
    noticeButton.hidden = !pendingRuleState.show_notice_button;
  }
  ensurePendingRuleNavDot("nontransSettingsPage", pendingRuleState.show_library_dot);
  ensurePendingRuleSubtabDot("nontransBuiltinPanel", pendingRuleState.show_library_dot);
}

function applyPendingRuleState(data) {
  pendingRuleState = {
    count: Number(data?.count || 0),
    has_pending: Boolean(data?.has_pending),
    notice_seen: Boolean(data?.notice_seen),
    library_seen: Boolean(data?.library_seen),
    show_notice_dot: Boolean(data?.show_notice_dot),
    show_library_dot: Boolean(data?.show_library_dot),
    show_notice_button: Boolean(data?.show_notice_button),
  };
  pendingRuleDefinitions = (data?.rules || []).map((item, index) => normalizePendingRule(item, index));
  renderPendingRuleEditors();
  renderPendingRuleIndicators();
}

function renderAppUpdateNotice() {
  const button = $("updateNoticeButton");
  if (!button) return;
  button.hidden = !appUpdateState.update_available;
}

function applyAppUpdateState(data) {
  appUpdateState = {
    supported: Boolean(data?.supported),
    current_version: String(data?.current_version || ""),
    latest_version: String(data?.latest_version || ""),
    update_available: Boolean(data?.update_available),
    release_notes: String(data?.release_notes || ""),
    published_at: String(data?.published_at || ""),
    download_url: String(data?.download_url || ""),
    asset_name: String(data?.asset_name || ""),
    message: String(data?.message || ""),
  };
  renderAppUpdateNotice();
}

async function loadAppUpdateInfo() {
  try {
    const data = await api("/api/app-update");
    applyAppUpdateState(data);
  } catch (error) {
    applyAppUpdateState({
      supported: false,
      current_version: "",
      latest_version: "",
      update_available: false,
      message: error.message,
    });
  }
}

function openAppUpdateModal() {
  $("appUpdateCurrentVersion").textContent = appUpdateState.current_version || "-";
  $("appUpdateLatestVersion").textContent = appUpdateState.latest_version || "-";
  $("appUpdateSummary").textContent = appUpdateState.message
    ? appUpdateState.message
    : `当前版本 ${appUpdateState.current_version || "-"}，最新版本 ${appUpdateState.latest_version || "-"}。`;
  $("appUpdateReleaseNotes").textContent = appUpdateState.release_notes || "暂无更新日志";
  $("appUpdateHint").textContent = "";
  $("confirmAppUpdateButton").disabled = !appUpdateState.update_available || !appUpdateState.download_url;
  $("appUpdateOverlay").hidden = false;
}

function closeAppUpdateModal() {
  $("appUpdateOverlay").hidden = true;
  $("appUpdateHint").textContent = "";
}

function leavePageForAppUpdate(message) {
  const safeMessage = escapeHtml(message || "更新已开始，请查看弹出的更新窗口。");
  document.body.innerHTML = `
    <div class="update-leaving-screen">
      <div class="update-leaving-card">
        <h2>正在更新</h2>
        <p>${safeMessage}</p>
      </div>
    </div>`;
  const tryCloseWindow = () => {
    try {
      window.open("", "_self");
      window.close();
    } catch (error) {
      console.warn(error);
    }
  };
  setTimeout(tryCloseWindow, 200);
  setTimeout(() => {
    tryCloseWindow();
    window.location.replace("about:blank");
  }, 1200);
}

async function startAppUpdate() {
  $("appUpdateHint").textContent = "正在启动更新...";
  $("confirmAppUpdateButton").disabled = true;
  try {
    const data = await api("/api/app-update/start", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const message = data.message || "更新已开始，当前页面会关闭，并弹出更新窗口显示进度。";
    $("appUpdateHint").textContent = message;
    setTimeout(() => {
      leavePageForAppUpdate(message);
    }, 180);
  } catch (error) {
    $("appUpdateHint").textContent = error.message;
    $("confirmAppUpdateButton").disabled = false;
  }
}

async function loadPendingRules() {
  const data = await api("/api/nontrans-pending-rules");
  applyPendingRuleState(data);
}

async function markPendingRuleSeen(payload) {
  const data = await api("/api/nontrans-pending-rules/seen", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  applyPendingRuleState(data);
}

function openPendingRuleModal() {
  $("pendingRuleOverlay").hidden = false;
  $("pendingRuleHint").textContent = "";
  if (pendingRuleState.show_notice_dot) {
    markPendingRuleSeen({ notice_seen: true }).catch(() => {});
  }
}

async function clearPendingRules() {
  const data = await api("/api/nontrans-pending-rules/clear", {
    method: "POST",
    body: "{}",
  });
  applyPendingRuleState(data);
  return data;
}

async function closePendingRuleModal() {
  if (pendingRuleState.has_pending) {
    await clearPendingRules();
  }
  $("pendingRuleOverlay").hidden = true;
  $("pendingRuleHint").textContent = "";
}

async function importPendingRules() {
  const selectedRules = pendingRuleDefinitions
    .filter((item) => item.selected !== false)
    .map((item) => ({
      cache_id: item.cache_id,
      rule_id: item.rule_id,
      name: item.name,
      role: item.role,
      element_type: item.element_type,
      pattern: item.regex,
      enabled: item.enabled !== false,
      examples: item.examples || [],
    }));
  if (!selectedRules.length) {
    $("pendingRuleHint").textContent = "请先勾选要导入的规则";
    return;
  }
  const data = await api("/api/nontrans-pending-rules/import", {
    method: "POST",
    body: JSON.stringify({ rules: selectedRules }),
  });
  $("pendingRuleHint").textContent = "已导入到内置规则库";
  builtinRuleDefinitions = (data.rules || []).map((item, index) => normalizeBuiltinRule(item, index));
  builtinRuleRows = data.rows || [];
  renderBuiltinRuleEditors();
  renderBuiltinRules(data.rule_count || 0, data.row_count || builtinRuleRows.length);
  applyPendingRuleState(data.pending_nontrans_rules || {});
  if (!pendingRuleState.has_pending) {
    closePendingRuleModal();
  }
}

async function saveBuiltinRules() {
  await api("/api/nontrans-builtin-rules", {
    method: "POST",
    body: JSON.stringify({
      rules: builtinRuleDefinitions.map((item, index) => ({
        rule_id: item.rule_id || `custom_rule_${String(index + 1).padStart(3, "0")}`,
        name: item.name || "",
        role: item.role || "empty",
        element_type: item.element_type || "other",
        pattern: item.regex || "",
        enabled: item.enabled !== false,
        examples: item.examples || [],
      })),
    }),
  });
  $("builtinRuleHint").textContent = "规则库已保存";
  setTimeout(() => ($("builtinRuleHint").textContent = ""), 1800);
  await loadBuiltinRules();
}

async function scanFolder() {
  const folder = $("folderPath").value.trim();
  if (!folder) {
    $("scanResult").textContent = "请先填写输入目录";
    return;
  }
  try {
    const data = await api(`/api/scan?folder_path=${encodeURIComponent(folder)}`);
    applyScanResult(data);
  } catch (error) {
    lastScanResult = null;
    $("headerName").disabled = false;
    setHeaderOptions([], "");
    $("scanResult").textContent = error.message;
  }
}

async function chooseFolder() {
  try {
    const data = await api("/api/dialog/select-folder", {
      method: "POST",
      body: "{}",
    });
    if (data.cancelled || !data.folder_path) {
      return;
    }
    $("folderPath").value = data.folder_path;
    await scanFolder();
  } catch (error) {
    $("scanResult").textContent = error.message;
  }
}

async function startTask() {
  const payload = {
    folder_path: $("folderPath").value.trim(),
    header_name: $("headerName").value.trim(),
    source_language: $("sourceLanguage").value.trim() || "中文",
    file_type: "",
    export_review_sheet: true,
    extraction_mode: $("extractionMode").value,
    single_item_char_limit: 500,
    batch_request_char_limit: Number($("recallLimit").value || 3000),
    resume: false,
  };
  $("errorPanel").hidden = true;
  await saveSettings();
  await api("/api/tasks/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await refreshStatus();
}

async function resumeTask() {
  $("errorPanel").hidden = true;
  await api("/api/tasks/resume", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function stopTask() {
  if (!window.confirm("确定停止当前任务吗？停止后可以继续上次任务。")) return;
  await api("/api/tasks/stop", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function clearRuntimeCache() {
  if (!window.confirm("清空缓存后将无法继续上次任务，确定要清空吗？")) return;
  await api("/api/tasks/clear-cache", { method: "POST", body: "{}" });
  await refreshStatus();
}

function renderResultSummary(data) {
  latestResultFile = data.exists && data.output_file ? data.output_file : "";
  $("resultOutputFile").textContent = data.output_file || "暂无输出";
  $("resultOutputFileMirror").textContent = data.output_file || "暂无输出";
  $("resultState").textContent = data.error
    ? data.error
    : data.exists
      ? "结果文件已生成"
      : "等待任务完成";
  $("resultStateMirror").textContent = $("resultState").textContent;
  $("resultTermCount").textContent = data.term_library_count || 0;
  $("resultTermCountMirror").textContent = data.term_library_count || 0;
  $("resultFailureCount").textContent = data.failure_count || 0;
  $("resultFailureCountMirror").textContent = data.failure_count || 0;
  $("resultRegexCount").textContent = data.nontrans_regex_count || 0;
  $("resultRegexCountMirror").textContent = data.nontrans_regex_count || 0;
  $("downloadResultButton").disabled = !latestResultFile;
  $("openResultFolderButton").disabled = !latestResultFile;
}

async function refreshResults(outputFile = "") {
  const query = outputFile ? `?output_file=${encodeURIComponent(outputFile)}` : "";
  const data = await api(`/api/results/summary${query}`);
  renderResultSummary(data);
}

function formatProgressPercent(current, total, isRunning) {
  const safeCurrent = Math.max(0, Number(current || 0));
  const safeTotal = Math.max(0, Number(total || 0));
  if (safeTotal <= 0) {
    return isRunning ? "0%" : "未开始";
  }
  const percent = Math.min(100, Math.max(0, Math.round((safeCurrent / safeTotal) * 100)));
  return `${percent}%`;
}

async function refreshStatus() {
  const data = await api("/api/status");
  $("statusPill").textContent = data.is_running ? "运行中" : data.last_error ? "失败" : "空闲";
  $("statusPill").className = `pill ${data.is_running ? "running" : data.last_error ? "failed" : ""}`;
  $("stageLabel").textContent = data.stage_label || data.stage || "空闲";
  $("heroStateText").textContent = data.is_running ? "运行中" : data.last_error ? "执行失败" : "未启动";
  $("statusMessage").textContent = data.message || (data.is_running ? "任务运行中" : "等待开始任务");
  $("progressText").textContent = formatProgressPercent(data.progress_current, data.progress_total, data.is_running);
  $("batchText").textContent = `${data.current_batch || 0} / ${data.total_batches || 0}`;
  $("successText").textContent = data.success_count || 0;
  $("failureText").textContent = data.failure_count || 0;
  $("retryText").textContent = data.retry_count || 0;
  $("concurrencyText").textContent = data.current_concurrency || 0;
  const stats = data.stats || {};
  $("statSourceRecords").textContent = stats.source_record_count || 0;
  $("statNontransCandidateRecords").textContent = stats.nontrans_candidate_record_count || 0;
  $("statNontransElements").textContent = stats.nontrans_element_count || 0;
  $("statNontransRegexRows").textContent = stats.nontrans_regex_row_count || 0;
  $("statSegments").textContent = stats.segment_count || 0;
  $("statCandidates").textContent = stats.candidate_count || 0;
  $("statApproved").textContent = stats.approved_count || 0;
  $("statRecallableRecords").textContent = stats.term_recall_recallable_record_count || 0;
  $("statUniqueRecallTexts").textContent = stats.term_recall_unique_text_count || 0;
  $("statDedupedRecords").textContent = stats.term_recall_deduped_record_count || 0;
  $("statDedupeSavingsPercent").textContent = `${stats.term_recall_dedupe_savings_percent || 0}%`;
  $("statRecallChunkBatches").textContent = stats.term_recall_chunk_batch_count || 0;
  $("statProtectedChanged").textContent = stats.nontrans_protected_changed_record_count || 0;
  $("statCleanLostMeaningful").textContent = stats.term_recall_clean_lost_meaningful_record_count || 0;
  $("statNumericNormalized").textContent = stats.term_recall_numeric_normalized_count || 0;
  $("statLlmRequests").textContent = stats.llm_request_count || 0;
  $("statLlmLatencyTotal").textContent = stats.llm_latency_ms_total || 0;
  $("statLlmLatencyAvg").textContent = stats.llm_latency_ms_avg || 0;
  $("statLlmPromptChars").textContent = stats.llm_prompt_char_count || 0;
  $("statLlmTokens").textContent = stats.llm_total_token_count || 0;
  const total = Number(data.progress_total || 0);
  const current = Number(data.progress_current || 0);
  $("progressBar").style.width = total > 0 ? `${Math.min(100, Math.round((current / total) * 100))}%` : "0";
  $("outputFile").value = data.output_file || "";
  $("lastError").value = data.last_error || "";
  $("errorPanel").hidden = !data.last_error;
  $("errorPanelText").textContent = data.last_error || "";
  $("logBox").textContent = (data.logs && data.logs.length) ? data.logs.join("\n") : "暂无日志";
  $("startButton").disabled = Boolean(data.is_running);
  $("resumeButton").disabled = Boolean(data.is_running) || !data.can_resume;
  $("stopButton").disabled = !data.is_running;
  $("clearCacheButton").disabled = Boolean(data.is_running) || !data.can_resume;
  if (data.output_file) {
    await refreshResults(data.output_file);
  } else {
    renderResultSummary({});
  }
}

$("saveModelConnectionButton").addEventListener("click", saveModelConnection);
$("saveSettingsButton").addEventListener("click", saveSettings);
$("savePromptTemplatesButton").addEventListener("click", savePromptTemplates);
$("resetPromptTemplatesButton").addEventListener("click", resetPromptTemplates);
$("addAsciiPatternButton").addEventListener("click", addAsciiPattern);
$("saveAsciiPatternsButton").addEventListener("click", saveAsciiPatterns);
$("addBuiltinRuleButton").addEventListener("click", addBuiltinRule);
$("saveBuiltinRulesButton").addEventListener("click", saveBuiltinRules);
$("updateNoticeButton").addEventListener("click", openAppUpdateModal);
$("pendingRuleNoticeButton").addEventListener("click", openPendingRuleModal);
$("closeAppUpdateModalButton").addEventListener("click", closeAppUpdateModal);
$("cancelAppUpdateButton").addEventListener("click", closeAppUpdateModal);
$("confirmAppUpdateButton").addEventListener("click", startAppUpdate);
$("closePendingRuleModalButton").addEventListener("click", closePendingRuleModal);
$("pendingRuleSelectAllButton").addEventListener("click", () => setAllPendingRuleSelection(true));
$("pendingRuleClearSelectionButton").addEventListener("click", () => setAllPendingRuleSelection(false));
$("confirmPendingRuleImportButton").addEventListener("click", importPendingRules);
$("chooseFolderButton").addEventListener("click", chooseFolder);
$("scanButton").addEventListener("click", scanFolder);
$("startButton").addEventListener("click", startTask);
$("resumeButton").addEventListener("click", resumeTask);
$("stopButton").addEventListener("click", stopTask);
$("clearCacheButton").addEventListener("click", clearRuntimeCache);
$("downloadResultButton").addEventListener("click", () => {
  if (!latestResultFile) return;
  window.location.href = `/api/results/download?output_file=${encodeURIComponent(latestResultFile)}`;
});
$("openResultFolderButton").addEventListener("click", async () => {
  if (!latestResultFile) return;
  await api(`/api/results/open-folder?output_file=${encodeURIComponent(latestResultFile)}`, {
    method: "POST",
    body: "{}",
  });
});

document.querySelectorAll(".nav-link, .shortcut-button").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.pageTarget));
});

document.querySelectorAll(".subnav-link").forEach((button) => {
  button.addEventListener("click", () => setSubtab(button.dataset.subtabGroup, button.dataset.subtabTarget));
});

Promise.all([loadSettings(), loadAsciiPatterns(), loadPromptTemplates(), loadBuiltinRules(), loadPendingRules(), loadAppUpdateInfo()]).then(refreshStatus).catch((error) => {
  $("statusMessage").textContent = error.message;
});
setInterval(refreshStatus, 1500);
"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)
