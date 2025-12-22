"""
Asset Browser Widget - Right panel of the Asset Explorer UI.

Pure UI component - No direct CLI calls.
Coordinates with main UI via callbacks for GUID navigation.

Architecture:
- Display asset info and related GUIDs
- Apply blacklist filter from config.json
- Related GUID navigation with hover effects
- Click disabled links to add element_name to config

Config sharing:
- Config loaded once at app startup (in ui.py::main)
- Passed to this widget
- Blacklist comes from config.json (modified manually for now)
- Disabled link clicks merge keywords into config
"""

# ============================================================
# IMPORTS
# ============================================================

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..cache import is_guid_not_found
from ..utils import setup_logging
from ._filter_manager import FilterManager, FilterApplier

logger = setup_logging()

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_FONT = ("Arial", 9)
COURIER_FONT = ("Courier", 9)
SEPARATOR_COLOR = "#eeeeee"
HOVER_COLOR = "#f5f5f5"
LINK_COLOR = "darkblue"


# ============================================================
# ASSET BROWSER WIDGET
# ============================================================


class AssetBrowserWidget:
    """
    UI widget for browsing and filtering related asset GUIDs.

    Features:
    - GUID search and navigation
    - Related GUIDs list with links
    - Blacklist filter from config.json
    - Click disabled links to add to blacklist
    """

    def __init__(
        self, parent, assets_dir: Path, current_guid_var: tk.StringVar, config: dict
    ):
        """
        Initialize Asset Browser widget.

        Args:
            parent: Parent tkinter widget.
            assets_dir: Path to assets directory.
            current_guid_var: StringVar for current GUID.
            config: Shared config dict (loaded once at app startup).
        """
        self.parent = parent
        self.assets_dir = assets_dir
        self.current_guid_var = current_guid_var
        self.config = config

        # Initialize filter manager
        self.filter_mgr = FilterManager(config)

        # State tracking
        self.current_asset_info = None
        self.current_related_guids = None
        self.current_filter_text = ""  # Active regex pattern from config

        # Callback hooks
        self.on_guid_requested = None
        self.on_related_guid_clicked = None
        self.on_back_clicked = None

        # Main frame
        self.frame = ttk.LabelFrame(parent, text="Asset Browser", padding=10)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up asset browser UI components."""
        # ============================================================
        # SEARCH SECTION
        # ============================================================

        ttk.Label(self.frame, text="Search by GUID:", font=DEFAULT_FONT).pack(
            anchor="w", pady=(5, 0)
        )

        search_frame = ttk.Frame(self.frame)
        search_frame.pack(fill="x", pady=5)

        self.guid_entry = ttk.Entry(search_frame, width=30)
        self.guid_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.guid_entry.bind("<Return>", lambda e: self._on_search_guid())

        ttk.Button(search_frame, text="Search", command=self._on_search_guid).pack(
            side="left"
        )

        # ============================================================
        # BACK BUTTON
        # ============================================================

        back_frame = ttk.Frame(self.frame)
        back_frame.pack(fill="x", pady=(0, 5))

        self.back_link = tk.Label(
            back_frame,
            text="← Back",
            foreground="gray",
            font=DEFAULT_FONT + ("underline",),
            cursor="arrow",
        )
        self.back_link.pack(side="right")
        self.back_link.bind("<Button-1>", lambda e: self._on_back_link_clicked())

        # ============================================================
        # CONTENT AREA
        # ============================================================

        self.nav_info_frame = ttk.Frame(self.frame)
        self.nav_info_frame.pack(fill="both", expand=True, pady=10)

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_search_guid(self) -> None:
        """Handle GUID search button/Enter key."""
        guid = self.guid_entry.get().strip()
        if guid:
            self.current_guid_var.set(guid)
            if self.on_guid_requested:
                self.on_guid_requested(guid)

    def _on_back_link_clicked(self) -> None:
        """Handle back button click."""
        if self.on_back_clicked:
            self.on_back_clicked()

    def _on_guid_link_clicked(self, guid: str) -> None:
        """Handle related GUID link click."""
        if self.on_related_guid_clicked:
            self.on_related_guid_clicked(guid)

    # ============================================================
    # DISPLAY METHODS
    # ============================================================

    def display_not_found(self, guid: str) -> None:
        """Display GUID not found error."""
        logger.info(f"Display: GUID {guid} not found")

        self._clear_content()

        frame = ttk.Frame(self.nav_info_frame)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"✗ GUID {guid} not found",
            font=DEFAULT_FONT,
            foreground="red",
        ).pack(anchor="w", pady=10)

        ttk.Label(
            frame,
            text="Click 'Back' to return to the previous asset",
            font=DEFAULT_FONT,
            foreground="gray",
        ).pack(anchor="w")

        self.parent.update_idletasks()

    def display_asset_info(
        self, guid: str, asset_info: dict, related_guids: list[dict] = None
    ) -> None:
        """
        Display asset info and related GUIDs.

        Applies blacklist filter from config to related GUIDs list.

        Args:
            guid: GUID being displayed.
            asset_info: Asset info dict.
            related_guids: List of related GUID dicts.
        """
        if related_guids is None:
            related_guids = []

        # Store state
        self.current_asset_info = asset_info
        self.current_related_guids = related_guids

        # Build filter regex from config keywords
        config_keywords = self.filter_mgr.get_config_keywords()
        self.current_filter_text = self.filter_mgr.build_regex(config_keywords, [])

        logger.info(f"Display: asset {guid} with {len(related_guids)} related GUIDs")

        # Render UI
        self._clear_content()
        self._render_asset_info(asset_info)
        self._render_related_guids(related_guids)

        self.parent.update_idletasks()

    # ============================================================
    # RENDERING METHODS
    # ============================================================

    def _clear_content(self) -> None:
        """Clear content area."""
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

    def _render_asset_info(self, asset_info: dict) -> None:
        """Render asset info section."""
        frame = ttk.LabelFrame(self.nav_info_frame, text="Asset Info", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        text = (
            f"GUID: {asset_info['guid']}\n"
            f"Name: {asset_info['name']}\n"
            f"Template: {asset_info['template']}\n"
            f"File: {asset_info['file']}"
        )
        label = tk.Label(
            frame, text=text, font=DEFAULT_FONT, justify="left", anchor="w"
        )
        label.pack(anchor="w", fill="x")

    def _render_related_guids(self, related_guids: list[dict]) -> None:
        """Render related GUIDs section."""
        title = f"Related GUIDs ({len(related_guids)})"
        frame = ttk.LabelFrame(self.nav_info_frame, text=title, padding=10)
        frame.pack(fill="both", expand=True, pady=(10, 0))

        self._render_related_list(frame, related_guids)

    def _render_related_list(
        self, parent: tk.Widget, related_guids: list[dict]
    ) -> None:
        """Render scrollable list of related GUIDs."""
        # Apply filter from config
        filtered = FilterApplier.apply(related_guids, self.current_filter_text)

        # Show empty state or list
        if not filtered:
            self._render_empty_list(
                parent, bool(related_guids), bool(self.current_filter_text)
            )
        else:
            self._render_guid_list(parent, filtered)

    def _render_empty_list(
        self, parent: tk.Widget, has_guids: bool, has_filter: bool
    ) -> None:
        """Render empty list message."""
        if has_guids and has_filter:
            msg = "All related GUIDs are blacklisted.\nEdit config.json to change."
        else:
            msg = "No related GUIDs found."

        label = tk.Label(
            parent,
            text=msg,
            font=DEFAULT_FONT,
            foreground="gray",
            bg="white",
            justify="center",
            pady=20,
        )
        label.pack(anchor="center", expand=True, fill="both")

    def _render_guid_list(self, parent: tk.Widget, filtered_guids: list[dict]) -> None:
        """Render scrollable list of GUID links."""
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        # Canvas with scrollbar
        canvas = tk.Canvas(
            container,
            highlightthickness=1,
            highlightbackground="#cccccc",
            bg="white",
        )
        scrollbar = tk.Scrollbar(
            container, orient="vertical", command=canvas.yview, width=12
        )
        scroll_frame = tk.Frame(canvas, bg="white")

        # Render GUID links
        for idx, ref in enumerate(filtered_guids):
            if idx > 0:
                # Separator between rows
                tk.Frame(scroll_frame, bg=SEPARATOR_COLOR, height=1).pack(
                    anchor="w", fill="x", padx=0, pady=0
                )

            self._render_guid_link(scroll_frame, ref)

        # Attach canvas
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scroll
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

    def _render_guid_link(self, parent: tk.Widget, guid_ref: dict) -> None:
        """Render a single GUID link with hover effects."""
        guid = guid_ref.get("guid", "???")
        element = guid_ref.get("element_name", "???")
        context = guid_ref.get("context", "???")
        text = f"{guid} (from <{element}> in {context})"

        is_not_found = is_guid_not_found(guid)

        label = tk.Label(
            parent,
            text=text,
            font=COURIER_FONT,
            fg="gray" if is_not_found else LINK_COLOR,
            cursor="hand2" if not is_not_found else "arrow",
            bg="white",
            justify="left",
            anchor="w",
            wraplength=400,
        )

        # Click handler
        if is_not_found:
            label.bind("<Button-1>", lambda e, el=element: self._add_to_blacklist(el))
        else:
            label.bind("<Button-1>", lambda e, g=guid: self._on_guid_link_clicked(g))

        # Hover effects
        label.bind("<Enter>", lambda e: label.config(bg=HOVER_COLOR))
        label.bind("<Leave>", lambda e: label.config(bg="white"))

        if not is_not_found:
            label.config(underline=True)

        label.pack(anchor="w", fill="x", padx=8, pady=5)

    # ============================================================
    # BLACKLIST OPERATIONS
    # ============================================================

    def _add_to_blacklist(self, element_name: str) -> None:
        """
        Add element_name to config blacklist.
        
        Merges with existing keywords without overwriting.
        """
        self.filter_mgr.add_to_config(element_name)
        logger.info(f"Added '{element_name}' to blacklist config")

    # ============================================================
    # LAYOUT
    # ============================================================

    def set_back_button_enabled(self, enabled: bool) -> None:
        """Enable/disable the back button."""
        if enabled:
            self.back_link.config(foreground=LINK_COLOR, cursor="hand2")
        else:
            self.back_link.config(foreground="gray", cursor="arrow")

    def pack(self, **kwargs) -> None:
        """Pack the widget frame."""
        self.frame.pack(**kwargs)
