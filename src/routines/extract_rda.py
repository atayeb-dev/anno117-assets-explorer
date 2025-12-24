"""
Extract RDA files for Anno using RdaConsole.

This module provides functionality to extract RDA (Resource Data Archive) files
using the RdaConsole.exe utility. Supports file selection via GUI and filtering.

Reference: https://github.com/anno-mods/RdaConsole
"""

# ============================================================
# IMPORTS
# ============================================================

import subprocess
from pathlib import Path

from ..config import get_file_path, get_value_or_none
from ..log import log
from ..cli import CliArgumentParser

# ============================================================
# EXTRACTION
# ============================================================


def _extract_rda(
    rda_path: Path,
    output_dir: Path,
    filter_pattern: str = "",
    rdaconsole_path: Path = None,
) -> None:
    """
    Execute RdaConsole.exe to extract RDA file.

    Args:
        rda_path: Path to the .rda file to extract.
        output_dir: Destination directory for extracted files.
        filter_pattern: Optional regex pattern to filter extracted files.
        rdaconsole_path: Path to RdaConsole.exe.

    Raises:
        subprocess.CalledProcessError: If RdaConsole.exe fails.
        FileNotFoundError: If RdaConsole.exe is not found.
    """
    cmd = [
        str(rdaconsole_path),
        "extract",
        "-f",
        str(rda_path),
        "-y",
        "-o",
        str(output_dir),
    ]
    if filter_pattern:
        cmd.extend(["--filter", filter_pattern])

    log(f"Running {rdaconsole_path}")
    subprocess.run(
        cmd,
        check=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE,  # required as rda console performs clear() in console
    )


# ============================================================
# CLI
# ============================================================


def build_parser(parser: CliArgumentParser) -> None:
    """Build argument parser for extract_rda."""

    rda_console_file = get_file_path(f"rda_console_file")
    unpack_dir = get_file_path("unpack_dir")
    input_rda_file = get_file_path("input_rda_file")
    filter_pattern = get_value_or_none("rda_filter_pattern")

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=input_rda_file,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=unpack_dir,
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=filter_pattern,
    )
    parser.add_argument(
        "--rdaconsole",
        type=Path,
        default=rda_console_file,
    )


def run(parsed: CliArgumentParser) -> int:
    """
    Main entry point for RDA extraction.

    Args:
        parsed: Parsed command-line arguments.

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    # Validate RdaConsole availability
    rdaconsole_path = parsed.rdaconsole
    if not rdaconsole_path.is_file():
        raise FileNotFoundError(f"RdaConsole.exe not found at: {rdaconsole_path}")

    # Validate input file
    rda_file = parsed.input
    if not rda_file.is_file():
        raise FileNotFoundError(f"RDA file not found: {rda_file}")

    # Extract with options
    output_dir = parsed.output
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    filter_pattern = parsed.filter

    log(f"Extracting RDA: {rda_file} {{arr/}} {output_dir}")
    if filter_pattern:
        log(f"Filter regex: {filter_pattern}")

    _extract_rda(
        rda_file,
        output_dir,
        filter_pattern,
        rdaconsole_path,
    )
    log("{succ/Extraction complete}")
    return 0
