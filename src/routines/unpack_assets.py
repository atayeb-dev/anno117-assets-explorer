"""
Unpack Anno assets from XML data.

Extracts and filters assets from assets.xml based on regex patterns,
generating individual XML output files grouped by asset template (Template field).
"""

# ============================================================
# IMPORTS
# ============================================================

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

from ..config import ConfigPath, get_file_path
from ..log import log, clean
from ..cli import CliArgumentParser
from ..utils import (
    sanitize_filename,
    indent_xml,
    load_xml_file,
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
    log(f"Loading: {assets_xml_path}")
    root = load_xml_file(assets_xml_path)
    if root is None:
        raise RuntimeError(f"Failed to parse XML: {assets_xml_path}")
    assets_by_template: DefaultDict[str, list] = defaultdict(list)

    # Compile regex if provided
    regex_pattern = re.compile(filter_regex) if filter_regex else None

    for asset in root.findall(".//Asset"):
        node = None
        if mode == "templates":
            node = asset.find("./Template")
            if node is None:
                continue
        elif mode == "guids":
            node = asset.find("./Values/Standard/GUID")
            if node is None:
                continue

        node_text = node.text.strip()

        # Apply regex filter
        if regex_pattern and not regex_pattern.search(node_text):
            continue

        assets_by_template[node_text].append(asset)

    return assets_by_template


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
    length = len(assets.keys())
    template = 0
    for asset_template, assets_list in assets.items():
        template += 1
        log(f"Writing assets for template: {template/length*100:.0f}%")
        safe_name = sanitize_filename(asset_template)

        for asset in assets_list:
            assets_root.append(asset)

        if not merge:
            output_path = unpacked_dir / f"{safe_name}.xml"
            indent_xml(assets_root)
            ET.ElementTree(assets_root).write(
                output_path, encoding="utf-8", xml_declaration=True
            )
            output_paths.append(output_path)
            assets_root = ET.Element("Assets")
        clean()
    if merge:
        output_path = unpacked_dir / f"{merge}.xml"
        indent_xml(assets_root)
        ET.ElementTree(assets_root).write(
            output_path, encoding="utf-8", xml_declaration=True
        )
        log(f"Unpacked assets: {len(assets_root)} assets → {output_path}", "success")


# ============================================================
# MAIN
# ============================================================


help_text = "\
{ind/1}{fh/[Unpack Help]}: unpacks assets from Anno assets.xml, {fh/parses} given asset file and {fh/unpacks found patterns} into new {fh/xml files}\n\
{ind/1}{hu/[Usage]}: unpack_assets \
{hur/'-a', '--assets'} {hv/[path/to/assets.xml]} \
{hu/'-t', '--templates'} {hv/[regex]} | \
{hu/'-g', '--guids'} {hv/[guid1,guid2]} \
{hu/'-m', '--merge'} {hv/[filename]}\n\
{ind/2}{hf/[Feature]}: {hu/-t} {hul/template} {hf/mode}: unpacks by template name {hvl/(optional regex filter)}. Writes unpacked files to {hfl/'templates/templatename.xml'}\n\
{ind/2}{hf/[Feature]}: {hu/-g} {hul/GUID} {hf/mode}: unpacks by {hvl/comma-separated GUIDs}. Writes unpacked files to {hfl/'guids/guid.xml'}\n\
{ind/2}{hf/[Feature]}: {hu/-m} {hul/merge} {hf/mode}: merges unpacked assets into a {hvl/single output filename}. Writes output to {hfl/'merge/[filename].xml'}\
"


def help():
    return help_text


def build_parser(parser: CliArgumentParser) -> None:
    """Build argument parser for unpack_assets."""
    parser.add_argument(
        long="assets_file",
        type=ConfigPath,
    )
    parser.add_argument(
        long="unpack_dir",
        type=ConfigPath,
    )
    parser.add_argument(
        long="templates",
        nargs="?",
        const=True,
    )
    parser.add_argument(
        long="guids",
        type=lambda s: s.split(","),
    )
    parser.add_argument(
        long="merge",
        action="store_true",
    )


def run(parser: CliArgumentParser) -> int:
    """
    Main entry point for unpack_assets module.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 on success, non-zero on failure).
    """

    unpacked_dir = parser.module_arg("unpack_dir")
    assets_file = parser.module_arg("assets_file")
    templates = parser.module_arg("templates")
    guids = parser.module_arg("guids")
    merge = parser.module_arg("merge")
    log(f"Assets file: {assets_file}")
    log(f"Unpack directory: {unpacked_dir}")
    log(f"Templates filter: {templates}")
    log(f"GUIDs filter: {guids}")
    log(f"Merge output filename: {merge}")

    # Validate unpack directory
    unpack_dir = unpacked_dir
    if not unpack_dir.exists():
        unpack_dir.mkdir(parents=True, exist_ok=True)

    # Validate input file
    assets_file = assets_file
    if not assets_file.is_file():
        raise FileNotFoundError(f"Assets file not found: {assets_file}")

    filter_regex = None
    mode = "templates" if templates else "guids" if guids else ""
    if mode:
        unpack_dir = unpack_dir.joinpath("merged" if merge else mode)

        if templates:
            filter_regex = templates if isinstance(templates, str) else None
        elif guids:
            filter_regex = "|".join(guids)
        log(f"Unpacking mode: {mode} (filter: {filter_regex})")
        assets = _unpack_assets(assets_file, mode, filter_regex)
        log(
            f"Valid assets founds: {sum(len(assets) for assets in assets.values())}",
            nl=False,
        )
        if mode == "templates":
            log(f" across {len(assets)} templates")
        else:
            log()
        _write_outputs(assets, unpack_dir, merge)
        log("{succ/}Unpack assets complete")
        return 0
    else:
        raise ValueError("Either {hu/--templates} or {hu/--guids} must be specified.")
