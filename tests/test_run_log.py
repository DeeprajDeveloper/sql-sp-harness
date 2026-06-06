"""Tests for step-by-step run logging."""

from pathlib import Path

from conftest import SAMPLES_SQL, sample_sql
from sql_sp_harness.run_log import RunLogger, resolve_log_path
from sql_sp_harness.transform import transform_sql


def test_resolve_log_path_explicit_file(tmp_path: Path):
    custom = tmp_path / "custom.log"
    assert resolve_log_path(SAMPLES_SQL / "my_proc.sql", log=False, log_file=custom) == custom


def test_resolve_log_path_default_stem():
    path = resolve_log_path(SAMPLES_SQL / "my_proc.sql", log=True, log_file=None)
    assert path == SAMPLES_SQL / "my_proc.log"


def test_log_line_format_includes_function_name(tmp_path: Path):
    log_path = tmp_path / "run.log"
    logger = RunLogger(log_path)
    logger.info("test_fn", "hello")
    logger.detail("other_fn", "detail msg")
    text = log_path.read_text(encoding="utf-8")
    assert "[test_fn] [INFO ] hello" in text
    assert "[other_fn] [DEBUG] detail msg" in text


def test_generate_writes_log_file(tmp_path: Path):
    sql = sample_sql("simple_proc.sql").read_text(encoding="utf-8")
    log_path = tmp_path / "run.log"
    logger = RunLogger(log_path)
    transform_sql(
        sql,
        on_log_info=logger.as_info_callback(),
        on_detail=logger.as_detail_callback(),
    )
    logger.info("test_generate_writes_log_file", "done")
    text = log_path.read_text(encoding="utf-8")
    assert "[transform_sql] [INFO ]" in text
    assert "[strip_sql_comments] [DEBUG]" in text
    assert "Stripping comments" in text or "Keeping original comments" in text
    assert "Stubbing" in text or "Injecting SET" in text
