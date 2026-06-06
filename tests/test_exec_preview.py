"""Tests for EXEC stored-procedure stubbing."""

from conftest import sample_sql
from sql_sp_harness.exec_preview import (
    build_exec_stub,
    find_exec_block_end,
    parse_exec_block,
)
from sql_sp_harness.transform import transform_sql


def test_find_exec_block_end_multiline():
    lines = [
        "exec dbo.proc_name2",
        "    @fld1 = @fld1,",
        "    @fld2 = @fld2",
        "insert into t (a) values (1)",
    ]
    assert find_exec_block_end(lines, 0) == 2


def test_parse_exec_block_multiline():
    block = [
        "exec dbo.proc_name2",
        "    @fld1 = @fld1,",
        "    @fld2 = @fld2,",
        "    @fld3 = @fld3",
    ]
    parsed = parse_exec_block(block)
    assert parsed is not None
    assert parsed.proc_name == "dbo.proc_name2"
    assert parsed.params == [
        ("@fld1", "@fld1"),
        ("@fld2", "@fld2"),
        ("@fld3", "@fld3"),
    ]
    assert "EXEC dbo.proc_name2 @fld1 = @fld1" in parsed.command_sql
    assert "@fld3 = @fld3" in parsed.command_sql


def test_build_exec_stub_prints_procedure_command_and_params():
    block = [
        "exec dbo.proc_name2",
        "    @fld1 = @fld1,",
        "    @fld2 = @fld2",
    ]
    stub = build_exec_stub(block, "    ")
    assert stub is not None
    text = "\n".join(stub)
    assert "[DBG-EXEC] Would have executed stored procedure dbo.proc_name2" in text
    assert "PRINT N'[DBG-EXEC] Procedure: dbo.proc_name2';" in text
    assert "PRINT N'[DBG-EXEC] Command: EXEC dbo.proc_name2 @fld1 = @fld1, @fld2 = @fld2';" in text
    assert "PRINT CONCAT(N'[DBG-EXEC] @fld1 = ', CAST(@fld1 AS NVARCHAR(4000)));" in text


def test_transform_sample1_stubs_exec_and_preserves_error_checks():
    sql = sample_sql("sample1.sql").read_text(encoding="utf-8")
    result = transform_sql(sql)
    assert result.stats.exec_stubbed >= 1
    assert "[DBG-EXEC] Procedure: dbo.proc_name2" in result.sql
    assert "EXEC dbo.proc_name2 @fld1 = @fld1" in result.sql
    assert "@@rowcount" in result.sql
    assert "goto error_label" in result.sql.lower()
    assert "scope_identity()" in result.sql.lower()
    assert not any(
        ln.strip().lower().startswith("exec dbo.proc_name2")
        for ln in result.sql.splitlines()
    )
