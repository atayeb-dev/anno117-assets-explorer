"""
Filter management for Asset Browser blacklist filtering.

Handles blacklist filter logic:
- Building regex patterns from config keywords
- Persisting keywords to config
- Applying filters to GUID lists

This module centralizes filter-related functionality from AssetBrowserWidget.
"""

# ============================================================
# IMPORTS
# ============================================================

import json
import logging
import re
from pathlib import Path

from ..config import reload_config_if_needed
from ..utils import make_json_serializable

logger = logging.getLogger(__name__)

# ============================================================
# FILTER MANAGER
# ============================================================


class FilterManager:
    """
    Manages blacklist filter logic and persistence.

    Responsibilities:
    - Get keywords from config (with auto-reload)
    - Build regex from keywords
    - Persist keywords to config
    """

    def __init__(self, config: dict):
        """
        Initialize filter manager.

        Args:
            config: Shared config dictionary (loaded once at app startup).
        """
        self.config = config

    def get_config_keywords(self) -> list[str]:
        """
        Get filter keywords from config.

        Reloads config from disk if it has been modified externally.

        Returns:
            List of keyword strings from config.
        """
        # Ensure config is up-to-date with disk
        reload_config_if_needed(self.config)
        return self.config.get("ui", {}).get("related_filter_keywords", [])

    def build_regex(self, keywords: list[str]) -> str:
        """
        Build regex pattern from keywords (OR them together).

        Escapes special regex characters and joins with |.

        Args:
            keywords: List of keyword strings.

        Returns:
            Regex pattern string (empty if no keywords).
        """
        if not keywords:
            return ""

        # Escape regex special characters and join with OR
        escaped = [re.escape(k) for k in keywords]
        return "|".join(escaped)

    def add_to_config(self, keyword: str) -> None:
        """
        Merge keyword into config without overwriting existing ones.

        Args:
            keyword: Single keyword string to add.
        """
        try:
            if "ui" not in self.config:
                self.config["ui"] = {}

            existing = self.config["ui"].get("related_filter_keywords", [])

            # Add if not already present
            if keyword not in existing:
                existing.append(keyword)
                self.config["ui"]["related_filter_keywords"] = existing

                # Persist to file
                config_path = Path("config.json")
                serializable_config = make_json_serializable(self.config)
                with open(config_path, "w") as f:
                    json.dump(serializable_config, f, indent=4)

                logger.info(f"Added '{keyword}' to blacklist config")
        except Exception as e:
            logger.error(f"Failed to add keyword to config: {e}")


# ============================================================
# FILTER APPLIER
# ============================================================


class FilterApplier:
    """Applies blacklist filter to related GUIDs list."""

    @staticmethod
    def apply(related_guids: list[dict], regex_pattern: str) -> list[dict]:
        """
        Filter related GUIDs list using regex pattern.

        Removes items where element_name or context match the pattern.

        Args:
            related_guids: List of related GUID dicts.
            regex_pattern: Regex pattern to match (empty = no filtering).

        Returns:
            Filtered list of GUIDs.
        """
        if not regex_pattern:
            return related_guids

        try:
            pattern = re.compile(regex_pattern, re.IGNORECASE)
            return [
                ref
                for ref in related_guids
                if not (
                    pattern.search(ref.get("element_name", ""))
                    or pattern.search(ref.get("context", ""))
                )
            ]
        except re.error:
            logger.error(f"Invalid regex pattern: {regex_pattern}")
            return related_guids
