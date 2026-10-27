from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .inline_xml import inner_xml


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text_content(element: ET.Element | None) -> str:
    return inner_xml(element, xliff=True)


def _first_child_by_local_name(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _strip_namespace(child.tag) == name:
            return child
    return None


def read_xliff_items(path: Path, source_file: str) -> list[dict[str, Any]]:
    tree = ET.parse(path)
    root = tree.getroot()
    version = root.attrib.get("version", "")
    items: list[dict[str, Any]] = []
    order = 0

    if version.startswith("2"):
        units = [element for element in root.iter() if _strip_namespace(element.tag) == "unit"]
        for unit in units:
            unit_id = unit.attrib.get("id", "")
            segments = [element for element in unit.iter() if _strip_namespace(element.tag) == "segment"]
            for segment in segments:
                source_element = _first_child_by_local_name(segment, "source")
                target_element = _first_child_by_local_name(segment, "target")
                source = _text_content(source_element)
                target = _text_content(target_element)
                if not source and not target:
                    continue
                segment_id = segment.attrib.get("id") or unit_id
                order += 1
                item = _make_item(source_file, segment_id, source, target, order)
                original_data = _first_child_by_local_name(unit, "originalData")
                if original_data is not None:
                    referenced = {
                        node.attrib[key]
                        for element in (source_element, target_element) if element is not None
                        for node in element.iter()
                        for key in ("dataRef", "dataRefStart", "dataRefEnd") if key in node.attrib
                    }
                    item["inline_code_data"] = {
                        data.attrib["id"]: "".join(data.itertext())
                        for data in original_data
                        if data.attrib.get("id") in referenced
                    }
                    if item["inline_code_data"]:
                        item["info"] = [{
                            "category": "XLIFF 行内代码定义",
                            "value": json.dumps(item["inline_code_data"], ensure_ascii=False),
                        }]
                items.append(item)
    else:
        units = [element for element in root.iter() if _strip_namespace(element.tag) == "trans-unit"]
        for unit in units:
            source = _text_content(_first_child_by_local_name(unit, "source"))
            target = _text_content(_first_child_by_local_name(unit, "target"))
            if not source and not target:
                continue
            segment_id = unit.attrib.get("id", "")
            order += 1
            items.append(_make_item(source_file, segment_id, source, target, order))

    if not items:
        raise ValueError("没有读取到 XLIFF 条目，请确认文件包含 source/target")
    return items


def read_xliff_language_metadata(path: Path) -> dict[str, str]:
    tree = ET.parse(path)
    root = tree.getroot()
    source_language = ""
    target_language = ""

    for element in root.iter():
        source_language = (
            element.attrib.get("source-language")
            or element.attrib.get("srcLang")
            or source_language
        )
        target_language = (
            element.attrib.get("target-language")
            or element.attrib.get("trgLang")
            or target_language
        )
        if source_language and target_language:
            break

    return {
        "source_language": source_language,
        "target_language": target_language,
    }


def _make_item(source_file: str, segment_id: str, source: str, target: str, order: int) -> dict[str, Any]:
    status_note = ""
    if not source:
        status_note = "原文为空"
    elif not target:
        status_note = "译文为空"

    return {
        "source_file": source_file,
        "sheet_name": None,
        "segment_id": segment_id,
        "row_number": None,
        "source_text": source,
        "target_text": target,
        "status_note": status_note,
        "item_order": order,
    }
