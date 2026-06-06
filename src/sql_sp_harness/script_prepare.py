"""Normalize SSMS-style deploy scripts for analysis and debug harness generation."""

from __future__ import annotations

import re

from sql_sp_harness.constants import (
    CREATE_PROC,
    CREATE_PROC_INLINE,
    AS_LINE,
    PROC_PARAM_WITH_DEFAULT,
    PROC_PARAM_PLAIN,
    AS_BEGIN_REST,
    IF_EXISTS,
    DROP_PROCEDURE,
    SET_ANSI_NULLS,
    SET_QUOTED_IDENTIFIER,
    STANDALONE_DROP_PROC,
    IGNORECASE,
)
from sql_sp_harness.run_log import LogCallback, emit_log, truncate_for_log

_EXISTS_OPEN = re.compile(r"\bEXISTS\s*\(", IGNORECASE)


def _scan_paren_block_end_line(lines: list[str], start_line: int, open_paren_col: int) -> int:
    """Return line index where parenthesis depth opened at ``open_paren_col`` returns to zero."""
    depth = 0
    for line_idx in range(start_line, len(lines)):
        line = lines[line_idx]
        col = open_paren_col if line_idx == start_line else 0
        in_string = False
        while col < len(line):
            ch = line[col]
            if ch == "'":
                if in_string and col + 1 < len(line) and line[col + 1] == "'":
                    col += 2
                    continue
                in_string = not in_string
                col += 1
                continue
            if not in_string:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        return line_idx
            col += 1
    return start_line


def _deploy_if_exists_drop_span(lines: list[str], start: int) -> tuple[int, int] | None:
    """
    If ``lines[start]`` is SSMS deploy ``IF EXISTS (...) DROP PROC``, return [start, end) line span.

    In-procedure ``IF EXISTS (SELECT ... FROM user_table ...)`` is followed by BEGIN, not DROP.
    """
    if start >= len(lines) or not IF_EXISTS.match(lines[start]):
        return None
    open_match = _EXISTS_OPEN.search(lines[start])
    if not open_match:
        return None
    close_line = _scan_paren_block_end_line(lines, start, open_match.end() - 1)
    scan = close_line + 1
    while scan < len(lines) and not lines[scan].strip():
        scan += 1
    if scan >= len(lines) or not DROP_PROCEDURE.search(lines[scan]):
        return None
    return start, scan + 1


def _split_param_list(text: str) -> list[str]:
    """Split a parameter list on commas (parenthesis-aware)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def strip_deploy_preamble(sql: str, *, on_detail: LogCallback | None = None) -> str:
    """Remove IF EXISTS/DROP PROCEDURE and SET ANSI_NULLS / QUOTED_IDENTIFIER setup."""
    had_trailing_newline = sql.endswith("\n")
    lines = sql.splitlines()
    kept: list[str] = []
    removed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        line_no = i + 1
        deploy_span = _deploy_if_exists_drop_span(lines, i)
        if deploy_span is not None:
            start, end = deploy_span
            for drop_idx in range(start, end):
                emit_log(
                    on_detail,
                    "strip_deploy_preamble",
                    f"  preamble line {drop_idx + 1}: removed deploy IF EXISTS/DROP: "
                    f"{truncate_for_log(lines[drop_idx])}",
                )
                removed += 1
            i = end
            continue
        if STANDALONE_DROP_PROC.match(line):
            emit_log(
                on_detail,
                "strip_deploy_preamble",
                f"  preamble line {line_no}: removed standalone DROP PROCEDURE: "
                f"{truncate_for_log(line)}",
            )
            i += 1
            removed += 1
            continue
        if SET_ANSI_NULLS.match(line) or SET_QUOTED_IDENTIFIER.match(line):
            emit_log(
                on_detail,
                "strip_deploy_preamble",
                f"  preamble line {line_no}: removed SET option: {truncate_for_log(line)}",
            )
            i += 1
            removed += 1
            continue
        kept.append(line)
        i += 1
    emit_log(
        on_detail,
        "strip_deploy_preamble",
        f"Deploy preamble: removed {removed} line(s), kept {len(kept)} line(s)",
    )
    if not kept:
        return "\n" if had_trailing_newline else ""
    body = "\n".join(kept)
    return body + "\n" if had_trailing_newline else body


def _parse_parameter_chunks(chunks: list[str]) -> list[tuple[str, str, str | None]]:
    """Return (@name, type_sql, default_expr|None) from comma-split param chunks."""
    params: list[tuple[str, str, str | None]] = []
    for chunk in chunks:
        text = chunk.strip().rstrip(",").strip()
        if not text or not text.startswith("@"):
            continue
        match = PROC_PARAM_WITH_DEFAULT.match(text)
        if match:
            params.append(
                (match.group(1), match.group(2).strip(), match.group(3).strip())
            )
            continue
        match = PROC_PARAM_PLAIN.match(text)
        if match:
            params.append((match.group(1), match.group(2).strip(), None))
    return params


def _declare_lines_for_params(
    proc_name: str,
    params: list[tuple[str, str, str | None]],
    indent: str,
) -> list[str]:
    header = (
        f"{indent}-- [DBG] Harness: was CREATE PROCEDURE {proc_name}; set parameter values below."
    )
    if not params:
        return [header, f"{indent}-- (no parameters)"]
    lines = [header]
    for name, type_sql, default in params:
        if default:
            lines.append(f"{indent}DECLARE {name} {type_sql} = {default};")
        else:
            lines.append(
                f"{indent}DECLARE {name} {type_sql} = NULL;  -- TODO: set test value"
            )
    return lines


def _split_create_tail(tail: str) -> tuple[str, bool]:
    """Split ``@params... AS [BEGIN]`` tail into param text and whether BEGIN follows."""
    match = re.search(r"\s+AS(?:\s+BEGIN)?\s*$", tail, re.IGNORECASE)
    if not match:
        return tail.strip(), False
    param_text = tail[: match.start()].strip()
    has_begin = "BEGIN" in match.group(0).upper()
    return param_text, has_begin


def convert_create_procedure_to_declares(
    sql: str,
    *,
    on_detail: LogCallback | None = None,
) -> str:
    """Replace CREATE PROCEDURE header with DECLARE parameters (debug script, no CREATE)."""
    lines = sql.splitlines()
    out: list[str] = []
    i = 0
    conversions = 0
    while i < len(lines):
        line = lines[i]
        head = CREATE_PROC.match(line)
        if not head:
            out.append(line)
            i += 1
            continue

        proc_name = head.group(1)
        line_no = i + 1
        indent_match = re.match(r"^(\s*)", line)
        indent = indent_match.group(1) if indent_match else ""

        inline = CREATE_PROC_INLINE.match(line)
        param_chunks: list[str] = []
        as_has_begin = False

        body_suffix = ""
        if inline and inline.group(2).strip():
            tail = inline.group(2).strip()
            begin_rest = AS_BEGIN_REST.match(tail)
            if begin_rest:
                as_has_begin = True
                body_suffix = begin_rest.group(1).strip()
                param_text = ""
            else:
                param_text, as_has_begin = _split_create_tail(tail)
                if param_text:
                    param_chunks = _split_param_list(param_text)
            i += 1
        else:
            i += 1
            param_parts: list[str] = []
            while i < len(lines):
                if AS_LINE.match(lines[i]):
                    as_has_begin = bool(re.search(r"\bBEGIN\b", lines[i], re.IGNORECASE))
                    i += 1
                    break
                param_parts.append(lines[i].strip())
                i += 1
            param_chunks = _split_param_list(" ".join(param_parts))

        params = _parse_parameter_chunks(param_chunks)
        declare_lines = _declare_lines_for_params(proc_name, params, indent)
        emit_log(
            on_detail,
            "convert_create_procedure_to_declares",
            f"  line {line_no}: CREATE PROCEDURE {proc_name} -> "
            f"{len(params)} parameter DECLARE(s), as_begin={as_has_begin}",
        )
        for decl in declare_lines:
            emit_log(
                on_detail,
                "convert_create_procedure_to_declares",
                f"    + {truncate_for_log(decl)}",
            )
        out.extend(declare_lines)
        conversions += 1

        if as_has_begin:
            out.append(f"{indent}BEGIN")
            if body_suffix:
                out.append(f"{indent}{body_suffix}" if indent else body_suffix)
        elif i < len(lines) and lines[i].strip().upper() == "BEGIN":
            out.append(lines[i])
            i += 1
        continue

    emit_log(
        on_detail,
        "convert_create_procedure_to_declares",
        f"CREATE PROC conversion: {conversions} procedure header(s) inlined",
    )
    return "\n".join(out)


def prepare_for_analysis(
    sql: str,
    *,
    strip_preamble: bool = True,
    on_detail: LogCallback | None = None,
) -> str:
    if strip_preamble:
        emit_log(
            on_detail,
            "prepare_for_analysis",
            "stripping deploy preamble",
        )
        sql = strip_deploy_preamble(sql, on_detail=on_detail)
    return sql


def prepare_for_transform(
    sql: str,
    *,
    strip_preamble: bool = True,
    inline_proc_params: bool = True,
    on_detail: LogCallback | None = None,
) -> str:
    if strip_preamble:
        emit_log(on_detail, "prepare_for_transform", "stripping deploy preamble")
        sql = strip_deploy_preamble(sql, on_detail=on_detail)
    if inline_proc_params:
        emit_log(
            on_detail,
            "prepare_for_transform",
            "converting CREATE PROCEDURE to DECLARE",
        )
        sql = convert_create_procedure_to_declares(sql, on_detail=on_detail)
    return sql
