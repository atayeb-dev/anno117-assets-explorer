"""
Asset Browser Widget - Right panel of the Asset Explorer UI.

Pure UI component - No direct CLI calls.
Communicates with main UI via callbacks:
- on_guid_requested: User typed/searched for a GUID
- on_related_guid_clicked: User clicked a related GUID link
- on_back_clicked: User clicked back button

CONFIG SHARING:
The config instance is loaded once at app startup (in ui.py::main) and passed
to this widget. All operations (save/load/add) work with the in-memory config:
- SAVE: Updates RAM config AND persists to config.json
- ADD: Merges with existing in RAM config AND persists to config.json
- LOAD: Reads from in-memory config (never re-reads from file)

This ensures all UI components share the same config state.
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ..cache import is_guid_not_found
from ..utils import setup_logging, make_json_serializable

logger = setup_logging()


class AssetBrowserWidget:
    """Pure UI widget for Asset Browser - GUID search and navigation."""

    def __init__(
        self, parent, assets_dir: Path, current_guid_var: tk.StringVar, config: dict
    ):
        """
        Initialize Asset Browser widget.

        Args:
            parent: Parent tkinter widget.
            assets_dir: Path to assets directory.
            current_guid_var: StringVar for current GUID.
            config: Shared config dict instance (loaded once at app startup).
        """
        self.parent = parent
        self.assets_dir = assets_dir
        self.current_guid_var = current_guid_var
        self.config = config  # Shared config instance

        # Store current asset for filter refresh
        self.current_asset_info = None
        self.current_related_guids = None
        self.current_filter_text = ""  # Regex pattern (complete, including config)
        self.current_filter_input = ""  # Raw user input (keywords added by user only)
        self.filter_has_been_edited = False  # Track if user has edited the filter

        # Callbacks set by parent (ui.py)
        self.on_guid_requested = None
        self.on_related_guid_clicked = None
        self.on_back_clicked = None

        # Main frame
        self.frame = ttk.LabelFrame(parent, text="Asset Browser", padding=10)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the asset browser UI components."""
        ttk.Label(self.frame, text="Search by GUID:", font=("Arial", 9)).pack(
            anchor="w", pady=(5, 0)
        )

        guid_search_frame = ttk.Frame(self.frame)
        guid_search_frame.pack(fill="x", pady=5)

        self.guid_entry = ttk.Entry(guid_search_frame, width=30)
        self.guid_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.guid_entry.bind("<Return>", lambda e: self._on_search_guid())

        ttk.Button(guid_search_frame, text="Search", command=self._on_search_guid).pack(
            side="left"
        )

        # Back button on a second line, right-aligned
        back_frame = ttk.Frame(self.frame)
        back_frame.pack(fill="x", pady=(0, 5))

        self.back_link = tk.Label(
            back_frame,
            text="← Back",
            foreground="gray",
            font=("Arial", 9, "underline"),
            cursor="arrow",
        )
        self.back_link.pack(side="right", padx=(0, 0))
        self.back_link.bind("<Button-1>", lambda e: self._on_back_link_clicked())

        # Info display area
        self.nav_info_frame = ttk.Frame(self.frame)
        self.nav_info_frame.pack(fill="both", expand=True, pady=10)

    def _on_search_guid(self) -> None:
        """Handle GUID search."""
        guid = self.guid_entry.get().strip()
        if guid:
            self.current_guid_var.set(guid)
            if self.on_guid_requested:
                self.on_guid_requested(guid)

    def _on_back_link_clicked(self) -> None:
        """Handle back button click."""
        if self.on_back_clicked:
            self.on_back_clicked()

    def _navigate_to_guid(self, guid: str) -> None:
        """Navigate to a GUID by clicking a related GUID link."""
        if self.on_related_guid_clicked:
            self.on_related_guid_clicked(guid)

    def display_not_found(self, guid: str) -> None:
        """Display not-found message."""
        logger.info(f"Display: GUID {guid} not found")

        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        content_frame = ttk.Frame(self.nav_info_frame)
        content_frame.pack(fill="both", expand=True)

        error_label = ttk.Label(
            content_frame,
            text=f"✗ GUID {guid} not found",
            font=("Arial", 10),
            foreground="red",
        )
        error_label.pack(anchor="w", pady=10)

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
        """Display asset information and related GUIDs."""
        if related_guids is None:
            related_guids = []

        # Store for filter refresh
        self.current_asset_info = asset_info
        self.current_related_guids = related_guids
        self.current_filter_text = ""
        # current_filter_input stores ONLY user-added keywords, starts empty
        # It's NOT reset when displaying new asset (preserves user's additions)

        logger.info(
            f"Display: asset {guid} with {len(related_guids)}/{len(related_guids)} related"
        )

        # Clear previous content
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        # Asset Info section
        self._create_asset_info_section(asset_info)

        # Related GUIDs section
        self._create_related_guids_section(related_guids)

        # Apply filter from blacklist if it exists
        if self.current_filter_input.strip():
            regex = self._build_complete_regex()
            self._apply_filter(regex)

        self.parent.update_idletasks()

    def _create_asset_info_section(self, asset_info: dict) -> None:
        """Create the asset info display section."""
        frame = ttk.LabelFrame(self.nav_info_frame, text="Asset Info", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        info_text = f"GUID: {asset_info['guid']}\nName: {asset_info['name']}\nTemplate: {asset_info['template']}\nFile: {asset_info['file']}"
        label = tk.Label(
            frame, text=info_text, font=("Arial", 9), justify="left", anchor="w"
        )
        label.pack(anchor="w", fill="x")

    def _create_related_guids_section(self, related_guids: list[dict]) -> None:
        """Create the related GUIDs section with filter."""
        title = f"Related GUIDs ({len(related_guids)})"
        frame = ttk.LabelFrame(self.nav_info_frame, text=title, padding=10)
        frame.pack(fill="both", expand=True, pady=(10, 0))

        # Filter section
        self._create_filter_frame(frame, related_guids)

        # List section - handles both empty and non-empty cases
        self._create_related_list(frame, related_guids)

    def _create_filter_frame(
        self, parent: tk.Widget, related_guids: list[dict]
    ) -> None:
        """Create the filter input section."""
        filter_frame = tk.Frame(parent)
        filter_frame.pack(anchor="w", fill="x", padx=0, pady=(0, 10))

        ttk.Label(filter_frame, text="Blacklist keywords:").pack(
            side="left", padx=(0, 5)
        )

        # Display all keywords (config + user)
        config_keywords = self.config.get("ui", {}).get("related_filter_keywords", [])
        user_keywords = (
            self.current_filter_input.split(",")
            if self.current_filter_input.strip()
            else []
        )
        user_keywords = [k.strip() for k in user_keywords if k.strip()]

        all_keywords = config_keywords + user_keywords
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for k in all_keywords:
            if k not in seen:
                unique_keywords.append(k)
                seen.add(k)
        display_text = ", ".join(unique_keywords)

        self.filter_entry = ttk.Entry(filter_frame, width=40)
        self.filter_entry.insert(0, display_text)
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def on_refresh():
            # Refresh just re-applies the filter with config+user keywords
            # Does NOT change what's stored or displayed
            regex = self._build_complete_regex()
            self._apply_filter(regex)

        ttk.Button(filter_frame, text="⟳ Refresh", command=on_refresh).pack(side="left")

        def on_save():
            # Save all displayed keywords
            display_text = self.filter_entry.get().strip()
            display_keywords = [k.strip() for k in display_text.split(",") if k.strip()]
            self.current_filter_input = ", ".join(display_keywords)
            self._save_filter_to_config(", ".join(display_keywords))

        def on_load():
            # Load config keywords and refresh display
            config_keywords = self.config.get("ui", {}).get(
                "related_filter_keywords", []
            )
            user_keywords = [
                k.strip() for k in self.current_filter_input.split(",") if k.strip()
            ]
            all_keywords = config_keywords + user_keywords
            seen = set()
            unique_keywords = []
            for k in all_keywords:
                if k not in seen:
                    unique_keywords.append(k)
                    seen.add(k)
            display_text = ", ".join(unique_keywords)
            self.filter_entry.delete(0, tk.END)
            self.filter_entry.insert(0, display_text)
            regex = self._build_complete_regex()
            self._apply_filter(regex)

        def on_add():
            # Add all displayed keywords to config
            display_text = self.filter_entry.get().strip()
            display_keywords = [k.strip() for k in display_text.split(",") if k.strip()]
            self.current_filter_input = ", ".join(display_keywords)
            self._add_filter_to_config(", ".join(display_keywords))

        ttk.Button(filter_frame, text="💾", width=2, command=on_save).pack(
            side="left", padx=(2, 0)
        )
        ttk.Button(filter_frame, text="📂", width=2, command=on_load).pack(
            side="left", padx=(2, 0)
        )
        ttk.Button(filter_frame, text="➕", width=2, command=on_add).pack(
            side="left", padx=(2, 0)
        )

    def _create_related_list(
        self, parent: tk.Widget, related_guids: list[dict]
    ) -> None:
        """Create the scrollable list of related GUIDs."""
        import re

        # Apply current filter (blacklist - exclude matching keywords)
        filtered = related_guids
        if self.current_filter_text:
            try:
                pattern = re.compile(self.current_filter_text, re.IGNORECASE)
                filtered = [
                    ref
                    for ref in related_guids
                    if not (
                        pattern.search(ref.get("element_name", ""))
                        or pattern.search(ref.get("context", ""))
                    )
                ]
            except re.error:
                filtered = related_guids

        # Check if we have results after filtering
        if not filtered:
            # Determine why there are no results
            if related_guids and self.current_filter_text:
                # The asset had related GUIDs, but the filter excluded all of them
                message_text = "No results match the current filter.\nTry adjusting or clearing the blacklist."
            else:
                # The asset has no related GUIDs at all
                message_text = "No related GUIDs found."

            tip_label = tk.Label(
                parent,
                text=message_text,
                font=("Arial", 10),
                foreground="gray",
                bg="white",
                justify="center",
                pady=20,
                padx=10,
            )
            tip_label.pack(anchor="center", expand=True, fill="both")
        else:
            # Scrollable container for related GUIDs - table-like appearance
            container = ttk.Frame(parent)
            container.pack(fill="both", expand=True)

            canvas = tk.Canvas(
                container,
                highlightthickness=1,
                highlightbackground="#cccccc",
                bg="white",
            )
            scrollbar = tk.Scrollbar(
                container, orient="vertical", command=canvas.yview, width=12
            )
            scrollable_frame = tk.Frame(canvas, bg="white")

            # Add related GUID links with table-like row styling
            for idx, ref in enumerate(filtered):
                guid = ref.get("guid", "???")
                element = ref.get("element_name", "???")
                context = ref.get("context", "???")
                link_text = f"{guid} (from <{element}> in {context})"

                is_not_found = is_guid_not_found(guid)

                # Create row frame with border separator
                row_frame = tk.Frame(scrollable_frame, bg="white", height=25)
                row_frame.pack(anchor="w", fill="x", padx=0, pady=0)

                # Add top border separator (except for first row)
                if idx > 0:
                    separator = tk.Frame(row_frame, bg="#eeeeee", height=1)
                    separator.pack(anchor="w", fill="x", padx=0, pady=0)

                if is_not_found:
                    link = tk.Label(
                        row_frame,
                        text=link_text,
                        foreground="gray",
                        font=("Courier", 9),
                        cursor="hand2",
                        bg="white",
                        justify="left",
                        anchor="w",
                        wraplength=400,
                    )
                    # Add element_name to filter on click
                    link.bind(
                        "<Button-1>", lambda e, el=element: self._add_to_filter(el)
                    )
                else:
                    link = tk.Label(
                        row_frame,
                        text=link_text,
                        foreground="darkblue",
                        font=("Courier", 9, "underline"),
                        cursor="hand2",
                        bg="white",
                        justify="left",
                        anchor="w",
                        wraplength=400,
                    )
                    link.bind("<Button-1>", lambda e, g=guid: self._navigate_to_guid(g))

                # Hover effect
                def on_enter(e, label=link):
                    label.config(bg="#f5f5f5")

                def on_leave(e, label=link):
                    label.config(bg="white")

                link.bind("<Enter>", on_enter)
                link.bind("<Leave>", on_leave)

                link.pack(anchor="w", fill="x", padx=8, pady=5, expand=False)

            # Attach scrollable_frame to canvas
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Mouse wheel scroll
            def on_scroll(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind_all("<MouseWheel>", on_scroll)

    def _keywords_to_regex(self, keywords_str: str) -> str:
        """Convert comma-separated keywords to regex blacklist pattern."""
        if not keywords_str.strip():
            return ""

        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        if not keywords:
            return ""

        import re

        escaped = [re.escape(k) for k in keywords]
        return "|".join(escaped)

    def _build_complete_regex(self) -> str:
        """Build regex combining both config keywords and user keywords."""
        config_keywords = self.config.get("ui", {}).get("related_filter_keywords", [])
        user_keywords = [
            k.strip() for k in self.current_filter_input.split(",") if k.strip()
        ]

        # Combine all keywords
        all_keywords = config_keywords + user_keywords

        # Remove duplicates
        seen = set()
        unique_keywords = []
        for k in all_keywords:
            if k not in seen:
                unique_keywords.append(k)
                seen.add(k)

        if not unique_keywords:
            return ""

        import re

        escaped = [re.escape(k) for k in unique_keywords]
        return "|".join(escaped)

    def _add_to_filter(self, element_name: str) -> None:
        """Add an element_name to the blacklist filter."""
        # Get current filter keywords
        current = self.current_filter_input.strip()

        # Parse current keywords
        keywords = [k.strip() for k in current.split(",") if k.strip()]

        # Add new element if not already present
        if element_name not in keywords:
            keywords.append(element_name)

        # Update filter input
        new_filter = ", ".join(keywords)
        self.current_filter_input = new_filter
        self.filter_has_been_edited = True

        # Convert to regex and apply (includes both config and user keywords)
        regex = self._build_complete_regex()
        self._apply_filter(regex)

        logger.info(f"Added '{element_name}' to blacklist filter")

    def _apply_filter(self, regex_pattern: str) -> None:
        """Re-display with new filter applied."""
        self.current_filter_text = regex_pattern

        if not self.current_asset_info or self.current_related_guids is None:
            return

        # Clear and redraw
        for widget in self.nav_info_frame.winfo_children():
            widget.destroy()

        self._create_asset_info_section(self.current_asset_info)
        self._create_related_guids_section(self.current_related_guids)

        self.parent.update_idletasks()

    def _save_filter_to_config(self, keywords: str) -> None:
        """Save filter keywords to config (RAM and file)."""
        try:
            import json
            from pathlib import Path

            # Update in-memory config
            if "ui" not in self.config:
                self.config["ui"] = {}

            keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
            self.config["ui"]["related_filter_keywords"] = keyword_list

            # Persist to file (convert Path objects to strings)
            config_path = Path("config.json")
            serializable_config = make_json_serializable(self.config)
            with open(config_path, "w") as f:
                json.dump(serializable_config, f, indent=4)

            logger.info(f"Saved filter keywords to config: {keyword_list}")
        except Exception as e:
            logger.error(f"Failed to save filter config: {e}")

    def _load_filter_from_config(self) -> str:
        """Load filter keywords from in-memory config."""
        try:
            keywords = self.config.get("ui", {}).get("related_filter_keywords", [])
            return ", ".join(keywords)
        except Exception as e:
            logger.error(f"Failed to load filter config: {e}")
            return ""

    def _add_filter_to_config(self, keywords: str) -> None:
        """Add filter keywords to in-memory config without overwriting existing ones."""
        try:
            import json
            from pathlib import Path

            # Initialize ui section if needed
            if "ui" not in self.config:
                self.config["ui"] = {}

            # Get existing keywords from in-memory config
            existing_keywords = self.config["ui"].get("related_filter_keywords", [])

            # Parse new keywords
            new_keywords = [k.strip() for k in keywords.split(",") if k.strip()]

            # Add new keywords without duplicates
            for keyword in new_keywords:
                if keyword not in existing_keywords:
                    existing_keywords.append(keyword)

            # Update in-memory config
            self.config["ui"]["related_filter_keywords"] = existing_keywords

            # Persist to file (convert Path objects to strings)
            config_path = Path("config.json")
            serializable_config = make_json_serializable(self.config)
            with open(config_path, "w") as f:
                json.dump(serializable_config, f, indent=4)

            logger.info(f"Added keywords to config: {new_keywords}")
            # Update the filter display to reflect the new config
            self._update_filter_display()
        except Exception as e:
            logger.error(f"Failed to add filter to config: {e}")

    def set_back_button_enabled(self, enabled: bool) -> None:
        """Enable/disable the back button."""
        if enabled:
            self.back_link.config(foreground="darkblue", cursor="hand2")
        else:
            self.back_link.config(foreground="gray", cursor="arrow")

    def pack(self, **kwargs) -> None:
        """Pack the widget frame."""
        self.frame.pack(**kwargs)
