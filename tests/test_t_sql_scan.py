"""Tests for text-based T-SQL scanning (sqlglot gap filler)."""

from conftest import sample_sql
from sql_sp_harness.t_sql_scan import scan_tsql
from sql_sp_harness.inventory import inventory_from_sql


def test_scan_my_proc_finds_update_and_try_catch():
    sql = sample_sql("my_proc.sql").read_text(encoding="utf-8")
    scan = scan_tsql(sql)
    assert scan.update == 1
    assert scan.insert == 1
    assert scan.try_catch_blocks == 1
    assert scan.begin_try == 1
    assert scan.begin_catch == 1
    assert len(scan.dml_findings) == 2
    assert any("dbo.AuditLog" in f.text for f in scan.dml_findings if f.kind == "INSERT")
    assert any("dbo.Employees" in f.text for f in scan.dml_findings if f.kind == "UPDATE")
    try_line = scan.try_catch_findings[0].try_line
    assert sql.splitlines()[try_line - 1].strip().upper().startswith("BEGIN TRY")


def test_scan_my_proc_2_finds_all_updates_and_try_catch():
    sql = sample_sql("my_proc_2.sql").read_text(encoding="utf-8")
    scan = scan_tsql(sql)
    assert scan.update == 3
    assert scan.try_catch_blocks == 1
    # Table-variable insert should not count as table DML.
    assert scan.insert == 1


def test_inventory_merges_scan_update_when_ast_misses():
    sql = sample_sql("my_proc.sql").read_text(encoding="utf-8")
    inv = inventory_from_sql(sql)
    assert inv.update == 1
    assert inv.update == 1
    assert inv.try_catch_blocks == 1
    assert inv.insert == 1
    assert "dbo.AuditLog" in " ".join(inv.details.get("INSERT", []))
    assert "dbo.Employees" in " ".join(inv.details.get("UPDATE", []))
    assert inv.details.get("TRY/CATCH blocks")


def test_inventory_report_shows_statement_details():
    sql = sample_sql("my_proc.sql").read_text(encoding="utf-8")
    text = inventory_from_sql(sql).to_text(non_zero_only=True)
    assert "dbo.AuditLog" in text
    assert "dbo.Employees" in text
    assert "BEGIN TRY" in text


def test_my_proc_2_identified_lists_all_inserts():
    sql = sample_sql("my_proc_2.sql").read_text(encoding="utf-8")
    inv = inventory_from_sql(sql)
    assert inv.insert == 2
    inserts = inv.details.get("INSERT", [])
    assert len(inserts) == 2
    assert any("@OrderQueue" in item for item in inserts)
    assert any("ErrorLog" in item for item in inserts)


def test_scan_skips_table_variable_dml():
    sql = """
    INSERT INTO @t (a) VALUES (1);
    UPDATE @t SET a = 2;
  DELETE FROM @t;
    """
    scan = scan_tsql(sql)
    assert scan.insert == 0
    assert scan.update == 0
    assert scan.delete == 0
