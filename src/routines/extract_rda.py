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
import sys
from pathlib import Path

from ..config import get_path
from ..log import log
from ..utils import select_file_gui, validate_file_exists, CustomArgumentParser

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
    output_dir.mkdir(parents=True, exist_ok=True)
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

    log(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


# ============================================================
# CLI
# ============================================================


def build_parser(parser: CustomArgumentParser) -> None:
    """Build argument parser for extract_rda."""

    rda_console_path = get_path("rda_console_exec")
    unpacked_dir = get_path("unpacked_dir")

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Path to the .rda file to extract",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=unpacked_dir,
        help=f"Output directory (default: {unpacked_dir})",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="(assets\\.xml|templates\\.xml|properties.*\\.xml|texts.*\\.xml)$",
        help="Optional regex pattern for rda extraction",
    )
    parser.add_argument(
        "--rdaconsole-path",
        type=Path,
        default=rda_console_path,
        help=f"Path to RdaConsole.exe (default: {rda_console_path})",
    )


def run(parsed: CustomArgumentParser) -> int:
    """
    Main entry point for RDA extraction.

    Args:
        parsed: Parsed command-line arguments.

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    # Validate RdaConsole availability
    rdaconsole_path = parsed.rdaconsole_path
    if not rdaconsole_path.exists():
        log(f"RdaConsole.exe not found at: {rdaconsole_path}", "error")
        return 1

    # Determine input file
    input_path = parsed.input
    if not input_path:
        selected_file = select_file_gui("Select RDA file to extract")
        if not selected_file:
            log("No input file selected", "error")
            return 1
        input_path = Path(selected_file)

    # Validate input file
    if not input_path.exists():
        log(f"RDA file not found: {input_path}", "error")
        return 1

    # Extract with options
    output_dir = parsed.output
    filter_pattern = parsed.filter

    log(f"Extracting RDA: {input_path} → {output_dir}")
    if filter_pattern:
        log(f"Filter regex: {filter_pattern}")

    _extract_rda(
        input_path,
        output_dir,
        filter_pattern,
        rdaconsole_path,
    )
    log("Extraction complete", "success")
    return 0
