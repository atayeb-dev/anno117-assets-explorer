"""
Asset Browser Widget - Right panel of the Asset Explorer UI.

Pure UI component - No direct CLI calls.
Communicates with main UI via callbacks:
- on_guid_requested: User typed/searched for a GUID
- on_related_guid_clicked: User clicked a related GUID link
- on_back_clicked: User clicked back button
"""

# ============================================================
# IMPORTS
# ============================================================

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..cache import is_guid_not_found
from ..utils import setup_logging

# ============================================================
# CONFIGURATION
# ============================================================

logger = setup_logging()

# ============================================================
# ASSET BROWSER WIDGET
# ============================================================


class AssetBrowserWidget:
    """
    Pure UI widget for Asset Browser - GUID search and navigation.
    
    Does NOT make CLI calls directly.
    Notifies parent (ui.py) via callbacks.
    """

    def __init__(self, parent, assets_dir: Path, current_guid_var: tk.StringVar):
        """
        Initialize Asset Browser widget.

        Args:
            parent: Parent tkinter widget.
            assets_dir: Path to assets directory.
            current_guid_var: StringVar for reactive updates.
        """
        self.parent = parent
        self.assets_dir = assets_dir
        self.current_guid_var = current_guid_var

        # Callbacks set by parent (ui.py)
        self.on_guid_requested = None  # (guid: str) -> None
        self.on_related_guid_clicked = None  # (guid: str) -> None
        self.on_back_clicked = None  # () -> None

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Asset Browser", padding=10)

        self._setup_ui()

    # ============================================================
    # UI SETUP
    # ============================================================

    def _setup_ui(self) -> None:
        """Set up the asset browser UI components."""
        # Search controls frame
        search_controls_frame = ttk.Frame(self.frame)
        search_controls_frame.pack(fill="x", pady=5)

        # Back link
        self.back_link = tk.Label(
            search_controls_frame,
            text="← Back",
            foreground="gray",
            font=("Arial", 9, "underline"),
            cursor="arrow",
        )
        self.back_link.pack(side="right", padx=(10, 0))
        self.back_link.bind("<Button-1>", lambda e: self._on_back_link_clicked())

        # GUID search label and entry
        ttk.Label(self.frame, text="Search by GUID:", font=("Arial", 9)).pack(
            anchor="w", pady=(5, 0)
        )

        guid_search_frame = ttk.Frame(self.frame)
        guid_search_frame.pack(fill="x", pady=5)

        self.guid_entry = ttk.Entry(guid_search_frame, width=30)
        self.guid_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ttk.Button(
            guid_search_frame,
            text="🔍 Search",
            command=self._search_asset_by_guid,
        ).pack(side="left")

        # Results display frame
        self.nav_info_frame = ttk.Frame(self.frame)
        self.nav_info_frame.pack(fill="both", expand=True, pady=(10, 0))

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_back_link_clicked(self) -> None:
        """Handle back link click."""
        if self.on_back_clicked:
            self.on_back_clicked()

    def _search_asset_by_guid(self) -> None:
        """Search for asset by GUID when button is clicked."""
        guid = self.guid_entry.get().strip()

        if not guid:
            logger.warning("Empty GUID entry")
            return

        # Notify parent
        if self.on_guid_requested:
            self.on_guid_requested(guid)

    def _navigate_to_guid(self, guid: str) -> None:
        """Navigate to a GUID by clicking a related GUID link."""
        # Notify parent
        if self.on_related_guid_clicked:
            self.on_related_guid_clicked(guid)

    # ============================================================
    # DISPLAY METHODS (called by parent after CLI call)
    # ============================================================

    def display_not_found(self, guid: str) -> None:
        """Display not-found message for a GUID.

        Called by parent (ui.py) after CLI call returns no result.

        Args:
            guid: The GUID that was not found
        """
        logger.info(f"Display: GUID {guid} not found")

        # Clear previous content
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        # Create error message
        content_frame = ttk.Frame(self.nav_info_frame)
        content_frame.pack(fill="both", expand=True)

        error_label = ttk.Label(
            content_frame,
            text=f"✗ GUID {guid} not found",
            font=("Arial", 10),
            foreground="red",
        )
        error_label.pack(anchor="w", pady=10)

        # Hint for user
        hint_label = ttk.Label(
            content_frame,
            text="Click 'Back' to return to the previous asset",
            font=("Arial", 9),
            foreground="gray",
        )
        hint_label.pack(anchor="w")

        self.parent.update_idletasks()

    def display_asset_info(
        self, guid: str, asset_info: dict, related_guids: list[dict] = None
    ) -> None:
        """
        Display asset information and related GUIDs.

        Called by parent (ui.py) after successful CLI call.

        Args:
            guid: The GUID of the asset.
            asset_info: Asset info dict from CLI.
            related_guids: List of related GUID dicts from CLI.
        """
        if related_guids is None:
            related_guids = []

        logger.info(f"Display: asset {guid} with {len(related_guids)} related")

        # Clear previous content
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        # Create simple content frame
        content_frame = ttk.Frame(self.nav_info_frame)
        content_frame.pack(fill="both", expand=True)

        # Asset details
        info_text = f"GUID: {asset_info['guid']}\nName: {asset_info['name']}\nTemplate: {asset_info['template']}\nFile: {asset_info['file']}"
        ttk.Label(
            content_frame, text=info_text, font=("Arial", 9), justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Related GUIDs
        if related_guids:
            logger.info(f"Display: {len(related_guids)} related GUIDs")
            ttk.Label(
                content_frame,
                text=f"Related GUIDs ({len(related_guids)}):",
                font=("Arial", 9, "bold"),
            ).pack(anchor="w", pady=(5, 0))

            for ref in related_guids:
                link_text = f"{ref['guid']} (from <{ref['element_name']}>)"

                # Check if GUID was previously searched and not found
                is_invalid = is_guid_not_found(ref["guid"])

                if is_invalid:
                    # Disabled link (grayed out)
                    logger.debug(f"Link disabled: {ref['guid']} is marked as not found")
                    link = tk.Label(
                        content_frame,
                        text=link_text,
                        foreground="gray",
                        font=("Arial", 9),
                        cursor="arrow",
                    )
                else:
                    # Active link (clickable)
                    link = tk.Label(
                        content_frame,
                        text=link_text,
                        foreground="darkblue",
                        font=("Arial", 9, "underline"),
                        cursor="hand2",
                    )
                    link.bind(
                        "<Button-1>", lambda e, g=ref["guid"]: self._navigate_to_guid(g)
                    )

                link.pack(anchor="w", padx=20, pady=2)

        # Force window resize to fit new content
        self.parent.update_idletasks()

    def set_back_button_enabled(self, enabled: bool) -> None:
        """
        Enable/disable the back button.

        Called by parent (ui.py) when history state changes.

        Args:
            enabled: True to enable, False to disable
        """
        if enabled:
            self.back_link.config(foreground="darkblue", cursor="hand2")
        else:
            self.back_link.config(foreground="gray", cursor="arrow")

    # ============================================================
    # PUBLIC INTERFACE
    # ============================================================

    def pack(self, **kwargs) -> None:
        """Pack the widget frame."""
        self.frame.pack(**kwargs)
