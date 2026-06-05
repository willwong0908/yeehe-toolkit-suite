from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from typing import Any

from .database import dumps_json, get_connection, loads_json, utc_now
from .directional_service import enabled_review_types, get_directional_template
from .forbidden_service import check_forbidden_words, get_forbidden_template, parse_forbidden_words
from .output_service import generate_review_excel
from .prompt_service import get_prompt_template
from .shared_provider import SharedProviderError, get_shared_ai_settings, review_chat

DEFAULT_DIRECTIONAL_SYSTEM_PROMPT = """你是专业翻译审校员。你的任务是按照用户指定的定向审校类型，检查译文相对于原文是否存在对应问题。

你必须遵守以下规则：
1. 只检查用户指定的审校类型，不要主动增加其他类型。
2. 每个条目都必须返回。
3. 每个审校类型都必须返回。
4. 如果某个类型没有问题，返回空字符串。
5. 如果某个类型有问题，用简洁中文说明问题，并给出必要的修改建议。
6. 不要输出 Markdown。
7. 不要输出解释性文字。
8. 只返回严格 JSON。"""

DEFAULT_DIRECTIONAL_USER_PROMPT = """请按照 review_types 中指定的审校类型，审校 items 中的译文。

输入 JSON：
{text}

返回格式必须严格如下：
{
  "items": [
    {
      "id": "条目 ID",
      "checks": {
        "审校类型名称": "如果有问题，写问题说明和修改建议；如果没有问题，返回空字符串"
      }
    }
  ]
}

要求：
1. 返回的 items 数量必须和输入 items 数量一致。
2. 返回的 id 必须和输入 id 一致。
3. checks 中的 key 必须和 review_types 的 key 完全一致。
4. 没有问题时，该类型的值必须是空字符串 ""。
5. 有问题时，写成一句简洁说明，必要时包含建议改法。
6. 不要返回 review_types 中不存在的类型。
7. 不要省略任何已启用的审校类型。"""


class ReviewTaskError(Exception):
    pass


def create_review_task(
    batch_id: str,
    prompt_template_id: str | None = None,
    source_language: str = "",
    target_language: str = "",
    mode: str = "normal",
    directional_template_id: str | None = None,
    enable_ai_review: bool = True,
    enable_forbidden_check: bool = False,
    forbidden_template_id: str | None = None,
) -> str:
    items = _get_batch_items(batch_id)
    if not items:
        raise ReviewTaskError("当前没有可审校条目，请先读取文件")
    if not enable_ai_review and not enable_forbidden_check:
        raise ReviewTaskError("请至少启用 AI 审校或禁用词检查")

    settings = get_shared_ai_settings()
    api_key = settings.get("api_key", "")
    model = settings.get("selected_model", "")
    if enable_ai_review:
        if not api_key:
            raise ReviewTaskError("请先加载 DeepSeek API Key")
        if not model:
            raise ReviewTaskError("请先选择 DeepSeek 模型")

    forbidden_template = None
    forbidden_words: list[str] = []
    if enable_forbidden_check:
        forbidden_template = get_forbidden_template(forbidden_template_id)
        forbidden_words = parse_forbidden_words(forbidden_template["words_text"])

    task_id = uuid.uuid4().hex
    now = utc_now()
    if not enable_ai_review:
        config = {
            "mode": "forbidden_only",
            "enable_ai_review": False,
            "enable_forbidden_check": True,
            "forbidden_template_id": forbidden_template["id"] if forbidden_template else "",
            "forbidden_template_name": forbidden_template["name"] if forbidden_template else "",
            "forbidden_words": forbidden_words,
            "source_language": source_language.strip(),
            "target_language": target_language.strip(),
            "max_chars_per_request": int(settings.get("max_chars_per_request") or 3000),
            "max_concurrency": int(settings.get("max_concurrency") or 8),
            "enable_thinking": bool(settings.get("enable_thinking", False)),
        }
    elif mode == "directional":
        directional_template = get_directional_template(directional_template_id)
        review_types = enabled_review_types(directional_template)
        if not review_types:
            raise ReviewTaskError("请至少启用一个定向审校类型")
        config = {
            "mode": "directional",
            "enable_ai_review": True,
            "enable_forbidden_check": enable_forbidden_check,
            "forbidden_template_id": forbidden_template["id"] if forbidden_template else "",
            "forbidden_template_name": forbidden_template["name"] if forbidden_template else "",
            "forbidden_words": forbidden_words,
            "model": model,
            "directional_template_id": directional_template["id"],
            "directional_template_name": directional_template["name"],
            "review_types": review_types,
            "system_prompt": DEFAULT_DIRECTIONAL_SYSTEM_PROMPT,
            "user_prompt": DEFAULT_DIRECTIONAL_USER_PROMPT,
            "source_language": source_language.strip(),
            "target_language": target_language.strip(),
            "max_chars_per_request": int(settings.get("max_chars_per_request") or 3000),
            "max_concurrency": int(settings.get("max_concurrency") or 8),
            "enable_thinking": bool(settings.get("enable_thinking", False)),
        }
    else:
        prompt = get_prompt_template(prompt_template_id)
        config = {
            "mode": "normal",
            "enable_ai_review": True,
            "enable_forbidden_check": enable_forbidden_check,
            "forbidden_template_id": forbidden_template["id"] if forbidden_template else "",
            "forbidden_template_name": forbidden_template["name"] if forbidden_template else "",
            "forbidden_words": forbidden_words,
            "model": model,
            "prompt_template_id": prompt["id"],
            "prompt_template_name": prompt["name"],
            "system_prompt": prompt["system_prompt"],
            "user_prompt": prompt["user_prompt"],
            "source_language": source_language.strip(),
            "target_language": target_language.strip(),
            "max_chars_per_request": int(settings.get("max_chars_per_request") or 3000),
            "max_concurrency": int(settings.get("max_concurrency") or 8),
            "enable_thinking": bool(settings.get("enable_thinking", False)),
        }
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO review_tasks (
                id, batch_id, status, total_count, config_json, created_at, updated_at
            )
            VALUES (?, ?, 'pending', ?, ?, ?, ?)
            """,
            (task_id, batch_id, len(items), dumps_json(config), now, now),
        )
    _add_log(task_id, "info", f"任务已创建，共 {len(items)} 条")
    thread = threading.Thread(target=_run_review_task, args=(task_id,), daemon=True)
    thread.start()
    return task_id


def get_review_task(task_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM review_tasks WHERE id = ?", (task_id,)).fetchone()
    return _task_to_dict(row) if row else None


def get_review_logs(task_id: str, after_id: int = 0) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM review_task_logs
            WHERE task_id = ? AND id > ?
            ORDER BY id ASC
            """,
            (task_id, after_id),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "task_id": row["task_id"],
            "level": row["level"],
            "message": row["message"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_review_results(task_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, i.source_text, i.target_text, i.source_file, i.sheet_name,
                   i.segment_id, i.row_number,
                   COALESCE(f.matched_words, '') AS matched_words
            FROM review_results r
            JOIN file_items i ON i.id = r.item_id
            LEFT JOIN forbidden_results f ON f.task_id = r.task_id AND f.item_id = r.item_id
            WHERE r.task_id = ?
            ORDER BY i.item_order ASC
            LIMIT ?
            """,
            (task_id, limit),
        ).fetchall()
    return [_result_to_dict(row) for row in rows]


def _run_review_task(task_id: str) -> None:
    task = get_review_task(task_id)
    if not task:
        return
    config = task["config"]
    items = _get_batch_items(task["batch_id"])
    enable_ai_review = bool(config.get("enable_ai_review", True))
    max_chars = max(1, int(config["max_chars_per_request"]))
    settings = get_shared_ai_settings()
    api_key = settings.get("api_key", "")

    _update_task(task_id, status="running")
    requested_count = 0
    failed_count = 0
    completed_count = 0

    if enable_ai_review:
        model = config["model"]
        prompt_signature = _prompt_signature(
            config["system_prompt"],
            config["user_prompt"],
            config.get("source_language", ""),
            config.get("target_language", ""),
        )
        directional_signature = _directional_signature(config)
        enable_thinking = bool(config.get("enable_thinking", False))
        request_items = []
        for item in items:
            cache_key = _cache_key(
                item["source_text"],
                item["target_text"],
                _item_info(item),
                model,
                prompt_signature,
                directional_signature,
                enable_thinking,
            )
            request_items.append({**item, "cache_key": cache_key})

        _update_task(task_id, cached_count=0, completed_count=0)
        _add_log(task_id, "info", f"AI 结果缓存已停用，本次将请求 {len(request_items)} 条")

        packages = _build_packages(request_items, max_chars)

        for index, package in enumerate(packages, start=1):
            _add_log(task_id, "info", f"请求第 {index}/{len(packages)} 包，包含 {len(package)} 条")
            try:
                results = _request_with_retry(task_id, api_key, model, config, package)
                result_by_id = {str(item.get("id")): item for item in results}
                for item in package:
                    if config.get("mode") == "directional":
                        result = _normalize_directional_result(
                            result_by_id.get(item["id"]),
                            item["id"],
                            config.get("review_types", []),
                        )
                    else:
                        result = _normalize_result(result_by_id.get(item["id"]), item["id"])
                    _save_review_result(task_id, item["id"], item["cache_key"], "completed", result)
                    completed_count += 1
                    requested_count += 1
            except Exception as exc:
                message = str(exc)
                _add_log(task_id, "error", f"第 {index} 包失败：{message}")
                for item in package:
                    _save_review_error(task_id, item["id"], item["cache_key"], message)
                    completed_count += 1
                    failed_count += 1
                    requested_count += 1

            _update_task(
                task_id,
                requested_count=requested_count,
                completed_count=completed_count,
                failed_count=failed_count,
            )
    else:
        _add_log(task_id, "info", "未启用 AI 审校，跳过 AI 请求")
        for item in items:
            _save_review_result(task_id, item["id"], "", "skipped_ai", {})
        completed_count = len(items)
        _update_task(task_id, completed_count=completed_count)

    if config.get("enable_forbidden_check"):
        _run_forbidden_check(task_id, items, config.get("forbidden_words", []))

    try:
        output_path = generate_review_excel(task_id)
        _update_task(task_id, output_path=str(output_path))
        _add_log(task_id, "info", f"结果已自动保存：{output_path}")
    except Exception as exc:
        _add_log(task_id, "error", f"结果 Excel 输出失败：{exc}")
        _update_task(task_id, status="completed_with_errors")
        return

    final_status = "completed" if failed_count == 0 else "completed_with_errors"
    _update_task(task_id, status=final_status)
    _add_log(task_id, "info", f"任务完成：成功 {completed_count - failed_count} 条，失败 {failed_count} 条")


def _run_forbidden_check(task_id: str, items: list[dict[str, Any]], words: list[str]) -> None:
    _add_log(task_id, "info", "开始禁用词检查")
    now = utc_now()
    hit_count = 0
    with get_connection() as conn:
        conn.execute("DELETE FROM forbidden_results WHERE task_id = ?", (task_id,))
        for item in items:
            matched = check_forbidden_words(item["target_text"], words)
            if matched:
                hit_count += 1
            conn.execute(
                """
                INSERT INTO forbidden_results (id, task_id, item_id, matched_words, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uuid.uuid4().hex, task_id, item["id"], "; ".join(matched), now, now),
            )
    _add_log(task_id, "info", f"禁用词检查完成，命中 {hit_count} 条")


def _request_with_retry(
    task_id: str,
    api_key: str,
    model: str,
    config: dict[str, Any],
    package: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    delays = [2, 5, 10]
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            payload_items = [
                _payload_item(item)
                for item in package
            ]
            payload: dict[str, Any] = {"items": payload_items}
            if config.get("mode") == "directional":
                payload["review_types"] = config.get("review_types", [])
            source_language = config.get("source_language", "").strip()
            target_language = config.get("target_language", "").strip()
            if source_language or target_language:
                payload["language"] = {
                    "source": source_language,
                    "target": target_language,
                }
            text = json.dumps(payload, ensure_ascii=False)
            user_prompt = _build_user_prompt(config, text, any(_item_info(item) for item in package))
            content = review_chat(
                api_key,
                model,
                config["system_prompt"],
                user_prompt,
                enable_thinking=bool(config.get("enable_thinking", False)),
            )
            parsed = _parse_json_object(content)
            items = parsed.get("items")
            if not isinstance(items, list):
                raise ReviewTaskError("AI 返回 JSON 中缺少 items 数组")
            return items
        except (SharedProviderError, ReviewTaskError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 3:
                delay = delays[attempt - 1]
                _add_log(task_id, "warning", f"请求失败，{delay} 秒后重试第 {attempt + 1} 次：{exc}")
                time.sleep(delay)
            else:
                break
    raise ReviewTaskError(str(last_error or "请求失败"))


def _build_packages(items: list[dict[str, Any]], max_chars: int) -> list[list[dict[str, Any]]]:
    packages: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0

    for item in items:
        item_chars = len(item["source_text"] or "") + len(item["target_text"] or "")
        if item_chars > max_chars:
            if current:
                packages.append(current)
                current = []
                current_chars = 0
            packages.append([item])
            continue
        if current and current_chars + item_chars > max_chars:
            packages.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars

    if current:
        packages.append(current)
    return packages


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return json.loads(text)


def _normalize_result(result: Any, item_id: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "id": item_id,
            "has_issue": False,
            "issue_type": "",
            "issue": "",
            "suggestion": "",
        }
    return {
        "id": str(result.get("id") or item_id),
        "has_issue": bool(result.get("has_issue")),
        "issue_type": str(result.get("issue_type") or ""),
        "issue": str(result.get("issue") or ""),
        "suggestion": str(result.get("suggestion") or ""),
    }


def _normalize_directional_result(result: Any, item_id: str, review_types: list[dict[str, str]]) -> dict[str, Any]:
    checks = {}
    raw_checks = result.get("checks", {}) if isinstance(result, dict) else {}
    if not isinstance(raw_checks, dict):
        raw_checks = {}
    for review_type in review_types:
        key = review_type["key"]
        checks[key] = str(raw_checks.get(key) or "")
    return {"id": item_id, "checks": checks}


def _get_batch_items(batch_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM file_items
            WHERE batch_id = ?
            ORDER BY item_order ASC
            """,
            (batch_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _item_info(item: dict[str, Any]) -> list[dict[str, str]]:
    data = loads_json(item.get("info_json"), []) if item.get("info_json") else []
    if not isinstance(data, list):
        return []
    normalized = []
    for info in data:
        if not isinstance(info, dict):
            continue
        value = str(info.get("value") or "").strip()
        if value:
            normalized.append(
                {
                    "category": str(info.get("category") or "").strip(),
                    "value": value,
                }
            )
    return normalized


def _payload_item(item: dict[str, Any]) -> dict[str, Any]:
    payload = {"id": item["id"], "source": item["source_text"], "target": item["target_text"]}
    info = _item_info(item)
    if info:
        payload["info"] = info
    return payload


def _build_user_prompt(config: dict[str, Any], text: str, has_info: bool) -> str:
    prefixes = []
    source_language = str(config.get("source_language") or "").strip()
    target_language = str(config.get("target_language") or "").strip()
    if source_language or target_language:
        prefixes.append(f"以下是 {source_language or '未指定语种'} 原文和 {target_language or '未指定语种'} 译文。")
    if has_info:
        prefixes.append(
            "如果 item 包含 info 字段，请把 info 作为参考信息。"
            "info 中 category 是信息类别，value 是信息内容；没有 info 的条目不要假设存在参考信息。"
        )
    prompt = config["user_prompt"].replace("{text}", text)
    return "\n".join([*prefixes, prompt]) if prefixes else prompt


def _cache_key(
    source: str,
    target: str,
    info: list[dict[str, str]],
    model: str,
    prompt_signature: str,
    directional_signature: str,
    enable_thinking: bool,
) -> str:
    raw = dumps_json(
        {
            "source": source,
            "target": target,
            "info": info,
            "model": model,
            "prompt_signature": prompt_signature,
            "directional_signature": directional_signature,
            "enable_thinking": enable_thinking,
        }
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prompt_signature(system_prompt: str, user_prompt: str, source_language: str, target_language: str) -> str:
    raw = dumps_json(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "source_language": source_language,
            "target_language": target_language,
        }
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _directional_signature(config: dict[str, Any]) -> str:
    raw = dumps_json(
        {
            "mode": config.get("mode", "normal"),
            "review_types": config.get("review_types", []),
        }
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_cached_result(cache_key: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT result_json FROM ai_result_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    if not row:
        return None
    return loads_json(row["result_json"], None)


def _set_cached_result(
    cache_key: str,
    source_text: str,
    target_text: str,
    model: str,
    prompt_signature: str,
    directional_signature: str,
    result: dict[str, Any],
) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ai_result_cache (
                cache_key, source_text, target_text, model, prompt_signature,
                directional_signature, result_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                result_json = excluded.result_json,
                updated_at = excluded.updated_at
            """,
            (
                cache_key,
                source_text,
                target_text,
                model,
                prompt_signature,
                directional_signature,
                dumps_json(result),
                now,
                now,
            ),
        )


def _save_review_result(task_id: str, item_id: str, cache_key: str, status: str, result: dict[str, Any]) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO review_results (
                id, task_id, item_id, cache_key, status, has_issue, issue_type,
                issue, suggestion, directional_checks_json, error_message, raw_result_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                task_id,
                item_id,
                cache_key,
                status,
                1 if result.get("has_issue") else 0,
                result.get("issue_type", ""),
                result.get("issue", ""),
                result.get("suggestion", ""),
                dumps_json(result.get("checks", {})),
                dumps_json(result),
                now,
                now,
            ),
        )


def _save_review_error(task_id: str, item_id: str, cache_key: str, message: str) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO review_results (
                id, task_id, item_id, cache_key, status, error_message, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'failed', ?, ?, ?)
            """,
            (uuid.uuid4().hex, task_id, item_id, cache_key, message, now, now),
        )


def _update_task(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(task_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE review_tasks SET {assignments} WHERE id = ?", values)


def _add_log(task_id: str, level: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO review_task_logs (task_id, level, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, level, message, utc_now()),
        )


def _task_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "status": row["status"],
        "total_count": row["total_count"],
        "cached_count": row["cached_count"],
        "requested_count": row["requested_count"],
        "completed_count": row["completed_count"],
        "failed_count": row["failed_count"],
        "output_path": row["output_path"],
        "config": loads_json(row["config_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _result_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "item_id": row["item_id"],
        "status": row["status"],
        "has_issue": bool(row["has_issue"]) if row["has_issue"] is not None else None,
        "issue_type": row["issue_type"],
        "issue": row["issue"],
        "suggestion": row["suggestion"],
        "checks": loads_json(row["directional_checks_json"], {}),
        "error_message": row["error_message"],
        "source_text": row["source_text"],
        "target_text": row["target_text"],
        "source_file": row["source_file"],
        "sheet_name": row["sheet_name"],
        "segment_id": row["segment_id"],
        "row_number": row["row_number"],
        "matched_words": row["matched_words"] if "matched_words" in row.keys() else "",
    }
