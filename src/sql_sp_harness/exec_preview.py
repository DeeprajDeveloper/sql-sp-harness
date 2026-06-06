"""Replace EXEC stored-procedure calls with PRINT debug stubs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sql_sp_harness.constants import (
    EXEC_DYNAMIC,
    EXEC_PARAM_LINE,
    EXEC_START,
    NEW_STMT_AFTER_DML,
)


@dataclass
class ParsedExec:
    """Parsed EXEC / EXECUTE call."""

    proc_name: str
    return_var: str | None
    params: list[tuple[str, str]]
    command_sql: str


def _line_starts_new_statement(line: str) -> bool:
    return bool(NEW_STMT_AFTER_DML.match(line))


def _is_exec_continuation(line: str) -> bool:
    return bool(EXEC_PARAM_LINE.match(line))


def find_exec_block_end(lines: list[str], start: int) -> int:
    """Inclusive end line for an EXEC / EXECUTE block (semicolon optional)."""
    i = start
    while i < len(lines):
        if ";" in lines[i]:
            return i
        if i > start:
            if _line_starts_new_statement(lines[i]):
                return i - 1
            if not _is_exec_continuation(lines[i]):
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and _line_starts_new_statement(lines[j]):
                    return i
        if i == len(lines) - 1:
            return i
        i += 1
    return start


def _split_param_assignments(text: str) -> list[tuple[str, str]]:
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

    result: list[tuple[str, str]] = []
    for part in parts:
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        if not name.startswith("@"):
            name = "@" + name.lstrip("@")
        value = value.strip().rstrip(",")
        result.append((name, value))
    return result


def _normalize_proc_name(proc: str) -> str:
    return proc.rstrip(",;")


def parse_exec_block(block_lines: list[str]) -> ParsedExec | None:
    """Parse a text EXEC block into procedure name, parameters, and command SQL."""
    if not block_lines:
        return None
    if EXEC_DYNAMIC.match(block_lines[0]):
        return None

    first = block_lines[0].strip()
    match = EXEC_START.match(first)
    if not match:
        return None

    proc_name = _normalize_proc_name(match.group("proc"))
    if not proc_name or proc_name.lower() in ("sp_executesql",):
        return None

    return_var = match.group("ret")
    params = _split_param_assignments((match.group("rest") or "").strip())
    for line in block_lines[1:]:
        stripped = line.strip().rstrip(",")
        if stripped and _is_exec_continuation(line):
            params.extend(_split_param_assignments(stripped))

    if return_var:
        command_sql = f"EXEC {return_var} = {proc_name}"
    else:
        command_sql = f"EXEC {proc_name}"
    if params:
        param_sql = ", ".join(f"{name} = {value}" for name, value in params)
        command_sql = f"{command_sql} {param_sql}"

    return ParsedExec(
        proc_name=proc_name,
        return_var=return_var,
        params=params,
        command_sql=command_sql,
    )


def _param_value_print(name: str, value: str, indent: str) -> str:
    if re.match(r"^@\w+$", value, re.IGNORECASE):
        return (
            f"{indent}PRINT CONCAT(N'[DBG-EXEC] {name} = ', "
            f"CAST({value} AS NVARCHAR(4000)));"
        )
    return f"{indent}PRINT N'[DBG-EXEC] {name} = {value}';"


def build_exec_stub(block_lines: list[str], indent: str) -> list[str] | None:
    """Return PRINT lines replacing an EXEC block, or None if unsupported."""
    parsed = parse_exec_block(block_lines)
    if parsed is None:
        return None

    lines = [
        f"{indent}-- [DBG-EXEC] Would have executed stored procedure {parsed.proc_name}",
        f"{indent}PRINT N'[DBG-EXEC] Procedure: {parsed.proc_name}';",
        f"{indent}PRINT N'[DBG-EXEC] Command: {parsed.command_sql}';",
    ]
    if parsed.params:
        lines.append(f"{indent}PRINT N'[DBG-EXEC] Parameters:';")
        for name, value in parsed.params:
            lines.append(_param_value_print(name, value, indent))
    return lines
