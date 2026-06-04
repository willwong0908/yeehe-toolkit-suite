from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime


def iso_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def iter_response_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("response_candidate_review*.json")):
        if path.is_file():
            yield path


def extract_rejected_terms(root: Path) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for path in iter_response_files(root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        timestamp = iso_timestamp(path)
        content = str(payload.get("content", "") or "").strip()
        if not content:
            continue
        try:
            data = json.loads(content)
        except Exception:
            continue
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("decision", "")).strip().lower() != "rejected":
                continue
            term = str(item.get("surface_form", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if not term:
                continue
            entry = grouped.get(term)
            if entry is None:
                grouped[term] = {
                    "term": term,
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "count": 1,
                    "reasons": [reason] if reason else [],
                    "source_files": [str(path)],
                }
                continue
            entry["count"] = int(entry["count"]) + 1
            entry["last_seen"] = timestamp
            if reason and reason not in entry["reasons"]:
                entry["reasons"].append(reason)
            if str(path) not in entry["source_files"]:
                entry["source_files"].append(str(path))
    return sorted(grouped.values(), key=lambda item: str(item["term"]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract unique rejected terms from task logs.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="output/task_logs",
        help="Task log directory or a single response file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/rejected_terms.json",
        help="Output file path (.json or .txt).",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    terms = extract_rejected_terms(input_path)
    if output_path.suffix.lower() == ".txt":
        lines = []
        for item in terms:
            reasons = " | ".join(item["reasons"])
            lines.append(
                "{term}\tfirst_seen={first_seen}\tlast_seen={last_seen}\tcount={count}\treasons={reasons}".format(
                    term=item["term"],
                    first_seen=item["first_seen"],
                    last_seen=item["last_seen"],
                    count=item["count"],
                    reasons=reasons,
                )
            )
        output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    else:
        output_path.write_text(json.dumps(terms, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("input={0}".format(input_path))
    print("output={0}".format(output_path))
    print("count={0}".format(len(terms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
