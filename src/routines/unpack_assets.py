"""
Unpack Anno assets from XML data.

Extracts and filters assets from assets.xml based on regex patterns,
generating individual XML output files grouped by asset template (Template field).
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

from ..shared.config import load_config
from ..shared.utils import setup_logging, sanitize_filename, indent_xml, select_file_gui

# ============================================================
# CONFIGURATION
# ============================================================

logger = setup_logging()
_config = load_config()
UNPACK_DIR = _config["paths"]["assets_unpack_dir"]


# ============================================================
# LOADING
# ============================================================


def _load_assets(
    assets_xml_path: Path, filter_regex: str = ""
) -> tuple[DefaultDict[str, list], list]:
    """
    Load and filter assets from XML file.

    Args:
        assets_xml_path: Path to assets.xml.
        filter_regex: Optional regex pattern to match asset templates.

    Returns:
        Tuple of (assets_by_template, all_assets).

    Raises:
        FileNotFoundError: If assets.xml not found.
        ET.ParseError: If XML is malformed.
    """
    if not assets_xml_path.exists():
        raise FileNotFoundError(f"assets.xml not found: {assets_xml_path}")

    logger.info(f"Loading: {assets_xml_path}")
    tree = ET.parse(assets_xml_path)
    root = tree.getroot()

    assets_by_template: DefaultDict[str, list] = defaultdict(list)
    all_assets = []

    # Compile regex if provided
    regex_pattern = re.compile(filter_regex) if filter_regex else None

    for asset in root.findall(".//Asset"):
        template_node = asset.find("./Template")
        if template_node is None:
            continue

        asset_template = template_node.text.strip()

        # Apply regex filter
        if regex_pattern and not regex_pattern.search(asset_template):
            continue

        assets_by_template[asset_template].append(asset)
        all_assets.append(asset)

    return assets_by_template, all_assets


# ============================================================
# OUTPUT
# ============================================================


def _write_outputs(
    assets_by_template: DefaultDict[str, list],
    unpacked_dir: Path,
) -> None:
    """
    Write filtered assets to output XML files.

    Creates per-template XML files for each asset template.

    Args:
        assets_by_template: Assets grouped by template name.
        unpacked_dir: Output directory for asset files.
    """
    # Create output directory if it doesn't exist (don't remove existing files)
    unpacked_dir.mkdir(parents=True, exist_ok=True)

    # Write per-template files
    for asset_template, assets in assets_by_template.items():
        safe_name = sanitize_filename(asset_template)
        output_path = unpacked_dir / f"{safe_name}.xml"

        assets_root = ET.Element("Assets")
        for asset in assets:
            assets_root.append(asset)

        indent_xml(assets_root)
        ET.ElementTree(assets_root).write(
            output_path, encoding="utf-8", xml_declaration=True
        )

        logger.info(f"✔ {asset_template}: {len(assets)} assets → {output_path}")


# ============================================================
# MAIN
# ============================================================
def _select_file_gui() -> str:
    """
    Open file dialog to select an assets XML file.

    Returns:
        Path to selected file, or empty string if cancelled.
    """
    return select_file_gui(
        title="Select assets.xml file",
        filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
    )


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for unpack_assets module.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    parser = argparse.ArgumentParser(description="Unpack assets from Anno assets.xml")
    parser.add_argument(
        "-a",
        "--assets-file",
        type=Path,
        default=None,
        help=f"Path to assets.xml file (default: select via GUI)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=UNPACK_DIR,
        help=f"Output directory for assets (default: {UNPACK_DIR})",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="",
        help="Optional regex pattern to filter asset types",
    )
    parsed = parser.parse_args(args)

    # Determine output path for assets
    unpacked_dir = parsed.output
    filter_regex = parsed.filter

    try:
        logger.info(f"Output directory (assets): {unpacked_dir}")
        if filter_regex:
            logger.info(f"Filter regex: {filter_regex}")

        # Determine assets file: CLI arg → GUI selection (no silent default)
        assets_file = parsed.assets_file
        if not assets_file:
            selected_file = _select_file_gui()
            if not selected_file:
                logger.error("No assets file selected")
                return 1
            assets_file = Path(selected_file)

        assets_by_template, all_assets = _load_assets(assets_file, filter_regex)
        logger.info(f"Valid assets found (after filter): {len(all_assets)}")

        _write_outputs(assets_by_template, unpacked_dir)
        logger.info("Unpack assets complete ✓")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        return 1
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


# Alias for compatibility
cli = main


if __name__ == "__main__":
    sys.exit(main())
