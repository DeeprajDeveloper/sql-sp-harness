"""Tests for verbose comment-strip logging."""

from pathlib import Path

from conftest import sample_sql
from sql_sp_harness.comments import strip_sql_comments
from sql_sp_harness.run_log import RunLogger
from sql_sp_harness.transform import transform_sql


def test_strip_sql_comments_emits_detail(tmp_path: Path):
    log_path = tmp_path / "comments.log"
    logger = RunLogger(log_path)
    sql = "/* header */\nSELECT 1 -- tail\n\n"
    strip_sql_comments(sql, on_detail=logger.as_detail_callback())
    text = log_path.read_text(encoding="utf-8")
    assert "[strip_sql_comments] [DEBUG]" in text
    assert "Comment strip:" in text
    assert "line 1" in text
    assert "header" in text


def test_generate_log_captures_comment_and_prepare_detail(tmp_path: Path):
    log_path = tmp_path / "gen.log"
    logger = RunLogger(log_path)
    sql = sample_sql("simple_proc.sql").read_text(encoding="utf-8")
    transform_sql(
        sql,
        on_log_info=logger.as_info_callback(),
        on_detail=logger.as_detail_callback(),
    )
    text = log_path.read_text(encoding="utf-8")
    assert "[strip_sql_comments] [DEBUG]" in text
    assert "[prepare_for_transform]" in text or "[strip_deploy_preamble]" in text
    assert "[convert_create_procedure_to_declares]" in text or "[_inject_set_traces]" in text
