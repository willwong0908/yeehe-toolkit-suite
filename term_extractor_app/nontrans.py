"""Non-translatable element rules and protection helpers."""

from __future__ import annotations

import re
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import NONTRANS_REGEX_COLUMNS
from .core import clean_api_response
from .models import NonTransElement, NonTransMatch, NonTransRegexRow, NonTransRegexRule, ProtectedText, SourceRecord


NONTRANS_ROLE_LABELS = {
    "open": "开始",
    "close": "结束",
    "empty": "空",
}

DEFAULT_NONTRANS_PLACEHOLDER_FORMAT = "<{n}>"

NONTRANS_ELEMENT_TYPE_LABELS = {
    "html": "HTML 代码",
    "hash_brace": "#花括号占位符",
    "brace": "花括号占位符",
    "bracket": "方括号标签",
    "at_var": "@变量",
    "dollar_var": "$变量",
    "percent_var": "%变量",
    "escape": "转义字符",
    "html_entity": "HTML 实体",
    "other": "其他",
}

ALLOWED_NONTRANS_ELEMENT_TYPES = set(NONTRANS_ELEMENT_TYPE_LABELS)
ALLOWED_NONTRANS_ROLES = set(NONTRANS_ROLE_LABELS)

ESCAPE_EQUIVALENT_TEXTS = {
    "\\n": "\n",
    "\\r": "\r",
    "\\t": "\t",
    "\\b": "\b",
    "\\f": "\f",
    '\\"': '"',
    "\\'": "'",
    "\\\\n": "\\n",
    "\\\\r": "\\r",
    "\\\\t": "\\t",
    "\\\\b": "\\b",
    "\\\\f": "\\f",
    '\\\\\"': '\\"',
    "\\\\'": "\\'",
}


def _decode_json_like_string_once(text: str) -> Optional[str]:
    raw = str(text or "")
    try:
        return json.loads('"{0}"'.format(raw.replace("\\", "\\\\").replace('"', '\\"')))
    except Exception:
        return None


def _decode_json_escape_sequences(text: str) -> List[str]:
    raw = str(text or "")
    variants: List[str] = []

    def add(value: Optional[str]) -> None:
        if value is None:
            return
        normalized = str(value)
        if normalized not in variants:
            variants.append(normalized)

    add(raw)
    add(raw.replace("\\/", "/"))

    current = raw
    for _ in range(3):
        decoded = _decode_json_like_string_once(current)
        if decoded is None or decoded == current:
            break
        add(decoded)
        add(decoded.replace("\\/", "/"))
        current = decoded

    # Common literal unicode-escape variants that models sometimes double-escape.
    simple_unicode_map = {
        "003c": "<",
        "003e": ">",
        "0022": '"',
        "0027": "'",
        "0026": "&",
        "007b": "{",
        "007d": "}",
        "005b": "[",
        "005d": "]",
        "0028": "(",
        "0029": ")",
        "0024": "$",
        "0023": "#",
        "0040": "@",
        "0025": "%",
        "003d": "=",
        "003a": ":",
        "002f": "/",
    }

    def replace_simple_unicode_escapes(value: str) -> str:
        def repl(match: re.Match[str]) -> str:
            code = str(match.group(1) or "").lower()
            return simple_unicode_map.get(code, match.group(0))

        return re.sub(r"\\u([0-9a-fA-F]{4})", repl, value)

    replaced = replace_simple_unicode_escapes(raw)
    if replaced != raw:
        add(replaced)

    return variants


def _normalized_nontrans_element_variants(element: str) -> List[str]:
    text = str(element or "")
    variants: List[str] = []

    def add(value: str) -> None:
        if value not in variants:
            variants.append(value)

    add(text)
    for decoded in _decode_json_escape_sequences(text):
        add(decoded)
    if "\\\"" in text:
        add(text.replace("\\\"", "\""))
    if "\\'" in text:
        add(text.replace("\\'", "'"))
    if "\\\\" in text:
        add(text.replace("\\\\", "\\"))
    if "\\\"" in text and "\\\\" in text:
        add(text.replace("\\\\", "\\").replace("\\\"", "\""))
    if "\\'" in text and "\\\\" in text:
        add(text.replace("\\\\", "\\").replace("\\'", "'"))
    return variants


DEFAULT_NONTRANS_BUILTIN_RULES: List[Dict[str, object]] = [
    {
        "rule_id": "builtin_html_attr_open",
        "name": "HTML属性开始标签",
        "pattern": r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s*=\s*[^\s<>]+)?(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*(?:\s*=\s*(?:\\\"[^\"<>\r\n]*\\\"|\\'[^'<> \r\n]*\\'|\"[^\"<>\r\n]*\"|'[^'<> \r\n]*'|[^\s\"'=<>`]+))?)*\s*>",
        "open_pattern": r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s*=\s*[^\s<>]+)?(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*(?:\s*=\s*(?:\\\"[^\"<>\r\n]*\\\"|\\'[^'<> \r\n]*\\'|\"[^\"<>\r\n]*\"|'[^'<> \r\n]*'|[^\s\"'=<>`]+))?)*\s*>",
        "element_type": "html",
        "examples": ["<color=#FFAA00>", "<color = {1}>"],
    },
    {
        "rule_id": "builtin_html_attr_empty",
        "name": "HTML属性自闭合标签",
        "pattern": r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s*=\s*[^\s<>]+)?(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*(?:\s*=\s*(?:\\\"[^\"<>\r\n]*\\\"|\\'[^'<> \r\n]*\\'|\"[^\"<>\r\n]*\"|'[^'<> \r\n]*'|[^\s\"'=<>`]+))?)*\s*/>",
        "empty_pattern": r"<[A-Za-z][A-Za-z0-9:_-]*(?:\s*=\s*[^\s<>]+)?(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*(?:\s*=\s*(?:\\\"[^\"<>\r\n]*\\\"|\\'[^'<> \r\n]*\\'|\"[^\"<>\r\n]*\"|'[^'<> \r\n]*'|[^\s\"'=<>`]+))?)*\s*/>",
        "element_type": "html",
        "examples": ['<sprite width="24"/>'],
    },
    {
        "rule_id": "builtin_html_close",
        "name": "HTML闭合标签",
        "pattern": r"</[A-Za-z][A-Za-z0-9:_-]*>",
        "close_pattern": r"</[A-Za-z][A-Za-z0-9:_-]*>",
        "element_type": "html",
        "examples": ["</color>"],
    },
    {
        "rule_id": "builtin_hash_brace",
        "name": "#花括号变量",
        "pattern": r"#\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}",
        "empty_pattern": r"#\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}",
        "element_type": "hash_brace",
        "examples": ["#{PlayerName}"],
    },
    {
        "rule_id": "builtin_brace",
        "name": "花括号占位符",
        "pattern": r"\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}",
        "empty_pattern": r"\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}",
        "element_type": "brace",
        "examples": ["{0}", "{PlayerName}"],
    },
    {
        "rule_id": "builtin_bracket",
        "name": "方括号标签",
        "pattern": r"\[(?:/?[A-Za-z_#][A-Za-z0-9_#|:.+\-]*|[A-Za-z_#][A-Za-z0-9_#|:.+\-]*=[A-Za-z0-9_#|:.+\-]+)\]",
        "empty_pattern": r"\[(?:/?[A-Za-z_#][A-Za-z0-9_#|:.+\-]*|[A-Za-z_#][A-Za-z0-9_#|:.+\-]*=[A-Za-z0-9_#|:.+\-]+)\]",
        "element_type": "bracket",
        "examples": ["[sprite=icon_coin]", "[BTN_A]"],
    },
    {
        "rule_id": "builtin_dollar_var",
        "name": "$变量",
        "pattern": r"\$(?:\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}|\([^\s()<>[\]{}]+\)|\[[^\s\[\]<>({})]+\]|<[^\s<>]+>|[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])*)",
        "empty_pattern": r"\$(?:\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}|\([^\s()<>[\]{}]+\)|\[[^\s\[\]<>({})]+\]|<[^\s<>]+>|[A-Za-z_][A-Za-z0-9_]*(?:\[\d+\])*)",
        "element_type": "dollar_var",
        "examples": ["${item.name}", "$value"],
    },
    {
        "rule_id": "builtin_at_var",
        "name": "@变量",
        "pattern": r"@[A-Za-z_][A-Za-z0-9_]*",
        "empty_pattern": r"@[A-Za-z_][A-Za-z0-9_]*",
        "element_type": "at_var",
        "examples": ["@PlayerName"],
    },
    {
        "rule_id": "builtin_percent_var",
        "name": "%变量",
        "pattern": r"%(?:[A-Za-z_][A-Za-z0-9_]*%|(?:\d+\$)?[#0\- +']*(?:\d+)?(?:\.\d+)?[A-Za-z])",
        "empty_pattern": r"%(?:[A-Za-z_][A-Za-z0-9_]*%|(?:\d+\$)?[#0\- +']*(?:\d+)?(?:\.\d+)?[A-Za-z])",
        "element_type": "percent_var",
        "examples": ["%s", "%PlayerName%"],
    },
    {
        "rule_id": "builtin_escape",
        "name": "转义符",
        "pattern": r"\\(?:[nrtbfav\\'\"0]|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2})",
        "empty_pattern": r"\\(?:[nrtbfav\\'\"0]|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2})",
        "element_type": "escape",
        "examples": [r"\n", r"\u3000"],
    },
    {
        "rule_id": "builtin_html_entity",
        "name": "HTML实体",
        "pattern": r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d{1,7}|#x[0-9A-Fa-f]{1,6});",
        "empty_pattern": r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d{1,7}|#x[0-9A-Fa-f]{1,6});",
        "element_type": "html_entity",
        "examples": ["&nbsp;", "&#160;"],
    },
]

PACKAGED_NONTRANS_LIBRARY_FILE = Path(__file__).resolve().with_name("nontrans_builtin_regex_library.json")
BUILTIN_NONTRANS_LIBRARY_FILE = (
    Path(sys.executable).resolve().parent / "data" / "nontrans_builtin_regex_library.json"
    if getattr(sys, "frozen", False)
    else PACKAGED_NONTRANS_LIBRARY_FILE
)


def _appdata_nontrans_library_file() -> Path:
    base_dir = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return base_dir / "Yeehe Toolkit" / "nontrans_builtin_regex_library.json"


def _candidate_builtin_library_files(library_file: Optional[Path] = None) -> List[Path]:
    if library_file is not None:
        return [Path(library_file)]
    candidates = [
        BUILTIN_NONTRANS_LIBRARY_FILE,
        _appdata_nontrans_library_file(),
        PACKAGED_NONTRANS_LIBRARY_FILE,
    ]
    unique_candidates: List[Path] = []
    seen = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(path)
    return unique_candidates


def _write_builtin_library_payload(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_nontrans_element(element: str) -> str:
    text = str(element or "").strip()
    if re.fullmatch(r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s*=\s*[^\s<>]+)?(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*(?:\s*=\s*(?:\\\"[^\"<>\r\n]*\\\"|\\'[^'<> \r\n]*\\'|\"[^\"<>\r\n]*\"|'[^'<> \r\n]*'|[^\s\"'=<>`]+))?)*\s*/?>", text):
        return "html"
    if re.fullmatch(r"#\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}", text):
        return "hash_brace"
    if re.fullmatch(r"\{(?:\d+|[A-Za-z_][A-Za-z0-9_.\[\]-]*)(?::[A-Za-z0-9_.,#%+\-]+)?\}", text):
        return "brace"
    if re.fullmatch(r"\[(?:/?[A-Za-z_#][A-Za-z0-9_#|:.+\-]*|[A-Za-z_#][A-Za-z0-9_#|:.+\-]*=[A-Za-z0-9_#|:.+\-]+)\]", text):
        return "bracket"
    if re.fullmatch(r"@[A-Za-z_][A-Za-z0-9_]*", text):
        return "at_var"
    if re.fullmatch(str(DEFAULT_NONTRANS_BUILTIN_RULES[6]["pattern"]), text):
        return "dollar_var"
    if re.fullmatch(str(DEFAULT_NONTRANS_BUILTIN_RULES[8]["pattern"]), text):
        return "percent_var"
    if re.fullmatch(r"\\(?:[nrtbfav\\'\"0]|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2})", text):
        return "escape"
    if re.fullmatch(r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d{1,7}|#x[0-9A-Fa-f]{1,6});", text):
        return "html_entity"
    return "other"


def load_builtin_nontrans_rules(library_file: Optional[Path] = None) -> List[NonTransRegexRule]:
    raw_rules = _load_builtin_nontrans_rule_dicts(library_file)
    rules = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        data = dict(raw_rule)
        data.setdefault("enabled", True)
        data.setdefault("source", "builtin")
        data["order_index"] = int(data.get("order_index", index) or index)
        rules.append(NonTransRegexRule.from_dict(data))
    return rules


def save_builtin_nontrans_rules(
    rules: Sequence[NonTransRegexRule],
    library_file: Optional[Path] = None,
) -> None:
    serialized_rules = []
    for index, rule in enumerate(rules, start=1):
        data = rule.to_dict()
        data["order_index"] = int(data.get("order_index", index) or index)
        serialized_rules.append(data)
    payload = {"version": 1, "rules": serialized_rules}
    errors: List[str] = []
    for path in _candidate_builtin_library_files(library_file):
        try:
            _write_builtin_library_payload(path, payload)
            return
        except OSError as exc:
            errors.append("{0}: {1}".format(path, exc))
    raise OSError("无法写入非译元素内置规则库：{0}".format("；".join(errors)))


def update_builtin_rule_examples_from_rows(
    rows: Sequence[NonTransRegexRow],
    max_examples_per_rule: int = 3,
    library_file: Optional[Path] = None,
) -> bool:
    builtin_rules = load_builtin_nontrans_rules(library_file)
    if not builtin_rules:
        return False

    limit = max(1, int(max_examples_per_rule or 1))
    matched_examples_by_rule_id: Dict[str, List[str]] = {}
    for row in rows:
        rule_id = str(row.rule_id or "").strip()
        examples = [str(item or "").strip() for item in list(row.examples or []) if str(item or "").strip()]
        if not rule_id or not examples:
            continue
        matched_examples_by_rule_id.setdefault(rule_id, [])
        matched_examples_by_rule_id[rule_id].extend(examples)
        matched_examples_by_rule_id[rule_id] = _preserve_unique(matched_examples_by_rule_id[rule_id])

    changed = False
    updated_rules: List[NonTransRegexRule] = []
    for rule in builtin_rules:
        rule_copy = NonTransRegexRule.from_dict(rule.to_dict())
        matched_examples = matched_examples_by_rule_id.get(rule_copy.rule_id, [])
        if matched_examples:
            combined = _preserve_unique(list(rule_copy.examples or []) + matched_examples)
            latest_examples = combined[-limit:]
            if latest_examples != list(rule_copy.examples or [])[:]:
                rule_copy.examples = latest_examples
                changed = True
        updated_rules.append(rule_copy)

    if changed:
        save_builtin_nontrans_rules(updated_rules, library_file=library_file)
    return changed


def _load_builtin_nontrans_rule_dicts(library_file: Optional[Path] = None) -> List[Dict[str, object]]:
    for path in _candidate_builtin_library_files(library_file):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw = raw.get("rules", [])
            if isinstance(raw, list):
                loaded = [dict(item) for item in raw if isinstance(item, dict)]
                if loaded:
                    return loaded
        except Exception:
            pass
    return [dict(item) for item in DEFAULT_NONTRANS_BUILTIN_RULES]


def validate_nontrans_rule(rule: NonTransRegexRule, examples: Optional[Sequence[str]] = None) -> List[str]:
    issues: List[str] = []
    if rule.element_type not in ALLOWED_NONTRANS_ELEMENT_TYPES:
        issues.append("不支持的非译元素类型：{0}".format(rule.element_type or "空值"))

    patterns = _rule_role_patterns(rule)
    if not patterns:
        issues.append("规则没有可执行正则")
        return issues

    for role, pattern in patterns:
        if role not in ALLOWED_NONTRANS_ROLES:
            issues.append("不支持的开始/结束/空类型：{0}".format(role))
        try:
            re.compile(pattern)
        except re.error as exc:
            issues.append("{0} 正则无法编译：{1}".format(role, exc))
            continue
        if _looks_like_dangerous_regex(pattern):
            issues.append("{0} 正则疑似包含高风险回溯结构".format(role))

        if _looks_like_overbroad_nontrans_regex(pattern):
            issues.append("{0} 正则过宽，可能匹配普通文本".format(role))

    sample_values = [str(item) for item in list(examples or rule.examples or []) if str(item or "").strip()]
    if sample_values:
        compiled_patterns = []
        for _, pattern in patterns:
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error:
                pass
        for sample in sample_values:
            if not any(pattern.search(sample) for pattern in compiled_patterns):
                issues.append("正则无法匹配样例：{0}".format(sample))
    return issues


def expand_nontrans_regex_rows(rules: Sequence[NonTransRegexRule]) -> List[NonTransRegexRow]:
    rows: List[NonTransRegexRow] = []
    for rule in sorted([item for item in rules if item.enabled], key=lambda item: item.order_index):
        role_patterns = _rule_role_patterns(rule)
        if not role_patterns and rule.pattern:
            role_patterns = [("empty", rule.pattern)]
        for role, pattern in role_patterns:
            if not str(pattern or "").strip():
                continue
            row_id = "{0}:{1}".format(rule.rule_id, role)
            rows.append(
                NonTransRegexRow(
                    row_id=row_id,
                    rule_id=rule.rule_id,
                    name=rule.name,
                    regex=str(pattern),
                    role=role,
                    element_type=rule.element_type,
                    order_index=len(rows) + 1,
                    examples=list(rule.examples or []),
                )
            )
    return rows


def deduplicate_nontrans_regex_rows(rows: Sequence[NonTransRegexRow]) -> List[NonTransRegexRow]:
    merged: "OrderedDict[Tuple[str, str], NonTransRegexRow]" = OrderedDict()
    for row in rows:
        key = (row.role, row.regex)
        existing = merged.get(key)
        if existing is None:
            clone = NonTransRegexRow.from_dict(row.to_dict())
            clone.order_index = len(merged) + 1
            merged[key] = clone
            continue
        existing.examples = _preserve_unique(existing.examples + list(row.examples or []))
        if existing.element_type == "other" and row.element_type != "other":
            existing.element_type = row.element_type

    covered_rows: List[NonTransRegexRow] = []
    for row in merged.values():
        covering = next(
            (
                existing
                for existing in covered_rows
                if _row_covers_examples(existing, row)
            ),
            None,
        )
        if covering is not None:
            covering.examples = _preserve_unique(covering.examples + list(row.examples or []))
            continue
        row.order_index = len(covered_rows) + 1
        covered_rows.append(row)
    return covered_rows


def _row_covers_examples(existing: NonTransRegexRow, row: NonTransRegexRow) -> bool:
    if existing.role != row.role:
        return False
    if existing.element_type != row.element_type and existing.element_type != "other":
        return False
    examples = [str(item).strip() for item in list(row.examples or []) if str(item or "").strip()]
    if not examples:
        return False
    try:
        compiled = re.compile(existing.regex)
    except re.error:
        return False
    return all(compiled.fullmatch(example) for example in examples)


def find_covering_builtin_rows(element: str, rows: Sequence[NonTransRegexRow]) -> List[NonTransRegexRow]:
    text = str(element or "").strip()
    if not text:
        return []
    matched_rows = []
    for row in rows:
        try:
            if re.fullmatch(row.regex, text):
                matched_rows.append(row)
        except re.error:
            continue
    return matched_rows




def validate_nontrans_rule_minimal(rule: NonTransRegexRule) -> List[str]:
    issues: List[str] = []
    if rule.element_type not in ALLOWED_NONTRANS_ELEMENT_TYPES:
        issues.append("unsupported element_type: {0}".format(rule.element_type or "empty"))

    patterns = _rule_role_patterns(rule)
    if not patterns:
        issues.append("rule has no executable regex")
        return issues

    for role, pattern in patterns:
        if role not in ALLOWED_NONTRANS_ROLES:
            issues.append("unsupported role: {0}".format(role))
        try:
            re.compile(pattern)
        except re.error as exc:
            issues.append("{0} regex compile failed: {1}".format(role, exc))
    return issues


def collect_covering_rows_for_elements(
    rows: Sequence[NonTransRegexRow],
    elements: Sequence[NonTransElement],
) -> Tuple[List[NonTransRegexRow], List[NonTransElement]]:
    matched_rows: List[NonTransRegexRow] = []
    uncovered_elements: List[NonTransElement] = []
    element_texts = [str(element.element or "").strip() for element in elements]

    for row in rows:
        matched_examples: List[str] = []
        try:
            compiled = re.compile(row.regex)
        except re.error:
            continue
        for element_text in element_texts:
            if element_text and compiled.fullmatch(element_text):
                matched_examples.append(element_text)
        if matched_examples:
            row_copy = NonTransRegexRow.from_dict(row.to_dict())
            row_copy.examples = _preserve_unique(list(row_copy.examples or []) + matched_examples)
            matched_rows.append(row_copy)

    for element in elements:
        text = str(element.element or "").strip()
        if not text:
            uncovered_elements.append(NonTransElement.from_dict(element.to_dict()))
            continue
        covered = False
        for row in matched_rows:
            try:
                if re.fullmatch(row.regex, text):
                    covered = True
                    break
            except re.error:
                continue
        if not covered:
            uncovered_elements.append(NonTransElement.from_dict(element.to_dict()))

    return matched_rows, uncovered_elements


def resolve_nontrans_regex_order(
    rows: Sequence[NonTransRegexRow],
    elements: Sequence[NonTransElement],
) -> Dict[str, object]:
    pending_rows = [
        NonTransRegexRow.from_dict(row.to_dict())
        for row in sorted(list(rows or []), key=lambda item: int(item.order_index or 0))
    ]
    remaining_elements: "OrderedDict[Tuple[str, str], NonTransElement]" = OrderedDict()
    for element in elements:
        key = (str(element.element or "").strip(), str(element.element_type or "").strip())
        if key[0] and key not in remaining_elements:
            remaining_elements[key] = NonTransElement.from_dict(element.to_dict())

    ordered_rows: List[NonTransRegexRow] = []
    deferred_rows: List[NonTransRegexRow] = []
    rounds = 0

    while pending_rows and remaining_elements:
        rounds += 1
        progressed = False
        next_pending: List[NonTransRegexRow] = []

        for row in pending_rows:
            try:
                compiled = re.compile(row.regex)
            except re.error:
                continue

            full_match_keys: List[Tuple[str, str]] = []
            partial_match_found = False
            for element_key, element in remaining_elements.items():
                element_text = str(element.element or "").strip()
                if not element_text:
                    continue
                if compiled.fullmatch(element_text):
                    full_match_keys.append(element_key)
                    continue
                if compiled.search(element_text):
                    partial_match_found = True
                    break

            if partial_match_found:
                next_pending.append(NonTransRegexRow.from_dict(row.to_dict()))
                continue

            if full_match_keys:
                row_copy = NonTransRegexRow.from_dict(row.to_dict())
                row_copy.order_index = len(ordered_rows) + 1
                row_copy.examples = _preserve_unique(
                    list(row_copy.examples or []) + [remaining_elements[key].element for key in full_match_keys]
                )
                ordered_rows.append(row_copy)
                for element_key in full_match_keys:
                    remaining_elements.pop(element_key, None)
                progressed = True
                continue

            next_pending.append(NonTransRegexRow.from_dict(row.to_dict()))

        if not progressed:
            deferred_rows = next_pending
            break
        pending_rows = next_pending
    else:
        deferred_rows = pending_rows

    unresolved_elements = [NonTransElement.from_dict(item.to_dict()) for item in remaining_elements.values()]
    return {
        "ordered_rows": ordered_rows,
        "unresolved_elements": unresolved_elements,
        "deferred_rows": deferred_rows,
        "round_count": rounds,
    }


def filter_candidate_nontrans_records(
    source_records: Sequence[SourceRecord],
    broad_patterns: Sequence[str],
) -> List[SourceRecord]:
    compiled = []
    for pattern in broad_patterns:
        try:
            compiled.append(re.compile(str(pattern)))
        except re.error:
            continue
    if not compiled:
        return []
    return [record for record in source_records if any(pattern.search(record.text) for pattern in compiled)]


def normalize_ascii_candidate_patterns(raw_patterns: object) -> List[str]:
    if not isinstance(raw_patterns, list):
        return []
    normalized = []
    for index, item in enumerate(raw_patterns, start=1):
        if isinstance(item, dict):
            if not bool(item.get("enabled", True)):
                continue
            pattern = str(item.get("pattern", "")).strip()
            order_index = int(item.get("order_index", index) or index)
        else:
            pattern = str(item or "").strip()
            order_index = index
        if not pattern:
            continue
        normalized.append((order_index, pattern))
    normalized.sort(key=lambda item: item[0])
    return _preserve_unique([pattern for _, pattern in normalized])


def build_nontrans_discovery_batches(
    source_records: Sequence[SourceRecord],
    user_prompt_template: str,
    chunk_char_limit: int,
) -> List[Dict[str, object]]:
    effective_limit = max(200, int(chunk_char_limit or 200))
    batches: List[Dict[str, object]] = []
    current_items: List[Dict[str, object]] = []

    for record in source_records:
        payload = {
            "id": str(len(current_items) + 1),
            "record_id": record.record_id,
            "text": record.text,
        }
        candidate_items = current_items + [payload]
        candidate_prompt = user_prompt_template.format(items_json=_dump_json(candidate_items))
        if current_items and len(candidate_prompt) > effective_limit:
            batches.append(_finalize_nontrans_batch(current_items, user_prompt_template))
            current_items = [
                {
                    "id": "1",
                    "record_id": record.record_id,
                    "text": record.text,
                }
            ]
        else:
            current_items = candidate_items

    if current_items:
        batches.append(_finalize_nontrans_batch(current_items, user_prompt_template))
    return batches


def parse_nontrans_discovery_response(
    response: str,
    records_by_request_id: Dict[str, SourceRecord],
) -> Dict[str, object]:
    import json

    cleaned = clean_api_response(response)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        items = data.get("items")
    else:
        items = data
    if not isinstance(items, list):
        raise ValueError("非译元素发现响应缺少 items 数组。")

    resolved: List[NonTransElement] = []
    item_issues: Dict[str, List[str]] = {}
    batch_issues: List[str] = []
    seen_keys = set()

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            batch_issues.append("第 {0} 项不是 JSON 对象。".format(index))
            continue
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            batch_issues.append("第 {0} 项缺少 id。".format(index))
            continue
        record = records_by_request_id.get(item_id)
        if record is None:
            batch_issues.append("返回了未请求的 id：{0}".format(item_id))
            continue

        raw_elements = item.get("elements")
        if raw_elements is None:
            raw_elements = item.get("nontrans_elements")
        if raw_elements is None and item.get("element") is not None:
            raw_elements = [item]
        if raw_elements is None:
            raw_elements = []
        if not isinstance(raw_elements, list):
            item_issues.setdefault(item_id, []).append("elements 不是数组。")
            continue

        for element_index, raw_element in enumerate(raw_elements, start=1):
            if not isinstance(raw_element, dict):
                item_issues.setdefault(item_id, []).append("第 {0} 个元素不是 JSON 对象。".format(element_index))
                continue
            raw_element_text = raw_element.get("element", "")
            element = "" if raw_element_text is None else str(raw_element_text)
            element_type = str(raw_element.get("element_type", raw_element.get("category", "")) or "").strip()
            if not element:
                item_issues.setdefault(item_id, []).append("存在空的非译元素。")
                continue
            if element_type == "escape" and element not in record.text:
                if element in ESCAPE_EQUIVALENT_TEXTS and ESCAPE_EQUIVALENT_TEXTS[element] in record.text:
                    element = ESCAPE_EQUIVALENT_TEXTS[element]
                else:
                    for literal_escape, actual_text in ESCAPE_EQUIVALENT_TEXTS.items():
                        if element == actual_text and literal_escape in record.text:
                            element = literal_escape
                            break
            if element not in record.text:
                matched_variant = next(
                    (variant for variant in _normalized_nontrans_element_variants(element) if variant in record.text),
                    "",
                )
                if matched_variant:
                    element = matched_variant
            if element not in record.text:
                item_issues.setdefault(item_id, []).append("返回的非译元素不在原文中：{0}".format(element))
                continue
            if element_type not in ALLOWED_NONTRANS_ELEMENT_TYPES:
                item_issues.setdefault(item_id, []).append("非译元素类型不受支持：{0}".format(element_type or "空"))
                continue
            key = (element, element_type, record.record_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(
                NonTransElement(
                    element_id="{0}:nontrans:{1}".format(record.record_id, element),
                    element=element,
                    element_type=element_type,
                    source_record_ids=[record.record_id],
                    sample_contexts=[record.text],
                    occurrence_count=1,
                )
            )

    return {
        "resolved": resolved,
        "item_issues": item_issues,
        "batch_issues": batch_issues,
    }


def build_missing_regex_generation_batches(
    elements: Sequence[NonTransElement],
    user_prompt_template: str,
    chunk_char_limit: int,
) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    for index, element in enumerate(elements, start=1):
        items.append(
            {
                "id": str(index),
                "element": element.element,
                "element_type": element.element_type,
                "examples": _preserve_unique([element.element] + list(element.sample_contexts or []))[:3],
            }
        )
    if not items:
        return []
    return [_finalize_nontrans_batch(items, user_prompt_template)]


def parse_missing_regex_generation_response(
    response: str,
    elements_by_request_id: Dict[str, NonTransElement],
) -> Dict[str, object]:
    import json

    cleaned = clean_api_response(response)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        rules = data.get("rules") or data.get("items")
    else:
        rules = data
    if not isinstance(rules, list):
        raise ValueError("缺失正则生成响应缺少 rules 数组。")

    resolved: List[NonTransRegexRule] = []
    item_issues: Dict[str, List[str]] = {}
    batch_issues: List[str] = []
    seen_rule_ids = set()
    covered_request_ids = set()

    for index, item in enumerate(rules, start=1):
        if not isinstance(item, dict):
            batch_issues.append("第 {0} 项不是 JSON 对象".format(index))
            continue
        covered_ids_raw = item.get("covered_ids")
        if covered_ids_raw is None:
            fallback_id = str(item.get("id", "")).strip()
            covered_ids = [fallback_id] if fallback_id else []
        elif isinstance(covered_ids_raw, list):
            covered_ids = [str(value or "").strip() for value in covered_ids_raw if str(value or "").strip()]
        else:
            covered_ids = []
        if not covered_ids:
            batch_issues.append("第 {0} 项缺少 covered_ids".format(index))
            continue
        missing_ids = [item_id for item_id in covered_ids if item_id not in elements_by_request_id]
        if missing_ids:
            batch_issues.append("返回了未请求的 id：{0}".format(",".join(missing_ids)))
            continue
        duplicate_ids = [item_id for item_id in covered_ids if item_id in covered_request_ids]
        if duplicate_ids:
            batch_issues.append("同一个 id 被多条规则重复覆盖：{0}".format(",".join(duplicate_ids)))
            continue
        covered_elements = [elements_by_request_id[item_id] for item_id in covered_ids]
        for item_id in covered_ids:
            covered_request_ids.add(item_id)

        default_element_type = covered_elements[0].element_type if covered_elements else "other"
        element_type = str(item.get("element_type", item.get("category", default_element_type)) or "").strip()
        example_values = _preserve_unique(
            list(item.get("examples", []) or []) + [element.element for element in covered_elements]
        )[:3]
        primary_element = covered_elements[0]
        rule = NonTransRegexRule(
            rule_id=str(
                item.get("rule_id", "") or "ai_{0}_{1}".format(covered_ids[0], _safe_rule_token(primary_element.element))
            ),
            name=str(item.get("name", "") or "AI生成规则_{0}".format(covered_ids[0])),
            pattern=str(item.get("pattern", "") or ""),
            open_pattern=str(item.get("open_pattern", item.get("open", "")) or ""),
            close_pattern=str(item.get("close_pattern", item.get("close", "")) or ""),
            empty_pattern=str(item.get("empty_pattern", item.get("empty", "")) or ""),
            element_type=element_type,
            enabled=True,
            source="ai_generated",
            examples=example_values,
        )
        if not rule.pattern:
            role_patterns = [rule.open_pattern, rule.close_pattern, rule.empty_pattern]
            rule.pattern = next((pattern for pattern in role_patterns if str(pattern or "").strip()), "")
        if rule.rule_id in seen_rule_ids:
            for item_id in covered_ids:
                item_issues.setdefault(item_id, []).append("重复 rule_id：{0}".format(rule.rule_id))
            continue
        seen_rule_ids.add(rule.rule_id)
        issues = validate_nontrans_rule_minimal(rule)
        if issues:
            for item_id in covered_ids:
                item_issues.setdefault(item_id, []).extend(issues)
            continue
        resolved.append(rule)

    uncovered_ids = [item_id for item_id in elements_by_request_id.keys() if item_id not in covered_request_ids]
    if uncovered_ids:
        batch_issues.append("以下 id 没有被任何规则覆盖：{0}".format(",".join(uncovered_ids)))

    return {
        "resolved": resolved,
        "item_issues": item_issues,
        "batch_issues": batch_issues,
    }


def build_nontrans_reorder_payload(rows: Sequence[NonTransRegexRow]) -> List[Dict[str, object]]:
    payload = []
    for index, row in enumerate(rows, start=1):
        payload.append(
            {
                "id": "row_{0}".format(index),
                "regex": row.regex,
            }
        )
    return payload


def build_nontrans_reorder_prompt(rows: Sequence[NonTransRegexRow], user_prompt_template: str) -> str:
    return user_prompt_template.format(items_json=_dump_json(build_nontrans_reorder_payload(rows)))


def _resolve_nontrans_reorder_ids(ordered_ids: Sequence[object], rows: Sequence[NonTransRegexRow]) -> List[NonTransRegexRow]:
    expected_aliases = ["row_{0}".format(index) for index, _ in enumerate(rows, start=1)]
    alias_to_actual: Dict[str, str] = {}
    actual_to_row: Dict[str, NonTransRegexRow] = {}
    for index, row in enumerate(rows, start=1):
        alias = "row_{0}".format(index)
        actual_id = str(row.row_id or alias).strip() or alias
        alias_to_actual[alias] = actual_id
        alias_to_actual[actual_id] = actual_id
        actual_to_row[actual_id] = row

    normalized_ids = [str(item).strip() for item in ordered_ids if str(item).strip()]
    resolved_ids: List[str] = []
    unknown_ids: List[str] = []
    for item in normalized_ids:
        resolved = alias_to_actual.get(item)
        if resolved:
            resolved_ids.append(resolved)
        else:
            unknown_ids.append(item)

    duplicate_ids = sorted({item for item in resolved_ids if resolved_ids.count(item) > 1})
    if duplicate_ids:
        raise ValueError("正则排序响应包含重复 id：{0}".format("、".join(duplicate_ids)))

    missing_aliases = [alias for alias in expected_aliases if alias_to_actual[alias] not in resolved_ids]
    if missing_aliases or unknown_ids:
        details = []
        if missing_aliases:
            details.append("缺少 id：{0}".format("、".join(missing_aliases)))
        if unknown_ids:
            details.append("包含未请求 id：{0}".format("、".join(unknown_ids)))
        raise ValueError("正则排序响应未覆盖全部规则，{0}".format("；".join(details)))

    reordered: List[NonTransRegexRow] = []
    for index, row_id in enumerate(resolved_ids, start=1):
        row = NonTransRegexRow.from_dict(actual_to_row[row_id].to_dict())
        row.order_index = index
        reordered.append(row)
    return reordered


def apply_nontrans_reorder_response_v2(response: str, rows: Sequence[NonTransRegexRow]) -> List[NonTransRegexRow]:
    import json

    cleaned = clean_api_response(response)
    data = json.loads(cleaned)
    ordered_ids = data.get("ordered_ids") if isinstance(data, dict) else None
    if not isinstance(ordered_ids, list):
        raise ValueError("正则排序响应缺少 ordered_ids 数组。")
    return _resolve_nontrans_reorder_ids(ordered_ids, rows)


def apply_nontrans_reorder_response(response: str, rows: Sequence[NonTransRegexRow]) -> List[NonTransRegexRow]:
    return apply_nontrans_reorder_response_v2(response, rows)


def run_nontrans_regex_pipeline(
    source_records: Sequence[SourceRecord],
    ascii_candidate_patterns: object,
    ai_call: Callable[[str, str, Dict[str, object]], str],
    discovery_prompt_template: str,
    regex_prompt_template: str,
    reorder_prompt_template: str,
    chunk_char_limit: int = 3000,
    builtin_rules: Optional[Sequence[NonTransRegexRule]] = None,
    max_reorder_attempts: int = 3,
    builtin_regex_enabled: bool = True,
    ai_discovery_enabled: bool = True,
    ai_regex_generation_enabled: bool = True,
) -> Dict[str, object]:
    broad_patterns = normalize_ascii_candidate_patterns(ascii_candidate_patterns)
    candidate_records = filter_candidate_nontrans_records(source_records, broad_patterns)
    if ai_discovery_enabled:
        discovered_elements = _run_nontrans_discovery_batches(
            candidate_records,
            ai_call=ai_call,
            prompt_template=discovery_prompt_template,
            chunk_char_limit=chunk_char_limit,
        )
    else:
        discovered_elements = []
    merged_elements = _merge_nontrans_elements(discovered_elements)

    if builtin_regex_enabled:
        builtin_rows = deduplicate_nontrans_regex_rows(
            expand_nontrans_regex_rows(
                list(builtin_rules) if builtin_rules is not None else load_builtin_nontrans_rules()
            )
        )
    else:
        builtin_rows = []
    used_builtin_rows, missing_elements = collect_covering_rows_for_elements(builtin_rows, merged_elements)

    if ai_regex_generation_enabled:
        generated_rules = _run_missing_regex_generation_batches(
            missing_elements,
            ai_call=ai_call,
            prompt_template=regex_prompt_template,
            chunk_char_limit=chunk_char_limit,
        )
    else:
        generated_rules = []
    generated_rows = expand_nontrans_regex_rows(generated_rules)
    final_rows = deduplicate_nontrans_regex_rows(used_builtin_rows + generated_rows)
    unresolved_elements = list(merged_elements)
    if final_rows:
        order_result = resolve_nontrans_regex_order(final_rows, merged_elements)
        final_rows = list(order_result["ordered_rows"])
        unresolved_elements = list(order_result["unresolved_elements"])
    sheet_rows = build_nontrans_regex_sheet_rows(final_rows)
    return {
        "candidate_records": list(candidate_records),
        "elements": merged_elements,
        "missing_elements": unresolved_elements,
        "regex_rows": final_rows,
        "sheet_rows": sheet_rows,
        "stats": {
            "candidate_record_count": len(candidate_records),
            "element_count": len(merged_elements),
            "missing_element_count": len(unresolved_elements),
            "regex_row_count": len(final_rows),
        },
    }


def protect_nontrans_text(
    text: str,
    rows: Sequence[NonTransRegexRow],
    placeholder_format: str = DEFAULT_NONTRANS_PLACEHOLDER_FORMAT,
) -> ProtectedText:
    source = str(text or "")
    if not source:
        return ProtectedText(original_text=source, protected_text="", matches=[])
    placeholder_format = normalize_nontrans_placeholder_format(placeholder_format)

    accepted: List[Tuple[int, int, NonTransRegexRow, str]] = []
    occupied: List[Tuple[int, int]] = []
    for row in rows:
        try:
            compiled = re.compile(row.regex)
        except re.error:
            continue
        for match in compiled.finditer(source):
            start, end = match.span()
            if start == end or _overlaps_any(start, end, occupied):
                continue
            accepted.append((start, end, row, match.group(0)))
            occupied.append((start, end))

    accepted.sort(key=lambda item: (item[0], item[1]))
    protected_parts: List[str] = []
    matches: List[NonTransMatch] = []
    cursor = 0
    for index, (start, end, row, matched_text) in enumerate(accepted, start=1):
        placeholder = placeholder_format.format(n=index)
        protected_parts.append(source[cursor:start])
        protected_parts.append(placeholder)
        matches.append(
            NonTransMatch(
                placeholder=placeholder,
                text=matched_text,
                rule_id=row.rule_id,
                row_id=row.row_id,
                role=row.role,
                element_type=row.element_type,
                start=start,
                end=end,
            )
        )
        cursor = end
    protected_parts.append(source[cursor:])
    return ProtectedText(original_text=source, protected_text="".join(protected_parts), matches=matches)


def normalize_nontrans_placeholder_format(placeholder_format: str) -> str:
    value = str(placeholder_format or "").strip()
    if value.count("{n}") != 1:
        return DEFAULT_NONTRANS_PLACEHOLDER_FORMAT
    try:
        formatted = value.format(n=1)
    except (KeyError, IndexError, ValueError):
        return DEFAULT_NONTRANS_PLACEHOLDER_FORMAT
    if not formatted or "1" not in formatted:
        return DEFAULT_NONTRANS_PLACEHOLDER_FORMAT
    return value


def placeholder_pattern_from_format(placeholder_format: str) -> str:
    value = normalize_nontrans_placeholder_format(placeholder_format)
    prefix, suffix = value.split("{n}", 1)
    return "{0}\\d+{1}".format(re.escape(prefix), re.escape(suffix))


def build_term_recall_dedupe_key(protected_text: str, placeholder_pattern: str = r"<\d+>") -> str:
    cleaned = re.sub(placeholder_pattern, "", str(protected_text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def build_nontrans_regex_sheet_rows(rows: Sequence[NonTransRegexRow]) -> List[Dict[str, object]]:
    sheet_rows = []
    for index, row in enumerate(rows, start=1):
        sheet_rows.append(
            {
                "排序": index,
                "正则表达式": row.regex,
                "开始/结束/空": NONTRANS_ROLE_LABELS.get(row.role, row.role),
                "类型": NONTRANS_ELEMENT_TYPE_LABELS.get(row.element_type, row.element_type),
                "非译元素例子": "、".join(_preserve_unique(row.examples)[:8]),
            }
        )
    return [{column: item.get(column, "") for column in NONTRANS_REGEX_COLUMNS} for item in sheet_rows]


def attach_runtime_examples_to_nontrans_rows(
    rows: Sequence[NonTransRegexRow],
    source_records: Sequence[SourceRecord],
    max_examples_per_row: int = 8,
) -> List[NonTransRegexRow]:
    enriched_rows: List[NonTransRegexRow] = [NonTransRegexRow.from_dict(row.to_dict()) for row in rows]
    if not enriched_rows or not source_records:
        return enriched_rows

    limit = max(1, int(max_examples_per_row or 1))
    for row in enriched_rows:
        matched_samples: List[str] = []
        fallback_samples = _preserve_unique(list(row.examples or []))
        try:
            compiled = re.compile(row.regex)
        except re.error:
            row.examples = fallback_samples[:limit]
            continue

        for record in source_records:
            text = str(record.text or "")
            if not text:
                continue
            for match in compiled.finditer(text):
                matched_text = str(match.group(0) or "").strip()
                if not matched_text:
                    continue
                matched_samples.append(matched_text)
                matched_samples = _preserve_unique(matched_samples)
                if len(matched_samples) >= limit:
                    break
            if len(matched_samples) >= limit:
                break
        row.examples = (matched_samples or fallback_samples)[:limit]
    return enriched_rows


def _run_nontrans_discovery_batches(
    candidate_records: Sequence[SourceRecord],
    ai_call: Callable[[str, str, Dict[str, object]], str],
    prompt_template: str,
    chunk_char_limit: int,
) -> List[NonTransElement]:
    discovered: List[NonTransElement] = []
    batches = build_nontrans_discovery_batches(candidate_records, prompt_template, chunk_char_limit)
    records_by_id = {record.record_id: record for record in candidate_records}
    for batch_index, batch in enumerate(batches, start=1):
        request_records = {
            str(item["id"]): records_by_id[str(item["record_id"])]
            for item in list(batch.get("items", []) or [])
            if str(item.get("record_id", "")) in records_by_id
        }
        response = ai_call(
            "nontrans_discovery",
            str(batch.get("prompt", "")),
            {"batch_index": batch_index, "items": list(batch.get("items", []) or [])},
        )
        parsed = parse_nontrans_discovery_response(response, request_records)
        if parsed["batch_issues"] or parsed["item_issues"]:
            raise ValueError(
                "非译元素发现响应校验失败：{0}".format(
                    _format_nontrans_issues(parsed["batch_issues"], parsed["item_issues"])
                )
            )
        discovered.extend(parsed["resolved"])
    return discovered


def _run_missing_regex_generation_batches(
    missing_elements: Sequence[NonTransElement],
    ai_call: Callable[[str, str, Dict[str, object]], str],
    prompt_template: str,
    chunk_char_limit: int,
) -> List[NonTransRegexRule]:
    rules: List[NonTransRegexRule] = []
    batches = build_missing_regex_generation_batches(missing_elements, prompt_template, chunk_char_limit)
    for batch_index, batch in enumerate(batches, start=1):
        elements_by_request_id = {}
        for item in list(batch.get("items", []) or []):
            request_id = str(item.get("id", ""))
            element_text = str(item.get("element", ""))
            matched = next((element for element in missing_elements if element.element == element_text), None)
            if matched is not None:
                elements_by_request_id[request_id] = matched
        response = ai_call(
            "nontrans_regex_generation",
            str(batch.get("prompt", "")),
            {"batch_index": batch_index, "items": list(batch.get("items", []) or [])},
        )
        parsed = parse_missing_regex_generation_response(response, elements_by_request_id)
        if parsed["batch_issues"] or parsed["item_issues"]:
            raise ValueError(
                "非译元素正则生成响应校验失败：{0}".format(
                    _format_nontrans_issues(parsed["batch_issues"], parsed["item_issues"])
                )
            )
        rules.extend(parsed["resolved"])
    return rules


def _run_nontrans_reorder(
    rows: Sequence[NonTransRegexRow],
    ai_call: Callable[[str, str, Dict[str, object]], str],
    prompt_template: str,
    max_attempts: int,
) -> List[NonTransRegexRow]:
    last_error = ""
    for attempt in range(1, max(1, int(max_attempts or 1)) + 1):
        prompt = build_nontrans_reorder_prompt(rows, prompt_template)
        response = ai_call(
            "nontrans_reorder",
            prompt,
            {"attempt": attempt, "items": build_nontrans_reorder_payload(rows)},
        )
        try:
            return apply_nontrans_reorder_response(response, rows)
        except Exception as exc:
            last_error = str(exc)
    raise ValueError("非译元素正则排序失败，已重试 {0} 次：{1}".format(max_attempts, last_error))


def _merge_nontrans_elements(elements: Sequence[NonTransElement]) -> List[NonTransElement]:
    merged: "OrderedDict[Tuple[str, str], NonTransElement]" = OrderedDict()
    for element in elements:
        key = (element.element, element.element_type)
        existing = merged.get(key)
        if existing is None:
            merged[key] = NonTransElement.from_dict(element.to_dict())
            continue
        existing.source_record_ids = _preserve_unique(existing.source_record_ids + list(element.source_record_ids or []))
        existing.sample_contexts = _preserve_unique(existing.sample_contexts + list(element.sample_contexts or []))
        existing.occurrence_count += max(1, int(element.occurrence_count or 1))
    return list(merged.values())


def _format_nontrans_issues(batch_issues: object, item_issues: object) -> str:
    parts = []
    if batch_issues:
        parts.append("批次问题={0}".format(batch_issues))
    if item_issues:
        parts.append("条目问题={0}".format(item_issues))
    return "；".join(parts) or "未知问题"


def _rule_role_patterns(rule: NonTransRegexRule) -> List[Tuple[str, str]]:
    role_patterns = [
        ("open", rule.open_pattern),
        ("close", rule.close_pattern),
        ("empty", rule.empty_pattern),
    ]
    filtered = [(role, str(pattern).strip()) for role, pattern in role_patterns if str(pattern or "").strip()]
    if filtered:
        return filtered
    pattern = str(rule.pattern or "").strip()
    return [("empty", pattern)] if pattern else []


def _overlaps_any(start: int, end: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end in spans)


def _looks_like_dangerous_regex(pattern: str) -> bool:
    compact = re.sub(r"\\.", "", str(pattern or ""))
    return bool(re.search(r"\((?:[^()|]*[+*][^()]*)+\)[+*]", compact))


def _looks_like_overbroad_nontrans_regex(pattern: str) -> bool:
    pattern_text = str(pattern or "").strip()
    if not pattern_text:
        return False
    try:
        compiled = re.compile(pattern_text)
    except re.error:
        return False
    plain_samples = (
        "自动采集器",
        "暴击伤害提高",
        "前往活动页面领取奖励",
        "角色露娜造成火焰伤害",
    )
    return any(compiled.fullmatch(sample) for sample in plain_samples)


def _preserve_unique(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _dump_json(items: Sequence[Dict[str, object]]) -> str:
    import json

    return json.dumps(list(items), ensure_ascii=False, indent=2)


def _finalize_nontrans_batch(items: Sequence[Dict[str, object]], user_prompt_template: str) -> Dict[str, object]:
    item_list = [dict(item) for item in items]
    return {
        "items": item_list,
        "prompt": user_prompt_template.format(items_json=_dump_json(item_list)),
    }


def _safe_rule_token(text: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_").lower()
    if not token:
        token = "rule"
    return token[:40]
