from __future__ import annotations

import uuid
from typing import Any

from .database import dumps_json, get_connection, loads_json, utc_now


def list_excel_mapping_presets() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM excel_mapping_presets
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [_preset_to_dict(row) for row in rows]


def get_excel_mapping_preset(preset_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM excel_mapping_presets WHERE id = ?", (preset_id,)).fetchone()
    if not row:
        raise ValueError("预设不存在")
    return _preset_to_dict(row)


def save_excel_mapping_preset(name: str, mapping: dict[str, Any], preset_id: str | None = None) -> dict[str, Any]:
    now = utc_now()
    preset_id = preset_id or uuid.uuid4().hex
    preset_name = name.strip() or "未命名列映射"
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM excel_mapping_presets WHERE id = ?", (preset_id,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE excel_mapping_presets
                SET name = ?, mapping_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (preset_name, dumps_json(mapping), now, preset_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO excel_mapping_presets (id, name, mapping_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (preset_id, preset_name, dumps_json(mapping), now, now),
            )
    return get_excel_mapping_preset(preset_id)


def delete_excel_mapping_preset(preset_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM excel_mapping_presets WHERE id = ?", (preset_id,)).fetchone()
        if not row:
            raise ValueError("映射预设不存在")
        conn.execute("DELETE FROM excel_mapping_presets WHERE id = ?", (preset_id,))


def _preset_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "mapping": loads_json(row["mapping_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
