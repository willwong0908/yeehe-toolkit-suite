from __future__ import annotations

import uuid
from typing import Any

from .database import dumps_json, get_connection, loads_json, utc_now

DEFAULT_DIRECTIONAL_ITEMS = [
    {"name": "低错", "enabled": True},
    {"name": "大小写问题", "enabled": True},
    {"name": "理解错误、错译", "enabled": True},
    {"name": "标点符号错误", "enabled": True},
]


def ensure_default_directional_template() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM directional_templates WHERE is_default = 1 LIMIT 1").fetchone()
        if row:
            return
        now = utc_now()
        conn.execute(
            """
            INSERT INTO directional_templates (id, name, items_json, is_default, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (uuid.uuid4().hex, "通用定向审校", dumps_json(DEFAULT_DIRECTIONAL_ITEMS), now, now),
        )


def list_directional_templates() -> list[dict[str, Any]]:
    ensure_default_directional_template()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM directional_templates
            ORDER BY is_default DESC, updated_at DESC
            """
        ).fetchall()
    return [_template_to_dict(row) for row in rows]


def get_directional_template(template_id: str | None = None) -> dict[str, Any]:
    ensure_default_directional_template()
    with get_connection() as conn:
        if template_id:
            row = conn.execute("SELECT * FROM directional_templates WHERE id = ?", (template_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM directional_templates WHERE is_default = 1 LIMIT 1").fetchone()
    if not row:
        raise ValueError("定向审校模板不存在")
    return _template_to_dict(row)


def save_directional_template(template_id: str | None, name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    clean_items = []
    for item in items:
        item_name = str(item.get("name", "")).strip()
        if item_name:
            clean_items.append({"name": item_name, "enabled": bool(item.get("enabled", True))})
    if not clean_items:
        raise ValueError("请至少填写一个定向审校类型")

    now = utc_now()
    with get_connection() as conn:
        if template_id:
            row = conn.execute("SELECT id FROM directional_templates WHERE id = ?", (template_id,)).fetchone()
            if not row:
                raise ValueError("定向审校模板不存在")
            conn.execute(
                """
                UPDATE directional_templates
                SET name = ?, items_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, dumps_json(clean_items), now, template_id),
            )
            saved_id = template_id
        else:
            saved_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO directional_templates (id, name, items_json, is_default, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (saved_id, name, dumps_json(clean_items), now, now),
            )
    return get_directional_template(saved_id)


def delete_directional_template(template_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT is_default FROM directional_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise ValueError("定向审校模板不存在")
        if row["is_default"]:
            raise ValueError("默认定向审校模板不能删除")
        conn.execute("DELETE FROM directional_templates WHERE id = ?", (template_id,))


def enabled_review_types(template: dict[str, Any]) -> list[dict[str, str]]:
    review_types = []
    for item in template["items"]:
        name = str(item.get("name", "")).strip()
        if name and item.get("enabled", True):
            review_types.append({"key": name, "description": name})
    return review_types


def _template_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "items": loads_json(row["items_json"], []),
        "is_default": bool(row["is_default"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
