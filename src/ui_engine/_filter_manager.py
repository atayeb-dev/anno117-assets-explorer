"""
Filter management for Asset Browser blacklist filtering.

Handles blacklist filter logic:
- Merging config and user keywords
- Building regex patterns
- Persisting filters to config
- Managing filter state

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
# CONSTANTS
# ============================================================

KEYWORDS_CONFIG_KEY = ("ui", "related_filter_keywords")
FILTER_SEPARATOR = ", "


# ============================================================
# FILTER MANAGER
# ============================================================


class FilterManager:
    """
    Manages blacklist filter logic and persistence.

    Responsibilities:
    - Merge config keywords with user keywords
    - Build and validate regex patterns
    - Parse and format keyword strings
    - Save/load filters from config
    """

    def __init__(self, config: dict):
        """
        Initialize filter manager.

        Args:
            config: Shared config dictionary (loaded once at app startup).
        """
        self.config = config

    # ============================================================
    # KEYWORD MANAGEMENT
    # ============================================================

    def get_config_keywords(self) -> list[str]:
        """
        Get filter keywords from config.

        Reloads config from disk if it has been modified externally.
        """
        # Ensure config is up-to-date with disk
        reload_config_if_needed(self.config)

        return self.config.get("ui", {}).get("related_filter_keywords", [])

    def parse_keywords(self, keyword_string: str) -> list[str]:
        """
        Parse comma-separated keyword string into list.

        Args:
            keyword_string: Comma-separated keywords.

        Returns:
            List of stripped, non-empty keywords.
        """
        if not keyword_string.strip():
            return []
        return [k.strip() for k in keyword_string.split(",") if k.strip()]

    def merge_keywords(self, config_kw: list[str], user_kw: list[str]) -> list[str]:
        """
        Merge config and user keywords, removing duplicates.

        Preserves order: config keywords first, then user keywords.

        Args:
            config_kw: Keywords from config.
            user_kw: User-added keywords.

        Returns:
            List of unique keywords (config first, then user).
        """
        seen = set()
        merged = []
        for k in config_kw + user_kw:
            if k not in seen:
                merged.append(k)
                seen.add(k)
        return merged

    def format_keywords(self, keywords: list[str]) -> str:
        """
        Format keyword list as comma-separated string.

        Args:
            keywords: List of keywords.

        Returns:
            Comma-separated string.
        """
        return FILTER_SEPARATOR.join(keywords)

    # ============================================================
    # REGEX BUILDING
    # ============================================================

    def build_regex(self, config_keywords: list[str], user_keywords: list[str]) -> str:
        """
        Build regex pattern from keywords (OR all keywords together).

        Merges config and user keywords, escapes special chars, builds regex.

        Args:
            config_keywords: Keywords from config.
            user_keywords: User keywords.

        Returns:
            Regex pattern string (empty if no keywords).
        """
        keywords = self.merge_keywords(config_keywords, user_keywords)
        if not keywords:
            return ""

        # Escape regex special characters and join with OR
        escaped = [re.escape(k) for k in keywords]
        return "|".join(escaped)

    def test_regex(self, pattern: str) -> bool:
        """
        Test if regex pattern is valid.

        Args:
            pattern: Regex pattern string to validate.

        Returns:
            True if valid, False otherwise.
        """
        if not pattern:
            return True
        try:
            re.compile(pattern, re.IGNORECASE)
            return True
        except re.error:
            return False

    # ============================================================
    # PERSISTENCE
    # ============================================================

    def save_to_config(self, keywords: str) -> None:
        """
        Save keywords to config (RAM and file).

        Args:
            keywords: Comma-separated keywords string.
        """
        try:
            if "ui" not in self.config:
                self.config["ui"] = {}

            keyword_list = self.parse_keywords(keywords)
            self.config["ui"]["related_filter_keywords"] = keyword_list

            # Persist to file
            config_path = Path("config.json")
            serializable_config = make_json_serializable(self.config)
            with open(config_path, "w") as f:
                json.dump(serializable_config, f, indent=4)

            logger.info(f"Saved filter keywords: {keyword_list}")
        except Exception as e:
            logger.error(f"Failed to save filter config: {e}")

    def add_to_config(self, keywords: str) -> None:
        """
        Merge keywords into config without overwriting existing ones.

        Args:
            keywords: Comma-separated keywords string to add.
        """
        try:
            if "ui" not in self.config:
                self.config["ui"] = {}

            existing = self.config["ui"].get("related_filter_keywords", [])
            new_keywords = self.parse_keywords(keywords)

            # Merge without duplicates
            merged = self.merge_keywords(existing, new_keywords)
            self.config["ui"]["related_filter_keywords"] = merged

            # Persist to file
            config_path = Path("config.json")
            serializable_config = make_json_serializable(self.config)
            with open(config_path, "w") as f:
                json.dump(serializable_config, f, indent=4)

            logger.info(f"Added filter keywords: {merged}")
        except Exception as e:
            logger.error(f"Failed to add filter to config: {e}")


# ============================================================
# FILTER APPLIER
# ============================================================


class FilterApplier:
    """
    Applies blacklist filter to related GUIDs list.

    Filters out GUIDs whose element_name or context match the pattern.
    """

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
