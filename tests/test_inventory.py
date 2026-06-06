"""Tests for inventory pass."""

from conftest import sample_sql
from sql_sp_harness.inventory import inventory_from_sql


def test_simple_proc_inventory_parses():
    sql = sample_sql("simple_proc.sql").read_text(encoding="utf-8")
    inv = inventory_from_sql(sql)
    assert inv.is_parsable
    assert inv.insert >= 1
    assert inv.set_variable >= 2


def test_loop_proc_inventory():
    sql = sample_sql("loop_with_update.sql").read_text(encoding="utf-8")
    inv = inventory_from_sql(sql)
    assert inv.is_parsable
    assert inv.while_count >= 1
    assert inv.set_variable >= 5
