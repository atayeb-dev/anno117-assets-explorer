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

        # Store current asset for filter refresh
        self.current_asset_info = None
        self.current_related_guids = None

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
        self.nav_info_frame.pack(fill="both", pady=(10, 0))

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

    def _apply_filter(self) -> None:
        """Refresh the display with current filter."""
        if self.current_asset_info and self.current_related_guids is not None:
            # Re-display with current filter
            self.display_asset_info(
                self.current_asset_info["guid"],
                self.current_asset_info,
                self.current_related_guids,
            )

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

        # Store for filter refresh
        self.current_asset_info = asset_info
        self.current_related_guids = related_guids

        # Apply filter if set (filter_text comes from parameter or empty)
        filtered_guids = related_guids
        filter_text = ""  # Default: no filter
        if filter_text and related_guids:
            import re

            try:
                pattern = re.compile(filter_text, re.IGNORECASE)
                filtered_guids = [
                    ref
                    for ref in related_guids
                    if pattern.search(ref["element_name"])
                    or pattern.search(ref["context"])
                ]
            except re.error as e:
                logger.warning(f"Invalid regex filter: {e}")
                filtered_guids = related_guids

        logger.info(
            f"Display: asset {guid} with {len(filtered_guids)}/{len(related_guids)} related"
        )

        # Clear previous content
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        # ============================================================
        # FIXED SECTION - Asset Details (no scroll)
        # ============================================================
        # Create a LabelFrame for asset info (matching Asset Browser style)
        fixed_info_frame = ttk.LabelFrame(
            self.nav_info_frame, text="Asset Info", padding=10
        )
        fixed_info_frame.pack(fill="x", pady=(0, 10))

        info_text = f"GUID: {asset_info['guid']}\nName: {asset_info['name']}\nTemplate: {asset_info['template']}\nFile: {asset_info['file']}"
        info_label = tk.Label(
            fixed_info_frame,
            text=info_text,
            font=("Arial", 9),
            justify="left",
            anchor="w",
        )
        info_label.pack(anchor="w", pady=0, padx=0, fill="x")

        # ============================================================
        # FIXED SECTION - Related GUIDs Title (no scroll)
        # ============================================================
        related_title_text = None
        if related_guids:
            if filter_text and len(filtered_guids) < len(related_guids):
                related_title_text = f"Related GUIDs ({len(filtered_guids)}/{len(related_guids)} filtered)"
            else:
                related_title_text = f"Related GUIDs ({len(related_guids)})"

        # ============================================================
        # SCROLLABLE SECTION - Related GUID Links
        # ============================================================
        if filtered_guids:
            # Create a LabelFrame container for related links (matching Asset Browser style)
            related_frame = ttk.LabelFrame(
                self.nav_info_frame, text=related_title_text, padding=10
            )
            related_frame.pack(fill="both", expand=True, pady=(10, 0))

            # Filter frame inside related_frame
            filter_frame = tk.Frame(related_frame)
            filter_frame.pack(anchor="w", fill="x", padx=0, pady=(0, 10))

            ttk.Label(filter_frame, text="Filter:").pack(side="left", padx=(0, 5))

            filter_entry_widget = ttk.Entry(filter_frame, width=20)
            filter_entry_widget.pack(side="left", fill="x", expand=True, padx=(0, 5))

            def refresh_with_filter():
                new_filter = filter_entry_widget.get().strip()
                # Re-display with new filter
                self._display_asset_with_filter(
                    guid, asset_info, related_guids, new_filter
                )

            ttk.Button(
                filter_frame,
                text="⟳ Refresh",
                command=refresh_with_filter,
            ).pack(side="left")

            # Create scrollable container for related links only
            scrollable_container = ttk.Frame(related_frame)
            scrollable_container.pack(fill="both", expand=True)

            # Create canvas with scrollbar
            canvas = tk.Canvas(scrollable_container, highlightthickness=0, bg="white")
            scrollbar = tk.Scrollbar(
                scrollable_container, orient="vertical", command=canvas.yview, width=12
            )
            # Use tk.Frame instead of ttk.Frame for better compatibility with Canvas
            scrollable_frame = tk.Frame(canvas, bg="white")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Enable mouse wheel scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            for idx, ref in enumerate(filtered_guids):
                link_text = f"{ref['guid']} (from <{ref['element_name']}>)"

                # Alternate background colors for better readability
                bg_color = (
                    "#e8f5e9" if idx % 2 == 0 else "white"
                )  # Light green alternating

                # Check if GUID was previously searched and not found
                is_invalid = is_guid_not_found(ref["guid"])

                if is_invalid:
                    # Disabled link (grayed out)
                    logger.debug(f"Link disabled: {ref['guid']} is marked as not found")
                    link = tk.Label(
                        scrollable_frame,
                        text=link_text,
                        foreground="gray",
                        font=("Courier", 9),
                        cursor="arrow",
                        bg=bg_color,
                    )
                else:
                    # Active link (clickable)
                    link = tk.Label(
                        scrollable_frame,
                        text=link_text,
                        foreground="darkblue",
                        font=("Courier", 9, "underline"),
                        cursor="hand2",
                        bg=bg_color,
                    )
                    link.bind(
                        "<Button-1>", lambda e, g=ref["guid"]: self._navigate_to_guid(g)
                    )

                link.pack(anchor="w", padx=25, pady=2, fill="x")

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
