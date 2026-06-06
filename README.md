<p align="center">
  <img
    src="https://raw.githubusercontent.com/DeeprajDeveloper/sql-sp-harness/master/docs/images/BANNER.png"
    alt="sql-sp-harness"
  >
</p>

[![PyPI version](https://badge.fury.io/py/sql-sp-harness.svg)](https://badge.fury.io/py/sql-sp-harness)
[![Python 3.10|3.12|3.13](https://img.shields.io/badge/python-3.10&nbsp;|&nbsp;3.12&nbsp;|&nbsp;3.13-blue.svg)](https://github.com/DeeprajDeveloper/sql-sp-harness)

# sql-sp-harness

**T-SQL Stored Procedure Debug Harness** — turn SQL Server stored procedures into **safe, runnable debug scripts** you can execute on a pre-production database without writing to real tables.

**Documentation site:** [https://deeprajdeveloper.github.io/sql-sp-harness/](https://deeprajdeveloper.github.io/sql-sp-harness/) (GitHub Pages). Site styles live in `docs/scss/`; compile with `npx sass docs/scss/styles.scss docs/scss/css/styles.css`. CI syncs `docs/version.json` from the package via `python3 scripts/sync_docs_version.py` before each Pages deploy.

> Not a live debugger. This tool generates a **static test harness** (DML previews + variable traces), not breakpoints or step-into debugging.
>
> Not affiliated with Microsoft. "SQL Server" and T-SQL are used descriptively only.

## What it does

| Command | Purpose |
|---------|---------|
| `analyze` | See what keyword elements that procedure contains along with counts — DML, TRY/CATCH, loops, SET, line-level detail |
| `generate` | Create a debug harness: real-table DML → `SELECT` previews, `PRINT` traces on variables |

Output includes a banner on the top of the procedure stating: **DEBUG HARNESS — DO NOT RUN ON PRODUCTION**.

## Install

**macOS / Linux:**

```bash
pip install sql-sp-harness
# or: pip3 install sql-sp-harness
```

**Windows:**

```bash
py -m pip install sql-sp-harness
```

Requires **Python 3.10+**.

Verify (console script or module):

```bash
sql-sp-harness version
# alias: sp-harness version

python3 -m sql_sp_harness version   # macOS / Linux
py -m sql_sp_harness version        # Windows
```

## Quick start

```bash
sql-sp-harness analyze -i MyProc.sql
sql-sp-harness generate -i MyProc.sql -o MyProc_debug.sql
```

With traces in the Messages tab (default):

```bash
sql-sp-harness generate -i MyProc.sql -o MyProc_debug.sql --trace-style print
```

By default, `generate` removes original line (`--`) and block (`/* */`) comments from the output. Use `--keep-comments` to preserve them (harness `[DBG-*]` markers are always added).

### Script preparation

Deploy preamble (`IF EXISTS … DROP PROCEDURE`, standalone `DROP PROCEDURE`, `SET ANSI_NULLS`, `SET QUOTED_IDENTIFIER`) is removed for both `analyze` and `generate`. Only SSMS-style deploy blocks are stripped — **in-procedure** `IF EXISTS (SELECT … FROM …)` checks (including multi-line predicates) are kept.

`generate` also rewrites `CREATE PROCEDURE` into `DECLARE` parameters so the script does not create the procedure on the server.

### Analyze options

```bash
sql-sp-harness analyze -i MyProc.sql --report MyProc.txt   # plain-text file
sql-sp-harness analyze -i MyProc.sql --plain               # no ANSI colors on terminal
sql-sp-harness analyze -i MyProc.sql --full                # show zero-count sections
```

### Step log (audit trail)

Use `--log` to write a timestamped log beside the input (`MyProc.log`), or `--log-file path/to/run.log` for a custom path. Works with both `analyze` and `generate`.

Each line uses the format `[datetime] [function_name] [LEVEL] message`. `INFO` lines mark milestones (file read, preamble strip, transform complete); `DEBUG` lines list per-line edits (comment removal, DML stubs, trace injection, preamble removal). Functions include `strip_deploy_preamble`, `strip_comments`, `stub_dml`, `inject_traces`, and others.

```bash
sql-sp-harness generate -i MyProc.sql -o MyProc_debug.sql --log
sql-sp-harness analyze -i MyProc.sql --log-file /tmp/myproc-analyze.log
```

With `--log`, progress still prints to stderr unless you also pass `--quiet` (the log file always receives full detail).

## Development

```bash
git clone https://github.com/DeeprajDeveloper/sql-sp-harness.git
cd sql-sp-harness
pip install -e ".[dev]"
pytest
```

Sample SQL files for manual testing live under `samples/` (e.g. `samples/sample1.sql`, `samples/sql/enterprise_complex_proc.sql`).

Build for PyPI:

```bash
./scripts/publish-pypi.sh
./scripts/publish-pypi.sh upload
```

When bumping the package version, also run `python3 scripts/sync_docs_version.py` so the docs site version badge stays in sync.

## File encoding

SSMS often saves scripts as **UTF-16 LE** (Unicode). Older Windows exports may use **Windows-1252** (smart quotes, en-dashes). The CLI auto-detects these; output is always UTF-8. Override with `--encoding` if needed:

```bash
sql-sp-harness generate -i MyProc.sql -o MyProc_debug.sql --encoding utf-16-le
```

## Limitations

| Pattern | Behavior |
|---------|----------|
| Dynamic SQL | Not analyzed |
| Encrypted procedures | No source |
| Cursors | Not rewritten |
| DDL inside proc | Not stubbed |
| SSMS deploy preamble | Stripped; in-procedure `IF EXISTS` preserved |

Always review generated scripts before running them on the database server.

## License

MIT
