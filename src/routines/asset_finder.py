"""
Asset Finder: Find which template contains a given GUID.

This module searches through all asset XML files to locate a specific asset
by its GUID and returns information about where it was found.
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import logging
from pathlib import Path
from typing import Optional

from ..cache import (
    get_cached_asset,
    set_cached_asset,
    set_guid_not_found,
)
from ..config import load_config
from ..utils import load_xml_file

# ============================================================
# CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)
config = load_config()
ASSETS_DIR = config["paths"]["assets_unpack_dir"]

# ============================================================
# SEARCH
# ============================================================


def _populate_cache_for_file(xml_file: Path) -> None:
    """
    Populate cache with all assets from a single XML file.

    Args:
        xml_file: Path to the XML asset file.
    """
    root = load_xml_file(xml_file)
    if root is None:
        return

    count = 0
    for asset in root.findall("Asset"):
        standard = asset.find("Values/Standard")
        if standard is None:
            continue

        guid_elem = standard.find("GUID")
        name_elem = standard.find("Name")
        template_elem = asset.find("Template")

        if guid_elem is None or guid_elem.text is None:
            continue

        guid = guid_elem.text.strip()
        # Skip if already cached
        cached = get_cached_asset(guid)
        if cached is not None:
            continue

        name = name_elem.text if name_elem is not None else "Unknown"
        template = template_elem.text if template_elem is not None else "Unknown"

        asset_data = {
            "guid": guid,
            "name": name,
            "template": template,
            "file": xml_file.name,
        }
        set_cached_asset(guid, asset_data)
        count += 1

    if count > 0:
        logger.info(f"Populated cache with {count} assets from {xml_file.name}")


def find_asset_by_guid(guid: str, assets_dir: Path) -> Optional[dict]:
    """
    Find which template contains the given GUID.

    Args:
        guid: The GUID to search for.
        assets_dir: Path to assets directory.

    Returns:
        Dictionary with 'guid', 'template', 'name' keys, or None if not found.
    """
    # Clean up GUID (remove whitespace)
    guid = guid.strip()

    # Check cache first (returns asset or not_found marker)
    cached = get_cached_asset(guid)
    if cached is not None:
        # If cached as "not found", return None to caller
        if cached.get("not_found", False):
            logger.debug(f"GUID {guid} was previously searched and not found (cached)")
            return None
        # Otherwise it's a cached asset
        return cached

    assets_dir = Path(assets_dir)

    if not assets_dir.exists():
        logger.error(f"Assets directory not found: {assets_dir}")
        return None

    # Iterate through all XML files in assets directory
    xml_files = sorted(assets_dir.glob("*.xml"))
    logger.info(f"Searching for GUID {guid} in {len(xml_files)} asset files...")

    for xml_file in xml_files:
        root = load_xml_file(xml_file)
        if root is None:
            continue

        # Search through all assets in this file
        for asset in root.findall("Asset"):
            standard = asset.find("Values/Standard")
            if standard is None:
                continue

            guid_elem = standard.find("GUID")
            if guid_elem is not None and guid_elem.text:
                if guid_elem.text.strip() == guid:
                    # Found it!
                    name_elem = standard.find("Name")
                    template_elem = asset.find("Template")

                    result = {
                        "guid": guid,
                        "template": (
                            template_elem.text
                            if template_elem is not None
                            else "Unknown"
                        ),
                        "name": name_elem.text if name_elem is not None else "Unknown",
                        "file": xml_file.name,
                    }
                    logger.info(
                        f"Found GUID {guid}: {result['name']} in {result['file']}"
                    )
                    # Cache the result
                    set_cached_asset(guid, result)

                    # Populate cache with all assets from this template
                    _populate_cache_for_file(xml_file)

                    return result

    logger.warning(f"GUID {guid} not found in any asset file")
    # Cache the fact that this GUID was not found
    set_guid_not_found(guid)
    return None


def find_related_guids(guid: str, assets_dir: Path) -> list[dict]:
    """
    Find all GUID references within a given asset.

    Recursively extracts numeric values from the asset's XML that could be
    references to other assets.

    Args:
        guid: The GUID to search for.
        assets_dir: Path to assets directory.

    Returns:
        List of dicts with 'guid', 'element_name', 'context' keys.
    """
    assets_dir = Path(assets_dir)

    # First, find the asset
    asset_info = find_asset_by_guid(guid, assets_dir)
    if asset_info is None:
        logger.warning(f"Asset {guid} not found, cannot find related GUIDs")
        return []

    # Load the asset file
    xml_file = assets_dir / asset_info["file"]
    root = load_xml_file(xml_file)
    if root is None:
        return []

    # Find the specific asset in the tree
    target_asset = None
    for asset in root.findall("Asset"):
        standard = asset.find("Values/Standard")
        if standard is not None:
            guid_elem = standard.find("GUID")
            if (
                guid_elem is not None
                and guid_elem.text
                and guid_elem.text.strip() == guid
            ):
                target_asset = asset
                break

    if target_asset is None:
        logger.warning(f"Could not locate asset {guid} in file")
        return []

    # Extract all numeric values from the asset (potential GUID references)
    related_guids = []
    seen = set()

    def extract_numeric_values(element, parent_name=""):
        """Recursively extract numeric values from XML elements."""
        # Check element text
        if element.text and element.text.strip().isdigit():
            num = element.text.strip()
            # Skip self, already seen, and boolean values (0, 1)
            if num not in seen and num != guid and num not in ("0", "1"):
                seen.add(num)
                related_guids.append(
                    {
                        "guid": num,
                        "element_name": element.tag,
                        "context": parent_name,
                    }
                )

        # Recurse into children
        for child in element:
            extract_numeric_values(child, element.tag)

    # Extract from Values section (skip Standard/Name/GUID)
    values = target_asset.find("Values")
    if values is not None:
        for child in values:
            if child.tag != "Standard":  # Skip Standard section
                extract_numeric_values(child, child.tag)

    logger.info(f"Found {len(related_guids)} related GUIDs for {guid}")
    return related_guids


# ============================================================
# MAIN
# ============================================================


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for asset finder.

    Args:
        args: Command-line arguments:
              -g GUID: GUID to search for

    Returns:
        Exit code (0 on success, 1 on error).
    """
    parser = argparse.ArgumentParser(
        description="Find which template contains a given GUID"
    )
    parser.add_argument(
        "-g",
        "--guid",
        type=str,
        required=True,
        help="GUID to search for",
    )
    parser.add_argument(
        "-ad",
        "--assets-dir",
        type=Path,
        default=ASSETS_DIR,
        help=f"Path to assets directory (default: {ASSETS_DIR})",
    )
    parser.add_argument(
        "-r",
        "--related",
        action="store_true",
        help="Find related GUIDs referenced by this asset",
    )
    parser.add_argument(
        "-f",
        "--filter",
        type=str,
        default=None,
        help="Regex filter for related GUIDs (matches element_name or context)",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    try:
        parsed = parser.parse_args(args or [])

        # Silence logger INFO if JSON output requested, but keep WARNING and ERROR
        if parsed.json:
            logger.setLevel(logging.WARNING)

        result = find_asset_by_guid(parsed.guid, parsed.assets_dir)

        if result:
            # Output as JSON if requested (or from --related flag)
            if parsed.related or parsed.json:
                import json

                output = {"asset": result}

                if parsed.related:
                    related = find_related_guids(parsed.guid, parsed.assets_dir)

                    # Apply filter if provided
                    if parsed.filter:
                        import re

                        pattern = re.compile(parsed.filter, re.IGNORECASE)
                        related = [
                            ref
                            for ref in related
                            if pattern.search(ref["element_name"])
                            or pattern.search(ref["context"])
                        ]

                    output["related"] = related
                else:
                    output["related"] = []

                print(json.dumps(output))
            else:
                print(f"\n✓ Found!")
                print(f"  GUID:     {result['guid']}")
                print(f"  Name:     {result['name']}")
                print(f"  Template: {result['template']}")
                print(f"  File:     {result['file']}\n")

            return 0
        else:
            if parsed.json:
                import json

                print(json.dumps({"asset": None, "related": []}))
            else:
                print(f"\n✗ GUID {parsed.guid} not found\n")
            return 1

    except Exception as e:
        logger.error(f"Error: {e}")
        if parsed.json:
            import json

            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
