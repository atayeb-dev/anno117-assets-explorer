"""
Extract RDA files for Anno using RdaConsole.

This module provides functionality to extract RDA (Resource Data Archive) files
using the RdaConsole.exe utility. Supports file selection via GUI and filtering.

Reference: https://github.com/anno-mods/RdaConsole
"""

import argparse
import subprocess
import sys
from pathlib import Path

from ..shared.config import load_config
from ..shared.utils import setup_logging, select_file_gui, validate_file_exists

# Configure logging
logger = setup_logging()

# Load configuration
_config = load_config()
RDA_CONSOLE_EXEC = _config["paths"]["rda_console_exec"]
UNPACKED_DIR = _config["paths"]["unpacked_dir"]


def _extract_rda(
    rda_path: Path,
    output_dir: Path,
    filter_pattern: str = "",
    rdaconsole_path: Path = RDA_CONSOLE_EXEC,
) -> None:
    """
    Execute RdaConsole.exe to extract RDA file.

    Args:
        rda_path: Path to the .rda file to extract.
        output_dir: Destination directory for extracted files.
        filter_pattern: Optional regex pattern to filter extracted files.
        rdaconsole_path: Path to RdaConsole.exe (default: RDA_CONSOLE_EXEC).
        detach_console: If True, run in separate console window (Windows only).

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

    logger.info(f"Running: {' '.join(cmd)}")
    kwargs = {"check": True}
    kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    subprocess.run(cmd, **kwargs)


def _select_file_gui() -> str:
    """
    Open file dialog to select an RDA file.

    Returns:
        Path to selected file, or empty string if cancelled.
    """
    return select_file_gui(
        title="Select an RDA file",
        filetypes=[("RDA files", "*.rda"), ("All files", "*.*")],
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build and return argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract RDA files for Anno using RdaConsole"
    )
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
        default=UNPACKED_DIR,
        help=f"Output directory (default: {UNPACKED_DIR})",
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
        default=RDA_CONSOLE_EXEC,
        help=f"Path to RdaConsole.exe (default: {RDA_CONSOLE_EXEC})",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for RDA extraction.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    parser = _build_parser()
    parsed = parser.parse_args(args)

    # Validate RdaConsole availability
    rdaconsole_path = parsed.rdaconsole_path
    if not rdaconsole_path.exists():
        logger.error(f"RdaConsole.exe not found at: {rdaconsole_path}")
        return 1

    # Determine input file
    input_path = parsed.input
    if not input_path:
        selected_file = _select_file_gui()
        if not selected_file:
            logger.error("No input file selected")
            return 1
        input_path = Path(selected_file)

    # Validate input file
    if not validate_file_exists(input_path, "RDA file"):
        return 1

    # Extract with options
    output_dir = parsed.output
    filter_pattern = parsed.filter

    logger.info(f"Extracting RDA: {input_path} → {output_dir}")
    if filter_pattern:
        logger.info(f"Filter regex: {filter_pattern}")

    try:
        # Use separate console in GUI mode (when file selected via dialog)
        _extract_rda(
            input_path,
            output_dir,
            filter_pattern,
            rdaconsole_path,
        )
        logger.info("Extraction complete")
        return 0
    except subprocess.CalledProcessError as e:
        logger.error(f"RdaConsole failed with exit code {e.returncode}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
