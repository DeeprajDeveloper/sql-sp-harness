"""Transform stored procedures into debug-safe harness scripts."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlglot import exp

from sql_sp_harness.constants import (
    ALREADY_STUBBED,
    DELETE_FROM_CLAUSE,
    DELETE_TABLE_VAR,
    DML_START,
    EXEC_DYNAMIC,
    EXEC_START,
    INLINE_SET,
    INSERT_TABLE_VAR,
    INSERT_TARGET,
    LINE_INDENT,
    SELECT_ASSIGN,
    SET_NOCOUNT,
    SET_VAR_LINE,
    UPDATE_TABLE_VAR,
    UPDATE_TARGET,
)
from sql_sp_harness.comments import strip_sql_comments
from sql_sp_harness.dml_preview import build_dml_preview
from sql_sp_harness.exec_preview import build_exec_stub, find_exec_block_end
from sql_sp_harness.parse import parse_for_transform, suppress_sqlglot_warnings
from sql_sp_harness.script_prepare import prepare_for_transform
from sql_sp_harness.run_log import LogCallback, emit_log, truncate_for_log
from sql_sp_harness.t_sql_scan import find_dml_block_end


@dataclass
class TransformStats:
    dml_stubbed: int = 0
    exec_stubbed: int = 0
    traces_added: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class TransformResult:
    sql: str
    stats: TransformStats
    parse_errors: list[str] = field(default_factory=list)


ProgressCallback = Callable[[str], None]


def _emit_log(
    *,
    on_progress: ProgressCallback | None,
    on_log_info: LogCallback | None,
    function: str,
    message: str,
) -> None:
    if on_progress is not None:
        on_progress(message)
    emit_log(on_log_info, function, message)


def _is_table_variable_dml(first_line: str) -> bool:
    return bool(
        INSERT_TABLE_VAR.match(first_line)
        or UPDATE_TABLE_VAR.match(first_line)
        or DELETE_TABLE_VAR.match(first_line)
    )


def _find_dml_line_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return (start_line, end_line) inclusive for DML blocks."""
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if ALREADY_STUBBED.search(line):
            i += 1
            continue
        if not DML_START.match(line):
            i += 1
            continue
        if _is_table_variable_dml(line):
            i += 1
            continue
        start = i
        end = find_dml_block_end(lines, start)
        blocks.append((start, end))
        i = end + 1
    return blocks


def _find_exec_line_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return (start_line, end_line) inclusive for EXEC / EXECUTE blocks."""
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if ALREADY_STUBBED.search(line):
            i += 1
            continue
        if EXEC_DYNAMIC.match(line) or not EXEC_START.match(line):
            i += 1
            continue
        start = i
        end = find_exec_block_end(lines, start)
        blocks.append((start, end))
        i = end + 1
    return blocks


def _replace_exec_block(block_lines: list[str], indent: str) -> list[str]:
    preview = build_exec_stub(block_lines, indent)
    if preview is not None:
        return preview

    first = block_lines[0].strip()
    commented = "\n".join(f"{indent}-- {ln}" if ln.strip() else ln for ln in block_lines)
    return [
        f"{indent}/* [DBG-DISABLED] EXEC",
        commented,
        f"{indent}*/",
        f"{indent}PRINT N'[DBG-EXEC] Skipped unsupported EXEC statement';",
    ]


def _replace_dml_block(block_lines: list[str], indent: str) -> list[str]:
    preview = build_dml_preview(block_lines, indent)
    if preview is not None:
        return preview

    first = block_lines[0].strip()
    kind = first.split()[0].upper()
    target = _dml_target_label(first, kind)
    stub_msg = f"{indent}RAISERROR(N'[DBG] Skipped {kind} {target}', 0, 1) WITH NOWAIT;"
    commented = "\n".join(f"{indent}-- {ln}" if ln.strip() else ln for ln in block_lines)
    return [
        f"{indent}/* [DBG-DISABLED] {kind} {target}",
        commented,
        f"{indent}*/",
        stub_msg,
    ]


def _dml_target_label(first_line: str, kind: str) -> str:
    if kind == "INSERT":
        m = INSERT_TARGET.search(first_line)
        return m.group(1) if m else "table"
    if kind == "UPDATE":
        m = UPDATE_TARGET.search(first_line)
        return m.group(1) if m else "table"
    if kind == "DELETE":
        m = DELETE_FROM_CLAUSE.search(first_line)
        return m.group(1) if m else "table"
    return "statement"


def _trace_line_for_var(var_name: str, indent: str, style: str) -> str:
    cast_expr = f"CAST({var_name} AS NVARCHAR(4000))"
    if style == "print":
        return f"{indent}PRINT CONCAT(N'[DBG] {var_name} = ', {cast_expr});"
    return (
        f"{indent}RAISERROR(N'[DBG] {var_name} = %s', 0, 1, {cast_expr}) WITH NOWAIT;"
    )


def _inject_set_traces(
    text: str,
    trace_style: str,
    *,
    on_detail: LogCallback | None = None,
) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        var = match.group("var")
        stmt = match.group("stmt")
        if "NOCOUNT" in stmt.upper():
            emit_log(
                on_detail,
                "_inject_set_traces",
                f"  SET trace skipped (NOCOUNT): {truncate_for_log(stmt)}",
            )
            return match.group(0)
        if f"[DBG] {var}" in text[match.end() : match.end() + 120]:
            emit_log(on_detail, "_inject_set_traces", f"  SET trace skipped (already traced): {var}")
            return match.group(0)
        indent = "    "
        if match.group("prefix"):
            line_start = match.group("prefix").rfind("\n")
            prefix_tail = match.group("prefix")[line_start + 1 :] if line_start >= 0 else match.group("prefix")
            m = LINE_INDENT.match(prefix_tail)
            if m:
                indent = m.group(1) or indent
        trace = _trace_line_for_var(var, indent, trace_style)
        count += 1
        emit_log(
            on_detail,
            "_inject_set_traces",
            f"  SET trace added: {var} ({trace_style}) after {truncate_for_log(stmt)}",
        )
        emit_log(on_detail, "_inject_set_traces", f"    + {truncate_for_log(trace)}")
        return match.group(0) + "\n" + trace

    return INLINE_SET.sub(repl, text), count


def _inject_select_traces(
    text: str,
    trace_style: str,
    *,
    on_detail: LogCallback | None = None,
) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        stmt = match.group("stmt")
        if "@OrderQueue" in stmt and "FROM @" in stmt.upper():
            pass
        vars_ = _vars_from_select_assignments(stmt)
        if not vars_:
            return match.group(0)
        indent = "    "
        traces = "\n".join(_trace_line_for_var(v, indent, trace_style) for v in vars_)
        count += len(vars_)
        emit_log(
            on_detail,
            "_inject_select_traces",
            f"  SELECT @assign trace(s) added: {', '.join(vars_)} ({trace_style}) "
            f"after {truncate_for_log(stmt)}",
        )
        for trace_line in traces.splitlines():
            emit_log(on_detail, "_inject_select_traces", f"    + {truncate_for_log(trace_line)}")
        return match.group(0) + "\n" + traces

    return SELECT_ASSIGN.sub(repl, text), count


def _vars_from_set_line(line: str) -> list[str]:
    m = SET_VAR_LINE.match(line)
    if not m:
        return []
    if SET_NOCOUNT.match(line):
        return []
    return [m.group(2)]


def _vars_from_select_assignments(select_sql: str) -> list[str]:
    try:
        with suppress_sqlglot_warnings():
            tree = exp.parse_one(select_sql, read="tsql")
    except Exception:
        return []
    if not isinstance(tree, exp.Select):
        return []
    names: list[str] = []
    for expr in tree.expressions:
        if isinstance(expr, exp.EQ) and isinstance(expr.left, (exp.Var, exp.Parameter)):
            left = expr.left
            if isinstance(left, exp.Parameter) and isinstance(left.this, exp.Var):
                left = left.this
            if isinstance(left, exp.Var) and left.name.startswith("@"):
                names.append(left.name)
    return names


def _apply_line_edits(
    lines: list[str],
    *,
    trace_style: str,
    stub_dml: bool,
    add_block_markers: bool,
    on_progress: ProgressCallback | None = None,
    on_log_info: LogCallback | None = None,
    on_detail: LogCallback | None = None,
) -> tuple[list[str], TransformStats]:
    stats = TransformStats()

    if stub_dml:
        blocks = _find_dml_line_blocks(lines)
        if blocks:
            _emit_log(
                on_progress=on_progress,
                on_log_info=on_log_info,
                function="_apply_line_edits",
                message=f"Stubbing {len(blocks)} DML block(s) (INSERT/UPDATE/DELETE/MERGE)...",
            )
        for start, end in reversed(blocks):
            block = lines[start : end + 1]
            indent_match = LINE_INDENT.match(block[0])
            indent = indent_match.group(1) if indent_match else ""
            kind = block[0].strip().split()[0].upper()
            preview = " ".join(block[0].strip().split())[:100]
            _emit_log(
                on_progress=on_progress,
                on_log_info=on_log_info,
                function="_apply_line_edits",
                message=f"Stubbing {kind} lines {start + 1}-{end + 1}: {preview}",
            )
            replacement = _replace_dml_block(block, indent)
            preview_kind = "SELECT preview" if replacement and "[DBG-PREVIEW]" in replacement[0] else "disabled stub"
            _emit_log(
                on_progress=on_progress,
                on_log_info=on_log_info,
                function="_apply_line_edits",
                message=f"  -> {preview_kind} ({len(replacement)} line(s))",
            )
            emit_log(on_detail, "_apply_line_edits", f"  DML replacement ({preview_kind}):")
            for repl_line in replacement[:12]:
                emit_log(on_detail, "_apply_line_edits", f"    + {truncate_for_log(repl_line)}")
            if len(replacement) > 12:
                emit_log(
                    on_detail,
                    "_apply_line_edits",
                    f"    ... {len(replacement) - 12} more line(s)",
                )
            lines[start : end + 1] = replacement
            stats.dml_stubbed += 1

    exec_blocks = _find_exec_line_blocks(lines)
    if exec_blocks:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="_apply_line_edits",
            message=f"Stubbing {len(exec_blocks)} EXEC block(s)...",
        )
    for start, end in reversed(exec_blocks):
        block = lines[start : end + 1]
        indent_match = LINE_INDENT.match(block[0])
        indent = indent_match.group(1) if indent_match else ""
        preview = " ".join(block[0].strip().split())[:100]
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="_apply_line_edits",
            message=f"Stubbing EXEC lines {start + 1}-{end + 1}: {preview}",
        )
        replacement = _replace_exec_block(block, indent)
        emit_log(on_detail, "_apply_line_edits", "  EXEC replacement:")
        for repl_line in replacement[:12]:
            emit_log(on_detail, "_apply_line_edits", f"    + {truncate_for_log(repl_line)}")
        if len(replacement) > 12:
            emit_log(
                on_detail,
                "_apply_line_edits",
                f"    ... {len(replacement) - 12} more line(s)",
            )
        lines[start : end + 1] = replacement
        stats.exec_stubbed += 1

    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="_apply_line_edits",
        message="Injecting SET variable traces...",
    )
    text = "\n".join(lines)
    text, set_traces = _inject_set_traces(text, trace_style, on_detail=on_detail)
    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="_apply_line_edits",
        message=f"  -> added {set_traces} SET trace(s) (style={trace_style})",
    )
    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="_apply_line_edits",
        message="Injecting SELECT assignment traces...",
    )
    text, select_traces = _inject_select_traces(text, trace_style, on_detail=on_detail)
    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="_apply_line_edits",
        message=f"  -> added {select_traces} SELECT @assign trace(s)",
    )
    stats.traces_added += set_traces + select_traces
    lines = text.splitlines()

    if add_block_markers:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="_apply_line_edits",
            message="Adding IF/WHILE block markers...",
        )
        step = 0
        markers: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            stripped = line.strip().upper()
            if stripped.startswith("IF ") or stripped.startswith("WHILE "):
                step += 1
                indent = LINE_INDENT.match(line).group(1)  # type: ignore[union-attr]
                marker = f"{indent}-- [DBG] Step {step}: {line.strip()[:80]}"
                markers.append((idx, marker))
                stats.warnings.append(f"Block marker at step {step}")
                emit_log(
                    on_detail,
                    "_apply_line_edits",
                    f"  block marker step {step} before line {idx + 1}: {truncate_for_log(line)}",
                )
        for offset, (idx, marker) in enumerate(markers):
            lines.insert(idx + offset, marker)

    return lines, stats


def transform_sql(
    sql: str,
    *,
    trace_style: str = "print",
    stub_dml: bool = True,
    add_block_markers: bool = False,
    strip_comments: bool = True,
    on_progress: ProgressCallback | None = None,
    on_log_info: LogCallback | None = None,
    on_detail: LogCallback | None = None,
) -> TransformResult:
    """Produce a debug harness script from T-SQL source."""
    if strip_comments:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="transform_sql",
            message="Stripping comments from source...",
        )
        sql = strip_sql_comments(sql, on_detail=on_detail)
    else:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="transform_sql",
            message="Keeping original comments (--keep-comments)",
        )
        emit_log(on_detail, "transform_sql", "Comment strip skipped (--keep-comments)")

    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="transform_sql",
        message="Preparing script (remove deploy preamble, inline parameters)...",
    )
    sql = prepare_for_transform(sql, on_detail=on_detail)

    line_count = len(sql.splitlines())
    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="transform_sql",
        message=f"Transform started ({line_count} lines)...",
    )
    emit_log(
        on_detail,
        "transform_sql",
        f"Prepared source: {line_count} line(s), {len(sql)} character(s)",
    )

    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="transform_sql",
        message="Preparing source (strip GO, scan constructs)...",
    )
    parsed = parse_for_transform(sql, strip_preamble=False, on_detail=on_detail)
    stats = TransformStats(warnings=list(parsed.warnings))
    scan = parsed.scan
    if scan is not None:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="parse_for_transform",
            message=(
                f"Text scan: INSERT={scan.insert} UPDATE={scan.update} DELETE={scan.delete} "
                f"MERGE={scan.merge} TRY/CATCH={scan.try_catch_blocks}"
            ),
        )
    for warning in parsed.warnings:
        _emit_log(
            on_progress=on_progress,
            on_log_info=on_log_info,
            function="parse_for_transform",
            message=f"Warning: {warning}",
        )
        emit_log(on_detail, "parse_for_transform", f"Parse warning: {warning}")

    if not stub_dml:
        emit_log(on_detail, "transform_sql", "DML stubbing disabled (--no-stub-dml)")

    lines, line_stats = _apply_line_edits(
        parsed.source.splitlines(),
        trace_style=trace_style,
        stub_dml=stub_dml,
        add_block_markers=add_block_markers,
        on_progress=on_progress,
        on_log_info=on_log_info,
        on_detail=on_detail,
    )
    stats.dml_stubbed = line_stats.dml_stubbed
    stats.exec_stubbed = line_stats.exec_stubbed
    stats.traces_added = line_stats.traces_added
    stats.warnings.extend(line_stats.warnings)

    from sql_sp_harness.emit import debug_banner

    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="transform_sql",
        message="Writing debug harness banner...",
    )
    body = "\n".join(lines)
    if not body.endswith("\n") and sql.endswith("\n"):
        body += "\n"
    output = debug_banner([], stats) + body

    _emit_log(
        on_progress=on_progress,
        on_log_info=on_log_info,
        function="transform_sql",
        message=(
            f"Transform complete: {stats.dml_stubbed} DML stubbed, "
            f"{stats.exec_stubbed} EXEC stubbed, "
            f"{stats.traces_added} trace(s) added."
        ),
    )
    return TransformResult(sql=output, stats=stats, parse_errors=list(parsed.errors))
