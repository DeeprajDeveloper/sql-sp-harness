"""Tests for deploy preamble stripping and CREATE PROC -> DECLARE conversion."""

from pathlib import Path

from sql_sp_harness.inventory import inventory_from_sql
from sql_sp_harness.script_prepare import (
    convert_create_procedure_to_declares,
    strip_deploy_preamble,
)
from sql_sp_harness.transform import transform_sql

SAMPLES = Path(__file__).parents[1] / "samples"

PREAMBLE = """
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[p]') AND type IN (N'P', N'PC'))
    DROP PROCEDURE [dbo].[p];
GO

SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
"""


def test_strip_deploy_preamble():
    sql = PREAMBLE + "CREATE PROCEDURE dbo.p AS BEGIN SELECT 1 END\n"
    stripped = strip_deploy_preamble(sql)
    assert "IF EXISTS" not in stripped
    assert "DROP PROCEDURE" not in stripped
    assert "ANSI_NULLS" not in stripped
    assert "QUOTED_IDENTIFIER" not in stripped
    assert "CREATE PROCEDURE" in stripped


def test_convert_create_proc_to_declares():
    sql = """CREATE PROCEDURE dbo.usp_Test
    @BatchID INT,
    @DryRun BIT = 0
AS
BEGIN
    SET @BatchID = 1
END
"""
    out = convert_create_procedure_to_declares(sql)
    assert not out.lstrip().upper().startswith("CREATE PROC")
    assert "DECLARE @BatchID INT = NULL" in out
    assert "DECLARE @DryRun BIT = 0" in out
    assert "BEGIN" in out
    assert "[DBG] Harness: was CREATE PROCEDURE dbo.usp_Test" in out


def test_transform_enterprise_strips_preamble_and_inlines_params():
    sql = (SAMPLES / "enterprise_complex_proc.sql").read_text(encoding="utf-8")
    result = transform_sql(sql)
    assert "IF EXISTS" not in result.sql
    assert "SET ANSI_NULLS" not in result.sql
    assert "was CREATE PROCEDURE" in result.sql
    assert "\nCREATE PROCEDURE " not in result.sql
    assert "DECLARE @BatchID INT" in result.sql
    assert "DECLARE @DryRun BIT = 0" in result.sql
    assert "[DBG-PREVIEW]" in result.sql


def test_analyze_enterprise_ignores_preamble_dml():
    sql = (SAMPLES / "enterprise_complex_proc.sql").read_text(encoding="utf-8")
    inv = inventory_from_sql(sql)
    assert "DROP PROCEDURE" not in " ".join(inv.details.get("DELETE", []))


def test_strip_deploy_preamble_keeps_nested_if_exists_blocks():
    """In-procedure IF EXISTS (... ) BEGIN must not be treated as deploy preamble."""
    sql = (SAMPLES / "sample1.sql").read_text(encoding="utf-8")
    stripped = strip_deploy_preamble(sql)
    assert "jshdcbjsdhc" in stripped
    assert stripped.count("if exists") >= 2
    assert "DROP procedure [dbo].[usp_ComplexProcedureName]" not in stripped
    assert "create procedure" in stripped.lower()


def test_nested_multiline_if_exists_predicate_end():
    lines = [
        "if exists(",
        "    select 1 from dbo.t",
        ")",
        "begin",
        "    select 2",
        "end",
    ]
    from sql_sp_harness.script_prepare import _deploy_if_exists_drop_span

    assert _deploy_if_exists_drop_span(lines, 0) is None
