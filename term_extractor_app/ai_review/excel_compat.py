"""Value-only Excel reader selected by file content, including legacy BIFF workbooks."""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
import zipfile
import struct
import xlrd
from openpyxl import load_workbook


class ExcelCompatibilityError(ValueError):
    pass


class _LegacySheet:
    def __init__(self, sheet, datemode):
        self._sheet = sheet
        self._datemode = datemode
        self.title = sheet.name

    def reset_dimensions(self):
        # BIFF dimensions are obtained from actual loaded cells.
        pass

    def iter_rows(self, *, min_row=1, max_row=None, min_col=1, max_col=None, values_only=False):
        if not values_only:
            raise ValueError("Legacy workbook access supports values_only=True")
        stop = min(self._sheet.nrows, max_row) if max_row is not None else self._sheet.nrows
        width = self._sheet.ncols if max_col is None else max_col
        for row in range(min_row - 1, stop):
            values = []
            for col in range(min_col - 1, width):
                if col >= self._sheet.row_len(row):
                    values.append(None)
                    continue
                cell = self._sheet.cell(row, col)
                value = cell.value
                if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    value = None
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(value, "#VALUE!")
                elif cell.ctype == xlrd.XL_CELL_DATE:
                    value = xlrd.xldate_as_datetime(value, self._datemode)
                    if 0 <= cell.value < 1:
                        value = value.time()
                elif cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
                    value = int(value)
                values.append(value)
            yield tuple(values)


class _Workbook:
    def __init__(self, book, stream=None, *, legacy=False):
        self._book = book
        self._stream = stream
        self._legacy = legacy
        self.worksheets = ([_LegacySheet(book.sheet_by_index(i), book.datemode) for i in range(book.nsheets)]
                           if legacy else book.worksheets)

    def close(self):
        try:
            if self._legacy:
                self._book.release_resources()
            else:
                self._book.close()
        finally:
            if self._stream is not None:
                self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def open_review_workbook(source: Path | BinaryIO, *, read_only=True, data_only=True):
    """Open actual XLS/XLSX content regardless of the displayed/cached filename.

    The caller owns streams passed in; internally opened path streams are closed
    together with the workbook. No conversion or source-file writes take place.
    """
    owned = Path(source).open("rb") if isinstance(source, (Path, str)) else None
    stream = owned if owned is not None else source
    try:
        stream.seek(0)
        head = stream.read(8)
        stream.seek(0)
        if zipfile.is_zipfile(stream):
            stream.seek(0)
            book = load_workbook(stream, read_only=read_only, data_only=data_only)
            if read_only:
                for sheet in book.worksheets:
                    sheet.reset_dimensions()
            return _Workbook(book, owned)
        if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") or head[:2] in (b"\x09\x08", b"\x09\x04", b"\x09\x02", b"\x09\x00"):
            stream.seek(0)
            try:
                if owned is not None:
                    book = xlrd.open_workbook(str(source), on_demand=True, ragged_rows=True)
                else:
                    book = xlrd.open_workbook(file_contents=stream.read(), on_demand=True, ragged_rows=True)
            except (xlrd.XLRDError, xlrd.compdoc.CompDocError, struct.error) as exc:
                raise ExcelCompatibilityError("无法读取旧版或加密 Excel 文件，请确认文件完整；若设置了打开密码，请移除密码后另存为 .xlsx 再试。") from exc
            if owned is not None:
                owned.close()
            return _Workbook(book, legacy=True)
        raise ExcelCompatibilityError("文件内容不是可读取的 Excel 工作簿。请确认文件完整，使用 Excel 或 WPS 打开后另存为 .xlsx 再试；仅修改扩展名不能转换格式。")
    except Exception:
        if owned is not None:
            owned.close()
        raise
