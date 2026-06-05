from __future__ import annotations

from pathlib import Path

from .config import SUPPORTED_EXCEL_EXTENSIONS, SUPPORTED_XLIFF_EXTENSIONS
from .excel_reader import read_excel_headers, read_excel_items, read_excel_items_by_mapping
from .xliff_reader import read_xliff_items, read_xliff_language_metadata


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_EXCEL_EXTENSIONS:
        return "excel"
    if suffix in SUPPORTED_XLIFF_EXTENSIONS:
        return "xliff"
    raise ValueError("仅支持 Excel（.xlsx/.xlsm）和 XLIFF（.xlf/.xliff）文件")


__all__ = [
    "detect_file_type",
    "read_excel_headers",
    "read_excel_items",
    "read_excel_items_by_mapping",
    "read_xliff_items",
    "read_xliff_language_metadata",
]
