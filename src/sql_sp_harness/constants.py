"""Shared regex patterns, byte markers, and numeric constants for T-SQL processing."""

from __future__ import annotations

import re

# --- Regex flag bundles ---
IGNORECASE = re.IGNORECASE
IGNORECASE_MULTILINE = re.IGNORECASE | re.MULTILINE
IGNORECASE_DOTALL = re.IGNORECASE | re.DOTALL

# --- File encoding (SSMS / Windows exports) ---
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
UTF8_BOM = b"\xef\xbb\xbf"

# --- Scan / inventory ---
SUMMARY_MAX_LEN = 120

# --- Batch separators ---
GO_PATTERN = re.compile(r"^\s*GO\s*(--.*)?$", IGNORECASE_MULTILINE)

# --- DML statement detection (line scan & transform) ---
DML_START = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", IGNORECASE)
INSERT_TABLE_VAR = re.compile(r"^\s*INSERT\s+INTO\s+@", IGNORECASE)
UPDATE_TABLE_VAR = re.compile(r"^\s*UPDATE\s+@", IGNORECASE)
DELETE_TABLE_VAR = re.compile(r"^\s*DELETE\s+FROM\s+@", IGNORECASE)

# --- DML / EXEC block boundary heuristics (semicolon-optional scripts) ---
NEW_STMT_AFTER_DML = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|MERGE|SET\s+@|BEGIN|END\b|DECLARE|SELECT\b|IF\b|WHILE\b|"
    r"PRINT\b|RETURN\b|THROW\b|RAISERROR\b|COMMIT\b|ROLLBACK\b|GOTO\b|EXEC\b|EXECUTE\b)",
    IGNORECASE,
)

# --- EXEC statement detection (transform stubbing) ---
EXEC_START = re.compile(
    r"^\s*(?:EXEC|EXECUTE)\s+(?:(?P<ret>@\w+)\s*=\s*)?(?P<proc>(?!\()[^\s;(]+)(?P<rest>.*)$",
    IGNORECASE,
)
EXEC_PARAM_LINE = re.compile(r"^\s*@?\w+\s*=", IGNORECASE)
EXEC_DYNAMIC = re.compile(r"^\s*(?:EXEC|EXECUTE)\s*\(", IGNORECASE)
DML_UPDATE_COLUMN_SET = re.compile(r"^\s+SET\s+(?!@)", IGNORECASE)
DML_UPDATE_CLAUSE = re.compile(r"^\s+(FROM|WHERE|JOIN|INNER|LEFT|RIGHT|FULL|CROSS|OUTPUT)\b", IGNORECASE)
DML_INSERT_CONTINUATION = re.compile(r"^\s+(VALUES|SELECT|DEFAULT)\b", IGNORECASE)
DML_INSERT_PAREN = re.compile(r"^\s*\(", IGNORECASE)
DML_DELETE_CLAUSE = re.compile(r"^\s+(FROM|WHERE|JOIN|OUTPUT)\b", IGNORECASE)

# --- DML target extraction (inventory, transform labels) ---
INSERT_TARGET = re.compile(r"INSERT\s+INTO\s+(\S+)", IGNORECASE)
UPDATE_TARGET = re.compile(r"UPDATE\s+(\S+)", IGNORECASE)
DELETE_TARGET = re.compile(r"DELETE\s+FROM\s+(\S+)", IGNORECASE)
MERGE_TARGET = re.compile(r"MERGE\s+(\S+)", IGNORECASE)
DELETE_FROM_CLAUSE = re.compile(r"FROM\s+(\S+)", IGNORECASE)

# --- TRY/CATCH keywords ---
BEGIN_TRY = re.compile(r"\bBEGIN\s+TRY\b", IGNORECASE)
END_TRY = re.compile(r"\bEND\s+TRY\b", IGNORECASE)
BEGIN_CATCH = re.compile(r"\bBEGIN\s+CATCH\b", IGNORECASE)
END_CATCH = re.compile(r"\bEND\s+CATCH\b", IGNORECASE)

# --- Transform / harness output ---
INLINE_SET = re.compile(r"(?P<indent>^|\n)(?P<prefix>.*?)(?P<stmt>SET\s+(?P<var>@\w+)\s*=[^\n;]+(?:;)?)", IGNORECASE_DOTALL)
SELECT_ASSIGN = re.compile(r"(?P<stmt>SELECT\s+[^;]*@\w+\s*=[^;]+;)", IGNORECASE_DOTALL)
SET_VAR_LINE = re.compile(r"^(\s*)SET\s+(@\w+)\s*=", IGNORECASE)
SET_NOCOUNT = re.compile(r"^\s*SET\s+NOCOUNT\b", IGNORECASE)
ALREADY_STUBBED = re.compile(
    r"\[DBG-PREVIEW\]|\[DBG-DISABLED\]|\[DBG-EXEC\]|\[DBG\]\s+Skipped",
    IGNORECASE,
)
LINE_INDENT = re.compile(r"^(\s*)")

# --- DML SELECT preview (dml_preview) ---
CLAUSE_FROM = re.compile(r"\bFROM\b", IGNORECASE)
CLAUSE_WHERE = re.compile(r"\bWHERE\b", IGNORECASE)
CLAUSE_SET = re.compile(r"\bSET\b", IGNORECASE)
INSERT_INTO_LINE = re.compile(r"^\s*INSERT\s+INTO\s+(\S+)", IGNORECASE)
DELETE_FROM_LINE = re.compile(r"^\s*DELETE\s+FROM\s+(\S+)(?:\s+WHERE\s+(.+))?\s*;?\s*$", IGNORECASE_DOTALL)
BARE_VAR = re.compile(r"^@\w+$", IGNORECASE)
QUOTED_LITERAL = re.compile(r"^(N?'([^']|'')*'|\d+(\.\d+)?)$", IGNORECASE)

# --- Inventory detail parsing ---
DETAIL_LINE_PREFIX = re.compile(r"^L(\d+):")
DETAIL_LINE_STRIP = re.compile(r"^L\d+:\s*")
DETAIL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

CALCULATION_PATTERN = re.compile(r"[\+\-\*/%]|^\w+\(", IGNORECASE)

IF_EXISTS = re.compile(r"^\s*IF\s+EXISTS\b", IGNORECASE)
DROP_PROCEDURE = re.compile(r"\bDROP\s+PROC(?:EDURE)?\b", IGNORECASE)
SET_ANSI_NULLS = re.compile(r"^\s*SET\s+ANSI_NULLS\b", IGNORECASE)
SET_QUOTED_IDENTIFIER = re.compile(r"^\s*SET\s+QUOTED_IDENTIFIER\b", IGNORECASE)
STANDALONE_DROP_PROC = re.compile(r"^\s*DROP\s+PROC(?:EDURE)?\b", IGNORECASE)
CREATE_PROC = re.compile(
    r"^\s*CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+(\S+)",
    IGNORECASE,
)
CREATE_PROC_INLINE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+(\S+)\s+(.+)$",
    IGNORECASE,
)
AS_LINE = re.compile(r"^\s*AS\s*(?:BEGIN)?\s*;?\s*$", IGNORECASE)
PROC_PARAM_WITH_DEFAULT = re.compile(r"^(@\w+)\s+(.+)\s+=\s*(.+)$", IGNORECASE)
PROC_PARAM_PLAIN = re.compile(r"^(@\w+)\s+(.+)$", IGNORECASE)
AS_BEGIN_REST = re.compile(r"^\s*AS\s+BEGIN\s*(.*)$", IGNORECASE)


APP_HELP = """
Turn a T-SQL stored procedure into a safe, runnable debug script.

\b
Commands:
  analyze    See what a stored procedure does (DML, TRY/CATCH, loops, variables)
  generate   Create a debug harness (DML previews, EXEC PRINT stubs, variable traces)

\b
Quick start:
  sql-sp-harness analyze -i MyProc.sql
  sql-sp-harness generate -i MyProc.sql -o MyProc_debug.sql

\b
More help:
  sql-sp-harness analyze --help
  sql-sp-harness generate --help
"""

