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

import logging
import re

from ..config import get_ui_keywords, set_ui_keywords

logger = logging.getLogger(__name__)

# ============================================================
# FILTER MANAGER
# ============================================================


class FilterManager:
    """
    Manages blacklist filter logic and persistence.

    Uses centralized config API for all access (smart reload included).
    """

    def get_keywords(self) -> list[str]:
        """
        Get filter keywords from config with auto-reload.

        Returns:
            List of keyword strings, guaranteed fresh from disk.
        """
        return get_ui_keywords()

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

    def add_keyword(self, keyword: str) -> None:
        """
        Add keyword to config without overwriting existing ones.

        Args:
            keyword: Single keyword string to add.
        """
        try:
            existing = get_ui_keywords()

            # Add if not already present
            if keyword not in existing:
                existing.append(keyword)
                set_ui_keywords(existing)
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
