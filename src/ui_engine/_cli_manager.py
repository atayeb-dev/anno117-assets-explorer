"""
CLI interaction manager for Asset Explorer.

Handles subprocess calls to CLI modules and JSON parsing.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

logger = logging.getLogger(__name__)


class CLIManager:
    """Manages all CLI interactions for asset searching and retrieval."""

    def __init__(self, assets_dir: Path):
        """
        Initialize CLI manager.

        Args:
            assets_dir: Path to assets directory
        """
        self.assets_dir = assets_dir

    def fetch_asset_info(self, guid: str) -> tuple:
        """
        Fetch asset info from CLI.

        Args:
            guid: The GUID to search for

        Returns:
            Tuple of (asset_info dict, related_guids list) or (None, []) if not found
        """
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "main.py"),
                "--cli",
                "asset_finder",
                "-g",
                guid,
                "--related",
                "--json",
                "-ad",
                str(self.assets_dir),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout:
                logger.debug(f"CLI returned no results for GUID {guid}")
                return None, []

            try:
                output = json.loads(result.stdout)
                asset_info = output.get("asset")
                related_guids = output.get("related", [])

                if asset_info:
                    logger.debug(
                        f"CLI found asset {guid} with {len(related_guids)} related"
                    )
                    return asset_info, related_guids
                else:
                    logger.debug(f"CLI: no asset found for {guid}")
                    return None, []

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse CLI JSON: {e}")
                return None, []

        except subprocess.TimeoutExpired:
            logger.error(f"CLI timeout for GUID {guid}")
            messagebox.showerror("Error", "Search timed out. Please try again.")
            return None, []
        except Exception as e:
            logger.error(f"CLI error: {e}")
            messagebox.showerror("Error", f"Error during search: {e}")
            return None, []

    def fetch_related_guids(self, guid: str, filter_regex: str = None) -> list[dict]:
        """
        Fetch related GUIDs for an asset (asset must already be found).

        Args:
            guid: The GUID to find related assets for
            filter_regex: Optional regex filter for element_name/context

        Returns:
            List of related GUID dicts or empty list if error
        """
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "main.py"),
                "--cli",
                "asset_finder",
                "-g",
                guid,
                "--related",
                "--json",
                "-ad",
                str(self.assets_dir),
            ]

            # Add filter if provided
            if filter_regex:
                cmd.extend(["-f", filter_regex])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0 or not result.stdout:
                logger.debug(f"CLI returned no related GUIDs for GUID {guid}")
                return []

            try:
                output = json.loads(result.stdout)
                related_guids = output.get("related", [])
                logger.debug(f"CLI found {len(related_guids)} related for {guid}")
                return related_guids

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse CLI JSON: {e}")
                return []

        except subprocess.TimeoutExpired:
            logger.error(f"CLI timeout for GUID {guid}")
            return []
        except Exception as e:
            logger.error(f"CLI error: {e}")
            return []
