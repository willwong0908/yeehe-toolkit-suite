"""FastAPI WebUI entry point."""

from __future__ import annotations

import json
import csv
import os
import re
import sqlite3
import logging
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from openpyxl.utils import get_column_letter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

if __package__:
    from .ai_review.cache_service import (
        create_batch as create_ai_review_batch,
        get_batch as get_ai_review_batch,
        get_batch_items as get_ai_review_batch_items,
        open_directory as open_ai_review_directory,
        replace_batch_items as replace_ai_review_batch_items,
        save_upload_file as save_ai_review_upload_file,
    )
    from .ai_review.config import OUTPUTS_DIR as AI_REVIEW_OUTPUTS_DIR
    from .ai_review.database import init_db as init_ai_review_db
    from .ai_review.conversation_routes import router as ai_review_conversation_router
    from .ai_review.term_base_routes import router as ai_review_term_base_router
    from .ai_review.directional_service import (
        delete_directional_template,
        get_directional_template,
        list_directional_templates,
        save_directional_template,
    )
    from .ai_review.excel_mapping_service import (
        delete_excel_mapping_preset,
        get_excel_mapping_preset,
        list_excel_mapping_presets,
        save_excel_mapping_preset,
    )
    from .ai_review.file_reader import (
        detect_file_type as detect_ai_review_file_type,
        read_excel_headers as read_ai_review_excel_headers,
        read_excel_items as read_ai_review_excel_items,
        read_excel_items_by_mapping as read_ai_review_excel_items_by_mapping,
        read_xliff_items as read_ai_review_xliff_items,
        read_xliff_language_metadata as read_ai_review_xliff_language_metadata,
    )
    from .ai_review.forbidden_service import (
        delete_forbidden_template,
        get_forbidden_template,
        list_forbidden_templates,
        save_forbidden_template,
    )
    from .ai_review.prompt_service import (
        delete_prompt_template as delete_ai_review_prompt_template,
        get_prompt_template as get_ai_review_prompt_template,
        list_prompt_templates as list_ai_review_prompt_templates,
        reset_default_prompt_template as reset_ai_review_prompt_template,
        save_prompt_template as save_ai_review_prompt_template,
    )
    from .ai_review.review_service import (
        ReviewTaskError,
        create_review_task,
        get_review_followup_messages,
        get_review_issue_results,
        get_review_logs,
        get_review_results,
        get_review_task,
        recover_interrupted_review_tasks,
        send_review_followup_message,
    )
    from .ai_review.shared_provider import (
        SharedProviderError,
        get_shared_ai_settings as get_ai_review_shared_ai_settings,
        list_models as list_ai_review_models,
        test_chat as test_ai_review_chat,
    )
    from .constants import APP_VERSION, UPDATE_ASSET_NAME_HINTS, UPDATE_RELEASE_API
    from .core import read_excel_header_metadata, scan_folder
    from .cross_excel import merge_excel_files_by_headers, scan_cross_excel_folder, search_excel_rows
    from .diff_excel import (
        DiffRecord as DiffExcelRecord,
        apply_highlight_to_records as apply_diff_excel_highlight,
        apply_highlight_from_cache as apply_diff_excel_highlight_from_cache,
        export_cached_diff_records as export_diff_excel_cached_records,
        read_cached_diff_preview as read_diff_excel_cached_preview,
        run_compare_to_cache as run_diff_excel_compare_to_cache,
        scan_field_match_headers as scan_diff_excel_field_match_headers,
    )
    from .diff_task_service import DiffTaskService
    from .feedback import FeedbackError, feedback_status, submit_feedback
    from .models import TaskInput, normalize_extraction_mode, sync_extraction_flags
    from .open_utils import open_folder as open_path_folder
    from .open_utils import open_path as open_any_path
    from .open_utils import open_spreadsheet_cell
    from .nontrans import (
        NONTRANS_ELEMENT_TYPE_LABELS,
        NONTRANS_ROLE_LABELS,
        BUILTIN_NONTRANS_LIBRARY_FILE,
        deduplicate_nontrans_regex_rows,
        expand_nontrans_regex_rows,
        load_builtin_nontrans_rules,
        save_builtin_nontrans_rules,
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
    from .telemetry import track_event
else:
    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from term_extractor_app.ai_review.cache_service import (
        create_batch as create_ai_review_batch,
        get_batch as get_ai_review_batch,
        get_batch_items as get_ai_review_batch_items,
        open_directory as open_ai_review_directory,
        replace_batch_items as replace_ai_review_batch_items,
        save_upload_file as save_ai_review_upload_file,
    )
    from term_extractor_app.ai_review.config import OUTPUTS_DIR as AI_REVIEW_OUTPUTS_DIR
    from term_extractor_app.ai_review.database import init_db as init_ai_review_db
    from term_extractor_app.ai_review.conversation_routes import router as ai_review_conversation_router
    from term_extractor_app.ai_review.term_base_routes import router as ai_review_term_base_router
    from term_extractor_app.ai_review.directional_service import (
        delete_directional_template,
        get_directional_template,
        list_directional_templates,
        save_directional_template,
    )
    from term_extractor_app.ai_review.excel_mapping_service import (
        delete_excel_mapping_preset,
        get_excel_mapping_preset,
        list_excel_mapping_presets,
        save_excel_mapping_preset,
    )
    from term_extractor_app.ai_review.file_reader import (
        detect_file_type as detect_ai_review_file_type,
        read_excel_headers as read_ai_review_excel_headers,
        read_excel_items as read_ai_review_excel_items,
        read_excel_items_by_mapping as read_ai_review_excel_items_by_mapping,
        read_xliff_items as read_ai_review_xliff_items,
        read_xliff_language_metadata as read_ai_review_xliff_language_metadata,
    )
    from term_extractor_app.ai_review.forbidden_service import (
        delete_forbidden_template,
        get_forbidden_template,
        list_forbidden_templates,
        save_forbidden_template,
    )
    from term_extractor_app.ai_review.prompt_service import (
        delete_prompt_template as delete_ai_review_prompt_template,
        get_prompt_template as get_ai_review_prompt_template,
        list_prompt_templates as list_ai_review_prompt_templates,
        reset_default_prompt_template as reset_ai_review_prompt_template,
        save_prompt_template as save_ai_review_prompt_template,
    )
    from term_extractor_app.ai_review.review_service import (
        ReviewTaskError,
        create_review_task,
        get_review_followup_messages,
        get_review_issue_results,
        get_review_logs,
        get_review_results,
        get_review_task,
        recover_interrupted_review_tasks,
        send_review_followup_message,
    )
    from term_extractor_app.ai_review.shared_provider import (
        SharedProviderError,
        get_shared_ai_settings as get_ai_review_shared_ai_settings,
        list_models as list_ai_review_models,
        test_chat as test_ai_review_chat,
    )
    from term_extractor_app.constants import APP_VERSION, UPDATE_ASSET_NAME_HINTS, UPDATE_RELEASE_API
    from term_extractor_app.core import read_excel_header_metadata, scan_folder
    from term_extractor_app.cross_excel import (
        merge_excel_files_by_headers,
        scan_cross_excel_folder,
        search_excel_rows,
    )
    from term_extractor_app.diff_excel import (
        DiffRecord as DiffExcelRecord,
        apply_highlight_to_records as apply_diff_excel_highlight,
        apply_highlight_from_cache as apply_diff_excel_highlight_from_cache,
        export_cached_diff_records as export_diff_excel_cached_records,
        read_cached_diff_preview as read_diff_excel_cached_preview,
        run_compare_to_cache as run_diff_excel_compare_to_cache,
    )
    from term_extractor_app.diff_task_service import DiffTaskService
    from term_extractor_app.feedback import FeedbackError, feedback_status, submit_feedback
    from term_extractor_app.models import TaskInput, normalize_extraction_mode, sync_extraction_flags
    from term_extractor_app.open_utils import open_folder as open_path_folder
    from term_extractor_app.open_utils import open_path as open_any_path
    from term_extractor_app.open_utils import open_spreadsheet_cell
    from term_extractor_app.nontrans import (
        NONTRANS_ELEMENT_TYPE_LABELS,
        NONTRANS_ROLE_LABELS,
        BUILTIN_NONTRANS_LIBRARY_FILE,
        deduplicate_nontrans_regex_rows,
        expand_nontrans_regex_rows,
        load_builtin_nontrans_rules,
        save_builtin_nontrans_rules,
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
    from term_extractor_app.telemetry import track_event


class StartTaskPayload(BaseModel):
    folder_path: str
    header_name: str | list[str] = ""
    source_language: str = "中文"
    file_type: str = ""
    export_review_sheet: bool = False
    extraction_mode: str = "terms"
    single_item_char_limit: int = 500
    batch_request_char_limit: int = 3000
    resume: bool = False
    memoq_term_base_ids: list[str] = Field(default_factory=list)
    column_selections: dict[str, list[str]] = Field(default_factory=dict)
    input_files: list[str] = Field(default_factory=list)
    file_mappings: dict[str, dict[str, list[str]]] = Field(default_factory=dict)


class SettingsPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_name: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: Optional[int] = None
    disable_system_proxy: Optional[bool] = None
    extraction_mode: Optional[str] = None
    source_language: Optional[str] = None
    nontrans_chunk_char_limit: Optional[int] = None
    nontrans_placeholder_format: Optional[str] = None
    term_recall_batch_char_limit: Optional[int] = None
    term_review_batch_char_limit: Optional[int] = None
    term_review_max_context_chars: Optional[int] = None
    ai_review_batch_char_limit: Optional[int] = None
    ai_review_max_items_per_request: Optional[int] = None
    ai_review_workspace_enable_thinking: Optional[bool] = None
    ai_review_reasoning_effort: Optional[str] = None
    nontrans_reasoning_effort: Optional[str] = None
    term_recall_reasoning_effort: Optional[str] = None
    term_review_reasoning_effort: Optional[str] = None
    nontrans_enable_thinking: Optional[bool] = None
    term_recall_enable_thinking: Optional[bool] = None
    term_review_enable_thinking: Optional[bool] = None
    ai_review_enable_thinking: Optional[bool] = None
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


class ToolOpenPayload(BaseModel):
    tool_key: str


class CrossExcelSearchPayload(BaseModel):
    folder_path: str
    query: str
    limit: int = 300


class CrossExcelMergePayload(BaseModel):
    folder_path: str
    headers: list[str]
    apply_format: bool = True


class DiffExcelComparePayload(BaseModel):
    path_a: str
    path_b: str
    compare_mode: str = "position"
    reference_field: str = ""
    compare_fields: list[str] = []
    include_unmatched: bool = False


class DiffExcelExportPayload(BaseModel):
    cache_file: str
    query: str = ""
    output_file: str = ""


class DiffExcelHighlightPayload(BaseModel):
    cache_file: str
    query: str = ""
    target: str = "A"
    color_hex: str = "#FFD966"


class DiffExcelOpenCellPayload(BaseModel):
    file_path: str
    sheet_name: str
    cell_address: str


class AIReviewOpenFilePayload(BaseModel):
    file_path: str


class AIReviewSelectColumnsPayload(BaseModel):
    batch_id: str
    source_column: str
    target_column: str


class AIReviewExcelMappingPayload(BaseModel):
    batch_id: str
    mapping: dict


class AIReviewExcelMappingPresetSavePayload(BaseModel):
    id: str | None = None
    name: str
    mapping: dict


class AIReviewPromptTemplateSavePayload(BaseModel):
    id: str | None = None
    name: str
    system_prompt: str
    user_prompt: str
    forbidden_words_text: str = ""


class AIReviewDirectionalTemplateSavePayload(BaseModel):
    id: str | None = None
    name: str
    items: list[dict]


class AIReviewForbiddenTemplateSavePayload(BaseModel):
    id: str | None = None
    name: str
    words_text: str


class AIReviewStartPayload(BaseModel):
    batch_id: str
    prompt_template_id: str | None = None
    source_language: str = ""
    target_language: str = ""
    mode: str = "normal"
    directional_template_id: str | None = None
    enable_ai_review: bool = True
    enable_forbidden_check: bool = False
    forbidden_template_id: str | None = None


class AIReviewFollowupPayload(BaseModel):
    message: str


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


TOOL_OPEN_EVENT_MAP = {
    "home_guide": "tool_open.home_guide",
    "text_preprocess": "tool_open.text_preprocess",
    "ai_review": "tool_open.ai_review",
    "cross_excel": "tool_open.cross_excel",
    "diff_excel": "diff.open",
}


async def fetch_app_update_info() -> dict:
    current_version = APP_VERSION
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                UPDATE_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Yeehe-Toolkit-Suite-Updater",
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
        release_data.get("latest_version")
        or release_data.get("tag_name")
        or release_data.get("name")
        or current_version
    ).strip() or current_version
    asset = _pick_update_asset(release_data) or {}
    download_url = str(
        release_data.get("download_url")
        or asset.get("browser_download_url", "")
        or ""
    ).strip()
    asset_name = str(
        release_data.get("asset_name")
        or asset.get("name", "")
        or ""
    ).strip()
    return {
        "supported": bool(getattr(sys, "frozen", False)),
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": _is_remote_version_newer(current_version, latest_version),
        "release_notes": str(release_data.get("release_notes") or release_data.get("body", "") or "").strip(),
        "published_at": str(release_data.get("published_at", "") or "").strip(),
        "download_url": download_url,
        "asset_name": asset_name,
        "message": str(release_data.get("message", "") or "").strip(),
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

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("yeehe_update_" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $workDir "update.zip"
$extractDir = Join-Path $workDir "extract"
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

try {
  $host.UI.RawUI.WindowTitle = "译禾工具合集 更新中"
  Write-Host "==============================================" -ForegroundColor DarkGray
  Write-Host "译禾工具合集 正在更新" -ForegroundColor Yellow
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
    script_dir = Path(tempfile.mkdtemp(prefix="yeehe_update_"))
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

    save_builtin_nontrans_rules([load_builtin_nontrans_rules()[0].from_dict(rule) for rule in normalized_rules])
    return builtin_nontrans_rules_response()


def _open_local_file(path_text: str) -> None:
    open_any_path(path_text)


def _open_excel_cell(path_text: str, sheet_name: str, cell_address: str) -> None:
    open_spreadsheet_cell(path_text, sheet_name, cell_address)


def _ai_review_batch_response(batch_id: str, message: str) -> dict:
    batch = get_ai_review_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="读取批次不存在")
    preview = get_ai_review_batch_items(batch_id, limit=5)
    metadata = dict(batch.get("metadata", {}) or {})
    return {
        "ok": True,
        "message": message,
        "batch": {
            "id": batch["id"],
            "filename": batch["original_filename"],
            "file_type": batch["file_type"],
            "source_column": batch["source_column"],
            "target_column": batch["target_column"],
            "item_count": batch["item_count"],
            "source_language": metadata.get("source_language", ""),
            "target_language": metadata.get("target_language", ""),
            "updated_at": batch["updated_at"],
            "metadata": metadata,
        },
        "preview": preview,
    }


def _diff_excel_record_from_dict(item: dict) -> DiffExcelRecord:
    return DiffExcelRecord(
        filename_a=str(item.get("filename_a", "") or ""),
        filename_b=str(item.get("filename_b", "") or ""),
        sheet=str(item.get("sheet", "") or ""),
        cell_address=str(item.get("cell_address", "") or ""),
        value_a=str(item.get("value_a", "") or ""),
        value_b=str(item.get("value_b", "") or ""),
        file_path_a=str(item.get("file_path_a", "") or ""),
        file_path_b=str(item.get("file_path_b", "") or ""),
    )


def _ai_review_excel_upload_response(
    *,
    batch_id: str,
    filename: str,
    metadata: dict,
    original_file_path: str = "",
) -> dict:
    metadata_with_path = {**metadata}
    if original_file_path:
        metadata_with_path["original_file_path"] = original_file_path
    return {
        "ok": True,
        "message": "Excel 文件已读取，请导入文本。",
        "file_type": "excel",
        "batch_id": batch_id,
        "filename": filename,
        "batch": {
            "id": batch_id,
            "filename": filename,
            "file_type": "excel",
            "source_column": "",
            "target_column": "",
            "item_count": 0,
            "source_language": "",
            "target_language": "",
            "updated_at": "",
            "metadata": metadata_with_path,
        },
        "preview": [],
        "headers": metadata["headers"],
        "headers_by_sheet": metadata["headers_by_sheet"],
        "columns_by_sheet": metadata["columns_by_sheet"],
        "sheet_names": metadata["sheet_names"],
        "needs_column_selection": False,
    }


def create_app(facade: Optional[ExtractionTaskFacade] = None) -> FastAPI:
    task_facade = facade or ExtractionTaskFacade()
    diff_task_service = DiffTaskService()
    app = FastAPI(title="AI Term Extractor WebUI")

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        # Record the traceback and route only; do not log request bodies or keys.
        logger = logging.getLogger("term_extractor_app")
        logger.error("[WEBUI] 数据库请求失败：%s %s", request.method, request.url.path, exc_info=(type(exc), exc, exc.__traceback__))
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            return JSONResponse(status_code=503, content={"detail": "本地数据库正忙，请稍后重试；已完成的审校结果会保留。"})
        return JSONResponse(status_code=500, content={"detail": "本地数据库操作失败，请查看日志。"})

    init_ai_review_db()
    recover_interrupted_review_tasks()
    app.include_router(ai_review_conversation_router)
    app.include_router(ai_review_term_base_router)
    from term_extractor_app.feishu_transfer import router as transfer_router
    app.include_router(transfer_router)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return build_index_html()

    @app.get("/assets/app.css")
    async def css() -> Response:
        return Response(APP_CSS, media_type="text/css")

    @app.get("/assets/app.js")
    async def js() -> Response:
        return Response(APP_JS, media_type="application/javascript")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/assets/logo.png")
    async def logo() -> FileResponse:
        try:
            logo_path = _resolve_logo_path()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(logo_path, media_type="image/png")

    @app.get("/api/feedback/status")
    async def get_feedback_status():
        return feedback_status()

    @app.post("/api/feedback/open-log")
    async def open_feedback_log():
        info = feedback_status()
        log_path = str(info.get("log_path", "") or "").strip()
        if not log_path:
            raise HTTPException(status_code=404, detail="未找到日志路径。")
        try:
            _open_local_file(log_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="打开日志失败：{0}".format(exc)) from exc
        return {"ok": True, "log_path": log_path}

    @app.post("/api/feedback/submit")
    async def submit_feedback_endpoint(
        message: str = Form(...),
        screenshot: UploadFile | None = File(default=None),
    ):
        screenshot_bytes = None
        screenshot_name = ""
        screenshot_type = ""
        if screenshot is not None:
            screenshot_name = str(screenshot.filename or "").strip()
            screenshot_type = str(screenshot.content_type or "").strip()
            screenshot_bytes = await screenshot.read()
            if not screenshot_bytes:
                screenshot_bytes = None
        try:
            result = submit_feedback(
                message,
                screenshot_name=screenshot_name,
                screenshot_type=screenshot_type,
                screenshot_bytes=screenshot_bytes,
            )
        except FeedbackError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="反馈发送失败：{0}".format(exc)) from exc
        return result

    @app.post("/api/telemetry/tool-open")
    async def telemetry_tool_open(payload: ToolOpenPayload):
        event_name = TOOL_OPEN_EVENT_MAP.get(str(payload.tool_key or "").strip())
        if event_name:
            track_event(event_name)
        return {"ok": True}

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
            "ai_review_stage_settings": dict(settings.input_defaults.get("ai_review_stage_settings", {}) or {}),
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
        if payload.nontrans_reasoning_effort is not None:
            effort = str(payload.nontrans_reasoning_effort or "low").strip().lower()
            nontrans["reasoning_effort"] = effort if effort in {"low", "medium", "high"} else "low"
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
        if payload.term_recall_reasoning_effort is not None:
            effort = str(payload.term_recall_reasoning_effort or "low").strip().lower()
            recall["reasoning_effort"] = effort if effort in {"low", "medium", "high"} else "low"
        if payload.term_recall_enable_thinking is not None:
            recall["enable_thinking"] = bool(payload.term_recall_enable_thinking)
        settings.input_defaults["term_recall_stage_settings"] = recall

        review = dict(settings.input_defaults.get("term_review_stage_settings", {}) or {})
        if payload.term_review_batch_char_limit is not None:
            review["batch_request_char_limit"] = int(payload.term_review_batch_char_limit)
        if payload.term_review_max_context_chars is not None:
            review["max_context_chars"] = int(payload.term_review_max_context_chars)
        if payload.term_review_reasoning_effort is not None:
            effort = str(payload.term_review_reasoning_effort or "low").strip().lower()
            review["reasoning_effort"] = effort if effort in {"low", "medium", "high"} else "low"
        if payload.term_review_enable_thinking is not None:
            review["enable_thinking"] = bool(payload.term_review_enable_thinking)
        settings.input_defaults["term_review_stage_settings"] = review

        ai_review = dict(settings.input_defaults.get("ai_review_stage_settings", {}) or {})
        if payload.ai_review_batch_char_limit is not None:
            ai_review["batch_request_char_limit"] = int(payload.ai_review_batch_char_limit)
        if payload.ai_review_enable_thinking is not None:
            ai_review["enable_thinking"] = bool(payload.ai_review_enable_thinking)
        if payload.ai_review_max_items_per_request is not None:
            ai_review["max_items_per_request"] = max(1, int(payload.ai_review_max_items_per_request))
        if payload.ai_review_workspace_enable_thinking is not None:
            ai_review["workspace_enable_thinking"] = bool(payload.ai_review_workspace_enable_thinking)
        if payload.ai_review_reasoning_effort is not None:
            effort = str(payload.ai_review_reasoning_effort or "low").strip().lower()
            ai_review["reasoning_effort"] = effort if effort in {"low", "medium", "high"} else "low"
        # These three stages always use model reasoning; the UI only exposes its intensity.
        nontrans["enable_thinking"] = True
        recall["enable_thinking"] = True
        review["enable_thinking"] = True
        settings.input_defaults["nontrans_stage_settings"] = nontrans
        settings.input_defaults["term_recall_stage_settings"] = recall
        settings.input_defaults["term_review_stage_settings"] = review
        ai_review["enable_thinking"] = True
        ai_review["workspace_enable_thinking"] = True
        ai_review.pop("workspace_model", None)
        settings.input_defaults["ai_review_stage_settings"] = ai_review

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
        if import_rows:
            track_event("feature_used.nontrans_regex_imported")
        return {
            "ok": True,
            **response,
            "pending_nontrans_rules": pending_nontrans_rules_response(settings),
        }

    @app.post("/api/nontrans-pending-rules/clear")
    async def clear_pending_nontrans_rules():
        settings = task_facade.load_settings()
        had_pending = bool(load_pending_nontrans_rule_imports(settings))
        clear_pending_nontrans_rule_imports(settings)
        task_facade.save_settings(settings)
        if had_pending:
            track_event("feature_used.nontrans_regex_discarded")
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
    def scan(folder_path: str):
        try:
            result = scan_folder(folder_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.to_dict()

    @app.get("/api/preprocess/mapping-scan")
    def preprocess_mapping_scan(folder_path: str):
        try:
            result = scan_folder(folder_path)
            if result.file_type != "excel" or not result.files:
                return {"file_type": result.file_type, "sheet_names": [], "columns_by_sheet": {}}
            metadata = read_ai_review_excel_headers(Path(folder_path) / result.files[0])
            return {"file_type": "excel", "sheet_names": metadata.get("sheet_names", []), "columns_by_sheet": metadata.get("columns_by_sheet", {})}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/preprocess/file-mapping-scan")
    def preprocess_file_mapping_scan(file_path: str):
        try:
            path = Path(file_path).expanduser().resolve()
            if not path.is_file():
                raise ValueError("文件不存在")
            if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
                metadata = read_excel_header_metadata(path)
            elif path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    headers = next(csv.reader(handle), [])
                metadata = {"sheet_names": ["CSV"], "columns_by_sheet": {"CSV": [{"index": i, "letter": get_column_letter(i + 1), "header": h.strip()} for i, h in enumerate(headers) if h.strip()]}}
            else:
                metadata = {"sheet_names": [], "columns_by_sheet": {}}
            return {"file_name": path.name, "file_path": str(path), "file_type": "excel" if metadata.get("sheet_names") else path.suffix.lower().lstrip("."), **metadata}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/preprocess/folder-files")
    def preprocess_folder_files(folder_path: str):
        try:
            folder = Path(folder_path).expanduser().resolve()
            if not folder.is_dir():
                raise ValueError("文件夹路径无效。")
            supported_suffixes = {".xlsx", ".xlsm", ".xls", ".csv", ".xlf", ".xliff"}
            paths = sorted(
                str(path.resolve())
                for path in folder.iterdir()
                if path.is_file()
                and not path.name.startswith("~$")
                and path.suffix.lower() in supported_suffixes
            )
            if not paths:
                raise ValueError("所选文件夹里没有可处理的 Excel、CSV 或 XLIFF 文件。")
            return {"folder_path": str(folder), "file_paths": paths, "file_count": len(paths)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/dialog/select-folder")
    def select_folder():
        try:
            folder_path = select_folder_dialog()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"folder_path": folder_path, "cancelled": not bool(folder_path)}

    @app.get("/api/cross-excel/scan")
    def cross_excel_scan(folder_path: str):
        try:
            return scan_cross_excel_folder(folder_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cross-excel/search")
    def cross_excel_search(payload: CrossExcelSearchPayload):
        try:
            track_event("task_action.cross_excel_search")
            result = search_excel_rows(payload.folder_path, payload.query, payload.limit)
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/cross-excel/merge")
    def cross_excel_merge(payload: CrossExcelMergePayload):
        try:
            track_event("task_action.cross_excel_merge")
            result = merge_excel_files_by_headers(
                payload.folder_path,
                payload.headers,
                apply_format=payload.apply_format,
            )
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diff-excel/compare")
    async def diff_excel_compare(payload: DiffExcelComparePayload):
        track_event("diff.compare.start")
        try:
            path_a = Path(str(payload.path_a or "").strip())
            path_b = Path(str(payload.path_b or "").strip())
            if path_a.is_file() and path_b.is_file():
                track_event("diff.mode.file_to_file")
            elif path_a.is_dir() or path_b.is_dir():
                track_event("diff.mode.folder_to_folder")
            if payload.compare_mode == "field_match":
                track_event("diff.mode.field_match")
            else:
                track_event("diff.mode.position")
            def operation(progress_callback):
                try:
                    result = run_diff_excel_compare_to_cache(
                        payload.path_a,
                        payload.path_b,
                        compare_mode=payload.compare_mode,
                        reference_field=payload.reference_field,
                        compare_fields=payload.compare_fields,
                        include_unmatched=payload.include_unmatched,
                        ignore_case=False,
                        trim_whitespace=False,
                        progress_callback=progress_callback,
                    )
                    track_event("diff.compare.success")
                    return result
                except Exception:
                    track_event("diff.compare.fail")
                    raise

            return diff_task_service.start(operation).to_dict()
        except Exception as exc:
            track_event("diff.compare.fail")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/diff-excel/task/{task_id}")
    async def diff_excel_task(task_id: str):
        task = diff_task_service.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="未找到比对任务。")
        return task.to_dict()

    @app.get("/api/diff-excel/field-match-headers")
    def diff_excel_field_match_headers(path_a: str, path_b: str):
        try:
            return scan_diff_excel_field_match_headers(path_a, path_b)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diff-excel/export")
    def diff_excel_export(payload: DiffExcelExportPayload):
        try:
            return export_diff_excel_cached_records(
                payload.cache_file,
                payload.output_file,
                query=payload.query,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diff-excel/highlight")
    def diff_excel_highlight(payload: DiffExcelHighlightPayload):
        try:
            track_event("diff.highlight")
            changed_cells, workbook_count = apply_diff_excel_highlight_from_cache(
                payload.cache_file,
                str(payload.target or "A"),
                str(payload.color_hex or "#FFD966"),
                query=payload.query,
            )
            return {
                "ok": True,
                "changed_cells": changed_cells,
                "workbook_count": workbook_count,
                "target": str(payload.target or "A"),
                "color_hex": str(payload.color_hex or "#FFD966"),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/diff-excel/preview")
    def diff_excel_preview(cache_file: str, query: str = "", limit: int = 200, offset: int = 0):
        try:
            return read_diff_excel_cached_preview(cache_file, query=query, limit=limit, offset=offset)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diff-excel/open-cell")
    def diff_excel_open_cell(payload: DiffExcelOpenCellPayload):
        file_path = str(payload.file_path or "").strip()
        sheet_name = str(payload.sheet_name or "").strip()
        cell_address = str(payload.cell_address or "").strip()
        if not file_path or not sheet_name or not cell_address:
            raise HTTPException(status_code=400, detail="缺少定位所需的信息。")
        try:
            track_event("diff.jump")
            _open_excel_cell(file_path, sheet_name, cell_address)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "ok": True,
            "file_path": file_path,
            "sheet_name": sheet_name,
            "cell_address": cell_address,
        }

    @app.get("/api/dialog/select-review-file")
    def select_review_file():
        try:
            selected_paths = select_files_dialog(
                "选择待审校文件",
                [
                    ("支持的文件", "*.xlsx *.xlsm *.xls *.xlf *.xliff"),
                    ("Excel 文件", "*.xlsx *.xlsm *.xls"),
                    ("XLIFF 文件", "*.xlf *.xliff"),
                ],
                multiple=False,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        selected = selected_paths[0] if selected_paths else ""
        return {"file_path": selected or "", "cancelled": not bool(selected)}

    @app.get("/api/dialog/select-review-files")
    @app.post("/api/dialog/select-review-files")
    def select_review_files():
        try:
            selected = select_files_dialog(
                "选择待审校文件",
                [
                    ("支持的文件", "*.xlsx *.xlsm *.xls *.xlf *.xliff *.csv *.tsv *.txt *.md *.docx *.pptx *.pdf *.json *.xml"),
                    ("所有文件", "*.*"),
                ],
                multiple=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        paths = [str(path) for path in selected if str(path)]
        return {"file_paths": paths, "cancelled": not bool(paths)}

    @app.post("/api/dialog/select-preprocess-files")
    def select_preprocess_files():
        try:
            selected = select_files_dialog(
                "选择待提取文件",
                [
                    ("支持的文件", "*.xlsx *.xlsm *.xls *.csv *.xlf *.xliff"),
                    ("Excel 文件", "*.xlsx *.xlsm *.xls"),
                    ("CSV 文件", "*.csv"),
                    ("XLIFF 文件", "*.xlf *.xliff"),
                ],
                multiple=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        paths = [str(Path(path).resolve()) for path in selected if str(path)]
        return {"file_paths": paths, "cancelled": not bool(paths)}

    @app.post("/api/ai-review/file/open")
    def ai_review_open_file(payload: AIReviewOpenFilePayload):
        file_path = str(payload.file_path or "").strip()
        if not file_path:
            raise HTTPException(status_code=400, detail="请先选择文件。")
        try:
            _open_local_file(file_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "file_path": file_path}

    @app.post("/api/ai-review/file/load")
    def ai_review_load_file(payload: AIReviewOpenFilePayload):
        file_path = Path(str(payload.file_path or "").strip())
        if not str(file_path):
            raise HTTPException(status_code=400, detail="请先选择文件。")
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=400, detail="文件不存在。")
        filename = file_path.name
        try:
            stored_path = save_ai_review_upload_file(filename, file_path.read_bytes())
            file_type = detect_ai_review_file_type(stored_path)
            if file_type == "excel":
                metadata = read_ai_review_excel_headers(stored_path)
                batch_id = create_ai_review_batch(
                    original_filename=filename,
                    stored_path=stored_path,
                    file_type=file_type,
                    status="uploaded",
                    metadata={**metadata, "original_file_path": str(file_path)},
                )
                return _ai_review_excel_upload_response(
                    batch_id=batch_id,
                    filename=filename,
                    metadata=metadata,
                    original_file_path=str(file_path),
                )

            items = read_ai_review_xliff_items(stored_path, filename)
            language_metadata = read_ai_review_xliff_language_metadata(stored_path)
            batch_id = create_ai_review_batch(
                original_filename=filename,
                stored_path=stored_path,
                file_type=file_type,
                status="uploaded",
                metadata={**language_metadata, "original_file_path": str(file_path)},
            )
            replace_ai_review_batch_items(
                batch_id=batch_id,
                items=items,
                metadata_update={"preview_ready": True, **language_metadata, "original_file_path": str(file_path)},
            )
            return _ai_review_batch_response(batch_id, "XLIFF 读取完成")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="读取失败：{0}".format(exc)) from exc

    @app.post("/api/ai-review/file/upload")
    async def ai_review_upload_file(file: UploadFile = File(...)):
        filename = file.filename or "unknown"
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="上传文件为空。")
        try:
            stored_path = save_ai_review_upload_file(filename, data)
            file_type = detect_ai_review_file_type(stored_path)
            if file_type == "excel":
                metadata = read_ai_review_excel_headers(stored_path)
                batch_id = create_ai_review_batch(
                    original_filename=filename,
                    stored_path=stored_path,
                    file_type=file_type,
                    status="uploaded",
                    metadata=metadata,
                )
                return _ai_review_excel_upload_response(
                    batch_id=batch_id,
                    filename=filename,
                    metadata=metadata,
                )

            items = read_ai_review_xliff_items(stored_path, filename)
            language_metadata = read_ai_review_xliff_language_metadata(stored_path)
            batch_id = create_ai_review_batch(
                original_filename=filename,
                stored_path=stored_path,
                file_type=file_type,
                status="uploaded",
                metadata=language_metadata,
            )
            replace_ai_review_batch_items(
                batch_id=batch_id,
                items=items,
                metadata_update={"preview_ready": True, **language_metadata},
            )
            return _ai_review_batch_response(batch_id, "XLIFF 读取完成")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="读取失败：{0}".format(exc)) from exc

    @app.post("/api/ai-review/select-columns")
    async def ai_review_select_columns(payload: AIReviewSelectColumnsPayload):
        batch = get_ai_review_batch(payload.batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="读取批次不存在")
        if batch["file_type"] != "excel":
            raise HTTPException(status_code=400, detail="只有 Excel 文件需要选择列")
        try:
            items = read_ai_review_excel_items(
                Path(batch["stored_path"]),
                payload.source_column,
                payload.target_column,
                batch["original_filename"],
            )
            replace_ai_review_batch_items(
                batch_id=payload.batch_id,
                items=items,
                source_column=payload.source_column,
                target_column=payload.target_column,
                metadata_update={"preview_ready": True},
            )
            return _ai_review_batch_response(payload.batch_id, "Excel 读取完成")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="读取失败：{0}".format(exc)) from exc

    @app.post("/api/ai-review/select-excel-mapping")
    async def ai_review_select_excel_mapping(payload: AIReviewExcelMappingPayload):
        batch = get_ai_review_batch(payload.batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="读取批次不存在")
        if batch["file_type"] != "excel":
            raise HTTPException(status_code=400, detail="只有 Excel 文件需要配置列映射")
        try:
            items = read_ai_review_excel_items_by_mapping(
                Path(batch["stored_path"]),
                payload.mapping,
                batch["original_filename"],
            )
            replace_ai_review_batch_items(
                batch_id=payload.batch_id,
                items=items,
                source_column=None,
                target_column=None,
                metadata_update={
                    "preview_ready": True,
                    "excel_mapping": payload.mapping,
                    "source_language": str(payload.mapping.get("source_language") or ""),
                    "target_language": str(payload.mapping.get("target_language") or ""),
                },
            )
            return _ai_review_batch_response(payload.batch_id, "Excel 列映射读取完成")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="读取失败：{0}".format(exc)) from exc

    @app.get("/api/ai-review/ai-settings")
    async def ai_review_ai_settings():
        settings = get_ai_review_shared_ai_settings()
        return {
            "provider": settings.get("provider", "DeepSeek"),
            "has_api_key": bool(settings.get("api_key")),
            "selected_model": settings.get("selected_model", ""),
            "max_chars_per_request": settings.get("max_chars_per_request", 3000),
            "enable_thinking": bool(settings.get("enable_thinking", False)),
        }

    @app.post("/api/ai-review/ai/test")
    def ai_review_test_model():
        settings = get_ai_review_shared_ai_settings()
        api_key = str(settings.get("api_key", "") or "")
        model = str(settings.get("selected_model", "") or "")
        if not api_key:
            raise HTTPException(status_code=400, detail="请先在模型设置中填写 API Key。")
        if not model:
            raise HTTPException(status_code=400, detail="请先在模型设置中选择模型。")
        try:
            content = test_ai_review_chat(
                api_key,
                model,
                enable_thinking=bool(settings.get("enable_thinking", False)),
            )
        except SharedProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "测试 OK", "model": model, "response": content}

    @app.get("/api/ai-review/excel-mapping-presets")
    async def ai_review_excel_mapping_presets():
        return {"presets": list_excel_mapping_presets()}

    @app.get("/api/ai-review/excel-mapping-presets/{preset_id}")
    async def ai_review_excel_mapping_preset(preset_id: str):
        try:
            return {"preset": get_excel_mapping_preset(preset_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/ai-review/excel-mapping-presets")
    async def ai_review_save_excel_mapping_preset(payload: AIReviewExcelMappingPresetSavePayload):
        try:
            preset = save_excel_mapping_preset(payload.name, payload.mapping, payload.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "Excel 映射模板已保存", "preset": preset}

    @app.delete("/api/ai-review/excel-mapping-presets/{preset_id}")
    async def ai_review_delete_excel_mapping_preset(preset_id: str):
        try:
            delete_excel_mapping_preset(preset_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": True, "message": "Excel 映射模板已删除"}

    @app.get("/api/ai-review/prompt-templates")
    async def ai_review_prompt_templates():
        return {"templates": list_ai_review_prompt_templates()}

    @app.get("/api/ai-review/prompt-templates/{template_id}")
    async def ai_review_prompt_template(template_id: str):
        try:
            return {"template": get_ai_review_prompt_template(template_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/ai-review/prompt-templates")
    async def ai_review_save_prompt_template(payload: AIReviewPromptTemplateSavePayload):
        try:
            template = save_ai_review_prompt_template(
                template_id=payload.id,
                name=payload.name.strip() or "未命名模板",
                system_prompt=payload.system_prompt,
                user_prompt=payload.user_prompt,
                forbidden_words_text=payload.forbidden_words_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "提示词模板已保存", "template": template}

    @app.post("/api/ai-review/prompt-templates/reset-default")
    async def ai_review_reset_prompt_template():
        template = reset_ai_review_prompt_template()
        return {"ok": True, "message": "默认提示词已恢复", "template": template}

    @app.delete("/api/ai-review/prompt-templates/{template_id}")
    async def ai_review_delete_prompt_template(template_id: str):
        try:
            fallback_template = delete_ai_review_prompt_template(template_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "提示词模板已删除", "fallback_template": fallback_template}

    @app.get("/api/ai-review/directional-templates")
    async def ai_review_directional_templates():
        return {"templates": list_directional_templates()}

    @app.get("/api/ai-review/directional-templates/{template_id}")
    async def ai_review_directional_template(template_id: str):
        try:
            return {"template": get_directional_template(template_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/ai-review/directional-templates")
    async def ai_review_save_directional_template(payload: AIReviewDirectionalTemplateSavePayload):
        try:
            template = save_directional_template(
                payload.id,
                payload.name.strip() or "未命名定向模板",
                payload.items,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "定向审校模板已保存", "template": template}

    @app.delete("/api/ai-review/directional-templates/{template_id}")
    async def ai_review_delete_directional_template(template_id: str):
        try:
            delete_directional_template(template_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "定向审校模板已删除"}

    @app.get("/api/ai-review/forbidden-templates")
    async def ai_review_forbidden_templates():
        return {"templates": list_forbidden_templates()}

    @app.get("/api/ai-review/forbidden-templates/{template_id}")
    async def ai_review_forbidden_template(template_id: str):
        try:
            return {"template": get_forbidden_template(template_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/ai-review/forbidden-templates")
    async def ai_review_save_forbidden_template(payload: AIReviewForbiddenTemplateSavePayload):
        try:
            template = save_forbidden_template(
                payload.id,
                payload.name.strip() or "未命名禁用词模板",
                payload.words_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "禁用词模板已保存", "template": template}

    @app.delete("/api/ai-review/forbidden-templates/{template_id}")
    async def ai_review_delete_forbidden_template(template_id: str):
        try:
            delete_forbidden_template(template_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "message": "禁用词模板已删除"}

    @app.post("/api/ai-review/start")
    async def ai_review_start(payload: AIReviewStartPayload):
        try:
            task_id = create_review_task(
                payload.batch_id,
                payload.prompt_template_id,
                payload.source_language.strip(),
                payload.target_language.strip(),
                payload.mode,
                payload.directional_template_id,
                payload.enable_ai_review,
                payload.enable_forbidden_check,
                payload.forbidden_template_id,
            )
        except (ReviewTaskError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        task = get_review_task(task_id)
        return {"ok": True, "message": "审校任务已启动", "task": task}

    @app.get("/api/ai-review/tasks/{task_id}")
    async def ai_review_task(task_id: str):
        task = get_review_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="审校任务不存在")
        return {"task": task, "results": get_review_results(task_id, limit=20)}

    @app.get("/api/ai-review/tasks/{task_id}/logs")
    async def ai_review_task_logs(task_id: str, after_id: int = 0):
        if not get_review_task(task_id):
            raise HTTPException(status_code=404, detail="审校任务不存在")
        return {"logs": get_review_logs(task_id, after_id)}

    @app.get("/api/ai-review/tasks/{task_id}/issue-results")
    async def ai_review_task_issue_results(task_id: str):
        task = get_review_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="审校任务不存在")
        return {"task": task, "results": get_review_issue_results(task_id)}

    @app.get("/api/ai-review/tasks/{task_id}/followup/{result_id}")
    async def ai_review_followup_messages(task_id: str, result_id: str):
        try:
            init_ai_review_db()
            if not get_review_task(task_id):
                raise HTTPException(status_code=404, detail="审校任务不存在")
            result = get_review_followup_messages(task_id, result_id)
            track_event("feature_used.ai_review_followup_open")
            return result
        except HTTPException:
            raise
        except ReviewTaskError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            print("[AI_REVIEW][ERROR][{0}] 追问读取失败：{1}\n{2}".format(task_id, exc, traceback.format_exc()), flush=True)
            raise HTTPException(status_code=500, detail="追问读取失败：{0}".format(exc)) from exc

    @app.post("/api/ai-review/tasks/{task_id}/followup/{result_id}")
    async def ai_review_followup_send(task_id: str, result_id: str, payload: AIReviewFollowupPayload):
        try:
            init_ai_review_db()
            if not get_review_task(task_id):
                raise HTTPException(status_code=404, detail="审校任务不存在")
            track_event("feature_used.ai_review_followup_send")
            result = await run_in_threadpool(send_review_followup_message, task_id, result_id, payload.message)
            track_event("feature_success.ai_review_followup_send")
            return result
        except HTTPException:
            raise
        except ReviewTaskError as exc:
            track_event("feature_fail.ai_review_followup_send")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            track_event("feature_fail.ai_review_followup_send")
            print("[AI_REVIEW][ERROR][{0}] 追问发送失败：{1}\n{2}".format(task_id, exc, traceback.format_exc()), flush=True)
            raise HTTPException(status_code=500, detail="追问发送失败：{0}".format(exc)) from exc

    @app.post("/api/ai-review/outputs/open-folder")
    def ai_review_open_outputs():
        try:
            open_ai_review_directory(AI_REVIEW_OUTPUTS_DIR)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="打开目录失败：{0}".format(exc)) from exc
        return {"ok": True, "message": "已打开结果目录", "path": str(AI_REVIEW_OUTPUTS_DIR)}

    @app.post("/api/ai-review/outputs/open-file")
    def ai_review_open_output_file(payload: AIReviewOpenFilePayload):
        file_path = str(payload.file_path or "").strip()
        if not file_path:
            raise HTTPException(status_code=400, detail="暂无可打开的结果文件。")
        try:
            _open_local_file(file_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="打开文件失败：{0}".format(exc)) from exc
        return {"ok": True, "file_path": file_path}

    @app.post("/api/tasks/start")
    async def start_task(payload: StartTaskPayload):
        settings = task_facade.load_settings()
        task_input = None
        if not payload.resume:
            explicit_files = [Path(item).expanduser().resolve() for item in payload.input_files if str(item).strip()]
            if explicit_files:
                missing_files = [str(path) for path in explicit_files if not path.is_file()]
                if missing_files:
                    raise HTTPException(status_code=400, detail="以下输入文件不存在：{0}".format("、".join(missing_files)))
                unsupported_files = [path.name for path in explicit_files if path.suffix.lower() not in {".xlsx", ".xlsm", ".xls", ".csv", ".xlf", ".xliff"}]
                if unsupported_files:
                    raise HTTPException(status_code=400, detail="包含不支持的文件：{0}".format("、".join(unsupported_files)))
                for path in explicit_files:
                    if path.suffix.lower() not in {".xlsx", ".xlsm", ".xls", ".csv"}:
                        continue
                    mapping = payload.file_mappings.get(str(path), payload.file_mappings.get(path.name, {}))
                    if not any(values for values in mapping.values() if values):
                        raise HTTPException(status_code=400, detail="请先配置文件映射：{0}".format(path.name))
            elif not str(payload.folder_path or "").strip():
                raise HTTPException(status_code=400, detail="请先选择文件或文件夹。")
            task_input = TaskInput(
                folder_path=payload.folder_path,
                header_name=payload.header_name,
                source_language=payload.source_language,
                single_item_char_limit=payload.single_item_char_limit,
                batch_request_char_limit=payload.batch_request_char_limit,
                file_type=payload.file_type,
                export_review_sheet=payload.export_review_sheet,
                extraction_mode=payload.extraction_mode,
                memoq_term_base_ids=payload.memoq_term_base_ids,
                column_selections=payload.column_selections,
                input_files=payload.input_files,
                file_mappings=payload.file_mappings,
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
    def results_summary(output_file: Optional[str] = None):
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
    def open_result_folder(output_file: str):
        path = Path(output_file)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Output file does not exist.")
        try:
            open_file_location(path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "folder": str(path.parent)}

    @app.post("/api/results/open-file")
    def open_result_file(output_file: str):
        path = Path(output_file)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Output file does not exist.")
        try:
            open_file_directly(path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True, "file": str(path)}

    return app


app = create_app()


def settings_to_json_for_debug() -> str:
    return json.dumps(build_default_settings().to_dict(), ensure_ascii=False, indent=2)


def open_file_location(path: Path) -> None:
    open_path_folder(path.parent)


def open_file_directly(path: Path) -> None:
    open_any_path(path)


_NATIVE_DIALOG_LOCK = threading.Lock()


def select_folder_dialog() -> str:
    if not _NATIVE_DIALOG_LOCK.acquire(blocking=False):
        raise RuntimeError("已有文件选择窗口打开，请先完成或关闭该窗口。")
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        _NATIVE_DIALOG_LOCK.release()
        raise RuntimeError("当前环境不支持原生文件夹选择窗口。") from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="选择待处理文件夹", mustexist=True)
    finally:
        if root is not None:
            root.destroy()
        _NATIVE_DIALOG_LOCK.release()
    return str(selected or "")


def select_files_dialog(
    title: str,
    filetypes: list[tuple[str, str]],
    *,
    multiple: bool = True,
) -> list[str]:
    if not _NATIVE_DIALOG_LOCK.acquire(blocking=False):
        raise RuntimeError("已有文件选择窗口打开，请先完成或关闭该窗口。")
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        _NATIVE_DIALOG_LOCK.release()
        raise RuntimeError("当前环境不支持原生文件选择窗口。") from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if multiple:
            selected = filedialog.askopenfilenames(title=title, filetypes=filetypes)
            return [str(path) for path in selected if str(path)]
        selected = filedialog.askopenfilename(title=title, filetypes=filetypes)
        return [str(selected)] if selected else []
    finally:
        if root is not None:
            root.destroy()
        _NATIVE_DIALOG_LOCK.release()


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>译禾工具合集</title>
  <script>
    try {
      if (localStorage.getItem("yeehe-ui-theme") === "light") {
        document.documentElement.classList.add("light-theme");
      }
    } catch (_) {}
  </script>
  <link rel="stylesheet" href="/assets/app.css" />
</head>
<body>
  <a class="skip-link" href="#mainContent">跳到主内容</a>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <img class="brand-mark" src="/assets/logo.png" alt="译禾工具合集" />
        <div class="brand-copy">
          <span class="brand-version">v__APP_VERSION__</span>
          <strong>译禾工具合集</strong>
          <small>作者：王子京</small>
        </div>
      </div>
      <nav class="sidebar-nav">
        <button class="nav-link nav-link-top active" data-page-target="toolGuidePage">工具说明</button>
        <button class="nav-link nav-link-top" data-page-target="modelSettingsPage">设置</button>

        <details class="nav-accordion" data-accordion-key="text-preprocess">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">文本预处理工具</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub" data-page-target="overviewPage">总览</button>
            <button class="nav-link nav-link-sub" data-page-target="modelStageSettingsPage">模型阶段设置</button>
            <button class="nav-link nav-link-sub" data-page-target="nontransSettingsPage">非译元素设置</button>
            <button class="nav-link nav-link-sub" data-page-target="promptSettingsPage">提示词设置</button>
          </div>
        </details>

        <button class="nav-link nav-link-top" data-page-target="diffExcelPage">Diff 工具</button>

        <details class="nav-accordion" data-accordion-key="ai-review-tool">
          <summary class="nav-accordion-summary">
            <span class="nav-group-title">AI 审校工具</span>
          </summary>
          <div class="nav-submenu">
            <button class="nav-link nav-link-sub" data-page-target="aiReviewTaskPage">审校任务</button>
            <button class="nav-link nav-link-sub" data-page-target="aiReviewSettingsPage">审校设置</button>
          </div>
        </details>

        <button class="nav-link nav-link-top" data-page-target="crossExcelPage">跨Excel搜索与合并</button>
        <button class="nav-link nav-link-top" data-page-target="feishuTransferPage">飞书文件传输</button>
      </nav>
      <div class="sidebar-actions-panel">
        <button id="themeToggleButton" class="theme-toggle-button" type="button" aria-pressed="false" title="切换主题">
          <span class="theme-toggle-icon" aria-hidden="true">☀</span>
          <span id="themeToggleLabel">浅色模式</span>
        </button>
        <button id="feedbackEntryButton" class="feedback-entry-button" type="button">我要反馈</button>
      </div>
    </aside>

    <main id="mainContent" class="content" tabindex="-1">
      <header class="hero">
        <div>
          <div class="hero-context"><span class="eyebrow">本地工作台</span><span class="hero-context-divider"></span><span>Localization &amp; Text Tooling</span></div>
          <h1 id="heroTitle">工具说明</h1>
          <p id="heroLede" class="lede">先了解每个工具能做什么，再开始任务。</p>
          <button id="updateNoticeButton" class="notice-button update-notice-button" type="button" hidden>
            <span class="notice-dot"></span>
            <span>发现新版本</span>
          </button>
          <button id="pendingRuleNoticeButton" class="notice-button" type="button" hidden>
            <span class="notice-dot"></span>
            <span>发现新的非译规则</span>
          </button>
        </div>
      </header>

      <section id="toolGuidePage" class="page-section active">
        <div class="inline-notice" role="note"><span class="inline-notice-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8.5"></circle><path d="M12 10.5v5M12 7.5h.01"></path></svg></span><span><strong>隐私优先</strong>常规功能仅统计匿名触发次数；AI 审校监控会额外记录 PM 归属、文件名和任务运行信息，不上传路径、原译文或明文密钥。</span></div>
        <div class="tool-guide-grid">
          <button class="tool-guide-card tool-guide-card-preprocess" type="button" data-tool-guide="textPreprocess" aria-label="打开文本预处理工具说明">
            <span class="tool-guide-card-top"><span class="tool-guide-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6.5 3.5h7l4 4v13h-11z"></path><path d="M13.5 3.5v4h4M8.5 12h7M8.5 15.5h7"></path></svg></span><span class="tool-guide-badge">批量处理</span></span>
            <span class="tool-guide-card-copy"><strong>文本预处理</strong><small>从本地表格中提取术语、非译元素和可复用规则。</small></span>
            <span class="tool-guide-card-footer"><span>目录级工作流</span><span class="tool-guide-arrow" aria-hidden="true">→</span></span>
          </button>
          <button class="tool-guide-card tool-guide-card-diff" type="button" data-tool-guide="diffExcel" aria-label="打开 Diff 工具说明">
            <span class="tool-guide-card-top"><span class="tool-guide-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 4v12M17 8v12M4 7l3-3 3 3M14 17l3 3 3-3"></path><path d="M9 7h5M10 17h4"></path></svg></span><span class="tool-guide-badge">Excel</span></span>
            <span class="tool-guide-card-copy"><strong>Diff 工具</strong><small>比较文件或目录差异，快速定位改动。</small></span>
            <span class="tool-guide-card-footer"><span>差异预览与导出</span><span class="tool-guide-arrow" aria-hidden="true">→</span></span>
          </button>
          <button class="tool-guide-card tool-guide-card-review" type="button" data-tool-guide="aiReview" aria-label="打开 AI 审校工具说明">
            <span class="tool-guide-card-top"><span class="tool-guide-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3.5 13.7 8l4.8 1.6-4.2 2.6.1 5-4.4-2.7-4.2 2.7.1-5-4.2-2.6L6.3 8z"></path><path d="m17.5 17.5 1 1 2-2"></path></svg></span><span class="tool-guide-badge tool-guide-badge-ai">Agent</span></span>
            <span class="tool-guide-card-copy"><strong>AI 审校</strong><small>让 Workspace Agent 识别结构，再按目标语言独立审校。</small></span>
            <span class="tool-guide-card-footer"><span>流式会话工作台</span><span class="tool-guide-arrow" aria-hidden="true">→</span></span>
          </button>
          <button class="tool-guide-card tool-guide-card-excel" type="button" data-tool-guide="crossExcel" aria-label="打开跨 Excel 搜索与合并工具说明">
            <span class="tool-guide-card-top"><span class="tool-guide-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="4" width="16" height="16" rx="1.5"></rect><path d="M4 10h16M10 4v16M14 10v10"></path></svg></span><span class="tool-guide-badge">多文件</span></span>
            <span class="tool-guide-card-copy"><strong>跨 Excel</strong><small>跨文件搜索和按表头合并。</small></span>
            <span class="tool-guide-card-footer"><span>搜索与合并</span><span class="tool-guide-arrow" aria-hidden="true">→</span></span>
          </button>
          <button class="tool-guide-card tool-guide-card-transfer" type="button" data-tool-guide="feishuTransfer" aria-label="打开飞书文件传输工具说明">
            <span class="tool-guide-card-top"><span class="tool-guide-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M6 3.5h8l4 4V14M14 3.5v4h4M6 3.5V20h5M13 17h8m-3-3 3 3-3 3"></path></svg></span></span>
            <span class="tool-guide-card-copy"><strong>飞书文件传输</strong><small>本机直传文件到飞书，按群发送附件或群文件文档链接。</small></span>
            <span class="tool-guide-card-footer"><span>多文件上传与大文件分享</span><span class="tool-guide-arrow" aria-hidden="true">→</span></span>
          </button>
        </div>
      </section>

      <section id="overviewPage" class="page-section">
        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>新建任务</h3>
              <p>选择文件或文件夹，完成列映射后开始提取。</p>
            </div>
            <div class="preprocess-task-grid">
              <div class="preprocess-file-pane">
                <label>文件<span class="secret-field"><input id="folderPath" placeholder="选择文件或文件夹" readonly /><button id="addPreprocessFilesButton" class="mini-button" type="button">选择文件</button><button id="chooseFolderButton" class="mini-button" type="button">选择文件夹</button></span></label>
                <div id="preprocessFileSummary" class="preprocess-file-summary" aria-live="polite">尚未添加文件</div>
                <div id="preprocessFileList" class="preprocess-file-list" aria-live="polite"><span class="hint">尚未添加文件</span></div>
              </div>
              <div class="preprocess-settings-pane">
                <label>源语言<span class="secret-field"><button id="preprocessSourceLanguageChip" class="secondary" type="button">源语言：自动检测</button><select id="sourceLanguage" class="visually-hidden"><option value="auto">自动检测</option><option value="zho-CN">简体中文</option><option value="zho-TW">繁体中文</option><option value="eng">英语</option><option value="jpn">日语</option><option value="kor">韩语</option><option value="fra">法语</option><option value="deu">德语</option><option value="spa">西班牙语</option><option value="por">葡萄牙语</option><option value="ita">意大利语</option><option value="rus">俄语</option></select></span></label>
                <label>运行模式<select id="extractionMode"><option value="terms">提取术语</option><option value="nontrans_only">仅提取非译元素</option></select></label>
                <div class="actions"><button id="preprocessTermBaseChip" class="secondary" type="button">术语表</button><button id="startButton" class="primary" disabled>开始提取</button></div>
              </div>
            </div>
            <div id="preprocessTermBasePopover" class="review-term-base-popover hidden" role="menu" aria-label="选择术语库">
              <div class="review-term-base-search"><input id="preprocessTermBaseSearch" type="search" placeholder="搜索 memoQ 术语库" autocomplete="off" /></div>
              <div id="preprocessTermBaseOptions" class="review-term-base-options"></div>
            </div>
            <div id="preprocessSourceLanguagePopover" class="review-term-base-popover hidden" role="dialog" aria-label="选择源语言">
              <div class="review-term-base-search"><input id="preprocessSourceLanguageSearch" type="search" placeholder="搜索源语言" autocomplete="off" /></div>
              <div id="preprocessSourceLanguageOptions" class="review-term-base-options"></div>
            </div>
            <div id="preprocessTaskHint" class="inline-task-hint" role="status" aria-live="polite">请选择文件或文件夹。</div>
          </section>

          <section class="card preprocess-progress-card">
            <div class="card-title">
              <div>
                <h3>任务进度</h3>
                <p id="preprocessProgressMessage">等待开始任务。</p>
              </div>
              <span id="preprocessProgressState" class="preprocess-status-pill">空闲</span>
            </div>
            <div class="preprocess-progress-overview">
              <div class="preprocess-progress-total">
                <span>已完成</span>
                <strong id="progressText">0 / 0</strong>
              </div>
              <div class="preprocess-progress-stage">
                <span>当前阶段</span>
                <strong id="preprocessProgressStage">未启动</strong>
              </div>
              <span id="preprocessProgressPercent" class="preprocess-progress-percent">未开始</span>
            </div>
            <div class="progress"><span id="progressBar"></span></div>
            <div class="preprocess-progress-metrics">
              <div><span>批次</span><strong id="batchText">0 / 0</strong></div>
              <div><span>成功</span><strong id="successText">0</strong></div>
              <div><span>失败</span><strong id="failureText">0</strong></div>
              <div><span>重试</span><strong id="retryText">0</strong></div>
              <div><span>并发</span><strong id="concurrencyText">0</strong></div>
              <div><span>AI 请求</span><strong id="preprocessLlmRequests">0</strong></div>
            </div>
            <section class="preprocess-events" aria-label="最近任务事件">
              <div class="preprocess-events-head"><strong>最近事件</strong><span>实时更新</span></div>
              <div id="preprocessRecentEvents" class="preprocess-events-list"><span class="preprocess-events-empty">暂无任务事件</span></div>
            </section>
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
              <button id="downloadResultButton" class="secondary" disabled>打开结果文件</button>
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
            <label class="check"><input id="disableSystemProxy" type="checkbox" checked /> 禁用系统代理</label>
          </div>
          <div class="actions">
            <span id="modelConnectionHint" class="hint"></span>
          </div>
        </section>
        <section class="card">
          <div class="card-title"><h3>memoQ 账号</h3><p>绑定后可在 AI 审校中搜索并多选 memoQ 术语库；凭证仅加密保存在本机。</p></div>
          <div id="memoqCredentialFields" class="grid two">
            <label>用户名<input id="memoqUsername" autocomplete="username" /></label>
            <label>密码<input id="memoqPassword" type="password" autocomplete="current-password" /></label>
          </div>
          <div class="actions"><button id="bindMemoQButton" class="primary" type="button">绑定 memoQ 账号</button><button id="unbindMemoQButton" class="secondary danger-text" type="button" hidden>解绑</button><span id="memoqAccountStatus" class="hint">未绑定</span></div>
        </section>
      </section>

      <section id="modelStageSettingsPage" class="page-section">
        <div class="stage-grid">
          <section class="card compact-card">
            <div class="card-title">
              <h3>非译元素阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="nontransLimit" type="number" min="200" value="5000" /></label>
            <label>思考强度（已开启）<select id="nontransReasoningEffort"><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          </section>
          <section class="card compact-card">
            <div class="card-title">
              <h3>术语召回阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="recallLimit" type="number" min="200" value="5000" /></label>
            <label>思考强度（已开启）<select id="recallReasoningEffort"><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          </section>
          <section class="card compact-card">
            <div class="card-title">
              <h3>术语校验阶段</h3>
              <p></p>
            </div>
            <label>单次处理长度<input id="reviewLimit" type="number" min="200" value="5000" /></label>
            <label>上下文长度<input id="reviewContextLimit" type="number" min="50" max="2000" value="220" /></label>
            <label>思考强度（已开启）<select id="termReviewReasoningEffort"><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          </section>
        </div>

        <div class="sticky-actions">
          <button id="saveSettingsButton" class="primary">保存设置</button>
          <span id="saveHint" class="hint"></span>
        </div>
      </section>

      <section id="nontransSettingsPage" class="page-section">
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

      <section id="runDetailsPage" class="page-section" data-internal-view="true" aria-hidden="true">
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

      <section id="resultsPage" class="page-section" data-internal-view="true" aria-hidden="true">
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

      __TRANSFER_PAGE__
      <section id="crossExcelPage" class="page-section">
        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>搜索范围</h3>
              <p>选择目录后可扫描全部 Excel 文件并加载表头。</p>
            </div>
            <div class="grid two">
              <label>输入目录
                <span class="secret-field">
                  <input id="crossExcelFolderPath" placeholder="D:\\项目\\Excel目录" />
                  <button id="chooseCrossExcelFolderButton" class="mini-button" type="button">选择文件夹</button>
                </span>
              </label>
              <div class="cross-summary-box">
                <span>文件数</span>
                <strong id="crossExcelFileCount">0</strong>
                <small id="crossExcelScanHint">请先选择目录并扫描。</small>
              </div>
            </div>
            <div class="actions">
              <button id="scanCrossExcelButton" class="secondary">扫描目录</button>
            </div>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>全局搜索</h3>
              <p>输入关键词后，再预览命中的整行内容。</p>
            </div>
            <div class="grid two">
              <label>搜索内容
                <span class="search-inline-field">
                  <input id="crossExcelQuery" placeholder="输入要搜索的文字" />
                  <button id="searchCrossExcelButton" class="primary" type="button">搜索</button>
                </span>
              </label>
              <label>结果上限<input id="crossExcelLimit" type="number" min="1" max="2000" value="300" /></label>
            </div>
            <div class="actions action-row-compact">
              <span id="crossExcelSearchHint" class="hint"></span>
            </div>
            <div class="summary-line">
              <span>命中结果 <strong id="crossExcelMatchCount">0</strong></span>
              <span>扫描行数 <strong id="crossExcelScannedRows">0</strong></span>
              <span>状态 <strong id="crossExcelTruncatedLabel">未搜索</strong></span>
            </div>
          </section>
        </div>

        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>搜索预览</h3>
              <p>按整行展示。点击单元格即可复制内容。</p>
            </div>
            <div id="crossExcelSearchResults" class="cross-search-results">
              <div class="cross-empty-state">执行搜索后，这里会显示命中的行。</div>
            </div>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>按表头合并</h3>
              <p>勾选需要保留的表头，再导出合并结果。</p>
            </div>
            <div class="actions">
              <button id="selectAllCrossHeadersButton" class="secondary" type="button">全选</button>
              <button id="clearCrossHeadersButton" class="secondary" type="button">清空</button>
              <button id="mergeCrossExcelButton" class="primary" type="button">合并</button>
            </div>
            <div id="crossExcelHeaderList" class="cross-header-list">
              <div class="cross-empty-state">扫描目录后会在这里显示全部表头。</div>
            </div>
            <div class="actions action-row-compact cross-merge-actions">
              <label class="check"><input id="crossExcelApplyFormat" type="checkbox" checked /> 保留单元格格式</label>
            </div>
            <div class="result-file">
              <span>合并结果</span>
              <strong id="crossExcelOutputFile">暂无输出</strong>
              <small id="crossExcelOutputHint">合并结果会保存到工具 output 目录。</small>
            </div>
            <div class="actions">
              <button id="openCrossExcelOutputFileButton" class="secondary" type="button" disabled>打开文件</button>
              <button id="openCrossExcelOutputButton" class="secondary" type="button" disabled>打开输出目录</button>
            </div>
          </section>
        </div>
      </section>

      <section id="diffExcelPage" class="page-section">
        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>比对范围</h3>
              <p>支持文件对文件，也支持目录对目录。</p>
            </div>
            <div class="grid two">
              <label>路径 A
                <span class="secret-field">
                  <input id="diffPathA" placeholder="D:\\项目\\旧版本 或旧文件.xlsx" />
                  <button id="chooseDiffPathAButton" class="mini-button" type="button">选择文件夹</button>
                  <button id="chooseDiffFileAButton" class="mini-button" type="button">选择文件</button>
                </span>
              </label>
              <label>路径 B
                <span class="secret-field">
                  <input id="diffPathB" placeholder="D:\\项目\\新版本 或新文件.xlsx" />
                  <button id="chooseDiffPathBButton" class="mini-button" type="button">选择文件夹</button>
                  <button id="chooseDiffFileBButton" class="mini-button" type="button">选择文件</button>
                </span>
              </label>
            </div>
            <div class="actions">
              <button id="startDiffExcelButton" class="primary" type="button">开始比对</button>
              <button id="clearDiffExcelButton" class="secondary" type="button">清空结果</button>
              <div class="diff-mode-actions">
                <select id="diffCompareMode" class="diff-mode-select" aria-label="比对方式">
                  <option value="position">按位置比对</option>
                  <option value="field_match">按字段匹配</option>
                </select>
                <button id="openDiffFieldSettingsButton" class="secondary icon-button" type="button" title="设置字段匹配" aria-label="设置字段匹配" hidden>⚙</button>
              </div>
              <span id="diffExcelHint" class="hint"></span>
            </div>
          </section>

          <section class="card">
            <div class="card-title">
              <h3>当前状态</h3>
              <p>比对完成后可直接导出结果或批量标记。</p>
            </div>
            <div class="metrics hero-metrics">
              <div><span>模式</span><strong id="diffModeLabel">未开始</strong></div>
              <div><span>A 文件数</span><strong id="diffFilesInA">0</strong></div>
              <div><span>B 文件数</span><strong id="diffFilesInB">0</strong></div>
              <div><span>配对数</span><strong id="diffMatchedPairs">0</strong></div>
              <div><span>差异数</span><strong id="diffTotalCount">0</strong></div>
              <div><span>预览数</span><strong id="diffVisibleCount">0</strong></div>
            </div>
            <div class="result-file">
              <span>导出文件</span>
              <strong id="diffOutputFile">暂无输出</strong>
              <small id="diffOutputHint">比对完成后可导出差异结果。</small>
            </div>
            <div class="actions">
              <button id="exportDiffExcelButton" class="secondary" type="button" disabled>导出结果</button>
              <button id="openDiffOutputFileButton" class="secondary" type="button" disabled>打开文件</button>
              <button id="openDiffOutputFolderButton" class="secondary" type="button" disabled>打开输出目录</button>
            </div>
          </section>
        </div>

        <div class="grid dashboard-grid">
          <section class="card">
            <div class="card-title">
              <h3>批量标记</h3>
              <p>把当前预览结果批量标记回原表。</p>
            </div>
            <div class="grid two">
              <label>标记到
                <select id="diffMarkTarget">
                  <option value="A">文件 A</option>
                  <option value="B">文件 B</option>
                </select>
              </label>
              <div class="color-picker-block">
                <label>颜色
                  <input id="diffHighlightColor" type="color" value="#FFD966" />
                </label>
                <div class="preset-color-row" aria-label="常用标记颜色">
                  <button type="button" class="preset-color-btn" data-color="#F44336" title="红色"></button>
                  <button type="button" class="preset-color-btn" data-color="#FF9800" title="橙色"></button>
                  <button type="button" class="preset-color-btn" data-color="#FFEB3B" title="黄色"></button>
                  <button type="button" class="preset-color-btn" data-color="#4CAF50" title="绿色"></button>
                  <button type="button" class="preset-color-btn" data-color="#2196F3" title="蓝色"></button>
                  <button type="button" class="preset-color-btn" data-color="#9C27B0" title="紫色"></button>
                </div>
              </div>
            </div>
            <div class="actions">
              <button id="highlightDiffExcelButton" class="primary" type="button" disabled>标记差异结果</button>
              <span id="diffHighlightHint" class="hint"></span>
            </div>
          </section>
        </div>

        <section class="card">
          <div class="card-title">
            <h3>差异预览</h3>
          </div>
          <div class="pattern-table-wrap diff-preview-table-wrap">
            <table class="pattern-table diff-preview-table">
              <colgroup>
                <col class="diff-preview-file-column" />
                <col class="diff-preview-file-column" />
                <col class="diff-preview-sheet-column" />
                <col class="diff-preview-location-column" />
                <col class="diff-preview-comparison-column" />
              </colgroup>
              <thead>
                <tr id="diffExcelHead">
                  <th>文件 A</th>
                  <th>文件 B</th>
                  <th>Sheet</th>
                  <th>单元格</th>
                  <th>差异对照</th>
                </tr>
              </thead>
              <tbody id="diffExcelBody">
                <tr><td colspan="5" class="empty-cell">暂无差异结果</td></tr>
              </tbody>
            </table>
          </div>
          <div class="actions action-row-compact">
            <button id="diffPreviewPreviousButton" class="secondary" type="button" disabled>上一页</button>
            <span id="diffPreviewPageLabel" class="hint">暂无结果</span>
            <button id="diffPreviewNextButton" class="secondary" type="button" disabled>下一页</button>
          </div>
        </section>
      </section>

      <div id="diffFieldSettingsOverlay" class="modal-overlay" hidden>
        <section class="modal-card diff-field-settings-modal" role="dialog" aria-modal="true" aria-labelledby="diffFieldSettingsTitle">
          <header class="modal-header">
            <div>
              <h3 id="diffFieldSettingsTitle">字段匹配设置</h3>
              <p id="diffFieldSettingsSummary">选择用于匹配数据行和比较内容的表头。</p>
            </div>
            <button id="closeDiffFieldSettingsButton" class="modal-close" type="button" aria-label="关闭">×</button>
          </header>
          <div class="diff-field-settings-grid">
            <label>参考字段
              <select id="diffReferenceField"><option value="">请选择参考字段</option></select>
            </label>
            <div class="diff-header-presence">
              <span>文件 A 表头 <strong id="diffHeadersACount">0</strong></span>
              <span>文件 B 表头 <strong id="diffHeadersBCount">0</strong></span>
              <span>共同表头 <strong id="diffHeadersCommonCount">0</strong></span>
            </div>
          </div>
          <div class="diff-compare-fields-block">
            <div class="field-block-head">
              <strong>比对字段</strong>
              <span>仅显示两侧均存在的表头</span>
            </div>
            <div id="diffCompareFieldList" class="diff-compare-field-list"></div>
          </div>
          <label class="check-line diff-unmatched-line">
            <input id="diffIncludeUnmatched" type="checkbox" />
            <span>标记未匹配行</span>
            <span class="info-tip" tabindex="0" aria-label="说明">i<span class="info-tip-content">开启后，其中一侧存在另一侧没有的参考值时也会列为差异；批量标记时会标记该侧对应的整行。关闭则会忽略该参考值。</span></span>
          </label>
          <div class="modal-footer">
            <span id="diffFieldSettingsHint" class="hint"></span>
            <div class="modal-footer-actions">
              <button id="cancelDiffFieldSettingsButton" class="secondary" type="button">取消</button>
              <button id="saveDiffFieldSettingsButton" class="primary" type="button">确定</button>
            </div>
          </div>
        </section>
      </div>

      <section id="aiReviewTaskPage" class="page-section">
        <div class="review-conversation-shell">
          <aside class="review-session-sidebar">
            <button id="newReviewConversationButton" class="primary review-new-chat" type="button">＋ 新建审校</button>
            <div id="reviewConversationList" class="review-conversation-list"></div>
          </aside>
          <div class="review-conversation-main">
            <div class="review-conversation-head">
              <div>
                <div class="review-conversation-title-row">
                  <h3 id="reviewConversationTitle">新审校</h3>
                  <input id="reviewConversationTitleInput" class="review-title-input hidden" type="text" maxlength="120" aria-label="会话名称" />
                  <button id="renameReviewConversationButton" class="review-title-edit" type="button" aria-label="重命名会话" title="重命名会话">✎</button>
                </div>
                <p id="reviewConversationStatus">添加文件或直接输入待审校文本</p>
              </div>
              <div class="actions compact-actions">
                <label class="check-line"><input id="reviewAutoStart" type="checkbox" /><span>识别后自动开始</span></label>
                <button id="deleteReviewConversationButton" class="secondary danger-text" type="button">删除会话</button>
              </div>
            </div>
            <div id="reviewConversationMessages" class="review-conversation-messages"></div>
            <div id="reviewComposer" class="review-composer">
              <div id="reviewAttachmentChips" class="review-attachment-chips"></div>
              <textarea id="reviewComposerInput" rows="3" placeholder="输入待审校文本，或拖拽多个文件到这里…"></textarea>
              <div class="review-composer-footer">
                <div class="review-composer-tools">
                  <button id="reviewPromptChip" class="composer-chip" type="button">提示词</button>
                  <button id="reviewSourceLanguageChip" class="composer-chip" type="button">源语言：自动</button>
                  <button id="reviewTargetLanguageChip" class="composer-chip" type="button">目标语言：自动</button>
                  <button id="reviewTermBaseChip" class="composer-chip review-term-base-chip" type="button" title="选择术语表">术语表</button>
                  <button id="reviewUploadChip" class="composer-chip" type="button">＋ 文件</button>
                  <button id="reviewFeedbackUploadButton" class="composer-chip" type="button">上传优化文件</button>
                  <input id="reviewFeedbackFileInput" type="file" accept=".xlsx" hidden />
                  <input id="reviewConversationFileInput" type="file" accept=".xlsx,.xlsm,.xls,.xlf,.xliff,.csv,.tsv,.txt,.md,.docx,.pptx,.pdf,.json,.xml" multiple hidden />
                  <input id="reviewTermBaseFileInput" type="file" accept=".xlsx,.xlsm,.xls" hidden />
                </div>
                <button id="sendReviewConversationButton" class="primary review-send-button" type="button">发送</button>
              </div>
              <div id="reviewLanguagePopover" class="review-language-popover hidden" role="dialog" aria-label="选择语言">
                <div class="review-language-popover-head">
                  <button id="closeReviewLanguagePopoverButton" class="review-language-back" type="button" aria-label="收起语言列表">‹</button>
                  <strong id="reviewLanguagePopoverTitle">选择语言</strong>
                  <span id="reviewLanguagePopoverHint">单选</span>
                </div>
                <div class="review-language-search-wrap">
                  <span>⌕</span><input id="reviewLanguageSearch" type="search" placeholder="搜索或输入自定义语种" autocomplete="off" />
                </div>
                <div id="reviewLanguageOptions" class="review-language-options"></div>
              </div>
              <div id="reviewTermBasePopover" class="review-term-base-popover hidden" role="menu" aria-label="选择术语表">
                <div class="review-term-base-search"><input id="reviewTermBaseSearch" type="search" placeholder="搜索 memoQ 术语库" autocomplete="off" /></div>
                <button id="uploadReviewTermBaseButton" class="review-term-base-action" type="button" role="menuitem">
                  <span class="review-term-base-action-icon">＋</span><span><strong>上传术语表</strong><small>支持 .xlsx、.xlsm、.xls；自动识别语种列</small></span>
                </button>
                <div id="reviewTermBaseOptions" class="review-term-base-options"></div>
              </div>
              <span id="reviewConversationHint" class="hint"></span>
              <div class="review-learning-panel">
                <div class="review-learning-summary-row">
                  <div id="reviewLearningStatus" class="hint" aria-live="polite"></div>
                  <button id="reviewMemoryButton" class="secondary review-memory-button" type="button">查看规范</button>
                </div>
                <div id="reviewLearningProgress" class="review-learning-progress" hidden aria-live="polite">
                  <div class="review-learning-progress-head">
                    <span id="reviewLearningProgressLabel">等待处理</span>
                    <span id="reviewLearningProgressValue">0%</span>
                  </div>
                  <div class="review-learning-progress-track"><span id="reviewLearningProgressBar"></span></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <dialog id="reviewAttachmentMappingDialog" class="modal">
          <form method="dialog" class="modal-card review-attachment-mapping-card">
            <div class="review-mapping-file-head">
              <div class="review-mapping-file-icon" aria-hidden="true">XLSX</div>
              <div class="review-mapping-file-copy">
                <span>文件导入设置</span>
                <h2 id="reviewAttachmentMappingTitle">文件导入方式</h2>
              </div>
              <button id="closeReviewAttachmentMappingButton" class="review-mapping-close" value="cancel" type="submit" aria-label="关闭">×</button>
            </div>
            <p class="review-mapping-lead">选择识别方式。Excel 可读取实际工作表和表头后手动调整映射。</p>
            <div class="review-import-mode-grid">
              <label class="review-import-mode-option">
                <input type="radio" name="reviewAttachmentMappingMode" value="ai" checked />
                <span class="review-import-mode-icon review-import-mode-ai" aria-hidden="true">✦</span>
                <span><strong>自动识别列 <em>默认</em></strong><small>由 Workspace Agent 判断原文、译文和同一行上下文列</small></span>
                <i aria-hidden="true">✓</i>
              </label>
              <label class="review-import-mode-option">
                <input type="radio" name="reviewAttachmentMappingMode" value="preset" />
                <span class="review-import-mode-icon" aria-hidden="true">▦</span>
                <span><strong>手动设置列与语种</strong><small>读取工作表结构，选择并编辑原文、译文和信息列</small></span>
                <i aria-hidden="true">✓</i>
              </label>
            </div>
            <div id="reviewAttachmentPresetField" class="review-mapping-preset-panel hidden">
              <div class="review-mapping-field-label"><label for="reviewAttachmentPresetSelect">映射模板</label><span>可选</span></div>
              <div class="review-mapping-preset-row">
                <select id="reviewAttachmentPresetSelect"></select>
                <button id="editReviewAttachmentMappingButton" class="secondary" type="button">设置列与语种</button>
              </div>
              <small>编辑器会显示当前文件的工作表、表头和列位置；现有模板也可以直接修改并更新。</small>
            </div>
            <p id="reviewAttachmentMappingHint" class="hint"></p>
            <div class="modal-footer">
              <button class="secondary" value="cancel" type="submit">取消</button>
              <button id="saveReviewAttachmentMappingButton" class="primary" type="button">确认</button>
            </div>
          </form>
        </dialog>

        <section id="reviewConversationResultCard" class="card review-conversation-results hidden">
          <div class="card-title">
            <div><h3>审校结果预览</h3><p>每个目标语言独立审校并生成结果文件。</p></div>
            <div class="actions compact-actions">
              <div id="reviewTargetTabs" class="review-target-tabs"></div>
            </div>
          </div>
          <div class="review-inline-progress">
            <span id="reviewProgress">尚未开始</span>
            <strong id="reviewProgressCount">0 / 0</strong>
            <div class="progress"><span id="reviewProgressBar"></span></div>
            <span id="reviewFailedCount" class="hidden">0</span>
            <span id="reviewRequestedCount" class="hidden">0</span>
            <span id="reviewProgressPercent" class="hidden">未开始</span>
          </div>
          <section id="reviewRequestQueue" class="review-request-queue hidden" aria-label="AI 请求状态">
            <div class="review-request-queue-head"><strong>AI 请求状态</strong><span id="reviewRequestQueueSummary">等待创建请求</span></div>
            <div id="reviewRequestColumns" class="review-request-columns"></div>
          </section>
          <div id="outputPanel" class="result-file hidden"><span>结果文件</span><strong id="outputPath">暂无输出</strong></div>
          <div class="actions">
            <button id="openOutputDirButton" class="secondary" type="button">打开输出目录</button>
            <button id="openOutputFileButton" class="secondary" type="button" disabled>打开结果文件</button>
          </div>
          <div class="review-result-preview-head">
            <span>预览</span>
            <button id="openReviewDetailButton" class="secondary" type="button" disabled>详情</button>
          </div>
          <div class="pattern-table-wrap review-result-table-wrap">
            <table class="pattern-table review-result-table">
              <thead id="reviewResultHead"><tr><th>原文</th><th>译文</th><th>是否有问题</th><th>问题类型</th><th>问题说明</th><th>修改建议</th></tr></thead>
              <tbody id="reviewResultBody"><tr><td colspan="6" class="empty-cell">暂无审校结果</td></tr></tbody>
            </table>
          </div>
        </section>

        <div class="hidden" aria-hidden="true">
          <div id="reviewFilePath"></div><button id="chooseReviewFileButton" type="button"></button>
          <input id="reviewFileInput" type="file" /><button id="openExcelMappingButton" type="button"></button>
          <div id="reviewBatchCount"></div><div id="reviewFileHint"></div><div id="excelMappingSummary"></div>
          <table><tbody id="previewBody"></tbody></table><input id="sourceLanguageInput" /><input id="targetLanguageInput" />
          <button id="startReviewButton" type="button"></button><button id="openReviewSettingsButton" type="button"></button>
          <button id="openReviewForbiddenButton" type="button"></button><span id="reviewTaskHint"></span><ol id="reviewLogList"></ol>
        </div>

      </section>

      <section id="aiReviewSettingsPage" class="page-section">
        <div class="grid one">
          <section class="card">
            <div class="card-title">
              <h3>参数设置</h3>
              <p>Workspace Agent 与 Task Workflow 统一使用“模型设置”中的当前模型和 API 配置。</p>
            </div>
            <div class="grid two">
              <label>思考强度<select id="reviewReasoningEffort"><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
              <label>单包正文预算<input id="reviewAiLimit" type="number" min="200" value="1500" /></label>
              <label>单包条目上限<input id="reviewMaxItems" type="number" min="1" max="500" value="20" /></label>
              <label class="check-line"><input id="reviewCacheEnabled" type="checkbox" checked /><span>审校缓存</span></label>
              <label class="check-line"><input id="reviewLearningEnabled" type="checkbox" checked /><span>自主学习</span></label>
            </div>
            <div class="actions">
              <button id="saveReviewAgentSettingsButton" class="primary" type="button">保存设置</button>
            </div>
            <span id="reviewSettingsHint" class="hint"></span>
            <div class="hidden" aria-hidden="true">
              <input id="enableAiReview" type="checkbox" checked /><input id="enableDirectionalReview" type="checkbox" />
              <span id="directionalReviewLine"></span><select id="promptTemplateSelect"></select>
              <span id="directionalTemplatePanel"><select id="directionalTemplateSelect"></select></span>
              <button id="editPromptButton" type="button"></button><button id="editDirectionalButton" type="button"></button>
            </div>
          </section>
        </div>
      </section>

      <section id="aiReviewForbiddenPage" class="page-section hidden" aria-hidden="true">
        <input id="enableForbiddenCheck" type="checkbox" /><span id="forbiddenTemplatePanel"><select id="forbiddenTemplateSelect"></select></span>
        <button id="editForbiddenButton" type="button"></button><span id="reviewForbiddenHint"></span>
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
  <div id="reviewDetailOverlay" class="modal-overlay" hidden>
    <div class="modal-card review-detail-modal">
      <div class="modal-header">
        <div>
          <h3>问题详情</h3>
          <p id="reviewDetailSummary">暂无问题条目</p>
        </div>
        <div class="actions compact-actions">
          <button id="confirmReviewFeedbackButton" class="primary" type="button">确定</button>
          <button id="closeReviewDetailButton" class="modal-close" type="button" aria-label="关闭">×</button>
        </div>
      </div>
      <div id="reviewDetailGroups" class="review-detail-wrap">
        <div class="empty-cell">暂无问题条目</div>
      </div>
      <span id="reviewFeedbackHint" class="hint" aria-live="polite"></span>
    </div>
  </div>
  <div id="reviewFollowupOverlay" class="modal-overlay" hidden>
    <div class="modal-card review-followup-modal">
      <div class="modal-header">
        <div>
          <h3>追问审校结果</h3>
          <p id="reviewFollowupSummary">围绕当前问题继续提问</p>
        </div>
        <button id="closeReviewFollowupButton" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div class="review-followup-layout">
        <aside id="reviewFollowupContext" class="review-followup-context"></aside>
        <section class="review-followup-chat">
          <div id="reviewFollowupMessages" class="review-followup-messages"></div>
          <div class="review-followup-input">
            <textarea id="reviewFollowupInput" placeholder="输入你的追问，例如：这个建议为什么这样改？有没有更自然的译法？"></textarea>
            <button id="sendReviewFollowupButton" class="primary" type="button">发送</button>
          </div>
          <span id="reviewFollowupHint" class="hint"></span>
        </section>
      </div>
    </div>
  </div>
  <div id="reviewMemoryOverlay" class="modal-overlay" hidden>
    <div class="modal-card review-memory-modal">
      <div class="modal-header">
        <div>
          <h3>会话规范</h3>
          <p id="reviewMemorySummary">查看并编辑当前会话自主学习形成的规范。</p>
        </div>
        <button id="closeReviewMemoryButton" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div id="reviewMemoryRuleList" class="review-memory-rule-list"></div>
      <div class="modal-footer review-memory-footer">
        <span id="reviewMemoryHint" class="hint" aria-live="polite"></span>
        <div class="actions compact-actions">
          <button id="cancelReviewMemoryButton" class="secondary" type="button">取消</button>
          <button id="restoreReviewMemoryButton" class="secondary" type="button">撤回上次更新</button>
          <button id="saveReviewMemoryButton" class="primary" type="button">保存修改</button>
        </div>
      </div>
    </div>
  </div>

  <dialog id="promptDialog" class="dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head">
        <div>
          <h2>提示词模板</h2>
          <p>用户提示词必须包含 {text}，工具会把待审校 JSON 条目填入这里。</p>
        </div>
        <button id="closePromptDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>
      <input id="promptTemplateId" type="hidden" />
      <div class="field">
        <label for="promptDialogTemplateSelect">当前模板</label>
        <select id="promptDialogTemplateSelect"></select>
      </div>
      <div class="field">
        <label for="promptNameInput">模板名</label>
        <input id="promptNameInput" type="text" />
      </div>
      <div class="field">
        <label for="systemPromptInput">系统提示词</label>
        <textarea id="systemPromptInput" rows="6"></textarea>
      </div>
      <div class="field">
        <label for="userPromptInput">用户提示词</label>
        <textarea id="userPromptInput" rows="10"></textarea>
      </div>
      <div class="field">
        <label for="promptForbiddenWordsInput">禁用词（可选，每行一个）</label>
        <textarea id="promptForbiddenWordsInput" rows="5" placeholder="命中内容会由本地规则检查，不交给模型判断"></textarea>
      </div>
      <div class="dialog-actions">
        <button id="savePromptButton" type="button" class="primary">保存模板</button>
        <button id="newPromptButton" class="secondary" type="button">新建模板</button>
        <button id="resetPromptButton" class="secondary" type="button">恢复默认</button>
        <button id="deletePromptButton" class="danger" type="button">删除模板</button>
        <button id="cancelPromptDialogButton" class="secondary" type="button">取消</button>
      </div>
    </form>
  </dialog>

  <dialog id="toolGuideDialog" class="dialog tool-guide-dialog">
    <div class="dialog-card">
      <header class="dialog-header">
        <div>
          <span class="dialog-kicker">工具说明</span>
          <h3 id="toolGuideDialogTitle">工具说明</h3>
        </div>
        <button id="closeToolGuideDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </header>
      <article id="toolGuideDialogBody" class="markdown-guide"></article>
    </div>
  </dialog>

  <dialog id="directionalDialog" class="dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head">
        <div>
          <h2>定向审校模板</h2>
          <p>每个启用的审校类型会成为结果 Excel 中的一列。</p>
        </div>
        <button id="closeDirectionalDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>
      <input id="directionalTemplateId" type="hidden" />
      <div class="field">
        <label for="directionalNameInput">模板名</label>
        <input id="directionalNameInput" type="text" />
      </div>
      <div id="directionalItems" class="directional-items"></div>
      <div class="actions">
        <button id="addDirectionalItemButton" class="secondary" type="button">新建选项</button>
      </div>
      <div class="dialog-actions">
        <button id="saveDirectionalButton" class="primary" type="button">保存模板</button>
        <button id="newDirectionalButton" class="secondary" type="button">新建模板</button>
        <button id="cancelDirectionalDialogButton" class="secondary" type="button">取消</button>
      </div>
    </form>
  </dialog>

  <dialog id="forbiddenDialog" class="dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head">
        <div>
          <h2>禁用词模板</h2>
          <p>一行一个禁用词；检查译文，不区分大小写，包含即命中。</p>
        </div>
        <button id="closeForbiddenDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>
      <input id="forbiddenTemplateId" type="hidden" />
      <div class="field">
        <label for="forbiddenNameInput">模板名</label>
        <input id="forbiddenNameInput" type="text" />
      </div>
      <div class="field">
        <label for="forbiddenWordsInput">禁用词列表</label>
        <textarea id="forbiddenWordsInput" rows="12"></textarea>
      </div>
      <div class="dialog-actions">
        <button id="saveForbiddenButton" class="primary" type="button">保存模板</button>
        <button id="newForbiddenButton" class="secondary" type="button">新建模板</button>
        <button id="cancelForbiddenDialogButton" class="secondary" type="button">取消</button>
      </div>
    </form>
  </dialog>
  <dialog id="excelMappingDialog" class="dialog wide-dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head">
        <div>
          <h2 id="excelMappingDialogTitle">Excel 映射</h2>
          <p id="excelMappingDialogSubtitle">按 sheet 选择原文列、译文列和信息列。</p>
        </div>
        <button id="closeExcelMappingDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>
      <div class="grid two mapping-default-languages">
        <div class="field">
          <label for="mappingSourceLanguageInput">默认原文语种（各列可单独设置）</label>
          <input id="mappingSourceLanguageInput" type="text" />
        </div>
        <div class="field">
          <label for="mappingTargetLanguageInput">默认译文语种（各列可单独设置）</label>
          <input id="mappingTargetLanguageInput" type="text" />
        </div>
      </div>
      <div class="mapping-template-bar">
        <label for="excelMappingPresetSelect">映射模板</label>
        <select id="excelMappingPresetSelect" title="选择后立即套用"></select>
        <button id="saveExcelMappingPresetButton" class="secondary" type="button">保存当前映射</button>
        <button id="deleteExcelMappingPresetButton" class="icon-button danger mapping-template-delete" type="button" aria-label="删除模板" title="删除当前模板" disabled>&#128465;</button>
      </div>
      <p id="excelMappingPresetHint" class="mapping-template-hint" aria-live="polite"></p>
      <div id="excelSheetTabs" class="sheet-tabs"></div>
      <div id="excelMappingColumns" class="excel-mapping-columns"></div>
      <div class="dialog-actions">
        <button id="applyExcelMappingButton" class="primary" type="button">确认读取</button>
        <button id="cancelExcelMappingDialogButton" class="secondary" type="button">取消</button>
      </div>
    </form>
  </dialog>
  <dialog id="excelMappingPresetDialog" class="dialog compact-dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head">
        <div>
          <h2>保存映射模板</h2>
        </div>
        <button id="closeExcelMappingPresetDialogButton" class="icon-button" type="button" aria-label="关闭">×</button>
      </div>
      <div class="field">
        <label for="excelMappingPresetNameInput">模板名称</label>
        <input id="excelMappingPresetNameInput" type="text" maxlength="80" autocomplete="off" />
      </div>
      <p id="excelMappingPresetSaveHint" class="mapping-template-hint" aria-live="polite"></p>
      <div class="dialog-actions">
        <button id="confirmExcelMappingPresetButton" type="button" class="primary">保存</button>
        <button id="cancelExcelMappingPresetDialogButton" class="secondary" type="button">取消</button>
      </div>
    </form>
  </dialog>
  <dialog id="preprocessMappingDialog" class="dialog wide-dialog">
    <form method="dialog" class="dialog-body">
      <div class="dialog-head"><div><h2>选择待提取列</h2><p>按工作表选择一个或多个提取列，可保存为模板。</p></div><button id="closePreprocessMappingButton" class="icon-button" type="button">×</button></div>
      <div class="field"><label for="preprocessMappingSourceLanguage">源语言</label><select id="preprocessMappingSourceLanguage"><option value="auto">自动检测</option><option value="zho-CN">简体中文</option><option value="zho-TW">繁体中文</option><option value="eng">英语</option><option value="jpn">日语</option><option value="kor">韩语</option><option value="fra">法语</option><option value="deu">德语</option><option value="spa">西班牙语</option><option value="por">葡萄牙语</option><option value="ita">意大利语</option><option value="rus">俄语</option></select></div>
      <div class="mapping-template-bar"><label for="preprocessMappingTemplateSelect">映射模板</label><select id="preprocessMappingTemplateSelect"><option value="">选择模板</option></select><button id="applyPreprocessTemplateButton" class="secondary" type="button">调用模板</button><button id="deletePreprocessTemplateButton" class="mapping-template-delete" type="button" aria-label="删除模板">×</button></div>
      <div id="preprocessMappingSheetTabs" class="sheet-tabs"></div><div id="preprocessMappingColumns" class="excel-mapping-columns"></div>
      <div id="preprocessMappingHint" class="inline-task-hint" role="status" aria-live="polite"></div>
      <div class="dialog-actions"><button id="savePreprocessMappingButton" class="secondary" type="button">保存模板</button><button id="applyPreprocessToButton" class="secondary" type="button">应用到</button><button id="applyPreprocessMappingButton" type="button" class="primary">确认选择</button><button id="cancelPreprocessMappingButton" class="secondary" type="button">取消</button></div>
    </form>
  </dialog>
  <dialog id="preprocessApplyToDialog" class="dialog compact-dialog"><form method="dialog" class="dialog-body"><div class="dialog-head"><h2>应用到</h2><button id="closePreprocessApplyToButton" class="icon-button" type="button">×</button></div><p>将当前 Sheet 的映射应用到其他工作表。</p><label class="check-line"><input id="preprocessApplyToAll" type="checkbox" /> 所有 Sheet</label><div id="preprocessApplyToSheets" class="preprocess-apply-sheet-list"></div><div class="dialog-actions"><button id="confirmPreprocessApplyToButton" type="button" class="primary">确认</button><button id="cancelPreprocessApplyToButton" class="secondary" type="button">取消</button></div></form></dialog>
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
  <div id="feedbackOverlay" class="modal-overlay" hidden>
    <div class="modal-card feedback-modal">
      <div class="modal-header">
        <div>
          <h3>我要反馈</h3>
          <p>问题为必填。当前日志会自动附带，截图可按需补充。</p>
        </div>
        <button id="closeFeedbackModalButton" class="modal-close" type="button" aria-label="关闭">×</button>
      </div>
      <div class="grid one">
        <label>问题<textarea id="feedbackMessageInput" rows="7" placeholder="请尽量写清楚出现了什么问题、在哪一步出现。"></textarea></label>
        <div class="feedback-attachment-card">
          <div class="feedback-attachment-head">
            <strong>截图</strong>
            <button id="chooseFeedbackScreenshotButton" class="secondary" type="button">选择截图</button>
          </div>
          <button id="feedbackScreenshotDropzone" class="feedback-dropzone" type="button">
            <span class="feedback-dropzone-title">点击选择截图 / 直接拖入这里</span>
            <span class="feedback-dropzone-subtitle">弹窗打开时也可以直接粘贴截图</span>
          </button>
          <small id="feedbackScreenshotName">未选择截图</small>
          <input id="feedbackScreenshotInput" type="file" accept="image/*" hidden />
        </div>
        <div class="feedback-log-card">
          <div>
            <strong>日志</strong>
            <small id="feedbackLogHint">会自动附带当前日志。</small>
          </div>
          <div class="actions feedback-log-actions">
            <button id="openFeedbackLogButton" class="secondary" type="button">打开日志</button>
          </div>
          <code id="feedbackLogPath">output/log.txt</code>
        </div>
      </div>
      <div class="modal-footer">
        <span id="feedbackSubmitHint" class="hint"></span>
        <div class="modal-footer-actions">
          <button id="cancelFeedbackButton" class="secondary" type="button">取消</button>
          <button id="submitFeedbackButton" class="primary" type="button">提交反馈</button>
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


from .workspace_layout import LAYOUT_CSS

APP_CSS = LAYOUT_CSS


APP_JS = r"""
const $ = (id) => document.getElementById(id);
const UI_THEME_STORAGE_KEY = "yeehe-ui-theme";

function applyUiTheme(theme) {
  const useLightTheme = theme === "light";
  document.documentElement.classList.toggle("light-theme", useLightTheme);
  try {
    localStorage.setItem(UI_THEME_STORAGE_KEY, useLightTheme ? "light" : "dark");
  } catch (_) {}
  const button = $("themeToggleButton");
  const label = $("themeToggleLabel");
  if (!button || !label) return;
  button.classList.toggle("is-active", useLightTheme);
  button.setAttribute("aria-pressed", String(useLightTheme));
  button.title = useLightTheme ? "切换至深色模式" : "切换至浅色模式";
  label.textContent = useLightTheme ? "浅色模式" : "深色模式";
  button.querySelector(".theme-toggle-icon").textContent = useLightTheme ? "☀" : "☾";
}

function initializeUiTheme() {
  applyUiTheme(document.documentElement.classList.contains("light-theme") ? "light" : "dark");
}

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
let appUpdateAutoPrompted = false;
let latestResultFile = "";
let lastResultSummaryPath = "";
let statusRefreshInFlight = false;
let availableModels = [];
let currentProviderName = "DeepSeek";
let currentBaseUrl = "";
let crossExcelScanState = null;
let crossExcelSearchState = null;
let crossExcelOutputFile = "";
let diffExcelState = {
  cacheFile: "",
  resultId: "",
  previewRecords: [],
  meta: null,
  outputFile: "",
  totalCount: 0,
  matchedCount: 0,
  previewLimit: 200,
  previewOffset: 0,
  taskId: "",
  previewTruncated: false,
};
let diffFieldMatchSettings = {
  headers: null,
  referenceField: "",
  compareFields: [],
  includeUnmatched: false,
};
let feedbackStatusState = { enabled: false, log_path: "output/log.txt", has_log_file: false };
let feedbackScreenshotFile = null;
let currentPageId = "toolGuidePage";
let lastTrackedToolKey = "";
let aiReviewBatch = null;
let aiReviewTaskId = "";
let aiReviewCurrentTask = null;
let aiReviewLogCursor = 0;
let aiReviewTaskPoller = null;
let aiReviewTaskPollInFlight = false;
let aiReviewPromptTemplates = [];
let aiReviewDirectionalTemplates = [];
let aiReviewForbiddenTemplates = [];
let aiReviewExcelMappingPresets = [];
let aiReviewSheetNames = [];
let aiReviewColumnsBySheet = {};
let aiReviewExcelMappingState = {};
let aiReviewActiveSheetName = "";
let aiReviewMappingTemplateIssues = [];
let aiReviewIssueResults = [];
let reviewFeedbackDraft = new Map();
let reviewFeedbackTaskId = '';
let reviewFeedbackSessionId = '';
let reviewFeedbackSaving = false;
let reviewMemoryState = { sessionId: '', version: 0, rules: [], saving: false };
const reviewLearningDrafts = new Map();
let aiReviewFollowupState = { taskId: "", resultId: "", item: null, messages: [] };
let reviewConversationState = {
  sessions: [],
  currentId: "",
  snapshot: null,
  eventSource: null,
  eventCursor: 0,
  refreshTimer: null,
  sourceLanguage: "auto",
  targetLanguages: ["auto"],
  promptTemplateId: "",
  termBaseId: "",
  memoqTermBaseIds: [],
  memoqTermBases: [],
  termBases: [],
  composerSaveQueue: Promise.resolve(),
  languageMode: "source",
  activeTarget: "",
  streamRunId: "",
  streamText: "",
  streamThinkingText: "",
  streamAnswerText: "",
  streamPhase: "reasoning",
  streamActive: false,
  mappingAttachmentId: "",
  mappingEditorAttachmentId: "",
  mappingEditorPresetId: "",
  mappingEditorContext: "",
  mappingEditorApplyAfterSave: false,
};
let preprocessTermBaseIds = [];
let preprocessMappingState = { sheetNames: [], columnsBySheet: {}, selected: {}, activeSheet: "" };
let preprocessFiles = [];
let preprocessActiveFile = null;
const reviewLanguages = [
  "自动检测", "无源文", "简体中文", "繁体中文", "英语", "日语", "韩语", "法语", "德语", "西班牙语", "葡萄牙语",
  "葡萄牙语（巴西）", "葡萄牙语（葡萄牙）",
  "意大利语", "俄语", "阿拉伯语", "泰语", "越南语", "印尼语", "土耳其语", "波兰语", "荷兰语", "瑞典语",
  "挪威语", "丹麦语", "芬兰语", "捷克语", "匈牙利语", "罗马尼亚语", "希腊语", "希伯来语", "乌克兰语",
];
const reviewTermBaseLanguageLabels = {
  English: "英语",
  English_United_Kingdom: "英语（英国）",
  French: "法语",
  German: "德语",
  Italian: "意大利语",
  Japanese: "日语",
  Korean: "韩语",
  Spanish: "西班牙语",
  Portuguese: "葡萄牙语",
  Portuguese_Brazil: "葡萄牙语（巴西）",
  Portuguese_Portugal: "葡萄牙语（葡萄牙）",
  Russian: "俄语",
  Arabic: "阿拉伯语",
  Thai: "泰语",
  Vietnamese: "越南语",
  Indonesian: "印尼语",
  Turkish: "土耳其语",
  Polish: "波兰语",
  Dutch: "荷兰语",
  Swedish: "瑞典语",
  Norwegian: "挪威语",
  Danish: "丹麦语",
  Finnish: "芬兰语",
  Czech: "捷克语",
  Hungarian: "匈牙利语",
  Romanian: "罗马尼亚语",
  Greek: "希腊语",
  Hebrew: "希伯来语",
  Ukrainian: "乌克兰语",
  Chinese_PRC: "简体中文",
  Chinese_Taiwan: "繁体中文",
};
const TASK_STATUS_BY_PAGE = {
  overviewPage: {
    taskLabel: "文本预处理工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
  crossExcelPage: {
    taskLabel: "跨Excel搜索与合并",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
  diffExcelPage: {
    taskLabel: "Diff 工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
  aiReviewTaskPage: {
    taskLabel: "AI 审校工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
  aiReviewSettingsPage: {
    taskLabel: "AI 审校工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
  aiReviewForbiddenPage: {
    taskLabel: "AI 审校工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  },
};
const PAGE_TASK_LABELS = {
  toolGuidePage: "工具说明",
  overviewPage: "文本预处理工具",
  modelSettingsPage: "设置",
  modelStageSettingsPage: "文本预处理工具",
  nontransSettingsPage: "文本预处理工具",
  promptSettingsPage: "文本预处理工具",
  runDetailsPage: "文本预处理工具",
  resultsPage: "文本预处理工具",
  diffExcelPage: "Diff 工具",
  crossExcelPage: "跨Excel搜索与合并",
  aiReviewTaskPage: "AI 审校工具",
  aiReviewSettingsPage: "AI 审校工具",
  aiReviewForbiddenPage: "AI 审校工具",
};
const PAGE_HERO_COPY = {
  feishuTransferPage: {title:"飞书文件传输", lede:"选择群聊，由信鸽发送文件。"},
  toolGuidePage: { title: "工具说明", lede: "先了解每个工具能做什么，再开始任务。" },
  overviewPage: { title: "文本预处理工具", lede: "用于提取术语、识别非译元素，并整理文本预处理结果。" },
  modelSettingsPage: { title: "设置", lede: "统一管理模型连接与 memoQ 账号。" },
  modelStageSettingsPage: { title: "模型阶段设置", lede: "分别控制非译元素、术语召回和术语校验阶段。" },
  nontransSettingsPage: { title: "非译元素设置", lede: "管理检测规则、内置规则库和保护方式。" },
  promptSettingsPage: { title: "提示词设置", lede: "按阶段维护默认提示词。" },
  runDetailsPage: { title: "运行详情", lede: "查看任务过程、统计和日志。" },
  resultsPage: { title: "结果", lede: "在这里查看导出结果和数量概览。" },
  diffExcelPage: { title: "Excel差异比对", lede: "对比两个 Excel 文件或目录，查看差异、导出结果并批量标记。" },
  crossExcelPage: { title: "跨Excel搜索与合并", lede: "跨文件搜索整行内容，并按表头合并结果。" },
  aiReviewTaskPage: { title: "审校任务", lede: "导入文件、确认映射、查看预览并启动审校任务。" },
  aiReviewSettingsPage: { title: "审校设置", lede: "管理审校请求参数与思考强度。" },
  aiReviewForbiddenPage: { title: "禁用词", lede: "单独管理禁用词开关与禁用词模板。" },
};
const PAGE_ACCORDION_KEYS = {
  overviewPage: "text-preprocess",
  modelStageSettingsPage: "text-preprocess",
  nontransSettingsPage: "text-preprocess",
  promptSettingsPage: "text-preprocess",
  runDetailsPage: "text-preprocess",
  resultsPage: "text-preprocess",
  aiReviewTaskPage: "ai-review-tool",
  aiReviewSettingsPage: "ai-review-tool",
  aiReviewForbiddenPage: "ai-review-tool",
};
const TOOL_GUIDES = {
  feishuTransfer: {
    title: "飞书文件传输",
    sections: [
      ["用途", "按群名选择飞书群聊，将本机文件直接上传到飞书，由信鸽发送附件或群文件文档链接。"],
      ["开始使用", ["在“设置”中登录公司 memoQ 账号。", "进入“飞书文件传输”，搜索并选择目标群。", "点击“选择文件”或拖入多个文件，核对目标群和文件后确认发送。"]],
      ["发送方式", ["单文件不超过 30 MB 时，信鸽直接发送群附件。", "超过 30 MB 时，文件分片上传到飞书云空间，原文件链接追加到该群专属云文档，由信鸽发送文档链接。", "同群后续上传复用原文档；确认文档被删除后才重新创建。", "信鸽尚未入群时会先尝试邀请，若需群管理员审批，界面会显示等待状态。"]],
    ],
  },
  textPreprocess: {
    title: "文本预处理工具",
    sections: [
      ["用途", "从游戏文本表中提取术语，识别不应翻译的标签、变量、占位符等非译元素，并导出整理好的结果表。"],
      ["适合处理", ["Excel 文本表", "XLIFF 文件", "带有 HTML 标签、花括号、变量、格式代码的游戏文本"]],
      ["基本用法", ["在“模型设置”中加载模型。", "进入“文本预处理工具”，选择输入目录和待提取列。", "选择运行模式，点击“开始提取”。", "完成后在“总览”中查看进度并打开输出文件。"]],
      ["输出结果", ["术语库", "非译元素正则规则", "失败记录和任务日志"]],
    ],
  },
  aiReview: {
    title: "AI 审校工具",
    sections: [
      ["用途", "由 Workspace Agent 自动理解附件结构、原文、译文和同一行上下文列，再按目标语言分别执行翻译审校与严格校验。"],
      ["适合处理", ["Excel、XLIFF、CSV 等双语文件", "只有译文的文档或直接粘贴文本", "多文件与多目标语言项目"]],
      ["基本用法", ["进入“AI 审校工具”，拖入一个或多个文件，也可以直接输入待审校文本。", "选择提示词、源语言和目标语言后发送。", "检查 Workspace Agent 的识别报告；默认确认后开始审校。", "首批结果会实时显示在会话下方，完成后可打开独立结果文件。"]],
      ["常用设置", ["模型与 API：统一使用工具“模型设置”中的当前配置。", "并发与分包：控制审校速度和单次响应规模。", "禁用词：关联在提示词模板中，由本地确定性规则检查。"]],
    ],
  },
  crossExcel: {
    title: "跨Excel搜索与合并",
    sections: [
      ["用途", "在多个 Excel 文件里快速搜索文本，或把多个 Excel 按相同表头合并成一个结果文件。"],
      ["适合处理", ["多个结构相近的 Excel", "需要全局查找某个词或句子的项目", "需要按表头抽取并合并列的项目"]],
      ["搜索用法", ["选择 Excel 所在目录。", "输入关键词后点击“搜索”。", "结果会按整行显示，点击单元格可以复制内容。"]],
      ["合并用法", ["选择要合并的表头列。", "点击“合并”。", "完成后打开输出文件或输出目录。"]],
    ],
  },
  diffExcel: {
    title: "Diff 工具",
    sections: [
      ["用途", "对比两个 Excel 文件，或两个目录下的同名 Excel 文件，快速找出所有差异单元格。"],
      ["适合处理", ["版本更新前后文本表比对", "校对不同翻译包的改动", "批量定位某批修改是否已经写入表格"]],
      ["基本用法", ["选择路径 A 和路径 B。", "点击“开始比对”。", "需要时导出差异结果，或把预览结果批量标记回原表。"]],
      ["当前版本支持", ["文件对文件", "目录对目录同名配对", "差异导出", "批量高亮回写原表"]],
    ],
  },
};

const TOOL_KEY_BY_PAGE = {
  toolGuidePage: "home_guide",
  overviewPage: "text_preprocess",
  modelStageSettingsPage: "text_preprocess",
  nontransSettingsPage: "text_preprocess",
  promptSettingsPage: "text_preprocess",
  runDetailsPage: "text_preprocess",
  resultsPage: "text_preprocess",
  diffExcelPage: "diff_excel",
  aiReviewTaskPage: "ai_review",
  aiReviewSettingsPage: "ai_review",
  aiReviewForbiddenPage: "ai_review",
  crossExcelPage: "cross_excel",
};

async function trackToolOpen(toolKey) {
  if (!toolKey || toolKey === lastTrackedToolKey) return;
  lastTrackedToolKey = toolKey;
  try {
    await api("/api/telemetry/tool-open", {
      method: "POST",
      body: JSON.stringify({ tool_key: toolKey }),
    });
  } catch (error) {
  }
}

function setPage(pageId) {
  if (pageId === "runDetailsPage" || pageId === "resultsPage") {
    pageId = "overviewPage";
  }
  currentPageId = pageId;
  if (pageId === "feishuTransferPage") transfer.enter();
  document.querySelectorAll(".page-section").forEach((section) => {
    section.classList.toggle("active", section.id === pageId);
  });
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.pageTarget === pageId);
  });
  const heroCopy = PAGE_HERO_COPY[pageId] || PAGE_HERO_COPY.overviewPage;
  $("heroTitle").textContent = heroCopy.title;
  $("heroLede").textContent = heroCopy.lede;
  const activeAccordionKey = PAGE_ACCORDION_KEYS[pageId] || "";
  document.querySelectorAll(".nav-accordion").forEach((accordion) => {
    if (!accordion.dataset.accordionKey) return;
    accordion.open = accordion.dataset.accordionKey === activeAccordionKey;
  });
  if (pageId === "nontransSettingsPage" && pendingRuleState.show_library_dot) {
    markPendingRuleSeen({ library_seen: true }).catch(() => {});
  }
  trackToolOpen(TOOL_KEY_BY_PAGE[pageId] || "");
  renderCurrentTaskStatus();
}

function taskStatusForPage(pageId) {
  if (TASK_STATUS_BY_PAGE[pageId]) {
    return TASK_STATUS_BY_PAGE[pageId];
  }
  if (PAGE_ACCORDION_KEYS[pageId] === "text-preprocess") {
    return TASK_STATUS_BY_PAGE.overviewPage;
  }
  return {
    taskLabel: PAGE_TASK_LABELS[pageId] || "当前任务",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
    active: false,
  };
}

function setTaskStatus(pageId, nextState = {}) {
  const base = taskStatusForPage(pageId);
  TASK_STATUS_BY_PAGE[pageId] = {
    ...base,
    ...nextState,
  };
}

function renderCurrentTaskStatus() {
  const state = taskStatusForPage(currentPageId);
  renderTaskStatus(
    state.taskLabel,
    state.pill,
    state.pillClass,
    state.stageLabel,
    state.message,
  );
}

function renderToolGuide(toolKey = "textPreprocess") {
  const guide = TOOL_GUIDES[toolKey] || TOOL_GUIDES.textPreprocess;
  $("toolGuideDialogTitle").textContent = guide.title;
  $("toolGuideDialogBody").innerHTML = guide.sections.map(([heading, content]) => {
    const body = Array.isArray(content)
      ? `<ul>${content.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : `<p>${escapeHtml(content)}</p>`;
    return `<section><h4>${escapeHtml(heading)}</h4>${body}</section>`;
  }).join("");
  $("toolGuideDialog").showModal();
}

function renderTaskStatus(taskLabel, pillText, pillClass, stageLabel, message) {
  const taskTypeLabel = $("taskTypeLabel");
  const statusPill = $("statusPill");
  const stageLabelNode = $("stageLabel");
  const statusMessage = $("statusMessage");
  if (!taskTypeLabel || !statusPill || !stageLabelNode || !statusMessage) return;
  taskTypeLabel.textContent = taskLabel || "文本预处理工具";
  statusPill.textContent = pillText || "空闲";
  statusPill.className = `pill ${pillClass || ""}`.trim();
  stageLabelNode.textContent = stageLabel || "未启动";
  statusMessage.textContent = message || "等待开始任务";
}

function clearFeedbackForm() {
  $("feedbackMessageInput").value = "";
  $("feedbackScreenshotInput").value = "";
  feedbackScreenshotFile = null;
  $("feedbackScreenshotName").textContent = "未选择截图";
  $("feedbackSubmitHint").textContent = "";
  $("feedbackScreenshotDropzone").classList.remove("drag-over");
}

function renderFeedbackStatus(data) {
  feedbackStatusState = {
    enabled: Boolean(data?.enabled),
    log_path: String(data?.log_path || "output/log.txt"),
    has_log_file: Boolean(data?.has_log_file),
  };
  $("feedbackLogPath").textContent = feedbackStatusState.log_path || "output/log.txt";
  $("feedbackLogHint").textContent = feedbackStatusState.has_log_file
    ? "会自动附带当前日志。"
    : "当前还没有生成日志，提交时会只发送问题描述。";
}

async function loadFeedbackStatus() {
  try {
    const data = await api("/api/feedback/status");
    renderFeedbackStatus(data);
  } catch (error) {
    renderFeedbackStatus({});
  }
}

function openFeedbackModal() {
  $("feedbackOverlay").hidden = false;
  $("feedbackSubmitHint").textContent = "";
  $("feedbackScreenshotDropzone").focus();
}

function closeFeedbackModal() {
  $("feedbackOverlay").hidden = true;
  $("feedbackSubmitHint").textContent = "";
}

async function submitFeedback() {
  const message = String($("feedbackMessageInput").value || "").trim();
  if (!message) {
    $("feedbackSubmitHint").textContent = "请先填写问题。";
    return;
  }
  const formData = new FormData();
  formData.append("message", message);
  const file = feedbackScreenshotFile || $("feedbackScreenshotInput").files?.[0];
  if (file) {
    formData.append("screenshot", file);
  }
  const button = $("submitFeedbackButton");
  button.disabled = true;
  $("feedbackSubmitHint").textContent = "正在提交...";
  try {
    await api("/api/feedback/submit", {
      method: "POST",
      body: formData,
    });
    $("feedbackSubmitHint").textContent = "反馈已提交。";
    setTimeout(() => {
      clearFeedbackForm();
      closeFeedbackModal();
    }, 500);
  } catch (error) {
    $("feedbackSubmitHint").textContent = String(error.message || "反馈提交失败，请稍后重试。");
  } finally {
    button.disabled = false;
  }
}

function setFeedbackScreenshotFile(file) {
  if (!file) {
    feedbackScreenshotFile = null;
    $("feedbackScreenshotName").textContent = "未选择截图";
    return;
  }
  feedbackScreenshotFile = file;
  const sizeKb = Math.max(1, Math.round((Number(file.size || 0) / 1024)));
  $("feedbackScreenshotName").textContent = `${file.name} (${sizeKb} KB)`;
}

async function readClipboardScreenshot(event) {
  if ($("feedbackOverlay").hidden) return;
  const clipboardItems = Array.from(event.clipboardData?.items || []);
  const imageItem = clipboardItems.find((item) => String(item.type || "").startsWith("image/"));
  if (!imageItem) return;
  const file = imageItem.getAsFile();
  if (!file) return;
  event.preventDefault();
  const extension = String(file.type || "image/png").split("/")[1] || "png";
  const stampedFile = new File([file], `pasted_screenshot.${extension}`, { type: file.type || "image/png" });
  setFeedbackScreenshotFile(stampedFile);
  $("feedbackSubmitHint").textContent = "已读取剪贴板截图。";
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
  const { timeoutMs = 60000, ...fetchOptions } = options;
  const isFormData = typeof FormData !== "undefined" && fetchOptions.body instanceof FormData;
  const headers = { ...(fetchOptions.headers || {}) };
  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const controller = Number(timeoutMs) > 0 ? new AbortController() : null;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), Math.max(1000, Number(timeoutMs)))
    : null;
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      headers,
      signal: controller ? controller.signal : fetchOptions.signal,
    });
    if (!response.ok) {
      const text = await response.text();
      let message = text || response.statusText;
      try {
        const data = JSON.parse(text);
        message = data?.detail || data?.message || message;
      } catch (_) {}
      throw new Error(message);
    }
    return response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("请求超时，请检查任务状态后重试。");
    }
    throw error;
  } finally {
    if (timeoutId !== null) window.clearTimeout(timeoutId);
  }
}

function settingsPayload() {
  return {
    provider_name: currentProviderName,
    model_name: $("modelName").value,
    api_key: $("apiKey").value,
    base_url: currentBaseUrl,
    timeout_seconds: Number($("timeoutSeconds").value || 90),
    disable_system_proxy: $("disableSystemProxy").checked,
    extraction_mode: $("extractionMode").value,
    source_language: $("sourceLanguage").value,
    nontrans_chunk_char_limit: Number($("nontransLimit").value || 5000),
    nontrans_placeholder_format: $("nontransPlaceholderFormat").value || "<{n}>",
    term_recall_batch_char_limit: Number($("recallLimit").value || 5000),
    term_review_batch_char_limit: Number($("reviewLimit").value || 5000),
    term_review_max_context_chars: Number($("reviewContextLimit").value || 220),
    nontrans_reasoning_effort: $("nontransReasoningEffort").value || "low",
    term_recall_reasoning_effort: $("recallReasoningEffort").value || "low",
    term_review_reasoning_effort: $("termReviewReasoningEffort").value || "low",
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
    disable_system_proxy: $("disableSystemProxy").checked,
  };
}

function setHeaderOptions(headers, preferredValue = "") {
  const select = $("headerName");
  if (!select) return;
  const values = Array.isArray(headers) ? headers.map((item) => String(item || "").trim()).filter(Boolean) : [];
  const preferred = Array.isArray(preferredValue) ? preferredValue.map(String) : String(preferredValue || select.value || "").split(/[|\n]/).map((item) => item.trim()).filter(Boolean);
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = values.length ? "请选择待提取列" : "请先选择文件夹";
  placeholder.selected = !preferred.length;
  select.appendChild(placeholder);

  values.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    if (preferred.includes(name)) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

function setCrossExcelHeaderSelection(selected) {
  document.querySelectorAll('#crossExcelHeaderList input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = Boolean(selected);
  });
}

function selectedCrossExcelHeaders() {
  return Array.from(document.querySelectorAll('#crossExcelHeaderList input[type="checkbox"]:checked'))
    .map((checkbox) => checkbox.value.trim())
    .filter(Boolean);
}

function renderCrossExcelHeaders(headers) {
  const container = $("crossExcelHeaderList");
  const values = Array.isArray(headers)
    ? headers.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  container.innerHTML = "";
  if (!values.length) {
    container.innerHTML = '<div class="cross-empty-state">扫描目录后会在这里显示全部表头。</div>';
    return;
  }
  values.forEach((header, index) => {
    const label = document.createElement("label");
    label.className = "cross-header-item";
    label.innerHTML = `
      <input type="checkbox" value="${escapeHtml(header)}" />
      <span>${escapeHtml(header)}</span>`;
    container.appendChild(label);
  });
}

function renderCrossExcelScan(data) {
  crossExcelScanState = data || null;
  $("crossExcelFileCount").textContent = Number(data?.file_count || 0);
  $("crossExcelScanHint").textContent = data
    ? `已发现 ${Number(data.file_count || 0)} 个文件，${Number((data.headers || []).length)} 个表头。`
    : "请先选择目录并扫描。";
  renderCrossExcelHeaders(data?.headers || []);
  renderCrossExcelSearchResults(null);
  $("crossExcelSearchHint").textContent = "";
  setCrossExcelOutput("");
}

function renderCrossExcelSearchResults(data) {
  crossExcelSearchState = data || null;
  const items = Array.isArray(data?.items) ? data.items : [];
  $("crossExcelMatchCount").textContent = items.length;
  $("crossExcelScannedRows").textContent = Number(data?.scanned_rows || 0);
  $("crossExcelTruncatedLabel").textContent = !data
    ? "未搜索"
    : data.truncated
      ? "已截断"
      : "已完成";

  const container = $("crossExcelSearchResults");
  container.innerHTML = "";
  if (!data) {
    container.innerHTML = '<div class="cross-empty-state">执行搜索后，这里会显示命中的行。</div>';
    return;
  }
  if (!items.length) {
    container.innerHTML = '<div class="cross-empty-state">没有找到匹配内容。</div>';
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "cross-result-card";
    const matched = new Set(Array.isArray(item.matched_columns) ? item.matched_columns.map((value) => Number(value)) : []);
    const cellsHtml = (Array.isArray(item.row_values) ? item.row_values : []).map((value, index) => `
      <button
        type="button"
        class="cross-cell ${matched.has(index) ? "matched" : ""}"
        data-copy-value="${escapeHtml(String(value || ""))}">
        <span class="cross-cell-index">第 ${index + 1} 列</span>
        <span class="cross-cell-text">${escapeHtml(String(value || "")) || "&nbsp;"}</span>
      </button>`).join("");
    card.innerHTML = `
      <div class="cross-result-meta">
        <span>${escapeHtml(String(item.file_name || ""))}</span>
        <span>${escapeHtml(String(item.sheet_name || ""))}</span>
        <span>第 ${Number(item.row_index || 0)} 行</span>
      </div>
      <div class="cross-row-grid">${cellsHtml}</div>`;
    card.querySelectorAll(".cross-cell").forEach((button) => {
      button.addEventListener("click", async () => {
        await copyToClipboard(button.dataset.copyValue || "");
        $("crossExcelSearchHint").textContent = "已复制单元格内容";
        setTimeout(() => {
          if ($("crossExcelSearchHint").textContent === "已复制单元格内容") {
            $("crossExcelSearchHint").textContent = "";
          }
        }, 1200);
      });
    });
    container.appendChild(card);
  });
}

function renderDiffExcelSummary() {
  const meta = diffExcelState.meta || {};
  $("diffModeLabel").textContent = String(meta.compare_mode_label || meta.mode_label || "未开始");
  $("diffFilesInA").textContent = Number(meta.files_in_a || 0);
  $("diffFilesInB").textContent = Number(meta.files_in_b || 0);
  $("diffMatchedPairs").textContent = Number(meta.matched_pairs || 0);
  $("diffTotalCount").textContent = Number(diffExcelState.totalCount || 0);
  $("diffVisibleCount").textContent = Number(diffExcelState.matchedCount || 0);
  $("diffOutputFile").textContent = diffExcelState.outputFile || "暂无输出";
  $("diffOutputHint").textContent = diffExcelState.outputFile
    ? "差异结果已导出，可以直接打开。"
    : diffExcelState.previewTruncated
      ? `当前只预览前 ${Number(diffExcelState.previewLimit || 1000)} 条，完整结果保存在本地缓存中。`
      : "比对完成后可导出差异结果。";
  $("exportDiffExcelButton").disabled = !diffExcelState.cacheFile || !Number(diffExcelState.totalCount || 0);
  $("highlightDiffExcelButton").disabled = !diffExcelState.cacheFile || !Number(diffExcelState.totalCount || 0);
  $("openDiffOutputFileButton").disabled = !diffExcelState.outputFile;
  $("openDiffOutputFolderButton").disabled = !diffExcelState.outputFile;
}

function diffCompareMode() {
  return $("diffCompareMode").value === "field_match" ? "field_match" : "position";
}

function resetDiffFieldMatchSettings() {
  diffFieldMatchSettings = {
    headers: null,
    referenceField: "",
    compareFields: [],
    includeUnmatched: false,
  };
}

function syncDiffCompareModeUi() {
  const isFieldMatch = diffCompareMode() === "field_match";
  $("openDiffFieldSettingsButton").hidden = !isFieldMatch;
  if (!isFieldMatch) {
    $("diffExcelHint").textContent = "";
  }
}

function renderDiffFieldSettings(data = diffFieldMatchSettings.headers || {}) {
  const commonHeaders = Array.isArray(data.common_headers) ? data.common_headers : [];
  $("diffHeadersACount").textContent = Number((data.headers_a || []).length || 0);
  $("diffHeadersBCount").textContent = Number((data.headers_b || []).length || 0);
  $("diffHeadersCommonCount").textContent = commonHeaders.length;
  $("diffFieldSettingsSummary").textContent = Number(data.matched_pairs || 0)
    ? `已检测到 ${Number(data.matched_pairs || 0)} 对文件，可选择两侧共同存在的表头。`
    : "没有找到可配对的文件，请先检查路径 A 和路径 B。";

  const reference = $("diffReferenceField");
  reference.innerHTML = '<option value="">请选择参考字段</option>';
  commonHeaders.forEach((header) => {
    const option = document.createElement("option");
    option.value = header;
    option.textContent = header;
    option.selected = header === diffFieldMatchSettings.referenceField;
    reference.appendChild(option);
  });

  const list = $("diffCompareFieldList");
  list.innerHTML = "";
  if (!commonHeaders.length) {
    list.innerHTML = '<div class="empty-cell">没有可用的共同表头</div>';
  }
  commonHeaders.forEach((header) => {
    const label = document.createElement("label");
    label.className = "diff-compare-field-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = header;
    checkbox.checked = diffFieldMatchSettings.compareFields.includes(header);
    checkbox.disabled = header === diffFieldMatchSettings.referenceField;
    const text = document.createElement("span");
    text.textContent = header;
    label.append(checkbox, text);
    list.appendChild(label);
  });
  $("diffIncludeUnmatched").checked = Boolean(diffFieldMatchSettings.includeUnmatched);
}

async function openDiffFieldSettings() {
  const pathA = $("diffPathA").value.trim();
  const pathB = $("diffPathB").value.trim();
  if (!pathA || !pathB) {
    $("diffExcelHint").textContent = "请先选择路径 A 和路径 B。";
    return;
  }
  $("diffFieldSettingsHint").textContent = "正在读取表头...";
  $("diffFieldSettingsOverlay").hidden = false;
  const data = await api(`/api/diff-excel/field-match-headers?path_a=${encodeURIComponent(pathA)}&path_b=${encodeURIComponent(pathB)}`, { timeoutMs: 300000 });
  diffFieldMatchSettings.headers = data;
  renderDiffFieldSettings(data);
  $("diffFieldSettingsHint").textContent = "";
}

function closeDiffFieldSettings() {
  $("diffFieldSettingsOverlay").hidden = true;
  $("diffFieldSettingsHint").textContent = "";
}

function saveDiffFieldSettings() {
  const referenceField = $("diffReferenceField").value.trim();
  const compareFields = Array.from(document.querySelectorAll('#diffCompareFieldList input[type="checkbox"]:checked'))
    .map((checkbox) => checkbox.value.trim())
    .filter(Boolean);
  if (!referenceField) {
    $("diffFieldSettingsHint").textContent = "请选择参考字段。";
    return;
  }
  if (!compareFields.length) {
    $("diffFieldSettingsHint").textContent = "请至少选择一个比对字段。";
    return;
  }
  if (compareFields.includes(referenceField)) {
    $("diffFieldSettingsHint").textContent = "参考字段不能同时作为比对字段。";
    return;
  }
  diffFieldMatchSettings.referenceField = referenceField;
  diffFieldMatchSettings.compareFields = compareFields;
  diffFieldMatchSettings.includeUnmatched = $("diffIncludeUnmatched").checked;
  closeDiffFieldSettings();
  $("diffExcelHint").textContent = `已设置参考字段：${referenceField}；已选择 ${compareFields.length} 个比对字段。`;
}

function buildDiffTokens(leftText, rightText) {
  function splitChars(text) {
    return Array.from(String(text || ""));
  }

  function buildLcsMatrix(leftTokens, rightTokens) {
    const rows = leftTokens.length + 1;
    const cols = rightTokens.length + 1;
    const matrix = Array.from({ length: rows }, () => new Uint16Array(cols));
    for (let i = leftTokens.length - 1; i >= 0; i -= 1) {
      for (let j = rightTokens.length - 1; j >= 0; j -= 1) {
        if (leftTokens[i] === rightTokens[j]) {
          matrix[i][j] = matrix[i + 1][j + 1] + 1;
        } else {
          matrix[i][j] = Math.max(matrix[i + 1][j], matrix[i][j + 1]);
        }
      }
    }
    return matrix;
  }

  function tokensToDiffHtml(parts, changedClass) {
    if (!parts.length) {
      return '<span class="diff-inline-empty">无</span>';
    }
    return parts.map((part) => {
      const html = escapeHtml(part.text || "");
      if (!html) {
        return "";
      }
      if (part.changed) {
        return `<span class="diff-token ${changedClass}">${html}</span>`;
      }
      return `<span class="diff-plain-token">${html}</span>`;
    }).join("");
  }

  const leftTokens = splitChars(leftText);
  const rightTokens = splitChars(rightText);
  if (!leftTokens.length && !rightTokens.length) {
    return {
      leftHtml: '<span class="diff-inline-empty">无</span>',
      rightHtml: '<span class="diff-inline-empty">无</span>',
    };
  }

  const matrix = buildLcsMatrix(leftTokens, rightTokens);
  const leftParts = [];
  const rightParts = [];
  let i = 0;
  let j = 0;
  while (i < leftTokens.length && j < rightTokens.length) {
    if (leftTokens[i] === rightTokens[j]) {
      leftParts.push({ text: leftTokens[i], changed: false });
      rightParts.push({ text: rightTokens[j], changed: false });
      i += 1;
      j += 1;
      continue;
    }
    if (matrix[i + 1][j] >= matrix[i][j + 1]) {
      leftParts.push({ text: leftTokens[i], changed: true });
      i += 1;
    } else {
      rightParts.push({ text: rightTokens[j], changed: true });
      j += 1;
    }
  }
  while (i < leftTokens.length) {
    leftParts.push({ text: leftTokens[i], changed: true });
    i += 1;
  }
  while (j < rightTokens.length) {
    rightParts.push({ text: rightTokens[j], changed: true });
    j += 1;
  }

  return {
    leftHtml: tokensToDiffHtml(leftParts, "diff-token-delete"),
    rightHtml: tokensToDiffHtml(rightParts, "diff-token-add"),
  };
}

function renderDiffExcelResults() {
  renderDiffExcelResultHead();
  const body = $("diffExcelBody");
  const records = Array.isArray(diffExcelState.previewRecords) ? diffExcelState.previewRecords : [];
  body.innerHTML = "";
  if (!records.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty-cell">暂无差异结果</td></tr>';
    renderDiffExcelSummary();
    renderDiffPreviewPager();
    return;
  }
  records.forEach((item) => {
    const tr = document.createElement("tr");
    const isFieldMatch = String(item.diff_kind || "") !== "cell";
    const location = isFieldMatch
      ? `${item.reference_field || "参考字段"}：${item.reference_value || ""}${item.compare_field ? `\n比对字段：${item.compare_field}` : ""}`
      : `${item.sheet || ""}\n${item.cell_address || ""}`;
    [item.filename_a || "", item.filename_b || "", isFieldMatch ? `${item.sheet_a || ""}\n${item.sheet_b || ""}` : (item.sheet || ""), location].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value || "");
      tr.appendChild(td);
    });

    const diffTd = document.createElement("td");
    if (String(item.diff_kind || "") === "unmatched_reference") {
      const existsInA = Boolean(item.sheet_a && item.cell_address_a);
      const label = existsInA ? "仅 A 有" : "仅 B 有";
      const side = existsInA ? "A" : "B";
      const style = existsInA ? "diff-inline-delete" : "diff-inline-add";
      diffTd.innerHTML = `
        <div class="diff-inline-card diff-inline-single">
          <div class="diff-inline-side ${style}" title="点击跳转到实际存在的参考字段">
            <div class="diff-inline-label">${label}</div>
            <div class="diff-inline-text">${escapeHtml(String(item.reference_value || ""))}</div>
          </div>
        </div>`;
      diffTd.querySelector(".diff-inline-side").addEventListener("click", () => openDiffExcelCell(item, side));
    } else {
      const tokens = buildDiffTokens(item.value_a || "", item.value_b || "");
      diffTd.innerHTML = `
        <div class="diff-inline-card">
          <div class="diff-inline-side diff-inline-delete" title="点击跳转到文件 A 的对应单元格">
            <div class="diff-inline-label">A 删除</div>
            <div class="diff-inline-text">${tokens.leftHtml}</div>
          </div>
          <div class="diff-inline-side diff-inline-add" title="点击跳转到文件 B 的对应单元格">
            <div class="diff-inline-label">B 添加</div>
            <div class="diff-inline-text">${tokens.rightHtml}</div>
          </div>
        </div>`;
      diffTd.querySelector(".diff-inline-delete").addEventListener("click", () => openDiffExcelCell(item, "A"));
      diffTd.querySelector(".diff-inline-add").addEventListener("click", () => openDiffExcelCell(item, "B"));
    }
    tr.appendChild(diffTd);
    body.appendChild(tr);
  });
  renderDiffExcelSummary();
  renderDiffPreviewPager();
}

function renderDiffExcelResultHead() {
  const head = $("diffExcelHead");
  const isFieldMatch = String(diffExcelState.meta?.compare_mode_label || "") === "按字段匹配";
  const labels = isFieldMatch
    ? ["文件 A", "文件 B", "A / B Sheet", "参考字段与比对字段", "差异对照"]
    : ["文件 A", "文件 B", "Sheet", "单元格", "差异对照"];
  head.innerHTML = "";
  labels.forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    head.appendChild(th);
  });
}

function renderDiffPreviewPager() {
  const total = Number(diffExcelState.matchedCount || 0);
  const limit = Number(diffExcelState.previewLimit || 200);
  const offset = Number(diffExcelState.previewOffset || 0);
  const shown = Array.isArray(diffExcelState.previewRecords) ? diffExcelState.previewRecords.length : 0;
  $("diffPreviewPreviousButton").disabled = offset <= 0;
  $("diffPreviewNextButton").disabled = offset + shown >= total;
  $("diffPreviewPageLabel").textContent = total
    ? `显示 ${offset + 1}-${offset + shown} / ${total}`
    : "暂无结果";
}

async function applyDiffExcelFilter() {
  if (!diffExcelState.cacheFile) {
    diffExcelState.previewRecords = [];
    diffExcelState.matchedCount = 0;
    diffExcelState.previewTruncated = false;
    renderDiffExcelResults();
    return;
  }
  const data = await api(`/api/diff-excel/preview?cache_file=${encodeURIComponent(diffExcelState.cacheFile)}&query=&limit=${encodeURIComponent(String(diffExcelState.previewLimit || 200))}&offset=${encodeURIComponent(String(diffExcelState.previewOffset || 0))}`);
  diffExcelState.previewRecords = Array.isArray(data.records) ? data.records : [];
  diffExcelState.matchedCount = Number(data.matched_count || 0);
  diffExcelState.previewTruncated = Boolean(data.preview_truncated);
  diffExcelState.previewOffset = Number(data.offset || 0);
  renderDiffExcelResults();
}

async function changeDiffPreviewPage(direction) {
  const limit = Number(diffExcelState.previewLimit || 200);
  const nextOffset = Math.max(0, Number(diffExcelState.previewOffset || 0) + (direction * limit));
  if (nextOffset === Number(diffExcelState.previewOffset || 0)) return;
  diffExcelState.previewOffset = nextOffset;
  await applyDiffExcelFilter();
}

function clearDiffExcelState() {
  diffExcelState = {
    cacheFile: "",
    resultId: "",
    previewRecords: [],
    meta: null,
    outputFile: "",
    totalCount: 0,
    matchedCount: 0,
    previewLimit: 200,
    previewOffset: 0,
    taskId: "",
    previewTruncated: false,
  };
  $("diffExcelHint").textContent = "";
  $("diffHighlightHint").textContent = "";
  renderDiffExcelResults();
  setTaskStatus("diffExcelPage", {
    active: false,
    taskLabel: "Diff 工具",
    pill: "空闲",
    pillClass: "",
    stageLabel: "未启动",
    message: "等待开始任务",
  });
  renderCurrentTaskStatus();
}

function refreshDiffPresetColorButtons() {
  const current = String($("diffHighlightColor").value || "#FFD966").toLowerCase();
  document.querySelectorAll(".preset-color-btn").forEach((button) => {
    const color = String(button.dataset.color || "").toLowerCase();
    button.classList.toggle("active", color === current);
    button.style.backgroundColor = color || "#FFD966";
  });
}

async function openDiffExcelCell(item, target) {
  const filePath = target === "A" ? item.file_path_a : item.file_path_b;
  const sheetName = target === "A" ? (item.sheet_a || item.sheet || "") : (item.sheet_b || item.sheet || "");
  const cellAddress = target === "A" ? (item.cell_address_a || item.cell_address || "") : (item.cell_address_b || item.cell_address || "");
  if (!filePath || !sheetName || !cellAddress) {
    $("diffExcelHint").textContent = `文件 ${target} 中没有可跳转的位置。`;
    return;
  }
  await api("/api/diff-excel/open-cell", {
    method: "POST",
    body: JSON.stringify({
      file_path: filePath,
      sheet_name: sheetName,
      cell_address: cellAddress,
    }),
  });
}

function renderAiReviewPreview(items) {
  const body = $("previewBody");
  body.innerHTML = "";
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-cell">暂无预览</td></tr>';
    return;
  }
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    const location = String(item.sheet_name || item.segment_id || "");
    const values = [
      item.source_file || "",
      location,
      item.row_number || "",
      item.source_text || "",
      item.target_text || "",
      item.status_note || "",
    ];
    values.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value || "");
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function setAiReviewFileCard(text = "") {
  const card = $("reviewFilePath");
  const displayText = String(text || "").trim();
  card.textContent = displayText || "请选择待审校文件";
  card.classList.toggle("empty", !displayText);
}

function initializeAiReviewExcelMapping(data) {
  aiReviewSheetNames = Array.isArray(data?.sheet_names) ? data.sheet_names : [];
  aiReviewColumnsBySheet = data?.columns_by_sheet || {};
  aiReviewActiveSheetName = aiReviewSheetNames[0] || "";
  aiReviewExcelMappingState = {};
  aiReviewMappingTemplateIssues = [];
  aiReviewSheetNames.forEach((sheetName) => {
    aiReviewExcelMappingState[sheetName] = { sources: [], targets: {}, infos: {} };
  });
  if ($("excelMappingPresetSelect")) {
    $("excelMappingPresetSelect").value = "";
  }
  if ($("excelMappingPresetHint")) {
    $("excelMappingPresetHint").textContent = "";
  }
  $("excelMappingSummary").textContent = "";
}

function renderAiReviewBatch(data) {
  const batch = data?.batch || null;
  aiReviewBatch = batch;
  const isExcel = String(batch?.file_type || "") === "excel";
  $("reviewBatchCount").textContent = Number(batch?.item_count || 0);
  $("reviewFileHint").textContent = data?.message || "尚未读取文件。";
  $("openExcelMappingButton").disabled = !isExcel;
  setAiReviewFileCard(batch?.metadata?.original_file_path || batch?.filename || "");
  $("sourceLanguageInput").value = String(batch?.source_language || $("sourceLanguageInput").value || "");
  $("targetLanguageInput").value = String(batch?.target_language || $("targetLanguageInput").value || "");
  const excelMapping = batch?.metadata?.excel_mapping || null;
  if (excelMapping) {
    $("excelMappingSummary").textContent = summarizeAiReviewExcelMapping(excelMapping);
  } else if (!isExcel) {
    $("excelMappingSummary").textContent = "";
  }
  if (isExcel && !excelMapping) {
    $("openExcelMappingButton").disabled = !aiReviewSheetNames.length;
  }
  if (isExcel && !excelMapping) {
    renderAiReviewPreview([]);
    return;
  }
  renderAiReviewPreview(data?.preview || []);
}

function setAiReviewTaskStatus(nextState = {}) {
  const pages = ["aiReviewTaskPage", "aiReviewSettingsPage", "aiReviewForbiddenPage"];
  pages.forEach((pageId) => {
    setTaskStatus(pageId, {
      taskLabel: "AI 审校工具",
      ...nextState,
    });
  });
  renderCurrentTaskStatus();
}

function updateAiReviewModeVisibility() {
  const enableAi = $("enableAiReview").checked;
  const enableDirectional = enableAi && $("enableDirectionalReview").checked;
  $("enableDirectionalReview").disabled = !enableAi;
  $("directionalReviewLine").classList.toggle("disabled-line", !enableAi);
  $("directionalTemplatePanel").classList.toggle("hidden", !enableDirectional);
  $("promptTemplateSelect").disabled = !enableAi || enableDirectional;
  $("directionalTemplateSelect").disabled = !enableDirectional;
}

function renderAiReviewPromptTemplateOptions() {
  const select = $("promptTemplateSelect");
  select.innerHTML = "";
  const dialogSelect = $("promptDialogTemplateSelect");
  if (dialogSelect) dialogSelect.innerHTML = "";
  aiReviewPromptTemplates.forEach((item) => {
    select.appendChild(new Option(String(item.name || ""), String(item.id || "")));
    if (dialogSelect) dialogSelect.appendChild(new Option(String(item.name || ""), String(item.id || "")));
  });
  if (!reviewConversationState.promptTemplateId && aiReviewPromptTemplates.length) {
    reviewConversationState.promptTemplateId = String(aiReviewPromptTemplates[0].id || "");
  }
  if ($("reviewPromptChip")) updateReviewComposerChips();
}

function renderAiReviewDirectionalTemplateOptions() {
  const select = $("directionalTemplateSelect");
  select.innerHTML = "";
  aiReviewDirectionalTemplates.forEach((item) => {
    select.appendChild(new Option(String(item.name || ""), String(item.id || "")));
  });
  updateAiReviewModeVisibility();
}

function renderAiReviewForbiddenTemplateOptions() {
  const select = $("forbiddenTemplateSelect");
  select.innerHTML = "";
  aiReviewForbiddenTemplates.forEach((item) => {
    select.appendChild(new Option(String(item.name || ""), String(item.id || "")));
  });
}

function clearAiReviewTaskHint() {
  $("reviewTaskHint").textContent = "";
  aiReviewIssueResults = [];
  aiReviewFollowupState = { taskId: "", resultId: "", item: null, messages: [] };
  closeReviewFollowupDialog();
}

function renderAiReviewProgress(task = {}) {
  const total = Math.max(0, Number(task.progress_total ?? task.total_count ?? 0));
  const current = Math.max(0, Number(task.progress_current ?? task.completed_count ?? 0));
  const safeCurrent = total > 0 ? Math.min(current, total) : current;
  const percent = total > 0 ? Math.min(100, Math.max(0, Math.round((safeCurrent / total) * 100))) : 0;
  const isActive = ["pending", "running"].includes(String(task.status || ""));
  $("reviewProgress").textContent = String(task.status_label || task.status || "尚未开始");
  $("reviewProgressPercent").textContent = total > 0 ? `${percent}%` : isActive ? "0%" : "未开始";
  $("reviewProgressCount").textContent = `${safeCurrent} / ${total}${Number(task.cached_count || 0) ? ` · 缓存命中 ${Number(task.cached_count)} 条` : ''}`;
  $("reviewFailedCount").textContent = Number(task.failed_count || 0);
  $("reviewRequestedCount").textContent = Number(task.requested_count || 0);
  $("reviewProgressBar").style.width = total > 0 ? `${percent}%` : "0";
}

const REVIEW_REQUEST_STATUS_LANES = [
  ["queued", "排队中"],
  ["submitted", "已提交"],
  ["thinking", "思考中"],
  ["output", "输出中"],
  ["retrying", "等待重试"],
  ["completed", "已完成"],
  ["failed", "失败"],
];

function renderReviewRequestQueue(task = {}) {
  const root = $("reviewRequestQueue");
  const columns = $("reviewRequestColumns");
  const summary = $("reviewRequestQueueSummary");
  if (!root || !columns || !summary) return;
  const states = Array.isArray(task?.request_states) ? task.request_states : [];
  root.classList.toggle("hidden", !task?.id || !states.length);
  columns.innerHTML = "";
  if (!states.length) {
    summary.textContent = task?.id ? "正在创建请求包…" : "等待创建请求";
    return;
  }
  const totalItems = states.reduce((sum, item) => sum + Math.max(0, Number(item.item_count || 0)), 0);
  const completedRequests = states.filter((item) => String(item.status || "queued") === "completed").length;
  summary.textContent = `已完成 ${completedRequests} / ${states.length} 个请求 · ${totalItems} 条`;
  REVIEW_REQUEST_STATUS_LANES.forEach(([status, label]) => {
    const items = states.filter((item) => String(item.status || "queued") === status);
    if (!items.length && status === "failed") return;
    const lane = document.createElement("section");
    lane.className = `review-request-lane status-${status}`;
    const head = document.createElement("div");
    head.className = "review-request-lane-head";
    const heading = document.createElement("strong");
    heading.textContent = label;
    const count = document.createElement("span");
    count.textContent = status === "completed" ? `${items.length} / ${states.length}` : String(items.length);
    head.append(heading, count);
    const body = document.createElement("div");
    body.className = "review-request-items";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "review-request-empty";
      empty.textContent = "—";
      body.appendChild(empty);
    } else {
      items.slice(0, 3).forEach((item) => {
        const entry = document.createElement("div");
        entry.className = "review-request-item";
        const title = document.createElement("strong");
        title.textContent = `请求 ${item.package_index}/${item.package_total} · ${item.item_count} 条`;
        const location = document.createElement("span");
        location.title = String(item.location || "待审校单元");
        location.textContent = location.title;
        entry.append(title, location);
        if (Number(item.attempt_count || 0) > 1) {
          const retry = document.createElement("em");
          retry.textContent = `第 ${item.attempt_count} 次请求`;
          entry.appendChild(retry);
        }
        body.appendChild(entry);
      });
      if (items.length > 3) {
        const more = document.createElement("div");
        more.className = "review-request-more";
        more.textContent = `另有 ${items.length - 3} 个请求，已折叠显示`;
        body.appendChild(more);
      }
    }
    lane.append(head, body);
    columns.appendChild(lane);
  });
}

function summarizeAiReviewExcelMapping(mapping) {
  const sheets = Array.isArray(mapping?.sheets) ? mapping.sheets : [];
  const count = sheets.reduce((total, sheet) => total + Number((sheet.mappings || []).length || 0), 0);
  return count > 0 ? `已配置 ${count} 组原文 / 译文列` : "";
}

function renderAiReviewExcelMappingPresets() {
  const select = $("excelMappingPresetSelect");
  const selectedId = String(select.value || "");
  select.innerHTML = "";
  select.appendChild(new Option("选择模板", ""));
  aiReviewExcelMappingPresets.forEach((item) => {
    const option = new Option(String(item.name || ""), String(item.id || ""));
    option.title = String(item.name || "");
    select.appendChild(option);
  });
  select.value = selectedId;
  $("deleteExcelMappingPresetButton").disabled = !select.value;
}

async function loadAiReviewExcelMappingPresets(selectedId = "") {
  const data = await api("/api/ai-review/excel-mapping-presets");
  aiReviewExcelMappingPresets = Array.isArray(data.presets) ? data.presets : [];
  renderAiReviewExcelMappingPresets();
  if (selectedId) {
    $("excelMappingPresetSelect").value = String(selectedId);
  }
  $("deleteExcelMappingPresetButton").disabled = !$("excelMappingPresetSelect").value;
}

function excelMappingColumnLetter(columnIndex) {
  let value = Number(columnIndex) + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result || "?";
}

function renderAiReviewMappingTemplateIssues() {
  const hint = $("excelMappingPresetHint");
  hint.textContent = aiReviewMappingTemplateIssues.join(" ");
}

function clearAiReviewMappingTemplateIssues() {
  if (!aiReviewMappingTemplateIssues.length) return;
  aiReviewMappingTemplateIssues = [];
  renderAiReviewMappingTemplateIssues();
}

function aiReviewColumnLabel(sheetName, columnIndex) {
  const columns = Array.isArray(aiReviewColumnsBySheet[sheetName]) ? aiReviewColumnsBySheet[sheetName] : [];
  const column = columns.find((item) => Number(item.index) === Number(columnIndex));
  if (!column) {
    return `第 ${Number(columnIndex) + 1} 列`;
  }
  return `${column.letter || ""}${column.header ? ` ${column.header}` : ""}`.trim();
}

function syncAiReviewActiveSheetMapping() {
  const sheetName = aiReviewActiveSheetName;
  if (!sheetName) return;
  const sources = [];
  const targets = {};
  const infos = {};
  $("excelMappingColumns").querySelectorAll(".mapping-row").forEach((row) => {
    const columnIndex = Number(row.dataset.columnIndex || 0);
    if (row.querySelector(".mapping-source").checked) {
      sources.push(columnIndex);
    }
    const targetValue = row.querySelector(".mapping-target").value;
    if (targetValue !== "") {
      targets[columnIndex] = Number(targetValue);
    }
    const infoValue = row.querySelector(".mapping-info").value;
    if (infoValue !== "" && targetValue === "") {
      infos[columnIndex] = {
        sourceColumns: [Number(infoValue)],
        category: row.querySelector(".mapping-info-category").value.trim(),
      };
    }
  });
  aiReviewExcelMappingState[sheetName] = { sources, targets, infos, languages: aiReviewExcelMappingState[sheetName]?.languages || {} };
}

function renderAiReviewExcelSheetTabs() {
  const container = $("excelSheetTabs");
  container.innerHTML = "";
  aiReviewSheetNames.forEach((sheetName) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `sheet-tab ${sheetName === aiReviewActiveSheetName ? "active" : ""}`.trim();
    button.textContent = String(sheetName || "");
    button.addEventListener("click", () => {
      clearAiReviewTaskHint();
      syncAiReviewActiveSheetMapping();
      aiReviewActiveSheetName = sheetName;
      renderAiReviewExcelMappingDialog();
    });
    container.appendChild(button);
  });
}

function renderAiReviewExcelMappingColumns() {
  const sheetName = aiReviewActiveSheetName;
  const columns = Array.isArray(aiReviewColumnsBySheet[sheetName]) ? aiReviewColumnsBySheet[sheetName] : [];
  const sheetState = aiReviewExcelMappingState[sheetName] || { sources: [], targets: {}, infos: {} };
  const container = $("excelMappingColumns");
  container.innerHTML = "";
  if (!columns.length) {
    container.innerHTML = '<div class="cross-empty-state">当前 sheet 没有可用列。</div>';
    return;
  }
  columns.forEach((column) => {
    const row = document.createElement("div");
    row.className = "mapping-row";
    row.dataset.columnIndex = String(column.index);
    const sourceChecked = Array.isArray(sheetState.sources) && sheetState.sources.includes(column.index);
    const targetValue = sheetState.targets[column.index] === undefined ? "" : String(sheetState.targets[column.index]);
    const infoValue = sheetState.infos[column.index]?.sourceColumns?.[0] === undefined
      ? ""
      : String(sheetState.infos[column.index].sourceColumns[0]);
    row.innerHTML = `
      <div class="mapping-col-id">${escapeHtml(String(column.letter || ""))}</div>
      <div class="mapping-header">${escapeHtml(String(column.header || ""))}</div>
      <label class="check-line"><input class="mapping-source" type="checkbox" ${sourceChecked ? "checked" : ""} /><span>原文</span></label>
      <select class="mapping-target"><option value="">非译文列</option></select>
      <select class="mapping-info"><option value="">非信息列</option></select>
      <input class="mapping-info-category" type="text" placeholder="信息类别" value="${escapeHtml(String(sheetState.infos[column.index]?.category || ""))}" />`;
    const targetSelect = row.querySelector(".mapping-target");
    const infoSelect = row.querySelector(".mapping-info");
    const sourceList = Array.isArray(sheetState.sources) ? sheetState.sources : [];
    sourceList.forEach((sourceIndex) => {
      targetSelect.appendChild(new Option(`译文 -> ${aiReviewColumnLabel(sheetName, sourceIndex)}`, String(sourceIndex)));
      infoSelect.appendChild(new Option(`信息 -> ${aiReviewColumnLabel(sheetName, sourceIndex)}`, String(sourceIndex)));
    });
    targetSelect.value = targetValue;
    infoSelect.value = infoValue;
    targetSelect.disabled = !sourceList.length || sourceChecked;
    infoSelect.disabled = !sourceList.length || sourceChecked;
    const categoryInput = row.querySelector(".mapping-info-category");
    categoryInput.disabled = infoSelect.disabled || !infoSelect.value;
    row.querySelector(".mapping-source").addEventListener("change", () => {
      if (row.querySelector(".mapping-source").checked) { targetSelect.value = ""; infoSelect.value = ""; }
      clearAiReviewTaskHint();
      clearAiReviewMappingTemplateIssues();
      syncAiReviewActiveSheetMapping();
      renderAiReviewExcelMappingDialog();
      if (aiReviewExcelMappingState[sheetName].sources.includes(column.index)) openColumnLanguageDialog(sheetName, column.index);
    });
    targetSelect.addEventListener("change", () => {
      clearAiReviewTaskHint();
      clearAiReviewMappingTemplateIssues();
      if (targetSelect.value !== "") {
        infoSelect.value = "";
        categoryInput.disabled = true;
      }
      syncAiReviewActiveSheetMapping();
      renderAiReviewExcelMappingDialog();
      if (aiReviewExcelMappingState[sheetName].targets[column.index] !== undefined) openColumnLanguageDialog(sheetName, column.index);
    });
    infoSelect.addEventListener("change", () => {
      clearAiReviewTaskHint();
      clearAiReviewMappingTemplateIssues();
      if (infoSelect.value !== "") {
        targetSelect.value = "";
        categoryInput.disabled = false;
      } else {
        categoryInput.disabled = infoSelect.disabled;
      }
      syncAiReviewActiveSheetMapping();
      renderAiReviewExcelMappingDialog();
    });
    categoryInput.addEventListener("input", () => {
      clearAiReviewTaskHint();
      clearAiReviewMappingTemplateIssues();
      syncAiReviewActiveSheetMapping();
      $("applyExcelMappingButton").disabled = validateAiReviewExcelMapping(buildAiReviewExcelMapping()).length > 0;
    });
    const language = document.createElement("button");
    language.type = "button"; language.className = "secondary mapping-column-language";
    const chosen = sheetState.languages?.[column.index] || (sourceChecked ? $("mappingSourceLanguageInput").value : $("mappingTargetLanguageInput").value) || "auto";
    language.textContent = "语种：" + (chosen === "auto" ? "自动检测" : chosen);
    language.disabled = !sourceChecked && targetValue === "";
    language.addEventListener("click", () => openColumnLanguageDialog(sheetName, column.index));
    row.appendChild(language);
    container.appendChild(row);
  });
}

function renderAiReviewExcelMappingDialog() {
  renderAiReviewExcelSheetTabs();
  renderAiReviewExcelMappingColumns();
  renderAiReviewMappingTemplateIssues();
  const mapping = buildAiReviewExcelMapping();
  $("applyExcelMappingButton").disabled = validateAiReviewExcelMapping(mapping).length > 0;
}

function buildAiReviewExcelMapping() {
  syncAiReviewActiveSheetMapping();
  const sheets = aiReviewSheetNames.map((sheetName) => {
    const sheetState = aiReviewExcelMappingState[sheetName] || { sources: [], targets: {}, infos: {} };
    const mappings = [...new Set(sheetState.sources || [])].flatMap((sourceColumn) => {
      const targetEntries = Object.entries(sheetState.targets || {}).filter(([, sourceIndex]) => Number(sourceIndex) === Number(sourceColumn));
      const infoColumns = Object.entries(sheetState.infos || {})
        .filter(([, info]) => Array.isArray(info.sourceColumns) && info.sourceColumns.includes(sourceColumn))
        .map(([column, info]) => ({ column: Number(column), category: String(info.category || "") }));
      return (targetEntries.length ? targetEntries : [null]).map(targetEntry => ({
        source_column: Number(sourceColumn),
        target_column: targetEntry ? Number(targetEntry[0]) : null,
        source_language: sheetState.languages?.[sourceColumn] || $("mappingSourceLanguageInput").value.trim() || "auto",
        target_language: (targetEntry && sheetState.languages?.[targetEntry[0]]) || $("mappingTargetLanguageInput").value.trim() || "auto",
        info_columns: infoColumns,
      }));
    });
    return { sheet_name: sheetName, mappings };
  });
  return {
    source_language: $("mappingSourceLanguageInput").value.trim(),
    target_language: $("mappingTargetLanguageInput").value.trim(),
    sheets,
  };
}

function validateAiReviewExcelMapping(mapping, { includeTemplateIssues = true } = {}) {
  const errors = includeTemplateIssues ? [...aiReviewMappingTemplateIssues] : [];
  (mapping.sheets || []).forEach((sheet) => {
    const usedTargets = new Set();
    (sheet.mappings || []).forEach((item) => {
      const label = aiReviewColumnLabel(sheet.sheet_name, item.source_column);
      if (item.target_column === null || item.target_column === undefined) {
        errors.push(`${sheet.sheet_name} 的 ${label} 缺少译文列`);
      } else if (usedTargets.has(item.target_column)) {
        errors.push(`${sheet.sheet_name} 的 ${aiReviewColumnLabel(sheet.sheet_name, item.target_column)} 被多个原文列共用`);
      } else if (item.target_column === item.source_column) {
        errors.push(`${sheet.sheet_name} 的 ${label} 不能同时作为译文列`);
      }
      (item.info_columns || []).forEach((info) => {
        if (info.column === item.target_column) {
          errors.push(`${sheet.sheet_name} 的 ${aiReviewColumnLabel(sheet.sheet_name, info.column)} 不能同时作为译文列和信息列`);
        }
        if (info.column === item.source_column) {
          errors.push(`${sheet.sheet_name} 的 ${aiReviewColumnLabel(sheet.sheet_name, info.column)} 不能同时作为原文列和信息列`);
        }
      });
      usedTargets.add(item.target_column);
    });
  });
  if (!(mapping.sheets || []).some((sheet) => Array.isArray(sheet.mappings) && sheet.mappings.length)) {
    errors.push("请至少选择一组原文列和译文列");
  }
  return errors;
}

function applyAiReviewExcelMappingPresetToState(mapping) {
  $("mappingSourceLanguageInput").value = String(mapping?.source_language || "");
  $("mappingTargetLanguageInput").value = String(mapping?.target_language || "");
  const issues = [];
  const nextState = {};
  aiReviewSheetNames.forEach((sheetName) => {
    nextState[sheetName] = { sources: [], targets: {}, infos: {} };
  });
  (mapping?.sheets || []).forEach((sheet, sheetIndex) => {
    const sheetName = aiReviewSheetNames[sheetIndex];
    if (!sheetName) {
      issues.push(`模板需要第 ${sheetIndex + 1} 个工作表，当前文件只有 ${aiReviewSheetNames.length} 个工作表。`);
      return;
    }
    const validColumns = new Set((aiReviewColumnsBySheet[sheetName] || []).map((column) => Number(column.index)));
    (sheet.mappings || []).forEach((item) => {
      const sourceColumn = Number(item.source_column);
      const targetColumn = Number(item.target_column);
      if (!validColumns.has(sourceColumn)) {
        issues.push(`第 ${sheetIndex + 1} 个工作表缺少模板需要的 ${excelMappingColumnLetter(sourceColumn)} 列。`);
        return;
      }
      if (!validColumns.has(targetColumn)) {
        issues.push(`第 ${sheetIndex + 1} 个工作表缺少模板需要的 ${excelMappingColumnLetter(targetColumn)} 列。`);
        return;
      }
      if (!nextState[sheetName].sources.includes(sourceColumn)) nextState[sheetName].sources.push(sourceColumn);
      nextState[sheetName].languages ||= {};
      nextState[sheetName].languages[sourceColumn] = item.source_language || mapping.source_language || "auto";
      nextState[sheetName].languages[targetColumn] = item.target_language || mapping.target_language || "auto";
      nextState[sheetName].targets[targetColumn] = sourceColumn;
      (item.info_columns || []).forEach((info) => {
        const infoColumn = Number(info.column);
        if (!validColumns.has(infoColumn)) {
          issues.push(`第 ${sheetIndex + 1} 个工作表缺少模板需要的 ${excelMappingColumnLetter(infoColumn)} 列。`);
          return;
        }
        const current = nextState[sheetName].infos[infoColumn] || { sourceColumns: [], category: String(info.category || "") };
        if (!current.sourceColumns.includes(sourceColumn)) {
          current.sourceColumns.push(sourceColumn);
        }
        if (info.category && !current.category) {
          current.category = String(info.category);
        }
        nextState[sheetName].infos[infoColumn] = current;
      });
    });
  });
  aiReviewExcelMappingState = nextState;
  aiReviewMappingTemplateIssues = [...new Set(issues)];
}

async function openAiReviewExcelMappingDialog() {
  if (!aiReviewBatch?.id || !aiReviewSheetNames.length) {
    throw new Error("请先读取 Excel 文件");
  }
  clearAiReviewTaskHint();
  await loadAiReviewExcelMappingPresets();
  reviewConversationState.mappingEditorContext = "legacy";
  reviewConversationState.mappingEditorAttachmentId = "";
  reviewConversationState.mappingEditorPresetId = "";
  reviewConversationState.mappingEditorApplyAfterSave = false;
  $("excelMappingDialogTitle").textContent = "Excel 映射";
  $("excelMappingDialogSubtitle").textContent = "按工作表选择原文列、译文列和信息列。";
  $("applyExcelMappingButton").textContent = "确认读取";
  $("mappingSourceLanguageInput").value = $("sourceLanguageInput").value || "";
  $("mappingTargetLanguageInput").value = $("targetLanguageInput").value || "";
  renderAiReviewExcelMappingDialog();
  $("excelMappingDialog").showModal();
}

async function applyAiReviewExcelMapping() {
  if (reviewConversationState.mappingEditorContext === "conversation") {
    const mapping = buildAiReviewExcelMapping();
    const errors = validateAiReviewExcelMapping(mapping);
    if (errors.length) throw new Error(errors[0]);
    await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/attachments/${encodeURIComponent(reviewConversationState.mappingEditorAttachmentId)}`, {
      method: "PATCH", body: JSON.stringify({mode: "preset", mapping}),
    });
    $("excelMappingDialog").close();
    await refreshCurrentReviewConversation();
    return;
  }
  if (!aiReviewBatch?.id) {
    throw new Error("请先读取 Excel 文件");
  }
  const mapping = buildAiReviewExcelMapping();
  const errors = validateAiReviewExcelMapping(mapping);
  if (errors.length) {
    throw new Error(errors[0]);
  }
  const data = await api("/api/ai-review/select-excel-mapping", {
    method: "POST",
    body: JSON.stringify({
      batch_id: aiReviewBatch.id,
      mapping,
    }),
  });
  $("sourceLanguageInput").value = mapping.source_language || "";
  $("targetLanguageInput").value = mapping.target_language || "";
  $("excelMappingSummary").textContent = summarizeAiReviewExcelMapping(mapping);
  $("excelMappingDialog").close();
  clearAiReviewTaskHint();
  renderAiReviewBatch(data);
}

function openAiReviewExcelMappingPresetDialog() {
  const mapping = buildAiReviewExcelMapping();
  const errors = validateAiReviewExcelMapping(mapping, { includeTemplateIssues: false });
  if (errors.length) {
    throw new Error(errors[0]);
  }
  $("excelMappingPresetNameInput").value = "";
  $("excelMappingPresetSaveHint").textContent = "";
  $("excelMappingPresetDialog").showModal();
  $("excelMappingPresetNameInput").focus();
}

async function saveAiReviewExcelMappingPreset() {
  const mapping = buildAiReviewExcelMapping();
  const errors = validateAiReviewExcelMapping(mapping, { includeTemplateIssues: false });
  if (errors.length) {
    throw new Error(errors[0]);
  }
  const name = $("excelMappingPresetNameInput").value.trim();
  if (!name) {
    throw new Error("请输入模板名称");
  }
  const existing = aiReviewExcelMappingPresets.find((item) => String(item.name || "").trim().toLowerCase() === name.toLowerCase());
  let presetId = null;
  if (existing) {
    if (!window.confirm(`已存在“${existing.name}”，是否覆盖？`)) {
      return;
    }
    presetId = String(existing.id || "") || null;
  }
  const data = await api("/api/ai-review/excel-mapping-presets", {
    method: "POST",
    body: JSON.stringify({
      id: presetId,
      name,
      mapping,
    }),
  });
  const savedId = String(data?.preset?.id || "");
  reviewConversationState.mappingEditorPresetId = savedId;
  await loadAiReviewExcelMappingPresets(savedId);
  $("excelMappingPresetDialog").close();
  $("excelMappingPresetHint").textContent = "映射模板已保存。";
  if (reviewConversationState.mappingEditorContext === "conversation" && reviewConversationState.mappingEditorApplyAfterSave) {
    reviewConversationState.mappingEditorApplyAfterSave = false;
    await configureConversationAttachmentWithPreset(savedId);
  }
}

async function configureConversationAttachmentWithPreset(presetId) {
  const attachmentId = reviewConversationState.mappingEditorAttachmentId;
  if (!attachmentId || !presetId) throw new Error("映射附件或模板无效");
  await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/attachments/${encodeURIComponent(attachmentId)}`, {
    method: "PATCH",
    body: JSON.stringify({ mode: "preset", preset_id: presetId }),
  });
  $("excelMappingDialog").close();
  reviewConversationState.mappingEditorContext = "";
  reviewConversationState.mappingEditorAttachmentId = "";
  reviewConversationState.mappingEditorPresetId = "";
  await refreshCurrentReviewConversation();
}

async function applyAiReviewExcelMappingPreset() {
  const presetId = $("excelMappingPresetSelect").value;
  $("deleteExcelMappingPresetButton").disabled = !presetId;
  if (!presetId) {
    clearAiReviewMappingTemplateIssues();
    return;
  }
  const data = await api(`/api/ai-review/excel-mapping-presets/${encodeURIComponent(presetId)}`);
  applyAiReviewExcelMappingPresetToState(data?.preset?.mapping || {});
  renderAiReviewExcelMappingDialog();
}

async function deleteAiReviewExcelMappingPreset() {
  const presetId = $("excelMappingPresetSelect").value;
  if (!presetId) return;
  if (!window.confirm("确定删除这个映射模板吗？")) {
    return;
  }
  await api(`/api/ai-review/excel-mapping-presets/${encodeURIComponent(presetId)}`, {
    method: "DELETE",
  });
  await loadAiReviewExcelMappingPresets();
  $("excelMappingPresetHint").textContent = "映射模板已删除。";
}

function fillAiReviewPromptDialog(template = {}) {
  $("promptTemplateId").value = String(template.id || "");
  $("promptNameInput").value = String(template.name || "");
  $("systemPromptInput").value = String(template.system_prompt || "");
  $("userPromptInput").value = String(template.user_prompt || "");
  $("promptForbiddenWordsInput").value = String(template.forbidden_words_text || "");
  $("promptDialogTemplateSelect").value = String(template.id || "");
  $("deletePromptButton").disabled = Boolean(template.is_default) || !template.id;
}

async function openAiReviewPromptDialog() {
  const templateId = $("promptTemplateSelect").value;
  if (!templateId) {
    return;
  }
  const data = await api(`/api/ai-review/prompt-templates/${encodeURIComponent(templateId)}`);
  fillAiReviewPromptDialog(data.template || {});
  $("promptDialog").showModal();
}

function newAiReviewPromptTemplate() {
  const defaultTemplate = aiReviewPromptTemplates.find((item) => item.is_default) || aiReviewPromptTemplates[0] || {};
  fillAiReviewPromptDialog({
    id: "",
    name: "新建模板",
    // A new template starts from the proven complete schema rather than a bare
    // {text} placeholder, so users can edit review rules without reconstructing
    // the JSON contract themselves.
    system_prompt: String(defaultTemplate.system_prompt || ""),
    user_prompt: String(defaultTemplate.user_prompt || "{text}"),
    forbidden_words_text: "",
    is_default: false,
  });
}

async function saveAiReviewPromptTemplate() {
  const data = await api("/api/ai-review/prompt-templates", {
    method: "POST",
    body: JSON.stringify({
      id: $("promptTemplateId").value || null,
      name: $("promptNameInput").value || "未命名模板",
      system_prompt: $("systemPromptInput").value,
      user_prompt: $("userPromptInput").value,
      forbidden_words_text: $("promptForbiddenWordsInput").value,
    }),
  });
  await loadAiReviewPromptTemplates();
  $("promptTemplateSelect").value = String(data?.template?.id || "");
  reviewConversationState.promptTemplateId = String(data?.template?.id || reviewConversationState.promptTemplateId || "");
  updateReviewComposerChips();
  await saveReviewConversationComposerSettings();
  $("promptDialog").close();
  $("reviewSettingsHint").textContent = data.message || "提示词模板已保存";
}

async function resetAiReviewPromptTemplate() {
  const data = await api("/api/ai-review/prompt-templates/reset-default", {
    method: "POST",
    body: "{}",
  });
  await loadAiReviewPromptTemplates();
  $("promptTemplateSelect").value = String(data?.template?.id || $("promptTemplateSelect").value || "");
  fillAiReviewPromptDialog(data.template || {});
}

async function deleteAiReviewPromptTemplate() {
  const templateId = $("promptTemplateId").value;
  if (!templateId) {
    return;
  }
  if (!window.confirm("确定删除这个提示词模板吗？")) {
    return;
  }
  const data = await api(`/api/ai-review/prompt-templates/${encodeURIComponent(templateId)}`, {
    method: "DELETE",
  });
  await loadAiReviewPromptTemplates();
  const fallbackId = String(data?.fallback_template?.id || aiReviewPromptTemplates[0]?.id || "");
  reviewConversationState.promptTemplateId = fallbackId;
  if (reviewConversationState.snapshot?.session) {
    reviewConversationState.snapshot.session.prompt_template_id = fallbackId || null;
  }
  if ($("promptTemplateSelect")) $("promptTemplateSelect").value = fallbackId;
  updateReviewComposerChips();
  renderReviewConversationList();
  $("promptDialog").close();
}

function renderDirectionalEditorItems(items) {
  const container = $("directionalItems");
  container.innerHTML = "";
  const rows = Array.isArray(items) ? items : [];
  rows.forEach((item) => {
    const row = document.createElement("label");
    row.className = "directional-item";
    row.innerHTML = `
      <input type="checkbox" ${item.enabled !== false ? "checked" : ""} />
      <input type="text" value="${escapeHtml(String(item.name || ""))}" placeholder="输入审校项名称" />`;
    container.appendChild(row);
  });
}

function appendDirectionalEditorItem(name = "", enabled = true) {
  const current = Array.from($("directionalItems").querySelectorAll(".directional-item")).map((row) => ({
    enabled: row.querySelector('input[type="checkbox"]').checked,
    name: row.querySelector('input[type="text"]').value,
  }));
  current.push({ name, enabled });
  renderDirectionalEditorItems(current);
}

function fillDirectionalDialog(template = {}) {
  $("directionalTemplateId").value = String(template.id || "");
  $("directionalNameInput").value = String(template.name || "");
  renderDirectionalEditorItems(template.items || []);
}

async function openDirectionalDialog() {
  const templateId = $("directionalTemplateSelect").value;
  if (!templateId) {
    return;
  }
  const data = await api(`/api/ai-review/directional-templates/${encodeURIComponent(templateId)}`);
  fillDirectionalDialog(data.template || {});
  $("directionalDialog").showModal();
}

function newDirectionalTemplate() {
  fillDirectionalDialog({
    id: "",
    name: "新建定向模板",
    items: [{ name: "", enabled: true }],
  });
}

async function saveDirectionalTemplateFromDialog() {
  const items = Array.from($("directionalItems").querySelectorAll(".directional-item")).map((row) => ({
    enabled: row.querySelector('input[type="checkbox"]').checked,
    name: row.querySelector('input[type="text"]').value,
  }));
  const data = await api("/api/ai-review/directional-templates", {
    method: "POST",
    body: JSON.stringify({
      id: $("directionalTemplateId").value || null,
      name: $("directionalNameInput").value || "未命名定向模板",
      items,
    }),
  });
  await loadAiReviewDirectionalTemplates();
  $("directionalTemplateSelect").value = String(data?.template?.id || "");
  $("directionalDialog").close();
  $("reviewSettingsHint").textContent = data.message || "定向模板已保存";
}

function fillForbiddenDialog(template = {}) {
  $("forbiddenTemplateId").value = String(template.id || "");
  $("forbiddenNameInput").value = String(template.name || "");
  $("forbiddenWordsInput").value = String(template.words_text || "");
}

async function openForbiddenDialog() {
  const templateId = $("forbiddenTemplateSelect").value;
  if (!templateId) {
    return;
  }
  const data = await api(`/api/ai-review/forbidden-templates/${encodeURIComponent(templateId)}`);
  fillForbiddenDialog(data.template || {});
  $("forbiddenDialog").showModal();
}

function newForbiddenTemplate() {
  fillForbiddenDialog({
    id: "",
    name: "新建禁用词模板",
    words_text: "",
  });
}

async function saveForbiddenTemplateFromDialog() {
  const data = await api("/api/ai-review/forbidden-templates", {
    method: "POST",
    body: JSON.stringify({
      id: $("forbiddenTemplateId").value || null,
      name: $("forbiddenNameInput").value || "未命名禁用词模板",
      words_text: $("forbiddenWordsInput").value,
    }),
  });
  await loadAiReviewForbiddenTemplates();
  $("forbiddenTemplateSelect").value = String(data?.template?.id || "");
  $("forbiddenDialog").close();
  $("reviewForbiddenHint").textContent = data.message || "禁用词模板已保存";
}

function renderAiReviewResults(task, results) {
  aiReviewCurrentTask = task || null;
  renderAiReviewResultHead(task || {});
  const outputFile = String(task?.output_path || task?.output_file || "");
  renderAiReviewProgress(task || {});
  renderReviewRequestQueue(task || {});
  $("outputPath").textContent = outputFile || "暂无输出";
  $("outputPanel").classList.toggle("hidden", !outputFile);
  $("openOutputFileButton").disabled = !outputFile;
  $("openReviewDetailButton").disabled = !task?.id;

  const body = $("reviewResultBody");
  body.innerHTML = "";
  const items = Array.isArray(results) ? results : [];
  if (!items.length) {
    const colspan = Number($("reviewResultHead").querySelectorAll("th").length || 6);
    body.innerHTML = `<tr><td colspan="${colspan}" class="empty-cell">暂无审校结果</td></tr>`;
    return;
  }
  const config = task?.config || {};
  const isDirectional = config.mode === "directional";
  const isForbiddenOnly = config.mode === "forbidden_only";
  const hasForbidden = Boolean(config.enable_forbidden_check);
  const reviewTypes = Array.isArray(config.review_types) ? config.review_types : [];
  items.forEach((item) => {
    const tr = document.createElement("tr");
    let cells = [];
    if (isForbiddenOnly) {
      cells = [
        item.source_text || "",
        item.target_text || "",
        item.matched_words || "",
      ];
    } else if (isDirectional) {
      const checks = item.checks || {};
      cells = [
        item.source_text || "",
        item.target_text || "",
        item.suggestion || "",
        ...reviewTypes.map((reviewType) => {
          const key = String(reviewType?.key || "");
          return item.error_message || checks[key] || "";
        }),
      ];
    } else {
      cells = [
        item.source_text || "",
        item.target_text || "",
        item.verification_label || (item.has_issue === null ? "" : item.has_issue ? "是" : "否"),
        item.issue_type || "",
        item.error_message || item.issue || "",
        item.suggestion || "",
      ];
    }
    if (hasForbidden && !isForbiddenOnly) {
      cells.push(item.matched_words || "");
    }
    cells.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value || "");
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function renderAiReviewResultHead(task) {
  const config = task?.config || {};
  const isDirectional = config.mode === "directional";
  const isForbiddenOnly = config.mode === "forbidden_only";
  const hasForbidden = Boolean(config.enable_forbidden_check);
  const reviewTypes = Array.isArray(config.review_types) ? config.review_types : [];
  const headers = isForbiddenOnly
    ? ["原文", "译文", "禁用词检查情况"]
    : isDirectional
      ? ["原文", "译文", "修改建议", ...reviewTypes.map((item) => String(item?.key || ""))]
      : ["原文", "译文", "是否有问题", "问题类型", "问题说明", "修改建议"];
  if (hasForbidden && !isForbiddenOnly) {
    headers.push("禁用词检查情况");
  }
  const table = $("reviewResultBody").closest("table");
  table.style.minWidth = "0";
  table.style.width = "100%";
  table.querySelector("colgroup")?.remove();
  const head = $("reviewResultHead");
  head.innerHTML = "";
  const tr = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    tr.appendChild(th);
  });
  head.appendChild(tr);
}

function reviewDetailExtraHeaders(task) {
  return ["问题类型", "问题说明"];
}

function reviewDetailExtraValues(task, item) {
  const config = task?.config || {};
  const isDirectional = config.mode === "directional";
  const isForbiddenOnly = config.mode === "forbidden_only";
  const hasForbidden = Boolean(config.enable_forbidden_check);
  if (isForbiddenOnly) {
    return ["禁用词", item.matched_words || ""];
  }
  if (isDirectional) {
    const checks = item.checks || {};
    const reviewTypes = Array.isArray(config.review_types) ? config.review_types : [];
    const issues = reviewTypes.map((reviewType) => {
      const key = String(reviewType?.key || "");
      const value = String(item.error_message || checks[key] || "").trim();
      return value ? { key, value } : null;
    }).filter(Boolean);
    if (hasForbidden && String(item.matched_words || "").trim()) {
      issues.push({ key: "禁用词", value: String(item.matched_words || "").trim() });
    }
    return [
      issues.map((issue) => issue.key).join("\n"),
      issues.map((issue) => `${issue.key}：${issue.value}`).join("\n"),
    ];
  }
  const types = [];
  const descriptions = [];
  if (item.issue_type || item.error_message || item.issue) {
    types.push(item.issue_type || "审校问题");
    descriptions.push(item.error_message || item.issue || "");
  }
  if (hasForbidden && String(item.matched_words || "").trim()) {
    types.push("禁用词");
    descriptions.push(`禁用词：${String(item.matched_words || "").trim()}`);
  }
  return [types.join("\n"), descriptions.join("\n")];
}

function createReviewDiffCell(html, mode) {
  const td = document.createElement("td");
  td.className = "review-diff-cell";
  const sideClass = mode === "add" ? "diff-inline-add" : "diff-inline-delete";
  const label = mode === "add" ? "建议" : "原译文";
  td.innerHTML = `
    <div class="diff-inline-side ${sideClass}">
      <div class="diff-inline-label">${label}</div>
      <div class="diff-inline-text">${html}</div>
    </div>`;
  return td;
}

function renderReviewDetailRows(task, results) {
  const groups = $("reviewDetailGroups");
  const extraHeaders = reviewDetailExtraHeaders(task);
  const headers = ["原文", "原译文", "修改建议", ...extraHeaders];
  const items = Array.isArray(results) ? results : [];
  aiReviewIssueResults = items;
  const grouped = new Map();
  items.forEach((item) => {
    const filename = String(item?.source_file || "直接输入").trim() || "直接输入";
    if (!grouped.has(filename)) grouped.set(filename, []);
    grouped.get(filename).push(item);
  });
  $("reviewDetailSummary").textContent = items.length
    ? `共 ${items.length} 条问题 · ${grouped.size} 个文件`
    : "暂无问题条目";
  groups.innerHTML = "";
  if (!items.length) {
    groups.innerHTML = '<div class="empty-cell">暂无问题条目</div>';
    return;
  }
  grouped.forEach((fileItems, filename) => {
    const section = document.createElement("section");
    section.className = "review-detail-group";
    const groupHead = document.createElement("div");
    groupHead.className = "review-detail-group-head";
    const title = document.createElement("h4");
    title.textContent = filename;
    const count = document.createElement("span");
    count.textContent = `${fileItems.length} 条问题`;
    groupHead.append(title, count);
    section.appendChild(groupHead);

    const tableWrap = document.createElement("div");
    tableWrap.className = "review-detail-group-table-wrap";
    const table = document.createElement("table");
    table.className = "pattern-table review-detail-table";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    headers.forEach((header) => {
      const th = document.createElement("th");
      th.textContent = header;
      headRow.appendChild(th);
    });
    head.appendChild(headRow);
    const body = document.createElement("tbody");
    fileItems.forEach((item) => {
      const tr = document.createElement("tr");
      const sourceTd = document.createElement("td");
      sourceTd.textContent = String(item.source_text || "");
      tr.appendChild(sourceTd);

      const tokens = buildDiffTokens(item.target_text || "", item.suggestion || "");
      tr.appendChild(createReviewDiffCell(tokens.leftHtml, "delete"));
      tr.appendChild(createReviewDiffCell(tokens.rightHtml, "add"));

      const extraValues = reviewDetailExtraValues(task, item);
      extraValues.forEach((value, index) => {
        const td = document.createElement("td");
        if (index === extraValues.length - 1) td.className = "review-detail-issue-cell";
        td.textContent = String(value || "");
        if (index === extraValues.length - 1) {
          const followupButton = document.createElement("button");
          followupButton.type = "button";
          followupButton.className = "secondary review-followup-inline-button";
          followupButton.textContent = "追问";
          followupButton.addEventListener("click", () => openReviewFollowupDialog(item.id).catch((error) => {
            $("reviewFollowupHint").textContent = error.message;
          }));
          const feedbackActions = document.createElement('div');
          feedbackActions.className = 'review-feedback-actions';
          feedbackActions.appendChild(followupButton);
          td.appendChild(feedbackActions);
          if (item.has_issue && item.status !== 'failed') {
            const ignore = document.createElement('button');
            ignore.type = 'button';
            ignore.className = 'secondary';
            ignore.textContent = '忽略';
            ignore.setAttribute('aria-pressed', 'false');
            const reason = document.createElement('input');
            reason.type = 'text';
            reason.placeholder = '忽略原因（可选）';
            reason.setAttribute('aria-label', '忽略原因');
            const draft = reviewFeedbackDraft.get(item.id) || {ignored:false, reason:''};
            reason.value = draft.reason;
            const update = () => {
              tr.style.opacity = draft.ignored ? '0.45' : '';
              ignore.textContent = draft.ignored ? '取消忽略' : '忽略';
              ignore.setAttribute('aria-pressed', String(draft.ignored));
              reviewFeedbackDraft.set(item.id, draft);
            };
            ignore.addEventListener('click', () => { if (!reviewFeedbackSaving) { draft.ignored = !draft.ignored; update(); } });
            reason.addEventListener('input', () => { draft.reason = reason.value; update(); });
            update();
            feedbackActions.append(ignore, reason);
          }
        }
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    table.append(head, body);
    tableWrap.appendChild(table);
    section.append(tableWrap);
    groups.appendChild(section);
  });
}

async function openReviewDetailDialog() {
  if (!aiReviewTaskId) {
    $("reviewTaskHint").textContent = "请先开始审校任务";
    return;
  }
  reviewFeedbackTaskId = aiReviewTaskId;
  reviewFeedbackSessionId = reviewConversationState.currentId;
  reviewFeedbackDraft.clear();
  $('reviewFeedbackHint').textContent = '';
  const data = await api(`/api/ai-review/tasks/${encodeURIComponent(aiReviewTaskId)}/issue-results`);
  renderReviewDetailRows(data.task || aiReviewCurrentTask || {}, data.results || []);
  $("reviewDetailOverlay").hidden = false;
}

function closeReviewDetailDialog() {
  if (reviewFeedbackSaving) return;
  reviewFeedbackDraft.clear();
  $("reviewDetailOverlay").hidden = true;
}

async function confirmReviewFeedback() {
  if (reviewFeedbackSaving) return;
  const entries = [...reviewFeedbackDraft.entries()].filter(([, d]) => d.ignored)
    .map(([result_id, d]) => ({result_id, decision:'disagree', reason:d.reason}));
  if (!entries.length) { closeReviewDetailDialog(); return; }
  reviewFeedbackSaving = true;
  $('confirmReviewFeedbackButton').disabled = true;
  $('closeReviewDetailButton').disabled = true;
  showReviewLearningProgress('saving');
  try {
    const result = await api(`/api/ai-review/conversations/${encodeURIComponent(reviewFeedbackSessionId)}/feedback`,
      {method:'POST', body:JSON.stringify({task_id:reviewFeedbackTaskId, entries})});
    reviewFeedbackSaving = false;
    closeReviewDetailDialog();
    showFeedbackResult(result, reviewFeedbackSessionId, reviewFeedbackTaskId);
    showReviewLearningProgress(result.event_id ? 'queued' : '');
    await refreshCurrentReviewConversation();
    await refreshReviewLearningStatus();
  } catch (error) {
    showReviewLearningProgress('');
    $('reviewFeedbackHint').textContent = error.message;
  }
  finally {
    reviewFeedbackSaving = false;
    $('confirmReviewFeedbackButton').disabled = false;
    $('closeReviewDetailButton').disabled = false;
  }
}

function showFeedbackResult(result, sessionId, taskId) {
  if (sessionId !== reviewConversationState.currentId) return;
  const hint = $('reviewConversationHint');
  hint.textContent = result.export_error || `已更新 ${result.changed || 0} 条反馈${result.event_id ? '，正在自主学习' : ''}`;
  if (result.export_error) {
    const retry = document.createElement('button');
    retry.type = 'button'; retry.textContent = '重试导出';
    retry.addEventListener('click', async () => {
      retry.disabled = true;
      try {
        const exported = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/feedback-export/${encodeURIComponent(taskId)}`, {method:'POST'});
        showFeedbackResult(exported, sessionId, taskId);
        await refreshCurrentReviewConversation();
      } catch (e) { hint.textContent = e.message; }
      finally { retry.disabled = false; }
    });
    hint.appendChild(retry);
  }
}

function showReviewLearningProgress(status, label) {
  const box = $('reviewLearningProgress');
  const values = {
    saving: {percent:8, text:'正在保存反馈'},
    queued: {percent:18, text:'学习请求已排队'},
    running: {percent:68, text:'AI 正在更新会话规范'},
    needs_input: {percent:68, text:'学习范围待确认，请在聊天中回答'},
    completed: {percent:100, text:'会话规范已更新'},
    failed: {percent:100, text:'会话规范更新失败'},
    uploading: {percent:10, text:'正在上传并校验反馈文件'}
  };
  const view = values[status];
  if (!view) {
    box.hidden = true;
    box.className = 'review-learning-progress';
    return;
  }
  box.hidden = false;
  box.className = `review-learning-progress ${status}`;
  $('reviewLearningProgressLabel').textContent = label || view.text;
  $('reviewLearningProgressValue').textContent = status === 'needs_input' ? '待确认' : `${view.percent}%`;
  $('reviewLearningProgressBar').style.width = `${view.percent}%`;
}

function renderReviewMemoryRules() {
  const list = $('reviewMemoryRuleList');
  list.replaceChildren();
  const rules = reviewMemoryState.rules || [];
  $('reviewMemorySummary').textContent = rules.length
    ? `版本 v${reviewMemoryState.version} · 使用中 ${rules.filter(rule => rule.active).length} 条 · 候补 ${rules.filter(rule => !rule.active).length} 条`
    : '当前会话还没有学习到规范。提交误报反馈后会自动生成。';
  $('saveReviewMemoryButton').disabled = !rules.length;
  if (!rules.length) {
    const empty = document.createElement('div');
    empty.className = 'review-memory-empty';
    empty.textContent = '暂无会话规范';
    list.appendChild(empty);
    return;
  }
  const sections = [
    {active:true, title:'使用中的规范', detail:'会注入本会话后续审校请求'},
    {active:false, title:'候补规范', detail:'不占用审校请求，仅参与后续权重更新'}
  ];
  sections.forEach(sectionInfo => {
    const entries = rules.filter(rule => Boolean(rule.active) === sectionInfo.active);
    if (!entries.length) return;
    const section = document.createElement('section');
    section.className = 'review-memory-section';
    const head = document.createElement('div');
    head.className = 'review-memory-section-head';
    const title = document.createElement('h4');
    title.textContent = `${sectionInfo.title}（${entries.length}）`;
    const detail = document.createElement('span');
    detail.textContent = sectionInfo.detail;
    head.append(title, detail);
    section.appendChild(head);
    entries.forEach((rule, index) => {
      const row = document.createElement('div');
      row.className = 'review-memory-rule';
      const number = document.createElement('span');
      number.className = 'review-memory-rule-index';
      number.textContent = `规范 ${index + 1}`;
      const weight = document.createElement('span');
      weight.className = 'review-memory-rule-weight';
      weight.textContent = `权重 ${Number(rule.weight || 0).toFixed(1)}`;
      const editor = document.createElement('textarea');
      editor.value = String(rule.text || '');
      editor.maxLength = 600;
      editor.dataset.ruleId = String(rule.id || '');
      editor.setAttribute('aria-label', `${sectionInfo.title} ${index + 1}`);
      row.append(number, weight, editor);
      const example = document.createElement('div');
      example.className = 'review-memory-example';
      const label = document.createElement('div');
      label.className = 'review-memory-example-title';
      label.textContent = rule.few_shot
        ? 'Few shot · 不计入规范字数 · 可手动改写；清空原文与译文可删除案例'
        : 'Few shot · 不计入规范字数 · 可填写一组双语案例';
      example.appendChild(label);
      for (const [key, title] of [['source_text', '原文'], ['target_text', '译文']]) {
        const field = document.createElement('label');
        field.textContent = title;
        const input = document.createElement('textarea');
        input.value = String(rule.few_shot?.[key] || '');
        input.dataset.ruleId = String(rule.id || '');
        input.dataset.fewShotKey = key;
        input.setAttribute('aria-label', `${sectionInfo.title} ${index + 1}案例${title}`);
        field.appendChild(input);
        example.appendChild(field);
      }
      row.appendChild(example);
      const scopeLines = [['适用范围',rule.scope],['判断依据',rule.principle],['边界',rule.boundary]]
        .filter(([,value])=>String(value || '').trim());
      if (scopeLines.length || rule.feedback_sources?.length || rule.manual_edited || rule.manual_example) {
        const evidence = document.createElement('details');evidence.className = 'review-memory-example';
        const summary = document.createElement('summary');summary.textContent = '查看适用范围与反馈依据';evidence.appendChild(summary);
        scopeLines.forEach(([label,value])=>{const line=document.createElement('p');line.textContent=`${label}：${value}`;evidence.appendChild(line);});
        (rule.feedback_sources || []).slice(-3).forEach(source=>{const line=document.createElement('p');line.textContent=`用户${source.decision === 'agree' ? '认可报错' : '忽略报错'}：${source.reason}`;evidence.appendChild(line);});
        if (rule.manual_edited || rule.manual_example) {const line=document.createElement('p');line.textContent='手动编辑的内容会保留，不由 AI 自动覆盖。';evidence.appendChild(line);}
        row.appendChild(evidence);
      }
      section.appendChild(row);
    });
    list.appendChild(section);
  });
}

async function openReviewMemoryDialog() {
  const sessionId = reviewConversationState.currentId;
  if (!sessionId) { showReviewConversationError(new Error('请先选择审校会话')); return; }
  $('reviewMemoryHint').textContent = '正在读取会话规范…';
  $('reviewMemoryOverlay').hidden = false;
  $('saveReviewMemoryButton').disabled = true;
  try {
    const memory = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/memory`);
    if (sessionId !== reviewConversationState.currentId) { closeReviewMemoryDialog(); return; }
    reviewMemoryState = {sessionId, version:Number(memory.version || 0), rules:memory.rules || [], saving:false};
    $('restoreReviewMemoryButton').disabled = !memory.can_restore;
    $('reviewMemoryHint').textContent = '';
    renderReviewMemoryRules();
  } catch (error) {
    $('reviewMemoryHint').textContent = error.message;
    $('reviewMemoryRuleList').replaceChildren();
  }
}

function closeReviewMemoryDialog() {
  if (reviewMemoryState.saving) return;
  reviewMemoryState = {sessionId:'', version:0, rules:[], saving:false};
  $('reviewMemoryOverlay').hidden = true;
  $('reviewMemoryHint').textContent = '';
}

async function saveReviewMemory() {
  if (reviewMemoryState.saving || !reviewMemoryState.sessionId) return;
  const rules = [...$('reviewMemoryRuleList').querySelectorAll('textarea[data-rule-id]')]
    .filter(editor => !editor.dataset.fewShotKey)
    .map(editor => {
      const id = editor.dataset.ruleId;
      const source = $('reviewMemoryRuleList').querySelector(`textarea[data-rule-id="${id}"][data-few-shot-key="source_text"]`);
      const target = $('reviewMemoryRuleList').querySelector(`textarea[data-rule-id="${id}"][data-few-shot-key="target_text"]`);
      return {id, text:editor.value.trim(), few_shot: source || target ? {
        source_text: source?.value.trim() || '', target_text: target?.value.trim() || ''
      } : null};
    });
  if (rules.some(rule => !rule.text)) { $('reviewMemoryHint').textContent = '规范内容不能为空。'; return; }
  reviewMemoryState.saving = true;
  $('saveReviewMemoryButton').disabled = true;
  $('closeReviewMemoryButton').disabled = true;
  $('cancelReviewMemoryButton').disabled = true;
  $('reviewMemoryHint').textContent = '正在保存…';
  try {
    const memory = await api(`/api/ai-review/conversations/${encodeURIComponent(reviewMemoryState.sessionId)}/memory`, {
      method:'PUT', body:JSON.stringify({version:reviewMemoryState.version, rules})
    });
    reviewMemoryState.version = Number(memory.version || reviewMemoryState.version);
    reviewMemoryState.rules = memory.rules || [];
    reviewMemoryState.saving = false;
    await refreshReviewLearningStatus();
    closeReviewMemoryDialog();
  } catch (error) {
    $('reviewMemoryHint').textContent = error.message;
  } finally {
    reviewMemoryState.saving = false;
    $('saveReviewMemoryButton').disabled = false;
    $('closeReviewMemoryButton').disabled = false;
    $('cancelReviewMemoryButton').disabled = false;
  }
}

async function refreshReviewLearningStatus() {
  const sessionId = reviewConversationState.currentId;
  if (!sessionId) {
    $('reviewLearningStatus').textContent = '';
    $('reviewMemoryButton').disabled = true;
    showReviewLearningProgress('');
    return;
  }
  const status = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/learning`);
  if (sessionId !== reviewConversationState.currentId) return;
  const box = $('reviewLearningStatus');
  $('reviewMemoryButton').disabled = false;
  box.replaceChildren();
  box.append(document.createTextNode(status.version
    ? `会话记忆 v${status.version} · ${status.active_count} 条使用中${status.candidate_count ? ` · ${status.candidate_count} 条候补` : ''}`
    : '会话记忆 · 暂无规范'));
  const event = (status.events || [])[0];
  showReviewLearningProgress(event?.status || '');
  if (reviewConversationState.snapshot) {
    const before = JSON.stringify(reviewConversationState.snapshot.learning_questions || []);
    reviewConversationState.snapshot.learning_questions = status.questions || [];
    if (before !== JSON.stringify(status.questions || [])) renderReviewConversationSnapshot();
  }
  if (event?.status === 'failed') {
    $('reviewLearningProgressLabel').textContent = `会话规范更新失败：${event.error || '未知错误'}`;
    const line = document.createElement('div');
    line.className = 'review-learning-retry';
      const retry = document.createElement('button');
      retry.type = 'button'; retry.textContent = '重试学习';
      retry.addEventListener('click', async () => {
        retry.disabled = true;
        try {
          await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/learning/${encodeURIComponent(event.id)}/retry`, {method:'POST'});
          await refreshReviewLearningStatus();
        } catch (e) { line.textContent = e.message; }
        finally { retry.disabled = false; }
      });
      line.appendChild(retry);
    box.appendChild(line);
  }
}

function reviewFollowupIssueText(item) {
  const task = aiReviewCurrentTask || {};
  const [issueType, issueText] = reviewDetailExtraValues(task, item || {});
  return { issueType, issueText };
}

function renderReviewFollowupContext(item) {
  const container = $("reviewFollowupContext");
  const issue = reviewFollowupIssueText(item || {});
  const sections = [
    ["原文", item?.source_text || ""],
    ["译文", item?.target_text || ""],
    ["修改建议", item?.suggestion || ""],
    ["问题类型", issue.issueType || ""],
    ["问题说明", issue.issueText || ""],
  ].filter(([, value]) => String(value || "").trim());
  container.innerHTML = `
    <div class="followup-context-card">
      ${sections.map(([label, value]) => `
        <div class="followup-context-section">
          <span>${escapeHtml(label)}</span>
          <p>${escapeHtml(String(value || ""))}</p>
        </div>
      `).join("")}
    </div>`;
}

function renderReviewFollowupMessages(messages) {
  const box = $("reviewFollowupMessages");
  const items = Array.isArray(messages) ? messages : [];
  box.innerHTML = "";
  if (!items.length) {
    box.innerHTML = '<div class="followup-message-empty">还没有追问记录，可以直接输入问题。</div>';
    return;
  }
  items.forEach((message) => {
    const div = document.createElement("div");
    const role = String(message.role || "") === "user" ? "user" : "assistant";
    div.className = `followup-message ${role}`;
    div.textContent = String(message.content || "");
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

function renderReviewFollowupDialog(data) {
  const item = data?.item || aiReviewFollowupState.item || {};
  const messages = Array.isArray(data?.messages) ? data.messages : [];
  aiReviewFollowupState.item = item;
  aiReviewFollowupState.messages = messages;
  $("reviewFollowupSummary").textContent = item?.row_number ? `第 ${item.row_number} 行` : "围绕当前问题继续提问";
  renderReviewFollowupContext(item);
  renderReviewFollowupMessages(messages);
}

async function openReviewFollowupDialog(resultId) {
  if (!aiReviewTaskId || !resultId) return;
  aiReviewFollowupState = { taskId: aiReviewTaskId, resultId: String(resultId), item: null, messages: [] };
  $("reviewFollowupInput").value = "";
  $("reviewFollowupHint").textContent = "正在读取对话...";
  $("reviewFollowupOverlay").hidden = false;
  try {
    const data = await api(`/api/ai-review/tasks/${encodeURIComponent(aiReviewTaskId)}/followup/${encodeURIComponent(resultId)}`);
    renderReviewFollowupDialog(data);
    $("reviewFollowupHint").textContent = "";
    $("reviewFollowupInput").focus();
  } catch (error) {
    $("reviewFollowupHint").textContent = error.message || "追问读取失败";
  }
}

function closeReviewFollowupDialog() {
  $("reviewFollowupOverlay").hidden = true;
}

async function sendReviewFollowupMessage() {
  const message = $("reviewFollowupInput").value.trim();
  if (!message) {
    $("reviewFollowupHint").textContent = "请输入追问内容";
    return;
  }
  const taskId = aiReviewFollowupState.taskId || aiReviewTaskId;
  const resultId = aiReviewFollowupState.resultId;
  if (!taskId || !resultId) {
    $("reviewFollowupHint").textContent = "当前没有可追问的条目";
    return;
  }
  $("sendReviewFollowupButton").disabled = true;
  $("reviewFollowupHint").textContent = "发送中...";
  try {
    const data = await api(`/api/ai-review/tasks/${encodeURIComponent(taskId)}/followup/${encodeURIComponent(resultId)}`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    $("reviewFollowupInput").value = "";
    renderReviewFollowupDialog(data);
    $("reviewFollowupHint").textContent = "";
  } finally {
    $("sendReviewFollowupButton").disabled = false;
  }
}

function appendAiReviewLogs(logs) {
  const list = $("reviewLogList");
  const items = Array.isArray(logs) ? logs : [];
  items.forEach((item) => {
    aiReviewLogCursor = Math.max(aiReviewLogCursor, Number(item.id || 0));
    const li = document.createElement("li");
    li.textContent = `${String(item.created_at || "")} ${String(item.message || "")}`.trim();
    if (String(item.level || "").toLowerCase() === "error") {
      li.classList.add("error");
    } else if (String(item.level || "").toLowerCase() === "debug") {
      li.classList.add("debug");
    }
    list.appendChild(li);
  });
}

async function loadAiReviewPromptTemplates() {
  const data = await api("/api/ai-review/prompt-templates");
  aiReviewPromptTemplates = Array.isArray(data.templates) ? data.templates : [];
  renderAiReviewPromptTemplateOptions();
}

async function loadAiReviewDirectionalTemplates() {
  const data = await api("/api/ai-review/directional-templates");
  aiReviewDirectionalTemplates = Array.isArray(data.templates) ? data.templates : [];
  renderAiReviewDirectionalTemplateOptions();
}

async function loadAiReviewForbiddenTemplates() {
  const data = await api("/api/ai-review/forbidden-templates");
  aiReviewForbiddenTemplates = Array.isArray(data.templates) ? data.templates : [];
  renderAiReviewForbiddenTemplateOptions();
}

async function loadReviewConversations(preferredId = "") {
  const data = await api("/api/ai-review/conversations");
  reviewConversationState.sessions = Array.isArray(data.sessions) ? data.sessions : [];
  renderReviewConversationList();
  let nextId = preferredId || reviewConversationState.currentId || reviewConversationState.sessions[0]?.id || "";
  if (!nextId) {
    const created = await createReviewConversation();
    nextId = created?.id || "";
  }
  if (nextId) await openReviewConversation(nextId);
}

async function loadReviewTermBases() {
  const data = await api("/api/ai-review/term-bases");
  reviewConversationState.termBases = Array.isArray(data.term_bases) ? data.term_bases : [];
  renderReviewTermBaseOptions();
  updateReviewComposerChips();
  try {
    const status = await api("/api/ai-review/term-bases/memoq/status");
    if (status.memoq?.bound) {
      const remote = await api("/api/ai-review/term-bases/memoq/termbases");
      reviewConversationState.memoqTermBases = Array.isArray(remote.termbases) ? remote.termbases : [];
    } else reviewConversationState.memoqTermBases = [];
  } catch (_) { reviewConversationState.memoqTermBases = []; }
  renderReviewTermBaseOptions();
}

let reviewConversationCreation = null;
let reviewAttachmentUploadQueue = Promise.resolve();
const reviewAttachmentUploads = new Map();
const reviewConversationSending = new Set();

function createReviewConversation() {
  if (!reviewConversationCreation) {
    reviewConversationCreation = createReviewConversationImpl().finally(() => { reviewConversationCreation = null; });
  }
  return reviewConversationCreation;
}

async function createReviewConversationImpl() {
  const promptId = reviewConversationState.promptTemplateId || aiReviewPromptTemplates[0]?.id || null;
  const data = await api("/api/ai-review/conversations", {
    method: "POST",
    body: JSON.stringify({
      title: "新审校",
      prompt_template_id: promptId,
      term_base_id: null,
      memoq_term_base_ids: [],
      source_language: "auto",
      target_languages: ["auto"],
      auto_start: false,
    }),
  });
  const session = data.session || {};
  reviewConversationState.currentId = String(session.id || "");
  reviewConversationState.sessions.unshift(session);
  renderReviewConversationList();
  if (session.id) await openReviewConversation(session.id);
  return session;
}

function renderReviewConversationList() {
  const list = $("reviewConversationList");
  if (!list) return;
  list.innerHTML = "";
  reviewConversationState.sessions.forEach((session) => {
    const row = document.createElement("div");
    row.className = `review-session-row ${session.id === reviewConversationState.currentId ? "active" : ""}`.trim();
    const button = document.createElement("button");
    button.type = "button";
    button.className = "review-session-item";
    const title = document.createElement("strong");
    title.textContent = session.title || "新审校";
    const status = document.createElement("span");
    status.textContent = reviewSessionStatusLabel(session.status);
    button.append(title, status);
    button.addEventListener("click", () => openReviewConversation(session.id).catch(showReviewConversationError));
    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.className = "review-session-rename";
    renameButton.title = "重命名会话";
    renameButton.setAttribute("aria-label", `重命名 ${session.title || "新审校"}`);
    renameButton.textContent = "✎";
    renameButton.addEventListener("click", () => beginRenameReviewSessionItem(session, row, button, renameButton));
    row.append(button, renameButton);
    list.appendChild(row);
  });
}

function beginRenameReviewSessionItem(session, row, sessionButton, renameButton) {
  const input = document.createElement("input");
  input.className = "review-session-inline-input";
  input.type = "text";
  input.maxLength = 120;
  input.value = session.title || "新审校";
  sessionButton.replaceWith(input);
  const saveButton = renameButton.cloneNode(true);
  saveButton.textContent = "✓";
  saveButton.title = "保存名称";
  saveButton.setAttribute("aria-label", "保存会话名称");
  renameButton.replaceWith(saveButton);
  const save = async () => {
    const title = input.value.trim();
    if (!title) throw new Error("会话名称不能为空");
    await renameReviewConversation(session.id, title);
  };
  saveButton.addEventListener("click", () => save().catch(showReviewConversationError));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      save().catch(showReviewConversationError);
    } else if (event.key === "Escape") {
      event.preventDefault();
      renderReviewConversationList();
    }
  });
  input.focus();
  input.select();
}

async function renameReviewConversation(sessionId, title) {
  const data = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  const updated = data.session || {};
  const sessionIndex = reviewConversationState.sessions.findIndex((item) => item.id === sessionId);
  if (sessionIndex >= 0) reviewConversationState.sessions[sessionIndex] = updated;
  if (reviewConversationState.snapshot?.session?.id === sessionId) {
    reviewConversationState.snapshot.session = updated;
    renderReviewConversationSnapshot();
  }
  renderReviewConversationList();
  return updated;
}

async function saveReviewConversationAutoStart(enabled) {
  const sessionId = String(reviewConversationState.currentId || "");
  if (!sessionId) return;
  const data = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    body: JSON.stringify({ auto_start: Boolean(enabled) }),
  });
  const updated = data.session || {};
  const sessionIndex = reviewConversationState.sessions.findIndex((item) => item.id === sessionId);
  if (sessionIndex >= 0) reviewConversationState.sessions[sessionIndex] = updated;
  if (reviewConversationState.snapshot?.session?.id === sessionId) {
    reviewConversationState.snapshot.session = updated;
  }
  renderReviewConversationList();
}

function applyReviewConversationSessionUpdate(updated) {
  if (!updated?.id) return;
  const sessionIndex = reviewConversationState.sessions.findIndex((item) => item.id === updated.id);
  if (sessionIndex >= 0) reviewConversationState.sessions[sessionIndex] = updated;
  if (reviewConversationState.snapshot?.session?.id === updated.id) {
    reviewConversationState.snapshot.session = updated;
  }
  renderReviewConversationList();
}

function saveReviewConversationComposerSettings() {
  const sessionId = String(reviewConversationState.currentId || "");
  if (!sessionId) return Promise.resolve();
    const payload = {
    prompt_template_id: reviewConversationState.promptTemplateId || null,
    source_language: reviewConversationState.sourceLanguage || "auto",
    target_languages: [...(reviewConversationState.targetLanguages || ["auto"])],
    term_base_id: reviewConversationState.termBaseId || null,
    memoq_term_base_ids: reviewConversationState.memoqTermBaseIds || [],
  };
  const save = async () => {
    const data = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    applyReviewConversationSessionUpdate(data.session || {});
  };
  // Language chips can be clicked rapidly. Serialize writes so a slower earlier
  // response cannot overwrite the newest selection for this session.
  reviewConversationState.composerSaveQueue = reviewConversationState.composerSaveQueue
    .catch(() => undefined)
    .then(save);
  return reviewConversationState.composerSaveQueue;
}

async function openReviewConversation(sessionId) {
  if (!sessionId) return;
  reviewConversationState.currentId = String(sessionId);
  reviewConversationState.streamRunId = "";
  reviewConversationState.streamText = "";
  reviewConversationState.streamThinkingText = "";
  reviewConversationState.streamAnswerText = "";
  reviewConversationState.streamPhase = "reasoning";
  reviewConversationState.streamActive = false;
  reviewConversationState.eventCursor = 0;
  const snapshot = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}`);
  if (reviewConversationState.currentId !== sessionId) return;
  reviewConversationState.snapshot = snapshot;
  const session = snapshot.session || {};
  reviewConversationState.sourceLanguage = session.source_language || "auto";
  reviewConversationState.targetLanguages = Array.isArray(session.target_languages) && session.target_languages.length ? session.target_languages : ["auto"];
  reviewConversationState.promptTemplateId = session.prompt_template_id || aiReviewPromptTemplates[0]?.id || "";
  reviewConversationState.termBaseId = session.term_base_id || "";
  reviewConversationState.memoqTermBaseIds = Array.isArray(session.memoq_term_base_ids) ? session.memoq_term_base_ids : [];
  reviewConversationState.activeTarget = reviewConversationState.activeTarget || snapshot.task_results?.[0]?.target_language || "";
  renderReviewConversationList();
  renderReviewConversationSnapshot();
  await refreshReviewLearningStatus();
  connectReviewConversationEvents(sessionId);
}

function renderReviewConversationSnapshot() {
  const snapshot = reviewConversationState.snapshot || {};
  const session = snapshot.session || {};
  $("reviewConversationTitle").textContent = session.title || "新审校";
  $("reviewConversationStatus").textContent = reviewSessionStatusLabel(session.status);
  $("reviewAutoStart").checked = Boolean(session.auto_start);
  const liveHints = {
    inspecting: "Workspace Agent 正在识别内容…",
    reviewing: "Task Workflow 正在审校…",
    validating: "正在校验审校结果…",
  };
  $("reviewConversationHint").textContent = liveHints[session.status] || "";
  updateReviewComposerChips();
  renderReviewAttachments(snapshot.attachments || []);
  renderReviewMessages(snapshot.messages || [], snapshot.questions || []);
  renderReviewConversationResults(snapshot.task_results || []);
  updateReviewUploadStatus();
}

function renderWorkspaceReportPreview(message) {
  const plan = message.payload || {};
  const files = Array.isArray(plan.file_summaries) ? plan.file_summaries : [];
  if (!files.length) return null;
  const totalUnits = (plan.targets || []).reduce(
    (total, target) => total + (
      Array.isArray(target?.units) ? target.units.length : Number(target?.unit_count || 0)
    ), 0,
  );
  const preview = document.createElement("section");
  preview.className = "review-workspace-preview";
  const previewHead = document.createElement("div");
  previewHead.className = "review-workspace-preview-head";
  const headCopy = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = "识别预览";
  const subtitle = document.createElement("span");
  subtitle.textContent = "请核对列映射与同一行样例";
  headCopy.append(title, subtitle);
  const count = document.createElement("span");
  count.className = "review-workspace-total";
  count.textContent = `${totalUnits} 条待审校`;
  previewHead.append(headCopy, count);
  preview.appendChild(previewHead);

  files.forEach((file) => {
    const fileCard = document.createElement("section");
    fileCard.className = "review-workspace-file-card";
    const fileHead = document.createElement("div");
    fileHead.className = "review-workspace-file-head";
    const fileIcon = document.createElement("span");
    fileIcon.className = "review-workspace-file-icon";
    fileIcon.textContent = String(file.file_type || "file").slice(0, 4).toUpperCase();
    const fileCopy = document.createElement("div");
    const filename = document.createElement("strong");
    filename.textContent = file.filename || "未命名文件";
    const fileMeta = document.createElement("span");
    fileMeta.textContent = file.mappings?.length ? `${file.mappings.length} 组映射` : (file.structure_label || "未形成审校映射");
    fileCopy.append(filename, fileMeta);
    fileHead.append(fileIcon, fileCopy);
    fileCard.appendChild(fileHead);

    const mappings = Array.isArray(file.mappings) ? file.mappings : [];
    if (!mappings.length) {
      const empty = document.createElement("div");
      empty.className = "review-workspace-empty";
      empty.textContent = file.structure_label || "尚未形成可执行映射";
      fileCard.appendChild(empty);
    }
    mappings.forEach((mapping) => {
      const mappingCard = document.createElement("div");
      mappingCard.className = "review-workspace-mapping";
      const mappingHead = document.createElement("div");
      mappingHead.className = "review-workspace-mapping-head";
      const language = document.createElement("span");
      language.className = "review-workspace-language";
      language.textContent = mapping.language || "自动识别";
      const mappingCount = document.createElement("span");
      mappingCount.textContent = `${mapping.count || 0} 条`;
      mappingHead.append(language, mappingCount);
      const flow = document.createElement("div");
      flow.className = "review-workspace-flow";
      const makeEndpoint = (label, value, muted = false) => {
        const endpoint = document.createElement("div");
        endpoint.className = `review-workspace-endpoint${muted ? " is-empty" : ""}`;
        const endpointLabel = document.createElement("span");
        endpointLabel.textContent = label;
        const endpointValue = document.createElement("strong");
        endpointValue.textContent = value || (label === "原文" ? "无源文" : "未识别");
        endpoint.append(endpointLabel, endpointValue);
        return endpoint;
      };
      flow.append(
        makeEndpoint("原文", mapping.source_location, !mapping.source_location),
        Object.assign(document.createElement("span"), { className: "review-workspace-arrow", textContent: "→" }),
        makeEndpoint("译文", mapping.target_location),
      );
      mappingCard.append(mappingHead, flow);
      if (mapping.reference_locations) {
        const reference = document.createElement("div");
        reference.className = "review-workspace-reference";
        reference.textContent = `同一行上下文：${mapping.reference_locations}`;
        mappingCard.appendChild(reference);
      }
      const samples = Array.isArray(mapping.samples) ? mapping.samples : [];
      if (samples.length) {
        const samplesGrid = document.createElement("div");
        samplesGrid.className = "review-workspace-samples";
        samples.slice(0, 3).forEach((sample, index) => {
          const sampleCard = document.createElement("article");
          sampleCard.className = "review-workspace-sample";
          const sampleMeta = document.createElement("span");
          sampleMeta.textContent = `样例 ${index + 1}${sample.position ? ` · ${sample.position}` : ""}`;
          const values = document.createElement("div");
          values.className = "review-workspace-sample-values";
          const source = document.createElement("div");
          source.className = "review-workspace-sample-source";
          source.textContent = sample.source || "无源文";
          const target = document.createElement("div");
          target.className = "review-workspace-sample-target";
          target.textContent = sample.target || "（空译文）";
          values.append(source, target);
          sampleCard.append(sampleMeta, values);
          samplesGrid.appendChild(sampleCard);
        });
        mappingCard.appendChild(samplesGrid);
      }
      fileCard.appendChild(mappingCard);
    });
    preview.appendChild(fileCard);
  });
  if ((plan.assumptions || []).length || (plan.warnings || []).length) {
  const notes = document.createElement("details");
  notes.className = "review-workspace-notes";
  notes.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "查看识别依据与注意事项";
    const noteCopy = document.createElement("div");
    noteCopy.className = "review-workspace-note-copy";
    [...(plan.assumptions || []), ...(plan.warnings || [])].slice(0, 5).forEach((note) => {
      const row = document.createElement("p");
      row.textContent = note;
      noteCopy.appendChild(row);
    });
    notes.append(summary, noteCopy);
    preview.appendChild(notes);
  }
  return preview;
}

function renderReviewMessages(messages, questions) {
  const container = $("reviewConversationMessages");
  container.innerHTML = "";
  messages.forEach((message) => {
    const item = document.createElement("div");
    item.className = `review-chat-message ${message.role === "user" ? "user" : "assistant"} ${message.kind === "error" ? "error" : ""} ${message.kind === "workspace_report" ? "workspace-report" : ""}`.trim();
    const workspacePreview = message.kind === "workspace_report" ? renderWorkspaceReportPreview(message) : null;
    if (workspacePreview) {
      item.appendChild(workspacePreview);
    } else {
      const content = document.createElement("div");
      content.textContent = message.content || "";
      item.appendChild(content);
    }
    const attachments = Array.isArray(message.payload?.attachments) ? message.payload.attachments : [];
    if (attachments.length) {
      const files = document.createElement("div");
      files.className = "review-message-files";
      attachments.forEach((attachment) => {
        const file = document.createElement("span");
        file.className = "review-message-file";
        file.textContent = `▤ ${attachment.original_filename || "文件"}`;
        files.appendChild(file);
      });
      item.appendChild(files);
    }
    const thinkingText = String(message.payload?._thinking_text || "");
    if (message.kind === "workspace_report" && thinkingText) {
      const details = document.createElement("details");
      details.className = "review-thinking-details";
      const summary = document.createElement("summary");
      summary.textContent = `查看思考过程 · ${thinkingText.length} 字`;
      const thinkingOutput = document.createElement("div");
      thinkingOutput.className = "review-stream-output";
      thinkingOutput.textContent = thinkingText;
      details.append(summary, thinkingOutput);
      item.appendChild(details);
    }
    const meta = document.createElement("div");
    meta.className = "review-chat-message-meta";
    meta.textContent = String(message.created_at || "").replace("T", " ");
    item.appendChild(meta);
    container.appendChild(item);
  });
  if (reviewConversationState.streamActive) {
    const item = document.createElement("div");
    item.className = "review-chat-message assistant workspace-report";
    const title = document.createElement("strong");
    title.textContent = reviewConversationState.streamText
      ? `${reviewConversationState.streamPhase === "reasoning" ? "Workspace Agent 正在思考" : "Workspace Agent 正在生成方案"} · 已接收 ${reviewConversationState.streamText.length} 字`
      : "Workspace Agent 已连接，等待首个输出…";
    const details = document.createElement("details");
    details.className = "review-thinking-details";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = reviewConversationState.streamPhase === "reasoning" ? "实时思考过程" : "实时模型输出";
    const output = document.createElement("div");
    output.className = "review-stream-output";
    const liveText = reviewConversationState.streamPhase === "reasoning"
      ? reviewConversationState.streamThinkingText
      : reviewConversationState.streamAnswerText;
    output.textContent = liveText.slice(-5000) || "正在分析文件结构…";
    details.append(summary, output);
    item.append(title, details);
    container.appendChild(item);
    window.requestAnimationFrame(() => {
      output.scrollTop = output.scrollHeight;
      container.scrollTop = container.scrollHeight;
    });
  }
  renderLearningQuestion(container);
  const latestRun = reviewConversationState.snapshot?.workspace_runs?.[0] || null;
  const latestRunId = String(latestRun?.id || "");
  const hasExecutablePlan = Boolean((latestRun?.plan?.targets || []).some((target) => Array.isArray(target?.units) && target.units.length));
  questions.filter((question) => question.status === "pending" && (!latestRunId || question.run_id === latestRunId)).forEach((question) => {
    const item = document.createElement("div");
    item.className = "review-chat-message assistant";
    const prompt = document.createElement("div");
    prompt.textContent = question.prompt || "请确认识别结果";
    const actions = document.createElement("div");
    actions.className = "review-decision-actions";
    const canConfirm = hasExecutablePlan && Boolean(String(question.recommended_label || "").trim()) && Boolean(String(question.recommended_value || "").trim());
    if (canConfirm) {
      const confirmRow = document.createElement("div");
      confirmRow.className = "review-decision-confirm-row";
      const confirmButton = document.createElement("button");
      confirmButton.type = "button";
      confirmButton.className = "primary";
      confirmButton.textContent = question.recommended_label;
      confirmButton.addEventListener("click", () => submitReviewDecision(question, "confirm", question.recommended_value).catch(showReviewConversationError));
      confirmRow.appendChild(confirmButton);
      actions.appendChild(confirmRow);
    }
    const otherInput = document.createElement("input");
    otherInput.placeholder = canConfirm ? "其他：自行输入" : "请补充目标语种、译文内容或文件位置";
    const otherButton = document.createElement("button");
    otherButton.type = "button";
    otherButton.className = "secondary";
    otherButton.textContent = "提交";
    otherButton.addEventListener("click", () => submitReviewDecision(question, "other", otherInput.value).catch(showReviewConversationError));
    const otherRow = document.createElement("div");
    otherRow.className = "review-decision-other-row";
    otherRow.append(otherInput, otherButton);
    actions.appendChild(otherRow);
    item.append(prompt, actions);
    container.appendChild(item);
  });
  container.scrollTop = container.scrollHeight;
}

async function submitReviewDecision(question, action, answer) {
  if (action === "other" && !String(answer || "").trim()) throw new Error("请输入补充说明");
  await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/decision`, {
    method: "POST",
    body: JSON.stringify({ run_id: question.run_id, question_id: question.id, action, answer: answer || action }),
  });
  await refreshCurrentReviewConversation();
}

function renderLearningQuestion(container) {
  const pending = reviewConversationState.snapshot?.learning_questions || [];
  const question = pending[0];
  if (!question) return;
  const sessionId = reviewConversationState.currentId;
  const card = document.createElement('section');
  card.className = 'review-learning-question';
  card.setAttribute('aria-label', '确认学习范围');
  const title = document.createElement('h4');
  title.textContent = `确认学习范围${pending.length > 1 ? ` · 还有 ${pending.length - 1} 个疑点` : ''}`;
  const prompt = document.createElement('p'); prompt.textContent = question.prompt;
  card.append(title, prompt);
  const examples = document.createElement('details');
  const summary = document.createElement('summary'); summary.textContent = '查看对应原译文与反馈';
  examples.appendChild(summary);
  (question.examples || []).forEach(example => {
    const text = document.createElement('p');
    text.textContent = `原文：${example.source}\n译文：${example.target}\n原报错：${example.issue}\n反馈理由：${example.reason || '未填写'}`;
    examples.appendChild(text);
  });
  card.appendChild(examples);
  const choices = document.createElement('div');choices.className = 'review-learning-choices';
  const hint = document.createElement('span');hint.className = 'hint';hint.setAttribute('role','status');
  const send = async payload => {
    card.querySelectorAll('button').forEach(button => button.disabled = true);
    hint.textContent = '正在保存你的解释…';
    try {
      await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/learning-questions/${encodeURIComponent(question.id)}/answer`, {method:'POST',body:JSON.stringify(payload)});
      reviewLearningDrafts.delete(question.id);
      if (sessionId === reviewConversationState.currentId) { await refreshCurrentReviewConversation();await refreshReviewLearningStatus(); }
    } catch(error) {
      hint.textContent = error.message;
      card.querySelectorAll('button').forEach(button => button.disabled = false);
    }
  };
  (question.options || []).forEach((option,index) => {
    const button = document.createElement('button');button.type = 'button';
    const title = document.createElement('strong');title.textContent = `${index + 1}. ${option.label}${index === 0 ? '（推荐）' : ''}`;
    const explanation = document.createElement('span');explanation.textContent = option.reason;
    const scope = document.createElement('span');scope.textContent = option.scope === 'case' ? '学习范围：当前案例' : '学习范围：确认的同类语境';
    button.append(title,explanation,scope);
    button.addEventListener('click', () => {
      if (option.requires_reason) { card.querySelector('textarea').focus();hint.textContent = option.reason;return; }
      send({option:index});
    });choices.appendChild(button);
  });
  card.appendChild(choices);
  const label = document.createElement('label');label.textContent = '3. 自行输入其他原因';
  const input = document.createElement('textarea');input.maxLength = 2000;
  input.setAttribute('aria-label','自行输入学习原因');input.value = reviewLearningDrafts.get(question.id) || '';
  input.addEventListener('input',()=>reviewLearningDrafts.set(question.id,input.value));
  label.appendChild(input);card.appendChild(label);
  const submit = document.createElement('button');submit.type = 'button';submit.className = 'secondary';submit.textContent = '提交说明';
  submit.addEventListener('click',()=>{if (!input.value.trim()) {hint.textContent = '请填写原因或选择上方解释';input.focus();return;}send({text:input.value.trim()});});
  card.append(submit,hint);container.appendChild(card);
}

async function restoreReviewMemory() {
  if (!reviewMemoryState.sessionId || reviewMemoryState.saving) return;
  $('restoreReviewMemoryButton').disabled = true;
  try {
    const memory = await api(`/api/ai-review/conversations/${encodeURIComponent(reviewMemoryState.sessionId)}/memory/restore`, {method:'POST',body:JSON.stringify({version:reviewMemoryState.version})});
    reviewMemoryState.version = memory.version;reviewMemoryState.rules = memory.rules || [];
    renderReviewMemoryRules();$('reviewMemoryHint').textContent = '已恢复更新前的规范';
    await refreshCurrentReviewConversation();
  } catch(error) { $('reviewMemoryHint').textContent = error.message; }
  finally { $('restoreReviewMemoryButton').disabled = false; }
}

function renderReviewAttachments(attachments) {
  const container = $("reviewAttachmentChips");
  container.innerHTML = "";
  attachments.filter((attachment) => !attachment.sent_at).forEach((attachment) => {
    const chip = document.createElement("span");
    chip.className = "review-attachment-chip";
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "review-attachment-open";
    const modeLabel = attachment.mapping_mode === "preset" ? "映射模板" : "AI 识别";
    openButton.textContent = `${attachment.original_filename} · ${modeLabel}`;
    openButton.addEventListener("click", () => openReviewAttachmentMappingDialog(attachment).catch(showReviewConversationError));
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "review-attachment-remove";
    removeButton.title = "移除文件";
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => removeReviewPendingAttachment(attachment.id).catch(showReviewConversationError));
    chip.append(openButton, removeButton);
    container.appendChild(chip);
  });
}

function renderReviewConversationResults(taskResults) {
  const card = $("reviewConversationResultCard");
  const tasks = Array.isArray(taskResults) ? taskResults : [];
  card.classList.toggle("hidden", !tasks.length);
  const tabs = $("reviewTargetTabs");
  tabs.innerHTML = "";
  if (!tasks.length) {
    reviewConversationState.activeTarget = "";
    aiReviewTaskId = "";
    aiReviewCurrentTask = null;
    renderAiReviewResults({}, []);
    return;
  }
  if (!tasks.some((item) => item.target_language === reviewConversationState.activeTarget)) {
    reviewConversationState.activeTarget = tasks[0].target_language;
  }
  tasks.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `review-target-tab ${item.target_language === reviewConversationState.activeTarget ? "active" : ""}`.trim();
    button.textContent = item.target_language || "自动识别";
    button.addEventListener("click", () => {
      reviewConversationState.activeTarget = item.target_language;
      renderReviewConversationResults(tasks);
    });
    tabs.appendChild(button);
  });
  const active = tasks.find((item) => item.target_language === reviewConversationState.activeTarget) || tasks[0];
  aiReviewTaskId = String(active?.task?.id || "");
  aiReviewCurrentTask = active?.task || null;
  renderAiReviewResults(active?.task || {}, active?.results || []);
}

async function refreshCurrentReviewConversation() {
  const sessionId = reviewConversationState.currentId;
  if (!sessionId) return;
  const snapshot = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}`);
  if (reviewConversationState.currentId !== sessionId) return;
  reviewConversationState.snapshot = snapshot;
  const sessionIndex = reviewConversationState.sessions.findIndex((item) => item.id === snapshot.session?.id);
  if (sessionIndex >= 0) reviewConversationState.sessions[sessionIndex] = snapshot.session;
  renderReviewConversationSnapshot();
}

function connectReviewConversationEvents(sessionId) {
  if (reviewConversationState.eventSource) reviewConversationState.eventSource.close();
  const source = new EventSource(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/events?after_id=${reviewConversationState.eventCursor}`);
  reviewConversationState.eventSource = source;
  const eventNames = [
    "message.created", "attachment.uploaded", "attachment.deleted", "attachment.inspected", "workspace.started", "workspace.ready",
    "workspace.needs_input", "workspace.failed", "workspace.question", "review.started", "review.progress",
    "review.request_status", "review.package_completed", "review.completed", "learning.updated",
  ];
  eventNames.forEach((name) => source.addEventListener(name, (event) => {
    if (reviewConversationState.currentId !== sessionId) return;
    if (name === "attachment.uploaded") {
      const payload = JSON.parse(event.data || "{}").payload || {};
      applyReviewUploadedAttachments(sessionId, {attachments: payload.attachment ? [payload.attachment] : []});
      reviewConversationState.eventCursor = Math.max(reviewConversationState.eventCursor, Number(event.lastEventId || 0));
      return;
    }
    reviewConversationState.eventCursor = Math.max(reviewConversationState.eventCursor, Number(event.lastEventId || 0));
    if (["workspace.ready", "workspace.needs_input", "workspace.failed"].includes(name)) {
      reviewConversationState.streamActive = false;
      reviewConversationState.streamText = "";
      reviewConversationState.streamThinkingText = "";
      reviewConversationState.streamAnswerText = "";
    }
    if (name === "workspace.started") renderReviewConversationResults([]);
    scheduleReviewConversationRefresh();
  }));
  source.addEventListener("workspace.output_started", (event) => {
    reviewConversationState.eventCursor = Math.max(reviewConversationState.eventCursor, Number(event.lastEventId || 0));
    const payload = JSON.parse(event.data || "{}").payload || {};
    reviewConversationState.streamRunId = String(payload.run_id || "");
    reviewConversationState.streamText = "";
    reviewConversationState.streamThinkingText = "";
    reviewConversationState.streamAnswerText = "";
    reviewConversationState.streamPhase = "reasoning";
    reviewConversationState.streamActive = true;
    renderReviewMessages(reviewConversationState.snapshot?.messages || [], reviewConversationState.snapshot?.questions || []);
  });
  source.addEventListener("workspace.delta", (event) => {
    reviewConversationState.eventCursor = Math.max(reviewConversationState.eventCursor, Number(event.lastEventId || 0));
    const payload = JSON.parse(event.data || "{}").payload || {};
    if (reviewConversationState.streamRunId && payload.run_id !== reviewConversationState.streamRunId) return;
    reviewConversationState.streamRunId = String(payload.run_id || reviewConversationState.streamRunId || "");
    reviewConversationState.streamActive = true;
    const delta = String(payload.delta || "");
    const phase = payload.phase === "content" ? "content" : "reasoning";
    reviewConversationState.streamPhase = phase;
    reviewConversationState.streamText += delta;
    if (phase === "reasoning") reviewConversationState.streamThinkingText += delta;
    else reviewConversationState.streamAnswerText += delta;
    renderReviewMessages(reviewConversationState.snapshot?.messages || [], reviewConversationState.snapshot?.questions || []);
  });
  source.onerror = () => {
    if (reviewConversationState.currentId !== sessionId) source.close();
  };
}

function scheduleReviewConversationRefresh() {
  if (reviewConversationState.refreshTimer) window.clearTimeout(reviewConversationState.refreshTimer);
  reviewConversationState.refreshTimer = window.setTimeout(() => refreshCurrentReviewConversation().catch(showReviewConversationError), 180);
}

function updateReviewUploadStatus() {
  const sessionId = reviewConversationState.currentId;
  const pending = reviewAttachmentUploads.get(sessionId);
  $("sendReviewConversationButton").disabled = Boolean(pending) || reviewConversationSending.has(sessionId);
  if (pending) $("reviewConversationHint").textContent = pending.message;
}

function applyReviewUploadedAttachments(sessionId, data) {
  const sessionIndex = reviewConversationState.sessions.findIndex(item => item.id === sessionId);
  if (data.session && sessionIndex >= 0) reviewConversationState.sessions[sessionIndex] = data.session;
  if (reviewConversationState.currentId !== sessionId) return;
  const snapshot = reviewConversationState.snapshot;
  if (!snapshot || snapshot.session?.id !== sessionId) return;
  const attachments = new Map((snapshot.attachments || []).map(item => [item.id, item]));
  for (const item of data.attachments || (data.attachment ? [data.attachment] : [])) attachments.set(item.id, item);
  snapshot.attachments = [...attachments.values()];
  if (data.session) {
    snapshot.session = data.session;
    $("reviewConversationTitle").textContent = data.session.title || "新审校";
    $("reviewConversationStatus").textContent = reviewSessionStatusLabel(data.session.status);
    renderReviewConversationList();
  }
  renderReviewAttachments(snapshot.attachments);
  updateReviewUploadStatus();
}

function uploadReviewAttachment(sessionId, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/ai-review/conversations/${encodeURIComponent(sessionId)}/attachments`);
    xhr.responseType = "json";
    xhr.timeout = 300000;
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.min(100, Math.floor(event.loaded * 100 / event.total)));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response || {});
      else reject(new Error(xhr.response?.detail || `添加文件失败（${xhr.status}）`));
    };
    xhr.onerror = () => reject(new Error("文件传输失败，请确认工具仍在运行后重试。"));
    xhr.ontimeout = () => reject(new Error("添加文件超时，请先检查附件列表，再决定是否重新添加。"));
    xhr.onabort = () => reject(new Error("文件传输已取消。"));
    const form = new FormData(); form.append("files", file); xhr.send(form);
  });
}

async function uploadReviewConversationFiles(files) {
  // A drag event's FileList is protected after its handler yields. Snapshot it first.
  const selected = Array.from(files || []);
  if (!selected.length) return;
  if (selected.length > 50) throw new Error("一次最多上传 50 个文件");
  if (reviewConversationCreation) await reviewConversationCreation;
  if (!reviewConversationState.currentId) await createReviewConversation();
  const sessionId = reviewConversationState.currentId;
  const pending = reviewAttachmentUploads.get(sessionId) || {count: 0, message: "等待添加文件…"};
  pending.count += 1;
  reviewAttachmentUploads.set(sessionId, pending); updateReviewUploadStatus();
  const run = async () => {
    try {
      for (const [index, file] of selected.entries()) {
        const label = `正在添加 ${index + 1}/${selected.length}：${file.name}`;
        pending.message = `${label} · 0%`; updateReviewUploadStatus();
        const data = await uploadReviewAttachment(sessionId, file, percent => {
          pending.message = percent >= 100 ? `${label} · 正在保存…` : `${label} · ${percent}%`;
          if (reviewConversationState.currentId === sessionId) updateReviewUploadStatus();
        });
        applyReviewUploadedAttachments(sessionId, data);
      }
      if (reviewConversationState.currentId === sessionId) $("reviewConversationHint").textContent = "文件已添加";
    } finally {
      pending.count -= 1;
      if (!pending.count) reviewAttachmentUploads.delete(sessionId);
      updateReviewUploadStatus();
    }
  };
  const work = reviewAttachmentUploadQueue.then(run);
  reviewAttachmentUploadQueue = work.catch(() => {});
  return work;
}

async function chooseReviewConversationFiles() {
  const data = await api("/api/dialog/select-review-files", { timeoutMs: 0 });
  const paths = Array.isArray(data.file_paths) ? data.file_paths.filter(Boolean) : [];
  if (!paths.length) return;
  if (!reviewConversationState.currentId) await createReviewConversation();
  $("reviewConversationHint").textContent = `正在添加 ${paths.length} 个文件…`;
  const sessionId = reviewConversationState.currentId;
  for (const filePath of paths) {
    const data = await api(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/attachments/local`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath }),
    });
    applyReviewUploadedAttachments(sessionId, data);
  }
  $("reviewConversationHint").textContent = "文件已添加，可在对话中溯源打开原文件";
}

async function sendReviewConversationMessage() {
  if (reviewConversationCreation) await reviewConversationCreation;
  if (!reviewConversationState.currentId) await createReviewConversation();
  const sendingSessionId = reviewConversationState.currentId;
  if (reviewAttachmentUploads.has(sendingSessionId)) throw new Error("文件仍在添加，请等待完成后再发送。");
  const text = $("reviewComposerInput").value.trim();
  const attachments = (reviewConversationState.snapshot?.attachments || []).filter((item) => !item.sent_at);
  if (!text && !attachments.length) throw new Error("请输入待审校文本或添加文件");
  reviewConversationSending.add(sendingSessionId);
  updateReviewUploadStatus();
  $("reviewConversationHint").textContent = "Workspace Agent 正在识别内容…";
  renderReviewConversationResults([]);
  try {
    await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/messages`, {
      method: "POST",
      body: JSON.stringify({
        text,
        prompt_template_id: reviewConversationState.promptTemplateId || null,
        term_base_id: reviewConversationState.termBaseId || null,
        memoq_term_base_ids: reviewConversationState.memoqTermBaseIds || [],
        source_language: reviewConversationState.sourceLanguage,
        target_languages: reviewConversationState.targetLanguages,
        auto_start: $("reviewAutoStart").checked,
      }),
    });
    $("reviewComposerInput").value = "";
    await refreshCurrentReviewConversation();
  } finally {
    reviewConversationSending.delete(sendingSessionId);
    updateReviewUploadStatus();
  }
}

function beginRenameCurrentReviewConversation() {
  const input = $("reviewConversationTitleInput");
  if (!input.classList.contains("hidden")) {
    saveCurrentReviewConversationTitle().catch(showReviewConversationError);
    return;
  }
  input.value = reviewConversationState.snapshot?.session?.title || "新审校";
  $("reviewConversationTitle").classList.add("hidden");
  input.classList.remove("hidden");
  $("renameReviewConversationButton").textContent = "✓";
  input.focus();
  input.select();
}

function cancelRenameCurrentReviewConversation() {
  $("reviewConversationTitleInput").classList.add("hidden");
  $("reviewConversationTitle").classList.remove("hidden");
  $("renameReviewConversationButton").textContent = "✎";
}

async function saveCurrentReviewConversationTitle() {
  const title = $("reviewConversationTitleInput").value.trim();
  if (!title) throw new Error("会话名称不能为空");
  await renameReviewConversation(reviewConversationState.currentId, title);
  cancelRenameCurrentReviewConversation();
}

async function removeReviewPendingAttachment(attachmentId) {
  await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/attachments/${encodeURIComponent(attachmentId)}`, {
    method: "DELETE",
  });
  await refreshCurrentReviewConversation();
}

async function openReviewAttachmentMappingDialog(attachment) {
  reviewConversationState.mappingAttachmentId = String(attachment.id || "");
  $("reviewAttachmentMappingTitle").textContent = attachment.original_filename || "文件导入方式";
  const suffix = String(attachment.original_filename || "FILE").split(".").pop().toUpperCase().slice(0, 5);
  document.querySelector(".review-mapping-file-icon").textContent = suffix || "FILE";
  if (!aiReviewExcelMappingPresets.length) await loadAiReviewExcelMappingPresets();
  const select = $("reviewAttachmentPresetSelect");
  select.innerHTML = "";
  aiReviewExcelMappingPresets.forEach((preset) => {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.name || "未命名模板";
    select.appendChild(option);
  });
  select.insertBefore(new Option("新建列设置", ""), select.firstChild);
  const requestedMode = attachment.mapping_mode === "preset" ? "preset" : "ai";
  document.querySelectorAll('input[name="reviewAttachmentMappingMode"]').forEach((input) => {
    input.checked = input.value === requestedMode;
  });
  select.value = attachment.mapping_preset_id || select.options[0]?.value || "";
  const isExcel = /\.(xlsx|xlsm|xls)$/i.test(attachment.original_filename || "");
  const presetRadio = document.querySelector('input[name="reviewAttachmentMappingMode"][value="preset"]');
  presetRadio.disabled = !isExcel;
  if (!isExcel && requestedMode === "preset") {
    document.querySelector('input[name="reviewAttachmentMappingMode"][value="ai"]').checked = true;
  }
  updateReviewAttachmentMappingControls();
  $("reviewAttachmentMappingHint").textContent = isExcel ? "" : "该格式仅支持 AI 识别；映射模板只适用于 Excel。";
  $("reviewAttachmentMappingDialog").showModal();
}

function updateReviewAttachmentMappingControls() {
  const mode = document.querySelector('input[name="reviewAttachmentMappingMode"]:checked')?.value || "ai";
  const presetRadio = document.querySelector('input[name="reviewAttachmentMappingMode"][value="preset"]');
  document.querySelectorAll(".review-import-mode-option").forEach((option) => {
    const input = option.querySelector('input[name="reviewAttachmentMappingMode"]');
    option.classList.toggle("selected", Boolean(input?.checked));
    option.classList.toggle("disabled", Boolean(input?.disabled));
  });
  $("reviewAttachmentPresetField").classList.toggle("hidden", mode !== "preset");
  $("reviewAttachmentPresetSelect").disabled = mode !== "preset" || Boolean(presetRadio?.disabled);
  $("editReviewAttachmentMappingButton").disabled = mode !== "preset" || Boolean(presetRadio?.disabled);
  $("saveReviewAttachmentMappingButton").textContent = mode === "preset" ? "下一步：设置列与语种" : "确认自动识别";
}

async function openReviewAttachmentMappingEditor() {
  const attachmentId = reviewConversationState.mappingAttachmentId;
  if (!attachmentId) throw new Error("没有可编辑的附件");
  $("reviewAttachmentMappingHint").textContent = "正在读取工作表结构…";
  const data = await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/attachments/${encodeURIComponent(attachmentId)}/structure`);
  const attachment = data.attachment || {};
  const structure = data.manifest?.structure || attachment.manifest?.structure || {};
  const sheets = Array.isArray(structure.sheets) ? structure.sheets : [];
  if (!sheets.length) throw new Error("没有读取到可映射的工作表结构");
  aiReviewSheetNames = sheets.map((sheet) => String(sheet.name || ""));
  aiReviewColumnsBySheet = Object.fromEntries(sheets.map((sheet) => [String(sheet.name || ""), Array.isArray(sheet.columns) ? sheet.columns : []]));
  aiReviewExcelMappingState = Object.fromEntries(aiReviewSheetNames.map((sheetName) => [sheetName, { sources: [], targets: {}, infos: {} }]));
  aiReviewActiveSheetName = aiReviewSheetNames[0] || "";
  aiReviewMappingTemplateIssues = [];
  reviewConversationState.mappingEditorAttachmentId = attachmentId;
  reviewConversationState.mappingEditorPresetId = $("reviewAttachmentPresetSelect").value || "";
  reviewConversationState.mappingEditorContext = "conversation";
  $("mappingSourceLanguageInput").value = reviewConversationState.sourceLanguage === "auto" ? "" : reviewConversationState.sourceLanguage;
  const chosenTargets = reviewConversationState.targetLanguages.filter((value) => value !== "auto");
  $("mappingTargetLanguageInput").value = chosenTargets.length === 1 ? chosenTargets[0] : "auto";
  await loadAiReviewExcelMappingPresets(reviewConversationState.mappingEditorPresetId);
  if (reviewConversationState.mappingEditorPresetId) {
    const presetData = await api(`/api/ai-review/excel-mapping-presets/${encodeURIComponent(reviewConversationState.mappingEditorPresetId)}`);
    applyAiReviewExcelMappingPresetToState(presetData?.preset?.mapping || {});
  } else if (attachment.manifest?.manual_mapping) {
    applyAiReviewExcelMappingPresetToState(attachment.manifest.manual_mapping);
  }
  $("excelMappingDialogTitle").textContent = attachment.original_filename || "Excel 映射";
  $("excelMappingDialogSubtitle").textContent = "已读取当前文件结构。按工作表选择原文列、译文列和补充信息列。";
  $("applyExcelMappingButton").textContent = "确认并应用映射";
  renderAiReviewExcelMappingDialog();
  $("reviewAttachmentMappingDialog").close();
  $("excelMappingDialog").showModal();
}

async function saveReviewAttachmentMapping() {
  const attachmentId = reviewConversationState.mappingAttachmentId;
  const mode = document.querySelector('input[name="reviewAttachmentMappingMode"]:checked')?.value || "ai";
  const presetId = mode === "preset" ? $("reviewAttachmentPresetSelect").value : null;
  if (mode === "preset") { await openReviewAttachmentMappingEditor(); return; }
  await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}/attachments/${encodeURIComponent(attachmentId)}`, {
    method: "PATCH",
    body: JSON.stringify({ mode, preset_id: presetId }),
  });
  $("reviewAttachmentMappingDialog").close();
  await refreshCurrentReviewConversation();
}

async function deleteCurrentReviewConversation() {
  if (!reviewConversationState.currentId) return;
  if (!window.confirm("删除后会同时清理本会话的附件和审校结果，确定继续吗？")) return;
  await api(`/api/ai-review/conversations/${encodeURIComponent(reviewConversationState.currentId)}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm: true }),
  });
  if (reviewConversationState.eventSource) reviewConversationState.eventSource.close();
  reviewConversationState.currentId = "";
  reviewConversationState.snapshot = null;
  reviewConversationState.activeTarget = "";
  await loadReviewConversations();
}

function openReviewLanguagePopover(mode, anchor) {
  reviewConversationState.languageMode = mode;
  $("reviewLanguagePopoverTitle").textContent = mode === "source" ? "源语言" : "目标语言";
  $("reviewLanguagePopoverHint").textContent = mode === "source" ? "单选" : "可多选";
  $("reviewLanguageSearch").value = "";
  renderReviewLanguageOptions();
  const popover = $("reviewLanguagePopover");
  popover.classList.remove("hidden");
  const composer = $("reviewComposer");
  const wantedLeft = Math.max(0, anchor.offsetLeft - 6);
  const maxLeft = Math.max(0, composer.clientWidth - popover.offsetWidth - 14);
  popover.style.left = `${Math.min(wantedLeft, maxLeft)}px`;
  $("reviewLanguageSearch").focus();
}

function closeReviewLanguagePopover() {
  $("reviewLanguagePopover").classList.add("hidden");
}

function currentReviewTermBase() {
  return reviewConversationState.termBases.find((item) => item.id === reviewConversationState.termBaseId) || null;
}

function reviewTermBaseLanguageLabel(value) {
  return reviewTermBaseLanguageLabels[value] || String(value || "").replaceAll("_", " ");
}

function toggleReviewTermBasePopover() {
  closeReviewLanguagePopover();
  renderReviewTermBaseOptions();
  const popover = $("reviewTermBasePopover");
  popover.classList.toggle("hidden");
  if (!popover.classList.contains("hidden")) {
    const anchor = $("reviewTermBaseChip");
    const composer = $("reviewComposer");
    const wantedLeft = Math.max(0, anchor.offsetLeft - 6);
    const maxLeft = Math.max(0, composer.clientWidth - popover.offsetWidth - 14);
    popover.style.left = `${Math.min(wantedLeft, maxLeft)}px`;
  }
}

function closeReviewTermBasePopover() {
  $("reviewTermBasePopover").classList.add("hidden");
}

function renderReviewTermBaseOptions() {
  const container = $("reviewTermBaseOptions");
  if (!container) return;
  container.innerHTML = "";
  const query = String($("reviewTermBaseSearch")?.value || "").trim().toLowerCase();
  const remoteBases = (reviewConversationState.memoqTermBases || []).filter((termBase) => !query || (String(termBase.name || "") + " " + String(termBase.project || "")).toLowerCase().includes(query));
  const selectedRemoteBases = remoteBases.filter((termBase) => reviewConversationState.memoqTermBaseIds.includes(termBase.id));
  const unselectedRemoteBases = remoteBases.filter((termBase) => !reviewConversationState.memoqTermBaseIds.includes(termBase.id));
  [...selectedRemoteBases, ...unselectedRemoteBases].forEach((termBase) => {
    const row = document.createElement("div");
    row.className = "review-term-base-option" + (reviewConversationState.memoqTermBaseIds.includes(termBase.id) ? " selected" : "");
    row.setAttribute("role", "menuitem");
    const check = document.createElement("span");
    check.className = "review-term-base-option-check";
    check.textContent = reviewConversationState.memoqTermBaseIds.includes(termBase.id) ? "✓" : "";
    const copy = document.createElement("span");
    copy.className = "review-term-base-option-copy";
    const name = document.createElement("strong");
    name.textContent = termBase.name || "memoQ 术语库";
    const meta = document.createElement("small");
    meta.textContent = "memoQ" + (termBase.project ? " · " + termBase.project : "");
    copy.append(name, meta); row.append(check, copy);
    row.addEventListener("click", () => {
      const ids = new Set(reviewConversationState.memoqTermBaseIds);
      if (ids.has(termBase.id)) ids.delete(termBase.id); else ids.add(termBase.id);
      reviewConversationState.memoqTermBaseIds = Array.from(ids);
      reviewConversationState.termBaseId = "";
      renderReviewTermBaseOptions(); updateReviewComposerChips();
      saveReviewConversationComposerSettings().catch(showReviewConversationError);
    });
    container.appendChild(row);
  });
  if (!reviewConversationState.termBases.length && !(reviewConversationState.memoqTermBases || []).length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "尚未缓存术语表";
    container.appendChild(empty);
    return;
  }
  const selectedLocalBases = reviewConversationState.termBases.filter((termBase) => termBase.id === reviewConversationState.termBaseId);
  const unselectedLocalBases = reviewConversationState.termBases.filter((termBase) => termBase.id !== reviewConversationState.termBaseId);
  [...selectedLocalBases, ...unselectedLocalBases].forEach((termBase) => {
    const row = document.createElement("div");
    row.className = `review-term-base-option ${termBase.id === reviewConversationState.termBaseId ? "selected" : ""}`.trim();
    row.setAttribute("role", "menuitem");
    row.tabIndex = 0;
    const check = document.createElement("span");
    check.className = "review-term-base-option-check";
    check.textContent = termBase.id === reviewConversationState.termBaseId ? "✓" : "";
    const copy = document.createElement("span");
    copy.className = "review-term-base-option-copy";
    const name = document.createElement("strong");
    name.textContent = termBase.filename || "未命名术语表";
    const meta = document.createElement("small");
    const noteLabel = termBase.has_entry_note ? " · 含备注" : "";
    const languages = (termBase.languages || []).map(reviewTermBaseLanguageLabel);
    meta.textContent = `${Number(termBase.entry_count || 0)} 条 · ${languages.join(" / ")}${noteLabel}`;
    copy.append(name, meta);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "review-term-base-delete";
    remove.title = `删除 ${termBase.filename || "术语表"}`;
    remove.setAttribute("aria-label", remove.title);
    remove.textContent = "×";
    const select = () => selectReviewTermBase(termBase.id).catch(showReviewConversationError);
    row.addEventListener("click", (event) => {
      if (!remove.contains(event.target)) select();
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select();
      }
    });
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteReviewTermBase(termBase).catch(showReviewConversationError);
    });
    row.append(check, copy, remove);
    container.appendChild(row);
  });
}

async function selectReviewTermBase(termBaseId) {
  reviewConversationState.termBaseId = String(termBaseId || "");
  updateReviewComposerChips();
  renderReviewTermBaseOptions();
  closeReviewTermBasePopover();
  await saveReviewConversationComposerSettings();
}

async function uploadReviewTermBase(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  $("reviewConversationHint").textContent = `正在读取术语表 ${file.name}…`;
  const data = await api("/api/ai-review/term-bases", { method: "POST", body: form });
  const termBase = data.term_base || {};
  await loadReviewTermBases();
  await selectReviewTermBase(termBase.id || "");
  $("reviewConversationHint").textContent = `已缓存并选择 ${termBase.filename || file.name}`;
}

async function deleteReviewTermBase(termBase) {
  if (!window.confirm(`确定删除术语表“${termBase.filename || "未命名术语表"}”吗？所有引用它的会话将改为不使用术语表。`)) return;
  await api(`/api/ai-review/term-bases/${encodeURIComponent(termBase.id)}`, { method: "DELETE" });
  if (reviewConversationState.termBaseId === termBase.id) reviewConversationState.termBaseId = "";
  await loadReviewTermBases();
  await refreshCurrentReviewConversation();
  $("reviewConversationHint").textContent = "术语表已删除";
}

function renderReviewLanguageOptions() {
  const search = $("reviewLanguageSearch").value.trim().toLowerCase();
  const container = $("reviewLanguageOptions");
  container.innerHTML = "";
  [...new Set([...reviewLanguages, reviewConversationState.sourceLanguage, ...reviewConversationState.targetLanguages].filter(x => x && !["auto", "none"].includes(x)))]
    .filter((language) => reviewConversationState.languageMode === "source" || language !== "无源文")
    .filter((language) => !search || language.toLowerCase().includes(search))
    .forEach((language) => {
    const value = language === "自动检测" ? "auto" : language === "无源文" ? "none" : language;
    const label = document.createElement("label");
    label.className = "review-language-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "review-language";
    input.value = value;
    input.checked = reviewConversationState.languageMode === "source"
      ? reviewConversationState.sourceLanguage === value
      : reviewConversationState.targetLanguages.includes(value);
    label.classList.toggle("selected", input.checked);
    const check = document.createElement("span");
    check.className = "review-language-check";
    check.textContent = "✓";
    label.append(input, check, document.createTextNode(language));
    label.addEventListener("click", (event) => {
      event.preventDefault();
      if (reviewConversationState.languageMode === "source") {
        reviewConversationState.sourceLanguage = value;
        updateReviewComposerChips();
        closeReviewLanguagePopover();
        saveReviewConversationComposerSettings().catch(showReviewConversationError);
        return;
      }
      let selected = [...reviewConversationState.targetLanguages];
      if (value === "auto") {
        selected = ["auto"];
      } else {
        selected = selected.filter((item) => item !== "auto");
        selected = selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value];
        if (!selected.length) selected = ["auto"];
      }
      reviewConversationState.targetLanguages = selected;
      updateReviewComposerChips();
      renderReviewLanguageOptions();
      saveReviewConversationComposerSettings().catch(showReviewConversationError);
    });
    container.appendChild(label);
  });
  const custom = $("reviewLanguageSearch").value.trim();
  if (custom && !reviewLanguages.some(x => x.toLowerCase() === custom.toLowerCase())) {
    const button = document.createElement("button"); button.type = "button"; button.className = "secondary custom-language-action";
    button.textContent = `添加并使用“${custom}”`;
    button.onclick = () => {
      if (reviewConversationState.languageMode === "source") reviewConversationState.sourceLanguage = custom;
      else reviewConversationState.targetLanguages = [...new Set([...reviewConversationState.targetLanguages.filter(x => x !== "auto"), custom])];
      updateReviewComposerChips(); closeReviewLanguagePopover(); saveReviewConversationComposerSettings().catch(showReviewConversationError);
    };
    container.appendChild(button);
  }
}

function updateReviewComposerChips() {
  const prompt = aiReviewPromptTemplates.find((item) => item.id === reviewConversationState.promptTemplateId) || aiReviewPromptTemplates[0];
  $("reviewPromptChip").textContent = `提示词：${prompt?.name || "默认"}`;
  const sourceLabel = reviewConversationState.sourceLanguage === "auto"
    ? "自动"
    : reviewConversationState.sourceLanguage === "none" ? "无" : reviewConversationState.sourceLanguage;
  $("reviewSourceLanguageChip").textContent = `源语言：${sourceLabel}`;
  const targets = reviewConversationState.targetLanguages.map((value) => value === "auto" ? "自动" : value);
  $("reviewTargetLanguageChip").textContent = `目标语言：${targets.join("、")}`;
  const termBase = currentReviewTermBase();
  const remote = (reviewConversationState.memoqTermBases || []).filter((item) => reviewConversationState.memoqTermBaseIds.includes(item.id));
  const remoteCount = remote.length;
  $("reviewTermBaseChip").textContent = remoteCount === 1 ? remote[0].name : remoteCount ? "术语表（" + remoteCount + "）" : (termBase?.filename || "术语表");
  $("reviewTermBaseChip").title = termBase
    ? `${termBase.filename} · ${Number(termBase.entry_count || 0)} 条术语`
    : "选择术语表";
}

async function openReviewConversationPromptDialog() {
  const templateId = reviewConversationState.promptTemplateId || aiReviewPromptTemplates[0]?.id;
  if (!templateId) throw new Error("没有可用提示词模板");
  $("promptTemplateSelect").value = templateId;
  const data = await api(`/api/ai-review/prompt-templates/${encodeURIComponent(templateId)}`);
  fillAiReviewPromptDialog(data.template || {});
  $("promptDialog").showModal();
}

function reviewSessionStatusLabel(status) {
  return ({ draft: "等待输入", inspecting: "正在识别文件", needs_input: "等待确认", ready: "识别完成", reviewing: "正在审校", validating: "正在校验", completed: "已完成", partial: "部分完成", failed: "失败" })[status] || status || "等待输入";
}

function reviewAttachmentStatusLabel(status) {
  return ({ uploaded: "待识别", ready: "已识别", needs_reader: "格式不支持", failed: "读取失败" })[status] || status || "待识别";
}

function showReviewConversationError(error) {
  $("reviewConversationHint").textContent = error?.message || String(error || "操作失败");
}

async function chooseAiReviewFile() {
  $("reviewFileInput").click();
}

async function uploadAiReviewFile(file) {
  if (!file) {
    return;
  }
  resetAiReviewTaskView();
  setAiReviewFileCard(file.name || "");
  $("reviewFileHint").textContent = "正在读取文件...";
  const formData = new FormData();
  formData.append("file", file);
  const data = await api("/api/ai-review/file/upload", {
    method: "POST",
    body: formData,
    timeoutMs: 300000,
  });
  if (String(data.file_type || "") === "excel") {
    initializeAiReviewExcelMapping(data);
    $("openExcelMappingButton").disabled = !aiReviewSheetNames.length;
  } else {
    aiReviewSheetNames = [];
    aiReviewColumnsBySheet = {};
    aiReviewExcelMappingState = {};
    aiReviewActiveSheetName = "";
    $("excelMappingSummary").textContent = "";
  }
  renderAiReviewBatch(data);
}

async function loadAiReviewFile(filePath) {
  resetAiReviewTaskView();
  const data = await api("/api/ai-review/file/load", {
    method: "POST",
    body: JSON.stringify({ file_path: filePath }),
    timeoutMs: 300000,
  });
  $("reviewFileHint").textContent = data.message || "读取完成";
  if (String(data.file_type || "") === "excel") {
    initializeAiReviewExcelMapping(data);
    $("openExcelMappingButton").disabled = !aiReviewSheetNames.length;
  } else {
    aiReviewSheetNames = [];
    aiReviewColumnsBySheet = {};
    aiReviewExcelMappingState = {};
    aiReviewActiveSheetName = "";
    $("excelMappingSummary").textContent = "";
  }
  renderAiReviewBatch(data);
}

function resetAiReviewTaskView() {
  aiReviewTaskId = "";
  aiReviewCurrentTask = null;
  aiReviewLogCursor = 0;
  if (aiReviewTaskPoller) {
    window.clearInterval(aiReviewTaskPoller);
    aiReviewTaskPoller = null;
  }
  $("reviewLogList").innerHTML = "";
  renderAiReviewResultHead({});
  $("reviewResultBody").innerHTML = '<tr><td colspan="6" class="empty-cell">暂无审校结果</td></tr>';
  $("outputPanel").classList.add("hidden");
  $("outputPath").textContent = "暂无输出";
  $("openOutputFileButton").disabled = true;
  $("openReviewDetailButton").disabled = true;
  renderAiReviewProgress({});
  $("reviewTaskHint").textContent = "";
}

async function startAiReviewTask() {
  if (!aiReviewBatch?.id) {
    $("reviewTaskHint").textContent = "请先读取文件";
    return;
  }
  const mode = $("enableAiReview").checked
    ? ($("enableDirectionalReview").checked ? "directional" : "normal")
    : "normal";
  const data = await api("/api/ai-review/start", {
    method: "POST",
    body: JSON.stringify({
      batch_id: aiReviewBatch.id,
      prompt_template_id: $("promptTemplateSelect").value || null,
      source_language: $("sourceLanguageInput").value || "",
      target_language: $("targetLanguageInput").value || "",
      mode,
      directional_template_id: $("directionalTemplateSelect").value || null,
      enable_ai_review: $("enableAiReview").checked,
      enable_forbidden_check: $("enableForbiddenCheck").checked,
      forbidden_template_id: $("forbiddenTemplateSelect").value || null,
    }),
  });
  aiReviewTaskId = String(data?.task?.id || "");
  aiReviewLogCursor = 0;
  $("reviewLogList").innerHTML = "";
  $("reviewTaskHint").textContent = data.message || "审校任务已启动";
  renderAiReviewProgress(data?.task || {});
  setAiReviewTaskStatus({
    active: true,
    pill: "运行中",
    pillClass: "running",
    stageLabel: "审校中",
    message: "正在执行 AI 审校",
  });
  await pollAiReviewTaskSafely();
  if (aiReviewTaskPoller) {
    window.clearInterval(aiReviewTaskPoller);
  }
  aiReviewTaskPoller = window.setInterval(pollAiReviewTaskSafely, 1500);
}

async function pollAiReviewTaskSafely() {
  if (aiReviewTaskPollInFlight || !aiReviewTaskId || document.hidden) return;
  aiReviewTaskPollInFlight = true;
  try {
    await pollAiReviewTask();
  } catch (error) {
    $("reviewTaskHint").textContent = error?.message || "审校状态读取失败，请稍后重试。";
  } finally {
    aiReviewTaskPollInFlight = false;
  }
}

async function pollAiReviewTask() {
  if (!aiReviewTaskId) {
    return;
  }
  const data = await api(`/api/ai-review/tasks/${encodeURIComponent(aiReviewTaskId)}`);
  renderAiReviewResults(data.task || {}, data.results || []);
  const task = data.task || {};
  const status = String(task.status || "");
  const done = ["completed", "completed_with_errors", "failed"].includes(status);
  const hasFailedItems = Number(task.failed_count || 0) > 0 || status === "completed_with_errors";
  setAiReviewTaskStatus({
    active: !done,
    pill: status === "failed" ? "失败" : hasFailedItems ? "有失败" : done ? "空闲" : "运行中",
    pillClass: status === "failed" || hasFailedItems ? "failed" : done ? "" : "running",
    stageLabel: String(task.status_label || task.status || "审校中"),
    message: String(task.message || task.status_label || "正在执行 AI 审校"),
  });
  const logs = await api(`/api/ai-review/tasks/${encodeURIComponent(aiReviewTaskId)}/logs?after_id=${aiReviewLogCursor}`);
  appendAiReviewLogs(logs.logs || []);
  if (done && aiReviewTaskPoller) {
    window.clearInterval(aiReviewTaskPoller);
    aiReviewTaskPoller = null;
  }
}

async function openAiReviewOutputDir() {
  await api("/api/ai-review/outputs/open-folder", {
    method: "POST",
    body: "{}",
  });
}

async function openAiReviewOutputFile() {
  const filePath = $("outputPath").textContent.trim();
  if (!filePath || filePath === "暂无输出") {
    return;
  }
  await api("/api/ai-review/outputs/open-file", {
    method: "POST",
    body: JSON.stringify({ file_path: filePath }),
  });
}

function setCrossExcelOutput(filePath, message = "") {
  crossExcelOutputFile = String(filePath || "").trim();
  $("crossExcelOutputFile").textContent = crossExcelOutputFile || "暂无输出";
  $("crossExcelOutputHint").textContent = message || (crossExcelOutputFile ? "合并完成，可以打开文件或输出目录。" : "合并结果会保存到工具 output 目录。");
  $("openCrossExcelOutputButton").disabled = !crossExcelOutputFile;
  $("openCrossExcelOutputFileButton").disabled = !crossExcelOutputFile;
}

async function copyToClipboard(text) {
  const value = String(text || "");
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

async function loadSettings() {
  const data = await api("/api/settings");
  const learningOptions = await api('/api/ai-review/conversations/learning/options');
  $('reviewCacheEnabled').checked = learningOptions.cache_enabled;
  $('reviewLearningEnabled').checked = learningOptions.learning_enabled;
  currentProviderName = data.provider_name || "DeepSeek";
  renderModelOptions([], data.model_name || "");
  $("apiKey").value = data.api_key || "";
  currentBaseUrl = data.base_url || "";
  $("timeoutSeconds").value = data.timeout_seconds || 90;
  $("disableSystemProxy").checked = data.disable_system_proxy !== false;
  $("sourceLanguage").value = data.source_language || "中文";
  $("extractionMode").value = data.extraction_mode || "terms";
  $("nontransPlaceholderFormat").value = data.nontrans_placeholder_format || "<{n}>";
  const nontrans = data.nontrans_stage_settings || {};
  const recall = data.term_recall_stage_settings || {};
  const review = data.term_review_stage_settings || {};
  const aiReview = data.ai_review_stage_settings || {};
  $("nontransLimit").value = Number(nontrans.chunk_char_limit || 0) > 0 ? nontrans.chunk_char_limit : 5000;
  $("recallLimit").value = Number(recall.batch_request_char_limit || 0) > 0 ? recall.batch_request_char_limit : 5000;
  $("reviewLimit").value = Number(review.batch_request_char_limit || 0) > 0 ? review.batch_request_char_limit : 5000;
  $("reviewContextLimit").value = review.max_context_chars || 220;
  const normalizeReasoningEffort = (value) => ["low", "medium", "high"].includes(value) ? value : "low";
  $("nontransReasoningEffort").value = normalizeReasoningEffort(nontrans.reasoning_effort);
  $("recallReasoningEffort").value = normalizeReasoningEffort(recall.reasoning_effort);
  $("termReviewReasoningEffort").value = normalizeReasoningEffort(review.reasoning_effort);
  if ($("reviewAiLimit")) {
    const configuredLimit = Number(aiReview.batch_request_char_limit || 0);
    $("reviewAiLimit").value = configuredLimit > 0 ? configuredLimit : 1500;
  }
  $("reviewMaxItems").value = aiReview.max_items_per_request || 20;
  $("reviewReasoningEffort").value = normalizeReasoningEffort(aiReview.reasoning_effort === "max" ? "high" : aiReview.reasoning_effort);
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
    timeoutMs: 120000,
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

function reviewSettingsPayload() {
  return {
    ai_review_batch_char_limit: Number($("reviewAiLimit").value || 1500),
    ai_review_max_items_per_request: Number($("reviewMaxItems").value || 20),
    ai_review_reasoning_effort: $("reviewReasoningEffort").value || "low",
  };
}

async function saveReviewSettings() {
  await api('/api/ai-review/conversations/learning/options', {method:'POST', body:JSON.stringify({
    cache_enabled:$('reviewCacheEnabled').checked, learning_enabled:$('reviewLearningEnabled').checked})});
  await api("/api/settings", { method: "POST", body: JSON.stringify(reviewSettingsPayload()) });
  $("reviewSettingsHint").textContent = "审校设置已保存";
  setTimeout(() => ($("reviewSettingsHint").textContent = ""), 1800);
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
  if (appUpdateState.update_available && !appUpdateAutoPrompted) {
    appUpdateAutoPrompted = true;
    window.setTimeout(openAppUpdateModal, 180);
  }
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

async function chooseFolder() {
  try {
    const data = await api("/api/dialog/select-folder", {
      method: "POST",
      body: "{}",
      timeoutMs: 0,
    });
    if (data.cancelled || !data.folder_path) {
      return;
    }
    $("folderPath").value = data.folder_path;
    const result = await api(`/api/preprocess/folder-files?folder_path=${encodeURIComponent(data.folder_path)}`);
    replacePreprocessFiles(result.file_paths || [], data.folder_path);
  } catch (error) {
    setPreprocessTaskHint(error.message, true);
  }
}

async function chooseCrossExcelFolder() {
  try {
    const data = await api("/api/dialog/select-folder", {
      method: "POST",
      body: "{}",
      timeoutMs: 0,
    });
    if (data.cancelled || !data.folder_path) {
      return;
    }
    $("crossExcelFolderPath").value = data.folder_path;
    await scanCrossExcelFolder();
  } catch (error) {
    $("crossExcelScanHint").textContent = error.message;
  }
}

async function chooseDiffFolder(side) {
  const data = await api("/api/dialog/select-folder", { method: "POST", body: "{}", timeoutMs: 0 });
  if (!data.cancelled && data.folder_path) {
    if (side === "A") {
      $("diffPathA").value = data.folder_path;
    } else {
      $("diffPathB").value = data.folder_path;
    }
    resetDiffFieldMatchSettings();
  }
}

async function chooseDiffFile(side) {
  const data = await api("/api/dialog/select-review-file", { timeoutMs: 0 });
  if (!data.cancelled && data.file_path) {
    if (side === "A") {
      $("diffPathA").value = data.file_path;
    } else {
      $("diffPathB").value = data.file_path;
    }
    resetDiffFieldMatchSettings();
  }
}

async function scanCrossExcelFolder() {
  const folder = $("crossExcelFolderPath").value.trim();
  if (!folder) {
    $("crossExcelScanHint").textContent = "请先填写输入目录";
    return;
  }
  setTaskStatus("crossExcelPage", {
    active: true,
    taskLabel: "跨Excel搜索与合并",
    pill: "运行中",
    pillClass: "running",
    stageLabel: "扫描目录",
    message: "正在扫描文件和表头",
  });
  renderCurrentTaskStatus();
  try {
    const data = await api(`/api/cross-excel/scan?folder_path=${encodeURIComponent(folder)}`);
    renderCrossExcelScan(data);
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "空闲",
      pillClass: "",
      stageLabel: "扫描完成",
      message: `已发现 ${Number(data.file_count || 0)} 个文件，${Number((data.headers || []).length)} 个表头`,
    });
    renderCurrentTaskStatus();
  } catch (error) {
    crossExcelScanState = null;
    $("crossExcelFileCount").textContent = "0";
    $("crossExcelScanHint").textContent = error.message;
    renderCrossExcelHeaders([]);
    renderCrossExcelSearchResults(null);
    setCrossExcelOutput("");
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "失败",
      pillClass: "failed",
      stageLabel: "扫描失败",
      message: error.message,
    });
    renderCurrentTaskStatus();
  }
}

async function searchCrossExcel() {
  const folder = $("crossExcelFolderPath").value.trim();
  const query = $("crossExcelQuery").value.trim();
  if (!folder) {
    $("crossExcelSearchHint").textContent = "请先选择目录";
    return;
  }
  if (!query) {
    $("crossExcelSearchHint").textContent = "请输入要搜索的内容";
    return;
  }
  $("crossExcelSearchHint").textContent = "搜索中...";
  setTaskStatus("crossExcelPage", {
    active: true,
    taskLabel: "跨Excel搜索与合并",
    pill: "运行中",
    pillClass: "running",
    stageLabel: "全局搜索",
    message: `正在搜索：${query}`,
  });
  renderCurrentTaskStatus();
  try {
    const data = await api("/api/cross-excel/search", {
      method: "POST",
      body: JSON.stringify({
        folder_path: folder,
        query,
        limit: Number($("crossExcelLimit").value || 300),
      }),
      timeoutMs: 600000,
    });
    renderCrossExcelSearchResults(data);
    $("crossExcelSearchHint").textContent = data.truncated ? "结果过多，已按上限截断显示" : "搜索完成";
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "空闲",
      pillClass: "",
      stageLabel: "搜索完成",
      message: data.truncated
        ? `已命中 ${Number((data.items || []).length)} 条，结果已截断`
        : `已命中 ${Number((data.items || []).length)} 条`,
    });
    renderCurrentTaskStatus();
  } catch (error) {
    renderCrossExcelSearchResults(null);
    $("crossExcelSearchHint").textContent = error.message;
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "失败",
      pillClass: "failed",
      stageLabel: "搜索失败",
      message: error.message,
    });
    renderCurrentTaskStatus();
  }
}

async function mergeCrossExcel() {
  const folder = $("crossExcelFolderPath").value.trim();
  if (!folder) {
    $("crossExcelOutputHint").textContent = "请先选择目录";
    return;
  }
  const headers = selectedCrossExcelHeaders();
  if (!headers.length) {
    $("crossExcelOutputHint").textContent = "请至少勾选一个表头";
    return;
  }
  $("crossExcelOutputHint").textContent = "合并中...";
  setTaskStatus("crossExcelPage", {
    active: true,
    taskLabel: "跨Excel搜索与合并",
    pill: "运行中",
    pillClass: "running",
    stageLabel: "按表头合并",
    message: `正在合并 ${headers.length} 个表头`,
  });
  renderCurrentTaskStatus();
  try {
    const data = await api("/api/cross-excel/merge", {
      method: "POST",
      body: JSON.stringify({
        folder_path: folder,
        headers,
        apply_format: $("crossExcelApplyFormat").checked,
      }),
      timeoutMs: 600000,
    });
    setCrossExcelOutput(
      data.output_file || "",
      `合并完成，共输出 ${Number(data.row_count || 0)} 行，${Number(data.column_count || 0)} 列。`,
    );
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "空闲",
      pillClass: "",
      stageLabel: "合并完成",
      message: `已输出 ${Number(data.row_count || 0)} 行到结果文件`,
    });
    renderCurrentTaskStatus();
  } catch (error) {
    setCrossExcelOutput("", error.message);
    setTaskStatus("crossExcelPage", {
      active: false,
      taskLabel: "跨Excel搜索与合并",
      pill: "失败",
      pillClass: "failed",
      stageLabel: "合并失败",
      message: error.message,
    });
    renderCurrentTaskStatus();
  }
}

async function startDiffExcel() {
  const pathA = $("diffPathA").value.trim();
  const pathB = $("diffPathB").value.trim();
  if (!pathA || !pathB) {
    $("diffExcelHint").textContent = "请先选择路径 A 和路径 B。";
    return;
  }
  const compareMode = diffCompareMode();
  if (compareMode === "field_match" && (!diffFieldMatchSettings.referenceField || !diffFieldMatchSettings.compareFields.length)) {
    $("diffExcelHint").textContent = "请先打开字段设置，选择参考字段和比对字段。";
    return;
  }
  $("diffExcelHint").textContent = "比对中...";
  setTaskStatus("diffExcelPage", {
    active: true,
    taskLabel: "Diff 工具",
    pill: "运行中",
    pillClass: "running",
    stageLabel: compareMode === "field_match" ? "按字段匹配" : "按位置比对",
    message: "正在读取并比较两个路径",
  });
  renderCurrentTaskStatus();
  try {
    const started = await api("/api/diff-excel/compare", {
      method: "POST",
      body: JSON.stringify({
        path_a: pathA,
        path_b: pathB,
        compare_mode: compareMode,
        reference_field: diffFieldMatchSettings.referenceField,
        compare_fields: diffFieldMatchSettings.compareFields,
        include_unmatched: diffFieldMatchSettings.includeUnmatched,
      }),
    });
    const taskId = String(started.task_id || "");
    if (!taskId) throw new Error("未能启动比对任务。");
    diffExcelState.taskId = taskId;
    let data = null;
    while (true) {
      const task = await api(`/api/diff-excel/task/${encodeURIComponent(taskId)}`);
      const message = String(task.message || "正在比对");
      $("diffExcelHint").textContent = message;
      setTaskStatus("diffExcelPage", {
        active: true,
        taskLabel: "Diff 工具",
        pill: "运行中",
        pillClass: "running",
        stageLabel: compareMode === "field_match" ? "按字段匹配" : "按位置比对",
        message,
      });
      renderCurrentTaskStatus();
      if (task.status === "completed") {
        data = task.result || {};
        break;
      }
      if (task.status === "failed") {
        throw new Error(String(task.error || "比对失败"));
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    diffExcelState.cacheFile = String(data.cache_file || "");
    diffExcelState.resultId = String(data.result_id || "");
    diffExcelState.previewOffset = 0;
    diffExcelState.previewRecords = [];
    diffExcelState.meta = data.meta || null;
    diffExcelState.outputFile = "";
    diffExcelState.totalCount = Number(data.total_count || 0);
    diffExcelState.matchedCount = Number(data.total_count || 0);
    diffExcelState.previewLimit = 200;
    diffExcelState.previewTruncated = Boolean(data.preview_truncated);
    const meta = diffExcelState.meta || {};
    const fieldSummary = compareMode === "field_match"
      ? `有效参考行 ${Number(meta.valid_reference_rows || 0)}，已配对 ${Number(meta.paired_reference_rows || 0)}，未匹配 ${Number(meta.unmatched_reference_rows || 0)}，跳过字段 ${Number(meta.skipped_field_count || 0)}。`
      : "";
    await applyDiffExcelFilter();
    $("diffExcelHint").textContent = `比对完成，共找到 ${diffExcelState.totalCount} 处差异。${fieldSummary}`;
    setTaskStatus("diffExcelPage", {
      active: false,
      taskLabel: "Diff 工具",
      pill: "空闲",
      pillClass: "",
      stageLabel: "比对完成",
      message: `已找到 ${diffExcelState.totalCount} 处差异`,
    });
    renderCurrentTaskStatus();
  } catch (error) {
    $("diffExcelHint").textContent = error.message;
    clearDiffExcelState();
    setTaskStatus("diffExcelPage", {
      active: false,
      taskLabel: "Diff 工具",
      pill: "失败",
      pillClass: "failed",
      stageLabel: "比对失败",
      message: error.message,
    });
    renderCurrentTaskStatus();
  }
}

async function exportDiffExcel() {
  if (!diffExcelState.cacheFile || !Number(diffExcelState.totalCount || 0)) {
    $("diffExcelHint").textContent = "当前没有可导出的差异。";
    return;
  }
  $("diffExcelHint").textContent = "导出中...";
  try {
    const data = await api("/api/diff-excel/export", {
      method: "POST",
      body: JSON.stringify({
        cache_file: diffExcelState.cacheFile,
        query: "",
        output_file: "",
      }),
      timeoutMs: 600000,
    });
    diffExcelState.outputFile = String(data.output_file || "");
    $("diffExcelHint").textContent = "差异结果已导出。";
    renderDiffExcelSummary();
  } catch (error) {
    $("diffExcelHint").textContent = error.message;
  }
}

async function highlightDiffExcel() {
  if (!(Array.isArray(diffExcelState.previewRecords) && diffExcelState.previewRecords.length)) {
    $("diffHighlightHint").textContent = "当前没有可标记的预览结果。";
    return;
  }
  $("diffHighlightHint").textContent = "标记中...";
  try {
    const data = await api("/api/diff-excel/highlight", {
      method: "POST",
      body: JSON.stringify({
        cache_file: diffExcelState.cacheFile,
        query: "",
        target: $("diffMarkTarget").value,
        color_hex: $("diffHighlightColor").value || "#FFD966",
      }),
      timeoutMs: 600000,
    });
    $("diffHighlightHint").textContent = `已标记 ${Number(data.changed_cells || 0)} 个单元格，涉及 ${Number(data.workbook_count || 0)} 个文件。`;
  } catch (error) {
    $("diffHighlightHint").textContent = error.message;
  }
}

async function startTask() {
  if (!preprocessFiles.length) {
    setPreprocessTaskHint("请先选择文件或文件夹。", true);
    return;
  }
  const pendingFiles = preprocessFiles.filter((file) => preprocessFileRequiresMapping(file) && !file.mapped);
  if (pendingFiles.length) {
    setPreprocessTaskHint(`请先完成映射：${pendingFiles.map((file) => file.name).join("、")}`, true);
    return;
  }
  const allMappings = Object.fromEntries(preprocessFiles.map((file) => [file.path, file.selected || {}]));
  const selectedHeaders = Object.values(allMappings).flatMap((mapping) => Object.values(mapping || {}).flat()).filter(Boolean);
  const firstPath = preprocessFiles[0]?.path || "";
  const inputFolder = firstPath.replace(/[\\/][^\\/]+$/, "") || $("folderPath").value.trim();
  const payload = {
    folder_path: inputFolder,
    header_name: selectedHeaders,
    source_language: $("sourceLanguage").value.trim() || "auto",
    file_type: "",
    export_review_sheet: true,
    extraction_mode: $("extractionMode").value,
    single_item_char_limit: 500,
    batch_request_char_limit: Number($("recallLimit").value || 3000),
    resume: false,
    memoq_term_base_ids: preprocessTermBaseIds || [],
    column_selections: {},
    input_files: preprocessFiles.map((file) => file.path),
    file_mappings: allMappings,
  };
  $("errorPanel").hidden = true;
  $("startButton").disabled = true;
  setPreprocessTaskHint("正在提交提取任务…", false);
  await saveSettings();
  await api("/api/tasks/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setPreprocessTaskHint("任务已开始，可在下方查看进度。", false);
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
  lastResultSummaryPath = outputFile || String(data.output_file || "");
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

let preprocessTermBases = [];
function renderPreprocessTermBases() {
  const q = $("preprocessTermBaseSearch").value.trim().toLowerCase();
  const container = $("preprocessTermBaseOptions"); container.replaceChildren();
  const visible = preprocessTermBases.filter((b) => `${b.name || ""} ${b.project || ""}`.toLowerCase().includes(q));
  const selected = visible.filter((b) => preprocessTermBaseIds.includes(String(b.id)));
  [...selected, ...visible.filter((b) => !preprocessTermBaseIds.includes(String(b.id)))].forEach((b) => {
    const row = document.createElement("div"); row.className = "review-term-base-option" + (preprocessTermBaseIds.includes(String(b.id)) ? " selected" : "");
    const check = document.createElement("span"); check.className = "review-term-base-option-check"; check.textContent = preprocessTermBaseIds.includes(String(b.id)) ? "✓" : "";
    const copy = document.createElement("span"); copy.className = "review-term-base-option-copy";
    const name = document.createElement("strong"); name.textContent = b.name || "memoQ 术语库";
    const meta = document.createElement("small"); meta.textContent = `memoQ${b.project ? " · " + b.project : ""}`; copy.append(name, meta); row.append(check, copy);
    row.addEventListener("click", () => { const id = String(b.id); preprocessTermBaseIds = preprocessTermBaseIds.includes(id) ? preprocessTermBaseIds.filter((x) => x !== id) : [...preprocessTermBaseIds, id]; renderPreprocessTermBases(); updatePreprocessTermBaseChip(); });
    container.appendChild(row);
  });
  if (!visible.length) { const empty = document.createElement("div"); empty.className = "hint"; empty.textContent = "没有匹配的术语库"; container.appendChild(empty); }
}
function updatePreprocessTermBaseChip() { $("preprocessTermBaseChip").textContent = preprocessTermBaseIds.length ? `术语表（${preprocessTermBaseIds.length}）` : "术语表"; }
const preprocessLanguages = [["auto","自动检测"],["zho-CN","简体中文"],["zho-TW","繁体中文"],["eng","英语"],["jpn","日语"],["kor","韩语"],["fra","法语"],["deu","德语"],["spa","西班牙语"],["por","葡萄牙语"],["ita","意大利语"],["rus","俄语"]];
function renderPreprocessLanguages() {
  const q = $("preprocessSourceLanguageSearch").value.trim().toLowerCase(); const box = $("preprocessSourceLanguageOptions"); box.replaceChildren();
  preprocessLanguages.filter(([, label]) => label.toLowerCase().includes(q)).forEach(([value, label]) => { const row = document.createElement("div"); row.className = "review-term-base-option" + ($("sourceLanguage").value === value ? " selected" : ""); row.innerHTML = `<span class="review-term-base-option-check">${$("sourceLanguage").value === value ? "✓" : ""}</span><span class="review-term-base-option-copy"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(value)}</small></span>`; row.onclick = () => { $("sourceLanguage").value = value; $("preprocessSourceLanguageChip").textContent = `源语言：${label}`; $("preprocessSourceLanguagePopover").classList.add("hidden"); $("preprocessSourceLanguageChip").closest(".card")?.classList.remove("popover-open"); }; box.appendChild(row); });
}
function positionPreprocessPopover(popover, anchor) {
  const card = anchor.closest(".card");
  if (!card) return;
  const cardRect = card.getBoundingClientRect();
  const anchorRect = anchor.getBoundingClientRect();
  const left = Math.max(10, Math.min(anchorRect.left - cardRect.left, card.clientWidth - popover.offsetWidth - 10));
  const top = anchorRect.bottom - cardRect.top + 8;
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
  popover.style.bottom = "auto";
}
async function choosePreprocessTermBases() {
  const status = await api("/api/ai-review/term-bases/memoq/status");
  const popover = $("preprocessTermBasePopover");
  if (!status.memoq?.bound) {
    $("preprocessTermBaseOptions").innerHTML = '<div class="hint">请先在“设置”中绑定 memoQ 账号</div>';
    popover.classList.toggle("hidden");
    const visible = !popover.classList.contains("hidden");
    $("preprocessTermBaseChip").closest(".card")?.classList.toggle("popover-open", visible);
    if (visible) positionPreprocessPopover(popover, $("preprocessTermBaseChip"));
    return;
  }
  const data = await api(`/api/ai-review/term-bases/memoq/termbases?q=${encodeURIComponent($("preprocessTermBaseSearch").value || "")}`);
  preprocessTermBases = Array.isArray(data.termbases) ? data.termbases : [];
  renderPreprocessTermBases();
  popover.classList.toggle("hidden");
  const visible = !popover.classList.contains("hidden");
  $("preprocessTermBaseChip").closest(".card")?.classList.toggle("popover-open", visible);
  if (visible) positionPreprocessPopover(popover, $("preprocessTermBaseChip"));
  if (!popover.classList.contains("hidden")) $("preprocessTermBaseSearch").focus();
}

async function openPreprocessMappingDialog() {
  if (!preprocessActiveFile) throw new Error("请先添加文件");
  if (!preprocessFileRequiresMapping(preprocessActiveFile)) {
    setPreprocessTaskHint("XLIFF 文件无需配置列映射，可直接开始提取。", false);
    return;
  }
  const data = await api(`/api/preprocess/file-mapping-scan?file_path=${encodeURIComponent(preprocessActiveFile.path)}`, { timeoutMs: 300000 });
  preprocessMappingState.sheetNames = data.sheet_names || [];
  preprocessMappingState.columnsBySheet = data.columns_by_sheet || {};
  preprocessMappingState.selected = preprocessActiveFile?.selected || {};
  if (!preprocessMappingState.sheetNames.includes(preprocessMappingState.activeSheet)) {
    preprocessMappingState.activeSheet = preprocessMappingState.sheetNames[0] || "";
  }
  if (!preprocessMappingState.activeSheet) throw new Error("没有读取到可映射的工作表或列。");
  $("preprocessMappingSourceLanguage").value = $("sourceLanguage").value || "auto";
  $("preprocessMappingHint").textContent = "";
  $("preprocessMappingHint").classList.remove("is-error");
  renderPreprocessMappingSheetTabs();
  renderPreprocessMappingColumns();
  if (!$("preprocessMappingDialog").open) $("preprocessMappingDialog").showModal();
}

function preprocessFileKind(path) {
  const suffix = String(path || "").toLowerCase().match(/\.[^.\\/]+$/)?.[0] || "";
  if ([".xlsx", ".xlsm", ".xls"].includes(suffix)) return "excel";
  if (suffix === ".csv") return "csv";
  if ([".xlf", ".xliff"].includes(suffix)) return "xliff";
  return "unsupported";
}
function preprocessFileRequiresMapping(file) { return ["excel", "csv"].includes(file?.kind || preprocessFileKind(file?.path)); }
function createPreprocessFile(path) {
  const normalizedPath = String(path || "");
  const kind = preprocessFileKind(normalizedPath);
  return { path: normalizedPath, name: normalizedPath.split(/[\\/]/).pop(), kind, mapped: kind === "xliff", selected: {}, sheetCount: 0 };
}
function setPreprocessTaskHint(message, isError = false) {
  const hint = $("preprocessTaskHint");
  hint.textContent = message || "";
  hint.classList.toggle("is-error", Boolean(isError));
}
function updatePreprocessWorkflowState(message = "") {
  const pending = preprocessFiles.filter((file) => preprocessFileRequiresMapping(file) && !file.mapped);
  $("startButton").disabled = !preprocessFiles.length || pending.length > 0;
  if (message) {
    setPreprocessTaskHint(message, false);
  } else if (!preprocessFiles.length) {
    setPreprocessTaskHint("请选择文件或文件夹。", false);
  } else if (pending.length) {
    setPreprocessTaskHint(`请点击文件配置映射，还剩 ${pending.length} 个文件。`, false);
  } else {
    setPreprocessTaskHint(`已准备 ${preprocessFiles.length} 个文件，可以开始提取。`, false);
  }
}
function replacePreprocessFiles(paths, displayPath = "") {
  const uniquePaths = [...new Set((paths || []).map((path) => String(path || "")).filter(Boolean))];
  preprocessFiles = uniquePaths.map(createPreprocessFile).filter((file) => file.kind !== "unsupported");
  preprocessActiveFile = preprocessFiles[0] || null;
  preprocessMappingState = { sheetNames: [], columnsBySheet: {}, selected: {}, activeSheet: "" };
  $("folderPath").value = displayPath || (preprocessFiles.length === 1 ? preprocessFiles[0].path : preprocessFiles.length ? `${preprocessFiles.length} 个文件` : "");
  renderPreprocessFiles();
}
function renderPreprocessFiles() {
  const box = $("preprocessFileList"); box.replaceChildren();
  if (!preprocessFiles.length) {
    box.innerHTML = '<span class="hint">尚未添加文件</span>';
    $("preprocessFileSummary").textContent = "尚未添加文件";
    updatePreprocessWorkflowState();
    return;
  }
  preprocessFiles.forEach((file) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "preprocess-file-item" + (file === preprocessActiveFile ? " active" : "");
    const status = preprocessFileRequiresMapping(file)
      ? (file.mapped ? `${file.sheetCount || 0} 个工作表已配置` : "点击配置映射")
      : "无需配置映射";
    row.innerHTML = `<strong>${escapeHtml(file.name)}</strong><small>${status}</small>`;
    row.onclick = () => {
      preprocessActiveFile = file;
      renderPreprocessFiles();
      openPreprocessMappingDialog().catch((error) => setPreprocessTaskHint(error.message, true));
    };
    box.appendChild(row);
  });
  const readyCount = preprocessFiles.filter((file) => !preprocessFileRequiresMapping(file) || file.mapped).length;
  $("preprocessFileSummary").textContent = `${preprocessFiles.length} 个文件 · ${readyCount} 个已就绪`;
  updatePreprocessWorkflowState();
}
async function addPreprocessFiles() {
  const data = await api("/api/dialog/select-preprocess-files", { method: "POST", body: "{}", timeoutMs: 0 });
  const paths = Array.isArray(data.file_paths) ? data.file_paths.filter(Boolean) : [];
  if (!paths.length) return;
  paths.forEach((path) => { if (!preprocessFiles.some((f) => f.path === path)) preprocessFiles.push(createPreprocessFile(path)); });
  if (!preprocessActiveFile) preprocessActiveFile = preprocessFiles[0] || null;
  $("folderPath").value = preprocessFiles.length === 1 ? preprocessFiles[0].path : `${preprocessFiles.length} 个文件`;
  renderPreprocessFiles();
}

function renderPreprocessMappingSheetTabs() {
  const tabs = $("preprocessMappingSheetTabs"); tabs.replaceChildren();
  preprocessMappingState.sheetNames.forEach((sheet) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sheet-tab" + (sheet === preprocessMappingState.activeSheet ? " active" : "");
    button.textContent = sheet;
    button.title = sheet;
    button.onclick = () => {
      capturePreprocessActiveSheetSelection();
      preprocessMappingState.activeSheet = sheet;
      renderPreprocessMappingSheetTabs();
      renderPreprocessMappingColumns();
    };
    tabs.appendChild(button);
  });
}

function applyPreprocessMappingDialog() {
  const sheet = preprocessMappingState.activeSheet;
  preprocessMappingState.selected[sheet] = Array.from($("preprocessMappingColumns").querySelectorAll("input:checked")).map((input) => input.value);
  $("sourceLanguage").value = $("preprocessMappingSourceLanguage").value;
  const languageLabel = preprocessLanguages.find(([value]) => value === $("sourceLanguage").value)?.[1] || "自动检测";
  $("preprocessSourceLanguageChip").textContent = `源语言：${languageLabel}`;
  const count = Object.values(preprocessMappingState.selected).flat().filter(Boolean).length;
  if (!count) {
    $("preprocessMappingHint").textContent = "请至少选择一个待提取列。";
    $("preprocessMappingHint").classList.add("is-error");
    return;
  }
  if (preprocessActiveFile) {
    preprocessActiveFile.selected = preprocessMappingState.selected;
    preprocessActiveFile.mapped = count > 0;
    preprocessActiveFile.sheetCount = Object.values(preprocessMappingState.selected).filter((items) => items?.length).length;
  }
  renderPreprocessFiles();
  $("preprocessMappingDialog").close();
}
function preprocessMappingTemplateKey() { return "yeehe_preprocess_mapping_templates_v1"; }
function renderPreprocessMappingTemplates() {
  const select = $("preprocessMappingTemplateSelect"); if (!select) return;
  const current = select.value; select.innerHTML = '<option value="">选择模板</option>';
  Object.keys(JSON.parse(localStorage.getItem(preprocessMappingTemplateKey()) || "{}")).forEach((name) => { const option = document.createElement("option"); option.value = name; option.textContent = name; select.appendChild(option); });
  select.value = current;
}
function savePreprocessMappingTemplate() {
  capturePreprocessActiveSheetSelection();
  const name = window.prompt("模板名称", "新建模板"); if (!name) return;
  const all = JSON.parse(localStorage.getItem(preprocessMappingTemplateKey()) || "{}");
  all[name] = { selected: preprocessMappingState.selected, source_language: $("preprocessMappingSourceLanguage").value };
  localStorage.setItem(preprocessMappingTemplateKey(), JSON.stringify(all));
  renderPreprocessMappingTemplates();
}
function applyPreprocessTemplate() {
  const name = $("preprocessMappingTemplateSelect").value; if (!name) return;
  const template = JSON.parse(localStorage.getItem(preprocessMappingTemplateKey()) || "{}")[name]; if (!template) return;
  preprocessMappingState.selected = JSON.parse(JSON.stringify(template.selected || {}));
  $("preprocessMappingSourceLanguage").value = template.source_language || "auto";
  renderPreprocessMappingColumns();
}
function deletePreprocessTemplate() {
  const name = $("preprocessMappingTemplateSelect").value; if (!name) return;
  const all = JSON.parse(localStorage.getItem(preprocessMappingTemplateKey()) || "{}"); delete all[name];
  localStorage.setItem(preprocessMappingTemplateKey(), JSON.stringify(all)); renderPreprocessMappingTemplates();
}
function capturePreprocessActiveSheetSelection() {
  const sheet = preprocessMappingState.activeSheet;
  if (!sheet) return;
  preprocessMappingState.selected[sheet] = Array.from($("preprocessMappingColumns").querySelectorAll("input:checked")).map((input) => input.value);
}
function renderPreprocessMappingColumns() {
  const columns = $("preprocessMappingColumns"); columns.innerHTML = "";
  const selected = new Set(preprocessMappingState.selected[preprocessMappingState.activeSheet] || []);
  (preprocessMappingState.columnsBySheet[preprocessMappingState.activeSheet] || []).forEach((column) => { const label = document.createElement("label"); label.className = "mapping-row preprocess-column-row"; label.innerHTML = `<span class="mapping-col-id">${escapeHtml(String(column.letter || ""))}</span><span class="mapping-header">${escapeHtml(String(column.header || ""))}</span><span class="check-line"><input type="checkbox" value="${escapeHtml(String(column.header || ""))}" ${selected.has(String(column.header || "")) ? "checked" : ""}/> 提取</span>`; columns.appendChild(label); });
}
function openPreprocessApplyTo() {
  capturePreprocessActiveSheetSelection();
  const box = $("preprocessApplyToSheets"); box.replaceChildren();
  preprocessMappingState.sheetNames.filter((sheet) => sheet !== preprocessMappingState.activeSheet).forEach((sheet) => { const label = document.createElement("label"); label.className = "check-line"; label.innerHTML = `<input type="checkbox" value="${escapeHtml(sheet)}" /> ${escapeHtml(sheet)}`; box.appendChild(label); });
  $("preprocessApplyToAll").checked = false; $("preprocessApplyToDialog").showModal();
}
function confirmPreprocessApplyTo() {
  const source = [...(preprocessMappingState.selected[preprocessMappingState.activeSheet] || [])];
  const targets = $("preprocessApplyToAll").checked ? preprocessMappingState.sheetNames : Array.from($("preprocessApplyToSheets").querySelectorAll("input:checked")).map((input) => input.value);
  targets.filter((sheet) => sheet !== preprocessMappingState.activeSheet).forEach((sheet) => { preprocessMappingState.selected[sheet] = [...source]; });
  $("preprocessApplyToDialog").close(); renderPreprocessMappingColumns();
}

function getPreprocessProgressState(data) {
  const current = Math.max(0, Number(data.progress_current || 0));
  const total = Math.max(0, Number(data.progress_total || 0));
  if (data.is_running) return { label: "运行中", className: "is-running" };
  if (data.last_error) return { label: "失败", className: "is-failed" };
  if (total > 0 && current >= total) return { label: "已完成", className: "is-completed" };
  if (data.can_resume) return { label: "已暂停", className: "is-paused" };
  return { label: "空闲", className: "" };
}

function renderPreprocessRecentEvents(data) {
  const container = $("preprocessRecentEvents");
  if (!container) return;
  const logs = Array.isArray(data.logs) ? data.logs.filter(Boolean).slice(-3).reverse() : [];
  container.replaceChildren();
  if (!logs.length) {
    const empty = document.createElement("span");
    empty.className = "preprocess-events-empty";
    empty.textContent = data.message || "暂无任务事件";
    container.appendChild(empty);
    return;
  }
  logs.forEach((entry, index) => {
    const item = document.createElement("div");
    item.className = "preprocess-event";
    const marker = document.createElement("i");
    marker.className = "preprocess-event-marker";
    const copy = document.createElement("span");
    copy.textContent = String(entry);
    item.append(marker, copy);
    if (index === 0) item.classList.add("is-latest");
    container.appendChild(item);
  });
}

function renderPreprocessProgress(data) {
  const current = Math.max(0, Number(data.progress_current || 0));
  const total = Math.max(0, Number(data.progress_total || 0));
  const state = getPreprocessProgressState(data);
  const stateElement = $("preprocessProgressState");
  stateElement.textContent = state.label;
  stateElement.className = `preprocess-status-pill ${state.className}`.trim();
  $("progressText").textContent = `${current} / ${total}`;
  $("preprocessProgressStage").textContent = data.stage_label || data.stage || "未启动";
  $("preprocessProgressMessage").textContent = data.message || (data.is_running ? "任务正在处理。" : "等待开始任务。");
  $("preprocessProgressPercent").textContent = formatProgressPercent(current, total, data.is_running);
  $("preprocessLlmRequests").textContent = Number((data.stats || {}).llm_request_count || 0);
  $("progressBar").style.width = total > 0 ? `${Math.min(100, Math.round((current / total) * 100))}%` : "0";
  renderPreprocessRecentEvents(data);
}

async function refreshStatus() {
  const data = await api("/api/status");
  const preprocessState = getPreprocessProgressState(data);
  setTaskStatus("overviewPage", {
    active: Boolean(data.is_running),
    taskLabel: "文本预处理工具",
    pill: preprocessState.label,
    pillClass: data.is_running ? "running" : data.last_error ? "failed" : "",
    stageLabel: data.stage_label || data.stage || "未启动",
    message: data.message || (data.is_running ? "任务运行中" : "等待开始任务"),
  });
  renderCurrentTaskStatus();
  renderPreprocessProgress(data);
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
  $("outputFile").value = data.output_file || "";
  $("lastError").value = data.last_error || "";
  $("errorPanel").hidden = !data.last_error;
  $("errorPanelText").textContent = data.last_error || "";
  $("logBox").textContent = (data.logs && data.logs.length) ? data.logs.join("\n") : "暂无日志";
  const hasPendingMappings = preprocessFiles.some((file) => preprocessFileRequiresMapping(file) && !file.mapped);
  $("startButton").disabled = Boolean(data.is_running) || !preprocessFiles.length || hasPendingMappings;
  $("resumeButton").disabled = Boolean(data.is_running) || !data.can_resume;
  $("stopButton").disabled = !data.is_running;
  $("clearCacheButton").disabled = Boolean(data.is_running) || !data.can_resume;
  if (data.output_file && data.output_file !== lastResultSummaryPath) {
    await refreshResults(data.output_file);
  } else if (!data.output_file && (latestResultFile || lastResultSummaryPath)) {
    lastResultSummaryPath = "";
    renderResultSummary({});
  }
}

async function refreshStatusSafely() {
  if (statusRefreshInFlight || document.hidden) return;
  statusRefreshInFlight = true;
  try {
    await refreshStatus();
  } catch (error) {
    if (currentPageId === "overviewPage") {
      setPreprocessTaskHint(error?.message || "任务状态读取失败，请稍后重试。", true);
    }
  } finally {
    statusRefreshInFlight = false;
  }
}

async function loadMemoQAccountStatus() {
  try {
    const data = await api("/api/ai-review/term-bases/memoq/status");
    const bound = Boolean(data.memoq?.bound);
    $("memoqAccountStatus").textContent = bound ? "已绑定：" + data.memoq.username : "未绑定";
    $("memoqAccountStatus").classList.remove("error");
    $("memoqCredentialFields").classList.toggle("hidden", bound);
    $("bindMemoQButton").classList.toggle("hidden", bound);
    $("unbindMemoQButton").hidden = !bound;
    $("unbindMemoQButton").classList.toggle("hidden", !bound);
  } catch (_) {
    $("memoqAccountStatus").textContent = "无法读取绑定状态，请稍后重试";
    $("memoqAccountStatus").classList.add("error");
  }
}
async function bindMemoQAccount() {
  const username = $("memoqUsername").value.trim();
  const password = $("memoqPassword").value;
  if (!username || !password) throw new Error("请输入 memoQ 用户名和密码");
  $("bindMemoQButton").disabled = true;
  $("memoqAccountStatus").textContent = "正在验证账号…";
  $("memoqAccountStatus").classList.remove("error");
  try {
    await api("/api/ai-review/term-bases/memoq/bind", { method: "POST", body: JSON.stringify({ username, password }) });
    $("memoqPassword").value = ""; transfer.afterLogin(); await loadMemoQAccountStatus(); await loadReviewTermBases();
  } catch (error) {
    $("memoqAccountStatus").textContent = "绑定失败，请检查账号、密码或 memoQ 服务器连接";
    $("memoqAccountStatus").classList.add("error");
    throw error;
  } finally { $("bindMemoQButton").disabled = false; }
}
$("saveModelConnectionButton").addEventListener("click", saveModelConnection);
$("preprocessTermBaseChip").addEventListener("click", () => choosePreprocessTermBases().catch((error) => setPreprocessTaskHint(error.message, true)));
$("preprocessTermBaseSearch").addEventListener("input", renderPreprocessTermBases);
$("preprocessSourceLanguageChip").addEventListener("click", () => { renderPreprocessLanguages(); const popover = $("preprocessSourceLanguagePopover"); popover.classList.toggle("hidden"); const visible = !popover.classList.contains("hidden"); $("preprocessSourceLanguageChip").closest(".card")?.classList.toggle("popover-open", visible); if (visible) { positionPreprocessPopover(popover, $("preprocessSourceLanguageChip")); $("preprocessSourceLanguageSearch").focus(); } });
$("preprocessSourceLanguageSearch").addEventListener("input", renderPreprocessLanguages);
document.addEventListener("pointerdown", (event) => {
  const langPopover = $("preprocessSourceLanguagePopover");
  const langChip = $("preprocessSourceLanguageChip");
  if (!langPopover.classList.contains("hidden") && !langPopover.contains(event.target) && !langChip.contains(event.target)) { langPopover.classList.add("hidden"); langChip.closest(".card")?.classList.remove("popover-open"); }
  const termPopover = $("preprocessTermBasePopover");
  const termChip = $("preprocessTermBaseChip");
  if (!termPopover.classList.contains("hidden") && !termPopover.contains(event.target) && !termChip.contains(event.target)) { termPopover.classList.add("hidden"); termChip.closest(".card")?.classList.remove("popover-open"); }
});
$("addPreprocessFilesButton").addEventListener("click", () => addPreprocessFiles().catch((error) => setPreprocessTaskHint(error.message, true)));
$("applyPreprocessMappingButton").addEventListener("click", applyPreprocessMappingDialog);
$("savePreprocessMappingButton").addEventListener("click", savePreprocessMappingTemplate);
$("applyPreprocessTemplateButton").addEventListener("click", applyPreprocessTemplate);
$("deletePreprocessTemplateButton").addEventListener("click", deletePreprocessTemplate);
$("applyPreprocessToButton").addEventListener("click", openPreprocessApplyTo);
$("confirmPreprocessApplyToButton").addEventListener("click", confirmPreprocessApplyTo);
$("cancelPreprocessApplyToButton").addEventListener("click", () => $("preprocessApplyToDialog").close());
$("closePreprocessApplyToButton").addEventListener("click", () => $("preprocessApplyToDialog").close());
renderPreprocessMappingTemplates();
$("cancelPreprocessMappingButton").addEventListener("click", () => $("preprocessMappingDialog").close());
$("closePreprocessMappingButton").addEventListener("click", () => $("preprocessMappingDialog").close());
$("bindMemoQButton").addEventListener("click", () => bindMemoQAccount().catch(() => undefined));
$("unbindMemoQButton").addEventListener("click", async () => {
  try {
    await api("/api/ai-review/term-bases/memoq/bind", { method: "DELETE" });
    transfer.logout();
    await loadMemoQAccountStatus();
    await loadReviewTermBases();
  } catch (error) {
    $("memoqAccountStatus").textContent = error?.message || "解绑失败，请稍后重试";
    $("memoqAccountStatus").classList.add("error");
  }
});
loadMemoQAccountStatus();
$("saveSettingsButton").addEventListener("click", () => saveSettings().catch((error) => { $("saveHint").textContent = error.message; }));
$("savePromptTemplatesButton").addEventListener("click", () => savePromptTemplates().catch((error) => { $("promptTemplateHint").textContent = error.message; }));
$("resetPromptTemplatesButton").addEventListener("click", () => resetPromptTemplates().catch((error) => { $("promptTemplateHint").textContent = error.message; }));
$("addAsciiPatternButton").addEventListener("click", addAsciiPattern);
$("saveAsciiPatternsButton").addEventListener("click", () => saveAsciiPatterns().catch((error) => { $("asciiPatternHint").textContent = error.message; }));
$("addBuiltinRuleButton").addEventListener("click", addBuiltinRule);
$("saveBuiltinRulesButton").addEventListener("click", () => saveBuiltinRules().catch((error) => { $("builtinRuleHint").textContent = error.message; }));
$("updateNoticeButton").addEventListener("click", openAppUpdateModal);
$("pendingRuleNoticeButton").addEventListener("click", openPendingRuleModal);
$("closeAppUpdateModalButton").addEventListener("click", closeAppUpdateModal);
$("cancelAppUpdateButton").addEventListener("click", closeAppUpdateModal);
$("confirmAppUpdateButton").addEventListener("click", startAppUpdate);
$("closePendingRuleModalButton").addEventListener("click", closePendingRuleModal);
$("pendingRuleSelectAllButton").addEventListener("click", () => setAllPendingRuleSelection(true));
$("pendingRuleClearSelectionButton").addEventListener("click", () => setAllPendingRuleSelection(false));
$("confirmPendingRuleImportButton").addEventListener("click", () => importPendingRules().catch((error) => { $("pendingRuleHint").textContent = error.message; }));
$("chooseFolderButton").addEventListener("click", chooseFolder);
$("chooseCrossExcelFolderButton").addEventListener("click", chooseCrossExcelFolder);
$("chooseDiffPathAButton").addEventListener("click", () => chooseDiffFolder("A").catch((error) => {
  $("diffExcelHint").textContent = error.message;
}));
$("chooseDiffPathBButton").addEventListener("click", () => chooseDiffFolder("B").catch((error) => {
  $("diffExcelHint").textContent = error.message;
}));
$("chooseDiffFileAButton").addEventListener("click", () => chooseDiffFile("A").catch((error) => {
  $("diffExcelHint").textContent = error.message;
}));
$("chooseDiffFileBButton").addEventListener("click", () => chooseDiffFile("B").catch((error) => {
  $("diffExcelHint").textContent = error.message;
}));
$("scanCrossExcelButton").addEventListener("click", scanCrossExcelFolder);
$("searchCrossExcelButton").addEventListener("click", searchCrossExcel);
$("mergeCrossExcelButton").addEventListener("click", mergeCrossExcel);
$("startDiffExcelButton").addEventListener("click", startDiffExcel);
$("clearDiffExcelButton").addEventListener("click", clearDiffExcelState);
$("diffPreviewPreviousButton").addEventListener("click", () => changeDiffPreviewPage(-1).catch((error) => { $("diffExcelHint").textContent = error.message; }));
$("diffPreviewNextButton").addEventListener("click", () => changeDiffPreviewPage(1).catch((error) => { $("diffExcelHint").textContent = error.message; }));
$("diffCompareMode").addEventListener("change", syncDiffCompareModeUi);
$("diffPathA").addEventListener("input", resetDiffFieldMatchSettings);
$("diffPathB").addEventListener("input", resetDiffFieldMatchSettings);
$("diffPathA").addEventListener("change", resetDiffFieldMatchSettings);
$("diffPathB").addEventListener("change", resetDiffFieldMatchSettings);
$("openDiffFieldSettingsButton").addEventListener("click", () => openDiffFieldSettings().catch((error) => {
  $("diffFieldSettingsHint").textContent = error.message;
}));
$("closeDiffFieldSettingsButton").addEventListener("click", closeDiffFieldSettings);
$("cancelDiffFieldSettingsButton").addEventListener("click", closeDiffFieldSettings);
$("saveDiffFieldSettingsButton").addEventListener("click", saveDiffFieldSettings);
$("diffReferenceField").addEventListener("change", () => {
  diffFieldMatchSettings.referenceField = $("diffReferenceField").value.trim();
  diffFieldMatchSettings.compareFields = diffFieldMatchSettings.compareFields.filter((field) => field !== diffFieldMatchSettings.referenceField);
  renderDiffFieldSettings();
});
$("exportDiffExcelButton").addEventListener("click", exportDiffExcel);
$("highlightDiffExcelButton").addEventListener("click", highlightDiffExcel);
$("diffHighlightColor").addEventListener("input", refreshDiffPresetColorButtons);
document.querySelectorAll(".preset-color-btn").forEach((button) => {
  button.addEventListener("click", () => {
    const color = String(button.dataset.color || "").trim();
    if (!color) return;
    $("diffHighlightColor").value = color;
    refreshDiffPresetColorButtons();
  });
});
$("selectAllCrossHeadersButton").addEventListener("click", () => setCrossExcelHeaderSelection(true));
$("clearCrossHeadersButton").addEventListener("click", () => setCrossExcelHeaderSelection(false));
$("newReviewConversationButton").addEventListener("click", () => createReviewConversation().catch(showReviewConversationError));
$("renameReviewConversationButton").addEventListener("click", beginRenameCurrentReviewConversation);
$("reviewConversationTitleInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    saveCurrentReviewConversationTitle().catch(showReviewConversationError);
  } else if (event.key === "Escape") {
    event.preventDefault();
    cancelRenameCurrentReviewConversation();
  }
});
$("deleteReviewConversationButton").addEventListener("click", () => deleteCurrentReviewConversation().catch(showReviewConversationError));
$("saveReviewAttachmentMappingButton").addEventListener("click", () => saveReviewAttachmentMapping().catch((error) => {
  $("reviewAttachmentMappingHint").textContent = error?.message || String(error || "保存失败");
}));
$("editReviewAttachmentMappingButton").addEventListener("click", () => openReviewAttachmentMappingEditor().catch((error) => {
  $("reviewAttachmentMappingHint").textContent = error?.message || String(error || "读取结构失败");
}));
document.querySelectorAll('input[name="reviewAttachmentMappingMode"]').forEach((input) => {
  input.addEventListener("change", updateReviewAttachmentMappingControls);
});
$("reviewUploadChip").addEventListener("click", () => chooseReviewConversationFiles().catch(showReviewConversationError));
$('confirmReviewFeedbackButton').addEventListener('click', confirmReviewFeedback);
$('reviewFeedbackUploadButton').addEventListener('click', () => {
  if (!reviewConversationState.currentId) { showReviewConversationError(new Error('请先选择审校会话')); return; }
  $('reviewFeedbackFileInput').click();
});
$('reviewFeedbackFileInput').addEventListener('change', async () => {
  const file = $('reviewFeedbackFileInput').files[0];
  if (!file) return;
  const sessionId = reviewConversationState.currentId;
  $('reviewFeedbackUploadButton').disabled = true;
  $('reviewConversationHint').textContent = '正在导入反馈…';
  showReviewLearningProgress('uploading');
  try {
    const form = new FormData(); form.append('file', file);
    const response = await fetch(`/api/ai-review/conversations/${encodeURIComponent(sessionId)}/feedback-file`, {method:'POST', body:form});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '反馈导入失败');
    showFeedbackResult(data, sessionId, data.task_id);
    showReviewLearningProgress(data.event_id ? 'queued' : '');
    await refreshCurrentReviewConversation();
    await refreshReviewLearningStatus();
  } catch (e) { showReviewLearningProgress(''); showReviewConversationError(e); }
  finally { $('reviewFeedbackUploadButton').disabled = false; $('reviewFeedbackFileInput').value = ''; }
});
$('reviewMemoryButton').addEventListener('click', () => openReviewMemoryDialog().catch(showReviewConversationError));
$('restoreReviewMemoryButton').addEventListener('click', restoreReviewMemory);
$('saveReviewMemoryButton').addEventListener('click', () => saveReviewMemory().catch(showReviewConversationError));
$('closeReviewMemoryButton').addEventListener('click', closeReviewMemoryDialog);
$('cancelReviewMemoryButton').addEventListener('click', closeReviewMemoryDialog);
$('reviewMemoryOverlay').addEventListener('click', event => {
  if (event.target === $('reviewMemoryOverlay')) closeReviewMemoryDialog();
});
setInterval(() => { if (!document.hidden) refreshReviewLearningStatus().catch(() => {}); }, 4000);
$("reviewTermBaseChip").addEventListener("click", toggleReviewTermBasePopover);
$("reviewTermBaseSearch").addEventListener("input", renderReviewTermBaseOptions);
$("uploadReviewTermBaseButton").addEventListener("click", () => {
  closeReviewTermBasePopover();
  $("reviewTermBaseFileInput").click();
});
$("reviewTermBaseFileInput").addEventListener("change", () => {
  const file = $("reviewTermBaseFileInput").files?.[0];
  uploadReviewTermBase(file).catch(showReviewConversationError).finally(() => ($("reviewTermBaseFileInput").value = ""));
});
$("reviewConversationFileInput").addEventListener("change", () => {
  const files = $("reviewConversationFileInput").files;
  uploadReviewConversationFiles(files).catch(showReviewConversationError).finally(() => ($("reviewConversationFileInput").value = ""));
});
$("reviewComposer").addEventListener("dragover", (event) => {
  event.preventDefault();
  $("reviewComposer").classList.add("dragging");
});
$("reviewComposer").addEventListener("dragleave", () => $("reviewComposer").classList.remove("dragging"));
$("reviewComposer").addEventListener("drop", (event) => {
  event.preventDefault();
  $("reviewComposer").classList.remove("dragging");
  uploadReviewConversationFiles(event.dataTransfer?.files).catch(showReviewConversationError);
});
$("sendReviewConversationButton").addEventListener("click", () => sendReviewConversationMessage().catch(showReviewConversationError));
$("reviewAutoStart").addEventListener("change", (event) => {
  saveReviewConversationAutoStart(event.currentTarget.checked).catch((error) => {
    event.currentTarget.checked = Boolean(reviewConversationState.snapshot?.session?.auto_start);
    showReviewConversationError(error);
  });
});
$("reviewComposerInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if ($("sendReviewConversationButton").disabled) return;
    sendReviewConversationMessage().catch(showReviewConversationError);
  }
});
$("reviewPromptChip").addEventListener("click", () => openReviewConversationPromptDialog().catch(showReviewConversationError));
$("reviewSourceLanguageChip").addEventListener("click", (event) => openReviewLanguagePopover("source", event.currentTarget));
$("reviewTargetLanguageChip").addEventListener("click", (event) => openReviewLanguagePopover("target", event.currentTarget));
$("reviewLanguageSearch").addEventListener("input", renderReviewLanguageOptions);
$("closeReviewLanguagePopoverButton").addEventListener("click", closeReviewLanguagePopover);
document.addEventListener("pointerdown", (event) => {
  const popover = $("reviewLanguagePopover");
  if (!popover.classList.contains("hidden") && !popover.contains(event.target)
    && !$("reviewSourceLanguageChip").contains(event.target) && !$("reviewTargetLanguageChip").contains(event.target)) {
    closeReviewLanguagePopover();
  }
  const termPopover = $("reviewTermBasePopover");
  if (!termPopover.classList.contains("hidden") && !termPopover.contains(event.target)
    && !$("reviewTermBaseChip").contains(event.target)) {
    closeReviewTermBasePopover();
  }
});
$("promptDialogTemplateSelect").addEventListener("change", async () => {
  try {
    const templateId = $("promptDialogTemplateSelect").value;
    if (!templateId) return;
    const data = await api(`/api/ai-review/prompt-templates/${encodeURIComponent(templateId)}`);
    reviewConversationState.promptTemplateId = templateId;
    fillAiReviewPromptDialog(data.template || {});
    updateReviewComposerChips();
    await saveReviewConversationComposerSettings();
  } catch (error) {
    $("promptTemplateHint").textContent = error?.message || "提示词模板切换失败";
  }
});
$("chooseReviewFileButton").addEventListener("click", () => chooseAiReviewFile().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("reviewFileInput").addEventListener("change", () => {
  const file = $("reviewFileInput").files?.[0];
  uploadAiReviewFile(file).catch((error) => {
    $("reviewTaskHint").textContent = error.message;
    $("reviewFileHint").textContent = error.message;
  }).finally(() => {
    $("reviewFileInput").value = "";
  });
});
$("openExcelMappingButton").addEventListener("click", () => openAiReviewExcelMappingDialog().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("startReviewButton").addEventListener("click", () => startAiReviewTask().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
  setAiReviewTaskStatus({
    active: false,
    pill: "失败",
    pillClass: "failed",
    stageLabel: "审校失败",
    message: error.message,
  });
}));
$("openReviewSettingsButton").addEventListener("click", () => setPage("aiReviewSettingsPage"));
$("openReviewForbiddenButton").addEventListener("click", () => setPage("aiReviewForbiddenPage"));
$("themeToggleButton").addEventListener("click", () => {
  applyUiTheme(document.documentElement.classList.contains("light-theme") ? "dark" : "light");
});
$("closeToolGuideDialogButton").addEventListener("click", () => $("toolGuideDialog").close());
$("feedbackEntryButton").addEventListener("click", openFeedbackModal);
$("closeFeedbackModalButton").addEventListener("click", closeFeedbackModal);
$("cancelFeedbackButton").addEventListener("click", closeFeedbackModal);
$("chooseFeedbackScreenshotButton").addEventListener("click", () => $("feedbackScreenshotInput").click());
$("feedbackScreenshotDropzone").addEventListener("click", () => {
  $("feedbackScreenshotDropzone").focus();
  $("feedbackSubmitHint").textContent = "现在可以直接按 Ctrl+V 粘贴截图，或把图片拖到这里。";
});
$("feedbackScreenshotInput").addEventListener("change", () => {
  const file = $("feedbackScreenshotInput").files?.[0];
  setFeedbackScreenshotFile(file || null);
});
$("feedbackScreenshotDropzone").addEventListener("dragover", (event) => {
  event.preventDefault();
  $("feedbackScreenshotDropzone").classList.add("drag-over");
});
$("feedbackScreenshotDropzone").addEventListener("dragleave", () => {
  $("feedbackScreenshotDropzone").classList.remove("drag-over");
});
$("feedbackScreenshotDropzone").addEventListener("drop", (event) => {
  event.preventDefault();
  $("feedbackScreenshotDropzone").classList.remove("drag-over");
  const files = Array.from(event.dataTransfer?.files || []);
  const imageFile = files.find((file) => String(file.type || "").startsWith("image/"));
  if (!imageFile) {
    $("feedbackSubmitHint").textContent = "这里只能接收图片文件。";
    return;
  }
  setFeedbackScreenshotFile(imageFile);
  $("feedbackSubmitHint").textContent = "已读取拖入的截图。";
});
$("openFeedbackLogButton").addEventListener("click", async () => {
  try {
    await api("/api/feedback/open-log", { method: "POST", body: "{}" });
  } catch (error) {
    $("feedbackSubmitHint").textContent = error.message;
  }
});
$("submitFeedbackButton").addEventListener("click", submitFeedback);
$("enableAiReview").addEventListener("change", updateAiReviewModeVisibility);
$("enableDirectionalReview").addEventListener("change", updateAiReviewModeVisibility);
$("reviewAiLimit").addEventListener("change", () => saveReviewSettings().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("editPromptButton").addEventListener("click", () => openAiReviewPromptDialog().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("newPromptButton").addEventListener("click", newAiReviewPromptTemplate);
$("savePromptButton").addEventListener("click", () => saveAiReviewPromptTemplate().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("resetPromptButton").addEventListener("click", () => resetAiReviewPromptTemplate().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("deletePromptButton").addEventListener("click", () => deleteAiReviewPromptTemplate().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("cancelPromptDialogButton").addEventListener("click", () => $("promptDialog").close());
$("closePromptDialogButton").addEventListener("click", () => $("promptDialog").close());
$("editDirectionalButton").addEventListener("click", () => openDirectionalDialog().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("newDirectionalButton").addEventListener("click", newDirectionalTemplate);
$("addDirectionalItemButton").addEventListener("click", () => appendDirectionalEditorItem("", true));
$("saveDirectionalButton").addEventListener("click", () => saveDirectionalTemplateFromDialog().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("cancelDirectionalDialogButton").addEventListener("click", () => $("directionalDialog").close());
$("closeDirectionalDialogButton").addEventListener("click", () => $("directionalDialog").close());
$("editForbiddenButton").addEventListener("click", () => openForbiddenDialog().catch((error) => {
  $("reviewForbiddenHint").textContent = error.message;
}));
$("newForbiddenButton").addEventListener("click", newForbiddenTemplate);
$("saveForbiddenButton").addEventListener("click", () => saveForbiddenTemplateFromDialog().catch((error) => {
  $("reviewForbiddenHint").textContent = error.message;
}));
$("cancelForbiddenDialogButton").addEventListener("click", () => $("forbiddenDialog").close());
$("closeForbiddenDialogButton").addEventListener("click", () => $("forbiddenDialog").close());
$("applyExcelMappingButton").addEventListener("click", () => applyAiReviewExcelMapping().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("saveExcelMappingPresetButton").addEventListener("click", () => {
  try {
    openAiReviewExcelMappingPresetDialog();
  } catch (error) {
    $("excelMappingPresetHint").textContent = error.message;
  }
});
$("confirmExcelMappingPresetButton").addEventListener("click", () => saveAiReviewExcelMappingPreset().catch((error) => {
  $("excelMappingPresetSaveHint").textContent = error.message;
}));
$("saveReviewAgentSettingsButton").addEventListener("click", () => saveReviewSettings().catch((error) => {
  $("reviewSettingsHint").textContent = error.message;
}));
$("excelMappingPresetNameInput").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  saveAiReviewExcelMappingPreset().catch((error) => {
    $("excelMappingPresetSaveHint").textContent = error.message;
  });
});
$("excelMappingPresetSelect").addEventListener("change", () => applyAiReviewExcelMappingPreset().catch((error) => {
  $("excelMappingPresetHint").textContent = error.message;
}));
$("deleteExcelMappingPresetButton").addEventListener("click", () => deleteAiReviewExcelMappingPreset().catch((error) => {
  $("excelMappingPresetHint").textContent = error.message;
}));
$("cancelExcelMappingPresetDialogButton").addEventListener("click", () => $("excelMappingPresetDialog").close());
$("closeExcelMappingPresetDialogButton").addEventListener("click", () => $("excelMappingPresetDialog").close());
$("cancelExcelMappingDialogButton").addEventListener("click", () => $("excelMappingDialog").close());
$("closeExcelMappingDialogButton").addEventListener("click", () => $("excelMappingDialog").close());
$("openOutputDirButton").addEventListener("click", () => openAiReviewOutputDir().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("openOutputFileButton").addEventListener("click", () => openAiReviewOutputFile().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("openReviewDetailButton").addEventListener("click", () => openReviewDetailDialog().catch((error) => {
  $("reviewTaskHint").textContent = error.message;
}));
$("closeReviewDetailButton").addEventListener("click", closeReviewDetailDialog);
$("reviewDetailOverlay").addEventListener("click", (event) => {
  if (event.target === $("reviewDetailOverlay")) {
    closeReviewDetailDialog();
  }
});
$("closeReviewFollowupButton").addEventListener("click", closeReviewFollowupDialog);
$("reviewFollowupOverlay").addEventListener("click", (event) => {
  if (event.target === $("reviewFollowupOverlay")) {
    closeReviewFollowupDialog();
  }
});
$("sendReviewFollowupButton").addEventListener("click", () => sendReviewFollowupMessage().catch((error) => {
  $("reviewFollowupHint").textContent = error.message;
  $("sendReviewFollowupButton").disabled = false;
}));
$("reviewFollowupInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendReviewFollowupMessage().catch((error) => {
      $("reviewFollowupHint").textContent = error.message;
      $("sendReviewFollowupButton").disabled = false;
    });
  }
});
$("startButton").addEventListener("click", () => startTask().catch((error) => {
  setPreprocessTaskHint(error.message, true);
  $("startButton").disabled = preprocessFiles.some((file) => preprocessFileRequiresMapping(file) && !file.mapped) || !preprocessFiles.length;
}));
$("resumeButton").addEventListener("click", () => resumeTask().catch((error) => setPreprocessTaskHint(error.message, true)));
$("stopButton").addEventListener("click", () => stopTask().catch((error) => setPreprocessTaskHint(error.message, true)));
$("clearCacheButton").addEventListener("click", () => clearRuntimeCache().catch((error) => setPreprocessTaskHint(error.message, true)));
$("crossExcelQuery").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchCrossExcel();
  }
});
async function openGeneratedOutput(endpoint, outputFile, hintId) {
  if (!outputFile) return;
  try {
    await api(`${endpoint}?output_file=${encodeURIComponent(outputFile)}`, {
      method: "POST",
      body: "{}",
    });
  } catch (error) {
    const hint = $(hintId);
    if (hint) hint.textContent = error?.message || "无法打开输出内容";
  }
}

$("openCrossExcelOutputButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-folder", crossExcelOutputFile, "crossExcelOutputHint"));
$("openCrossExcelOutputFileButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-file", crossExcelOutputFile, "crossExcelOutputHint"));
$("openDiffOutputFolderButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-folder", diffExcelState.outputFile, "diffExcelHint"));
$("openDiffOutputFileButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-file", diffExcelState.outputFile, "diffExcelHint"));
$("downloadResultButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-file", latestResultFile, "preprocessTaskHint"));
$("openResultFolderButton").addEventListener("click", () => openGeneratedOutput("/api/results/open-folder", latestResultFile, "preprocessTaskHint"));

document.querySelectorAll(".nav-link, .shortcut-button").forEach((button) => {
  button.addEventListener("click", () => setPage(button.dataset.pageTarget));
});

document.querySelectorAll(".tool-guide-card").forEach((button) => {
  button.addEventListener("click", () => renderToolGuide(button.dataset.toolGuide));
});

document.querySelectorAll(".subnav-link").forEach((button) => {
  button.addEventListener("click", () => setSubtab(button.dataset.subtabGroup, button.dataset.subtabTarget));
});
document.addEventListener("paste", (event) => {
  readClipboardScreenshot(event).catch((error) => {
    $("feedbackSubmitHint").textContent = error.message;
  });
});
$("feedbackOverlay").addEventListener("click", (event) => {
  if (event.target === $("feedbackOverlay")) {
    closeFeedbackModal();
  }
});

setPage("toolGuidePage");
initializeUiTheme();
renderCrossExcelHeaders([]);
renderCrossExcelSearchResults(null);
setCrossExcelOutput("");
refreshDiffPresetColorButtons();
syncDiffCompareModeUi();
updateAiReviewModeVisibility();
renderCurrentTaskStatus();
Promise.allSettled([
  loadFeedbackStatus(),
  loadSettings(),
  loadAsciiPatterns(),
  loadPromptTemplates(),
  loadBuiltinRules(),
  loadPendingRules(),
  loadAppUpdateInfo(),
  Promise.all([loadAiReviewPromptTemplates(), loadReviewTermBases()]).then(() => loadReviewConversations()),
  loadAiReviewDirectionalTemplates(),
  loadAiReviewForbiddenTemplates(),
]).then((results) => {
  const failed = results.filter((item) => item.status === "rejected");
  if (failed.length) {
    console.warn(`有 ${failed.length} 项初始化数据加载失败，相关页面可稍后重试。`);
  }
  return refreshStatusSafely();
});
setInterval(refreshStatusSafely, 1500);
"""


from .workspace_ui import THEME_CSS, LANGUAGE_JS
APP_CSS += THEME_CSS
APP_JS += LANGUAGE_JS
_TRANSFER_ASSETS = Path(__file__).resolve().parent / "transfer_assets"
INDEX_HTML = INDEX_HTML.replace("__TRANSFER_PAGE__", (_TRANSFER_ASSETS / "page.html").read_text(encoding="utf-8"))
APP_JS += "\n" + (_TRANSFER_ASSETS / "page.js").read_text(encoding="utf-8")
APP_CSS += "\n" + (_TRANSFER_ASSETS / "page.css").read_text(encoding="utf-8")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)

