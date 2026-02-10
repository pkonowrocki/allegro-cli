from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any


def _to_serializable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


def output_json(data: Any, file=None) -> None:
    file = file or sys.stdout
    json.dump(_to_serializable(data), file, indent=2, ensure_ascii=False)
    print(file=file)


def output_error(errors: list[dict], file=None) -> None:
    file = file or sys.stderr
    json.dump({"errors": errors}, file, indent=2, ensure_ascii=False)
    print(file=file)


def make_error(
    message: str,
    code: str,
    details: str | None = None,
    path: str | None = None,
    userMessage: str | None = None,
) -> dict:
    return {
        "message": message,
        "code": code,
        "details": details,
        "path": path,
        "userMessage": userMessage or message,
    }


def _get_nested(d: dict, key: str) -> str:
    parts = key.split(".")
    val: Any = d
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p, "")
        else:
            return ""
    if val is None:
        return ""
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def output_text(rows: list[dict], columns: list[str], file=None) -> None:
    file = file or sys.stdout
    if not rows:
        print("(no results)", file=file)
        return

    # compute column widths
    widths = {col: len(col) for col in columns}
    str_rows = []
    for row in rows:
        sr = {col: _get_nested(row, col) for col in columns}
        for col in columns:
            widths[col] = max(widths[col], len(sr[col]))
        str_rows.append(sr)

    # header
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    print(header, file=file)
    print("  ".join("-" * widths[col] for col in columns), file=file)

    # rows
    for sr in str_rows:
        line = "  ".join(sr[col].ljust(widths[col]) for col in columns)
        print(line, file=file)


def output_tsv(rows: list[dict], columns: list[str], file=None) -> None:
    file = file or sys.stdout
    if not rows:
        return
    print("\t".join(columns), file=file)
    for row in rows:
        print("\t".join(_get_nested(row, col) for col in columns), file=file)
