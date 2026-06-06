"""CLI for sql-sp-harness — Typer option wiring only."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from sql_sp_harness import __version__
from sql_sp_harness.commands import package_version, run_analyze, run_generate
from sql_sp_harness.constants import APP_HELP

app = typer.Typer(
    name="sql-sp-harness",
    help=APP_HELP,
    no_args_is_help=True,
    add_completion=False,
)


@app.command("version")
def cmd_version() -> None:
    """Print package version."""
    typer.echo(__version__)


@app.callback()
def _root_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        is_eager=True,
    ),
) -> None:
    """T-SQL stored procedure debug harness generator."""
    if version:
        typer.echo(f"sql-sp-harness {package_version()}")
        raise typer.Exit()


@app.command("analyze")
def analyze_cmd(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="Input .sql file (use - for stdin).",
    ),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        "-r",
        help="Write plain-text (.txt) file report (no ANSI colors).",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Disable ANSI colors on terminal output.",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Show all sections, including zero counts.",
    ),
    encoding: Optional[str] = typer.Option(
        None,
        "--encoding",
        "-e",
        help="Force input encoding (e.g. utf-8, utf-16-le, cp1252). Auto-detected if omitted.",
    ),
    log: bool = typer.Option(
        False,
        "--log",
        help="Write a step-by-step log to <input_stem>.log (use --log-file to override path).",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log-file",
        help="Write step-by-step log to this file (implies detailed logging).",
    ),
) -> None:
    """
    Analyze a stored procedure and show what it does.

    Summarizes DML against real tables, TRY/CATCH blocks, loops, SET statements,
    and other structural detail — useful before generating a debug harness.
    """
    run_analyze(input, report, plain, full, encoding, log, log_file)


@app.command("generate")
def generate_cmd(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        help="Input .sql file (use - for stdin).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: <input>_debug.sql).",
    ),
    trace_style: str = typer.Option(
        "print",
        "--trace-style",
        help="Trace style: print (default) or raiserror (NOWAIT).",
    ),
    no_stub_dml: bool = typer.Option(
        False,
        "--no-stub-dml",
        help="Skip DML stubbing; only add traces (nested EXEC calls are still stubbed).",
    ),
    block_markers: bool = typer.Option(
        False,
        "--block-markers",
        help="Insert -- [DBG] Step N markers before IF/WHILE.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress progress messages on stderr.",
    ),
    keep_comments: bool = typer.Option(
        False,
        "--keep-comments",
        help="Retain original line and block comments in the output (stripped by default).",
    ),
    encoding: Optional[str] = typer.Option(
        None,
        "--encoding",
        "-e",
        help="Force input encoding (e.g. utf-8, utf-16-le, cp1252). Auto-detected if omitted.",
    ),
    log: bool = typer.Option(
        False,
        "--log",
        help="Write a step-by-step log to <input_stem>.log (use --log-file to override path).",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log-file",
        help="Write step-by-step log to this file (implies detailed logging).",
    ),
) -> None:
    """
    Generate a debug harness script from a stored procedure.

    Replaces writes to real tables with SELECT previews, replaces nested EXEC calls
    with PRINT stubs, and adds PRINT traces on variables so you can run the script
    on a dev database without side effects.
    """
    run_generate(
        input,
        output,
        trace_style,
        no_stub_dml,
        block_markers,
        keep_comments,
        quiet,
        encoding,
        log,
        log_file,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
