"""Text-based T-SQL construct scanner for gaps sqlglot misses in the AST.

sqlglot often falls back to ``exp.Command`` fragments for TRY/CATCH and nested
blocks, which hides UPDATE and other DML from ``tree.find_all(...)``. This module
supplements the AST with comment-aware line scanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sql_sp_harness.comments import strip_block_comments_on_line
from sql_sp_harness.constants import (
    BEGIN_CATCH,
    BEGIN_TRY,
    DELETE_TABLE_VAR,
    DML_DELETE_CLAUSE,
    DML_INSERT_CONTINUATION,
    DML_INSERT_PAREN,
    DML_START,
    DML_UPDATE_CLAUSE,
    DML_UPDATE_COLUMN_SET,
    END_CATCH,
    END_TRY,
    INSERT_TABLE_VAR,
    NEW_STMT_AFTER_DML,
    SUMMARY_MAX_LEN,
    UPDATE_TABLE_VAR,
)


@dataclass
class DmlFinding:
    """A DML statement located by text scan."""

    kind: str
    start_line: int
    end_line: int
    text: str

    def summary(self, max_len: int = SUMMARY_MAX_LEN) -> str:
        one_line = " ".join(self.text.split())
        if len(one_line) > max_len:
            one_line = one_line[: max_len - 3] + "..."
        return f"L{self.start_line}: {one_line}"


@dataclass
class TryCatchFinding:
    """A TRY/CATCH block located by text scan."""

    index: int
    try_line: int
    end_try_line: int
    catch_line: int
    end_catch_line: int

    def summary(self) -> str:
        return (
            f"#{self.index} L{self.try_line}-L{self.end_catch_line}: "
            f"BEGIN TRY (L{self.try_line}) ... END CATCH (L{self.end_catch_line})"
        )


@dataclass
class TsqlScanResult:
    """Findings from text scanning (independent of sqlglot AST)."""

    insert: int = 0
    update: int = 0
    delete: int = 0
    merge: int = 0
    try_catch_blocks: int = 0
    begin_try: int = 0
    end_try: int = 0
    begin_catch: int = 0
    end_catch: int = 0
    dml_findings: list[DmlFinding] = field(default_factory=list)
    try_catch_findings: list[TryCatchFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _is_table_variable_dml(first_line: str) -> bool:
    return bool(
        INSERT_TABLE_VAR.match(first_line)
        or UPDATE_TABLE_VAR.match(first_line)
        or DELETE_TABLE_VAR.match(first_line)
    )


def _line_starts_new_statement(line: str, dml_kind: str) -> bool:
    """True when line begins a new statement after a multi-line DML block."""
    if not line.strip():
        return False
    if dml_kind in ("UPDATE", "MERGE"):
        if DML_UPDATE_COLUMN_SET.match(line):
            return False
        if DML_UPDATE_CLAUSE.match(line):
            return False
    if dml_kind == "INSERT":
        if DML_INSERT_CONTINUATION.match(line):
            return False
        if DML_INSERT_PAREN.match(line):
            return False
    if dml_kind == "DELETE":
        if DML_DELETE_CLAUSE.match(line):
            return False
    return bool(NEW_STMT_AFTER_DML.match(line))


def find_dml_block_end(lines: list[str], start: int) -> int:
    """Inclusive end line for a DML statement (semicolon optional)."""
    dml_kind = lines[start].strip().split()[0].upper()
    i = start
    while i < len(lines):
        if ";" in lines[i]:
            return i
        if i > start:
            if _line_starts_new_statement(lines[i], dml_kind):
                return i - 1
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _line_starts_new_statement(lines[j], dml_kind):
                return i
        if i == len(lines) - 1:
            return i
        i += 1
    return start


def _find_dml_statements(lines: list[str]) -> list[DmlFinding]:
    """Locate DML statements (same boundaries as transform stubbing)."""
    findings: list[DmlFinding] = []
    in_block_comment = False
    i = 0
    while i < len(lines):
        effective, in_block_comment = strip_block_comments_on_line(lines[i], in_block_comment)
        if not effective.strip():
            i += 1
            continue
        if not DML_START.match(effective):
            i += 1
            continue
        if _is_table_variable_dml(effective):
            i += 1
            continue

        start = i
        end = find_dml_block_end(lines, start)
        kind = effective.strip().split()[0].upper()
        findings.append(
            DmlFinding(
                kind=kind,
                start_line=start + 1,
                end_line=end + 1,
                text="\n".join(lines[start : end + 1]),
            )
        )
        i = end + 1
    return findings


def _try_catch_events(lines: list[str]) -> list[tuple[str, int]]:
    events: list[tuple[str, int]] = []
    in_block_comment = False
    for i, raw in enumerate(lines):
        effective, in_block_comment = strip_block_comments_on_line(raw, in_block_comment)
        if not effective.strip():
            continue
        line_no = i + 1
        if BEGIN_TRY.search(effective):
            events.append(("BEGIN TRY", line_no))
        if END_TRY.search(effective):
            events.append(("END TRY", line_no))
        if BEGIN_CATCH.search(effective):
            events.append(("BEGIN CATCH", line_no))
        if END_CATCH.search(effective):
            events.append(("END CATCH", line_no))
    return events


def _find_try_catch_blocks(lines: list[str]) -> list[TryCatchFinding]:
    events = _try_catch_events(lines)
    findings: list[TryCatchFinding] = []
    idx = 0
    pos = 0
    while pos < len(events):
        if events[pos][0] != "BEGIN TRY":
            pos += 1
            continue

        try_line = events[pos][1]
        end_try_line = catch_line = end_catch_line = 0
        pos += 1
        while pos < len(events) and events[pos][0] != "END TRY":
            pos += 1
        if pos >= len(events):
            break
        end_try_line = events[pos][1]
        pos += 1

        while pos < len(events) and events[pos][0] != "BEGIN CATCH":
            pos += 1
        if pos >= len(events):
            break
        catch_line = events[pos][1]
        pos += 1

        while pos < len(events) and events[pos][0] != "END CATCH":
            pos += 1
        if pos >= len(events):
            break
        end_catch_line = events[pos][1]
        pos += 1

        idx += 1
        findings.append(
            TryCatchFinding(
                index=idx,
                try_line=try_line,
                end_try_line=end_try_line,
                catch_line=catch_line,
                end_catch_line=end_catch_line,
            )
        )
    return findings


def _count_try_catch_keywords(lines: list[str]) -> tuple[int, int, int, int]:
    begin_try = end_try = begin_catch = end_catch = 0
    for kind, _line in _try_catch_events(lines):
        if kind == "BEGIN TRY":
            begin_try += 1
        elif kind == "END TRY":
            end_try += 1
        elif kind == "BEGIN CATCH":
            begin_catch += 1
        elif kind == "END CATCH":
            end_catch += 1
    return begin_try, end_try, begin_catch, end_catch


def scan_tsql(sql: str) -> TsqlScanResult:
    """Scan T-SQL source for constructs that sqlglot may omit from the AST."""
    lines = sql.splitlines()
    dml_findings = _find_dml_statements(lines)
    try_catch_findings = _find_try_catch_blocks(lines)
    begin_try, end_try, begin_catch, end_catch = _count_try_catch_keywords(lines)

    notes: list[str] = []
    if begin_try != end_try or begin_catch != end_catch:
        notes.append(
            "[ScanWarning] Unbalanced TRY/CATCH keywords "
            f"(BEGIN TRY={begin_try}, END TRY={end_try}, "
            f"BEGIN CATCH={begin_catch}, END CATCH={end_catch})."
        )

    insert = sum(1 for f in dml_findings if f.kind == "INSERT")
    update = sum(1 for f in dml_findings if f.kind == "UPDATE")
    delete = sum(1 for f in dml_findings if f.kind == "DELETE")
    merge = sum(1 for f in dml_findings if f.kind == "MERGE")

    return TsqlScanResult(
        insert=insert,
        update=update,
        delete=delete,
        merge=merge,
        try_catch_blocks=len(try_catch_findings),
        begin_try=begin_try,
        end_try=end_try,
        begin_catch=begin_catch,
        end_catch=end_catch,
        dml_findings=dml_findings,
        try_catch_findings=try_catch_findings,
        notes=notes,
    )
