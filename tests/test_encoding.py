"""Tests for SQL file encoding detection."""

from conftest import sample_sql
from sql_sp_harness.encoding import decode_sql_bytes, read_sql_file


def test_decode_utf8():
    data = b"CREATE PROC dbo.p AS BEGIN SELECT 1; END"
    text, enc = decode_sql_bytes(data)
    assert enc == "utf-8"
    assert "CREATE PROC" in text


def test_decode_utf16_le_bom_ssms_unicode():
    data = "SELECT 1".encode("utf-16-le")
    data = b"\xff\xfe" + data
    text, enc = decode_sql_bytes(data)
    assert enc == "utf-16-le"
    assert "SELECT 1" in text


def test_decode_cp1252_en_dash_byte_96():
    # 0x96 is en-dash in Windows-1252; invalid as standalone UTF-8 start byte.
    data = b"-- status: settled \x96 done\r\nCREATE PROC dbo.p AS BEGIN END"
    text, enc = decode_sql_bytes(data)
    assert enc == "cp1252"
    assert "CREATE PROC" in text
    assert "\x96" not in text


def test_read_sql_file_explicit_encoding(tmp_path: Path):
    path = tmp_path / "proc.sql"
    path.write_bytes("CREATE PROC dbo.p AS BEGIN END".encode("utf-16-le"))
    text, detected = read_sql_file(path, encoding="utf-16-le")
    assert "CREATE PROC" in text
    assert detected is None


def test_read_sql_file_auto_utf16(tmp_path: Path):
    path = tmp_path / "proc.sql"
    path.write_bytes(b"\xff\xfe" + "CREATE PROC dbo.p AS BEGIN END".encode("utf-16-le"))
    text, detected = read_sql_file(path)
    assert "CREATE PROC" in text
    assert detected == "utf-16-le"


def test_read_utf8_sample():
    text, detected = read_sql_file(sample_sql("my_proc.sql"))
    assert "usp_ProcessEmployeeBonus" in text
    assert detected is None
