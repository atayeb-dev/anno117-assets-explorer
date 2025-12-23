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

from ..config import get_path, load_global_config
from ..log import log, ansi_text
from ..utils import (
    sanitize_filename,
    indent_xml,
    load_xml_file,
    CustomArgumentParser,
)

# ============================================================
# LOADING
# ============================================================


def _unpack_assets(
    assets_xml_path: Path, mode: str, filter_regex: str = ""
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

    log(f"Loading: {assets_xml_path}", "info")
    root = load_xml_file(assets_xml_path)
    if root is None:
        raise RuntimeError(f"Failed to parse XML: {assets_xml_path}")

    assets_by_template: DefaultDict[str, list] = defaultdict(list)
    all_assets = []

    # Compile regex if provided
    regex_pattern = re.compile(filter_regex) if filter_regex else None

    for asset in root.findall(".//Asset"):
        node = None
        if mode == "templates":
            node = asset.find("./Template")
            if node is None:
                # assets_by_template["_no_template"].append(asset)
                continue
        elif mode == "guids":
            node = asset.find("./Values/Standard/GUID")
            if node is None:
                # assets_by_template["_no_guid"].append(asset)
                continue

        node_text = node.text.strip()

        # Apply regex filter
        if regex_pattern and not regex_pattern.search(node_text):
            continue

        assets_by_template[node_text].append(asset)
        all_assets.append(asset)

    return assets_by_template, all_assets


# ============================================================
# OUTPUT
# ============================================================


def _write_outputs(
    assets: DefaultDict[str, list], unpacked_dir: Path, merge=False
) -> None:
    """
    Write filtered assets to output XML files.

    Creates per-template XML files for each asset template.

    Args:
        assets_by_template: Assets grouped by template name.
        unpacked_dir: Output directory for asset files.
    """
    # Create output directory (don't remove existing files)
    unpacked_dir.mkdir(parents=True, exist_ok=True)

    assets_root = ET.Element("Assets")
    output_paths: list[Path] = []

    for asset_template, assets in assets.items():
        safe_name = sanitize_filename(asset_template)

        for asset in assets:
            assets_root.append(asset)

        if not merge:
            output_path = unpacked_dir / f"{safe_name}.xml"
            indent_xml(assets_root)
            ET.ElementTree(assets_root).write(
                output_path, encoding="utf-8", xml_declaration=True
            )
            output_paths.append(output_path)
            assets_root = ET.Element("Assets")
    if merge:
        output_path = unpacked_dir / f"{merge}.xml"
        indent_xml(assets_root)
        ET.ElementTree(assets_root).write(
            output_path, encoding="utf-8", xml_declaration=True
        )
        log(f"Unpacked assets: {len(assets_root)} assets → {output_paths}", "success")


# ============================================================
# MAIN
# ============================================================


help_text = "\
\t{fh/[Unpack Help]}: unpacks assets from {fh/Anno assets.xml}, parses given {fh/asset} file and outputs found patterns into new {fh/xml} files\n\
\t{hu/[Usage]}: unpack_assets \
{hur/'-a', '--assets'} {hv/[path/to/assets.xml]} \
{hu/'-t', '--templates'} {hv/[regex]} | \
{hu/'-g', '--guids'} {hv/[guid1,guid2]} \
{hu/'-m', '--merge'} {hv/[filename]}\n\
\t{hf/[Feature]}: {hu/-t} {hul/template} {hf/mode}: unpacks by template name {hvl/(optional regex filter)}. Writes unpacked files to {hfl/'templates/templatename.xml'}\n\
\t{hf/[Feature]}: {hu/-g} {hul/GUID} {hf/mode}: unpacks by {hvl/comma-separated GUIDs}. Writes unpacked files to {hfl/'guids/guid.xml'}\n\
\t{hf/[Feature]}: {hu/-m} {hul/merge} {hf/mode}: merges unpacked assets into a {hvl/single output filename}. Writes output to {hfl/'merge/[filename].xml'}\
"


def help():
    return help_text


def build_parser(parser: CustomArgumentParser) -> None:
    parser.add_argument(
        "-a",
        "--assets-file",
        type=Path,
    )
    parser.add_argument(
        "-t",
        "--templates",
        nargs="?",
        const=True,  # Value if present without argument
        type=str,
    )
    parser.add_argument(
        "-g",
        "--guids",
        type=lambda s: s.split(","),
    )
    parser.add_argument(
        "-m",
        "--merge",
        type=str,
    )


def run(parsed: CustomArgumentParser) -> int:
    """
    Main entry point for unpack_assets module.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """
    from ..log import log_args

    if not parsed.assets_file:
        raise ValueError("argument {hu/--assets-file} is required.")
    unpack_dir = get_path("unpack_dir")
    filter_regex = None
    mode = "templates" if parsed.templates else "guids" if parsed.guids else ""
    try:
        if mode:
            assets_file = parsed.assets_file
            unpack_dir = unpack_dir.joinpath("merged" if parsed.merge else mode)

            if parsed.templates:
                filter_regex = (
                    parsed.templates if isinstance(parsed.templates, str) else None
                )
            elif parsed.guids:
                filter_regex = "|".join(parsed.guids)

            log(f"Unpacking mode: {mode} (filter: {filter_regex})")
            assets_by_template, all_assets = _unpack_assets(
                assets_file, mode, filter_regex
            )

            log(f"Valid assets founds: {len(all_assets)}")
            _write_outputs(assets_by_template, unpack_dir, parsed.merge)
            log("Unpack assets complete ✓")
            return 0
        else:
            raise ValueError(
                "Either {hu/--templates} or {hu/--guids} must be specified."
            )
    except FileNotFoundError as e:
        log(f"File error: {e}", "error")
        return 1
    except ET.ParseError as e:
        log(f"XML parse error: {e}", "error")
        return 1
