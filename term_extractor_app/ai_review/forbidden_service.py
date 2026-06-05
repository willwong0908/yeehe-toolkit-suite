from __future__ import annotations

import uuid
from typing import Any

from .database import get_connection, utc_now


def ensure_default_forbidden_template() -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM forbidden_templates WHERE is_default = 1 LIMIT 1").fetchone()
        if row:
            return
        now = utc_now()
        conn.execute(
            """
            INSERT INTO forbidden_templates (id, name, words_text, is_default, created_at, updated_at)
            VALUES (?, ?, '', 1, ?, ?)
            """,
            (uuid.uuid4().hex, "默认禁用词", now, now),
        )


def list_forbidden_templates() -> list[dict[str, Any]]:
    ensure_default_forbidden_template()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM forbidden_templates
            ORDER BY is_default DESC, updated_at DESC
            """
        ).fetchall()
    return [_template_to_dict(row) for row in rows]


def get_forbidden_template(template_id: str | None = None) -> dict[str, Any]:
    ensure_default_forbidden_template()
    with get_connection() as conn:
        if template_id:
            row = conn.execute("SELECT * FROM forbidden_templates WHERE id = ?", (template_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM forbidden_templates WHERE is_default = 1 LIMIT 1").fetchone()
    if not row:
        raise ValueError("禁用词模板不存在")
    return _template_to_dict(row)


def save_forbidden_template(template_id: str | None, name: str, words_text: str) -> dict[str, Any]:
    now = utc_now()
    with get_connection() as conn:
        if template_id:
            row = conn.execute("SELECT id FROM forbidden_templates WHERE id = ?", (template_id,)).fetchone()
            if not row:
                raise ValueError("禁用词模板不存在")
            conn.execute(
                """
                UPDATE forbidden_templates
                SET name = ?, words_text = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, words_text, now, template_id),
            )
            saved_id = template_id
        else:
            saved_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO forbidden_templates (id, name, words_text, is_default, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (saved_id, name, words_text, now, now),
            )
    return get_forbidden_template(saved_id)


def delete_forbidden_template(template_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT is_default FROM forbidden_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise ValueError("禁用词模板不存在")
        if row["is_default"]:
            raise ValueError("默认禁用词模板不能删除")
        conn.execute("DELETE FROM forbidden_templates WHERE id = ?", (template_id,))


def parse_forbidden_words(words_text: str) -> list[str]:
    words = []
    seen = set()
    for line in words_text.splitlines():
        word = line.strip()
        if word and word.lower() not in seen:
            words.append(word)
            seen.add(word.lower())
    return words


def check_forbidden_words(target_text: str, words: list[str]) -> list[str]:
    target_lower = (target_text or "").lower()
    return [word for word in words if word.lower() in target_lower]


def _template_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "words_text": row["words_text"],
        "is_default": bool(row["is_default"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
