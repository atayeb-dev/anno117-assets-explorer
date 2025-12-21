"""
Main UI module for Atayeb Assets Explorer.

Data manager - handles CLI calls, cache updates, history, GUID updates.
Coordinates between pure UI widgets and data sources.

Architecture:
- ui.py: Data manager - handles CLI calls, cache updates, history, GUID updates
- ui_components/: Pure UI components (mapper/browser) - communicate with ui.py via callbacks
- Cache: Persists not-found GUIDs to avoid redundant CLI calls
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .cache import get_cached_asset, set_guid_not_found, reload_cache
from .config import load_config
from .utils import setup_logging
from .ui_components.mapper import AssetMapperWidget
from .ui_components.browser import AssetBrowserWidget

# ============================================================
# CONFIGURATION
# ============================================================

logger = setup_logging()
config = load_config()
ASSETS_XML = config["paths"]["assets_xml"]
ASSETS_DIR = config["paths"]["assets_unpack_dir"]
APP_TITLE = "atayeb Assets Explorer"

# ============================================================
# FILE SYSTEM WATCHER
# ============================================================


class AssetWatcher(FileSystemEventHandler):
    """Watch assets directory for changes and trigger UI updates."""

    def __init__(self, callback):
        """Initialize watcher with callback function."""
        self.callback = callback

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory or not event.src_path.endswith(".xml"):
            return
        self.callback()

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory or not event.src_path.endswith(".xml"):
            return
        self.callback()

    def on_deleted(self, event):
        """Handle file deletion events."""
        if event.is_directory or not event.src_path.endswith(".xml"):
            return
        self.callback()


# ============================================================
# MAIN UI CLASS - DATA MANAGER
# ============================================================


class AssetExplorerUI:
    """
    Main UI application for atayeb Assets Explorer.

    Responsibilities:
    - Manage all CLI calls for asset finding/mapping
    - Update cache after CLI calls for data consistency
    - Manage GUID history for back button navigation
    - Update current_guid_var which triggers reactive updates in widgets
    - Coordinate between widgets and data sources
    """

    def __init__(
        self,
        root: tk.Tk,
        assets_xml: Path,
        assets_dir: Path,
    ):
        """
        Initialize the UI application.

        Args:
            root: Tkinter root window.
            assets_xml: Path to assets.xml.
            assets_dir: Path to assets directory.
        """
        self.root = root
        self.root.title(APP_TITLE)

        # Store provided paths
        self.assets_xml = assets_xml
        self.assets_dir = assets_dir

        # ============================================================
        # DATA MANAGEMENT STATE
        # ============================================================

        # Track current displayed GUID (reactive - changes trigger UI update)
        self.current_guid_var = tk.StringVar()

        # History for browser navigation (like real browser history)
        self.guid_history = []  # List of all viewed GUIDs
        self.history_index = -1  # Current position in history

        # Start file system watcher
        self.observer = Observer()
        self.observer.schedule(
            AssetWatcher(self._on_assets_changed),
            path=str(self.assets_dir),
            recursive=True,
        )
        self.observer.start()

        # Setup UI with widgets
        self._setup_ui()

        # Hook browser widget to notify on GUID changes from user
        self.browser_widget.on_guid_requested = self._handle_new_guid_search
        self.browser_widget.on_related_guid_clicked = self._handle_related_guid_clicked
        self.browser_widget.on_back_clicked = self.handle_back_clicked

        # Auto-size window to fit content
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        self.root.geometry(f"{width}x{height}")

    # ============================================================
    # UI SETUP
    # ============================================================

    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        # Title frame
        title_frame = ttk.Frame(self.root)
        title_frame.pack(pady=10)

        title_label = ttk.Label(
            title_frame,
            text="Explore assets",
            font=("Arial", 16, "bold"),
        )
        title_label.pack()

        # Initialization features (Unpack RDA / Unpack from assets file)
        self._setup_init_links()

        # Separator
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Main content: Mapper (left) + Browser (right)
        main_container = ttk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Asset Mapper (left side)
        self.mapper_widget = AssetMapperWidget(main_container, self.assets_dir)
        self.mapper_widget.pack(side="left", fill="both", padx=(0, 5))

        # Asset Browser (right side)
        self.browser_widget = AssetBrowserWidget(
            main_container, self.assets_dir, self.current_guid_var
        )
        self.browser_widget.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Separator
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Footer
        self._setup_footer()

    def _setup_init_links(self) -> None:
        """Set up initialization links (Unpack RDA / assets file)."""
        init_frame = ttk.Frame(self.root)
        init_frame.pack(pady=10)

        # Unpack from RDA link
        link = ttk.Label(init_frame, text="Unpack from RDA", style="Link.TLabel")
        link.pack(side="left", padx=10)
        link.bind(
            "<Button-1>", lambda e: self._on_initialization_clicked(skip_rda=False)
        )

        # Separator between links
        ttk.Separator(init_frame, orient="vertical").pack(side="left", fill="y", padx=5)

        # Unpack from Assets file link
        link = ttk.Label(
            init_frame, text="Unpack from assets file", style="Link.TLabel"
        )
        link.pack(side="left", padx=10)
        link.bind("<Button-1>", lambda e: self._on_initialization_clicked(True))

        # Configure link style
        style = ttk.Style()
        style.configure(
            "Link.TLabel",
            foreground="darkblue",
            font=("Arial", 10, "underline"),
            cursor="hand2",
        )
        style.map("Link.TLabel", foreground=[("active", "red")])

    def _setup_footer(self) -> None:
        """Set up footer with description."""
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(pady=10)

        footer_label = ttk.Label(
            footer_frame,
            text="Assets extraction utility",
            font=("Arial", 9),
            foreground="gray",
        )
        footer_label.pack()

    # ============================================================
    # DATA MANAGEMENT - GUID REQUESTS FROM WIDGETS
    # ============================================================

    def _handle_new_guid_search(self, guid: str) -> None:
        """
        Handle a new GUID search from the search button.

        Resets history to start a new navigation sequence.

        Args:
            guid: The GUID to search for
        """
        logger.info(f"New GUID search: {guid}")
        # Clear history on new search
        self.guid_history = []
        self.history_index = -1
        # Process the GUID
        self._process_guid_request(guid)

    def _handle_related_guid_clicked(self, guid: str) -> None:
        """
        Handle a related GUID link click.

        Continues the current navigation history.

        Args:
            guid: The GUID to navigate to
        """
        logger.info(f"Related GUID clicked: {guid}")
        # Continue history (don't clear)
        self._process_guid_request(guid)

    def _process_guid_request(self, guid: str) -> None:
        """
        Process a GUID request from widgets.

        Common logic for all GUID changes.
        Ensures all data goes through cache + CLI + history chain.

        Args:
            guid: The GUID to search for
        """
        guid = guid.strip()
        logger.debug(f"Processing GUID request: {guid}")

        # Step 1: Check if GUID is cached (asset or not-found)
        cached = get_cached_asset(guid)
        if cached is not None:
            # If cached as "not found", display error
            if cached.get("not_found", False):
                logger.debug(f"Cache hit: GUID {guid} is marked as not found")
                self.browser_widget.display_not_found(guid)
            else:
                # Cached asset found (CLI already ran earlier)
                logger.debug(f"Cache hit: GUID {guid} found, displaying cached asset")
                # For cached assets, we don't have related_guids, but that's OK
                # The browser widget will display just the main asset info
                self.browser_widget.display_asset_info(guid, cached, [])
            self._add_to_history(guid)
            return

        # Step 2: Not in cache, call CLI to fetch asset info
        asset_info, related_guids = self._fetch_asset_from_cli(guid)

        if asset_info is None:
            # Not found - cache it and display error
            logger.info(f"CLI: GUID {guid} not found, caching...")
            set_guid_not_found(guid)
            self.browser_widget.display_not_found(guid)
            self._add_to_history(guid)
            return

        # Step 3: Cache is already updated by CLI call, display results
        logger.debug(f"CLI success: asset found, displaying...")
        self.browser_widget.display_asset_info(guid, asset_info, related_guids)
        self._add_to_history(guid)

    def _display_guid_from_history(self, guid: str) -> None:
        """
        Display a GUID from navigation history without modifying history.

        Used by back button navigation - just displays without re-adding to history.

        Args:
            guid: The GUID to display
        """
        guid = guid.strip()
        logger.debug(f"Displaying GUID from history: {guid}")

        # Step 1: Check if GUID is cached (asset or not-found)
        cached = get_cached_asset(guid)
        if cached is not None:
            # If cached as "not found", display error
            if cached.get("not_found", False):
                logger.debug(f"Cache hit: GUID {guid} is marked as not found")
                self.browser_widget.display_not_found(guid)
            else:
                # Cached asset found (CLI already ran earlier)
                logger.debug(f"Cache hit: GUID {guid} found, displaying cached asset")
                self.browser_widget.display_asset_info(guid, cached, [])
            return

        # Step 2: Not in cache, call CLI to fetch asset info
        asset_info, related_guids = self._fetch_asset_from_cli(guid)

        if asset_info is None:
            # Not found - cache it and display error
            logger.debug(f"CLI: GUID {guid} not found")
            self.browser_widget.display_not_found(guid)
            return

        # Step 3: Display results
        logger.debug(f"Displaying asset for {guid}")
        self.browser_widget.display_asset_info(guid, asset_info, related_guids)

    def _fetch_asset_from_cli(self, guid: str) -> tuple:
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
                str(Path(__file__).parent.parent / "main.py"),
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

    def _add_to_history(self, guid: str) -> None:
        """
        Add a GUID to history and update history_index.

        Handles the case where user came back and is now navigating forward.

        Args:
            guid: The GUID to add to history
        """
        if self.history_index == len(self.guid_history) - 1:
            # We're at the end of history, append new GUID
            self.guid_history.append(guid)
            self.history_index += 1
            logger.debug(f"Added {guid} to history (index {self.history_index})")
        elif self.history_index < len(self.guid_history) - 1:
            # We're in the middle (came from back), truncate future and add new
            self.guid_history = self.guid_history[: self.history_index + 1]
            self.guid_history.append(guid)
            self.history_index += 1
            logger.debug(
                f"Truncated history and added {guid} (index {self.history_index})"
            )
        else:
            # First GUID
            self.guid_history = [guid]
            self.history_index = 0
            logger.debug(f"First GUID in history: {guid}")

        # Update back button state in browser
        self.browser_widget.set_back_button_enabled(self.history_index > 0)

    def handle_back_clicked(self) -> None:
        """Handle back button click - navigate to previous GUID in history."""
        if self.history_index <= 0:
            logger.info("No history to go back to")
            return

        self.history_index -= 1
        previous_guid = self.guid_history[self.history_index]
        logger.info(f"Back to GUID: {previous_guid}")

        # Display from history without modifying history again
        self._display_guid_from_history(previous_guid)

        # Update back button state
        self.browser_widget.set_back_button_enabled(self.history_index > 0)

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_assets_changed(self) -> None:
        """Handle assets directory changes - refresh asset list."""
        logger.info("Assets directory changed, refreshing asset list")
        self.mapper_widget.refresh_asset_list()

    def _on_initialization_clicked(self, skip_rda: bool) -> None:
        """Handle Extract RDA & Unpack Assets button click."""
        try:
            if not skip_rda:
                logger.info("Launching Extract RDA module...")

                from .routines import extract_rda

                result = extract_rda.main([])
                if result != 0:
                    messagebox.showerror(
                        "Error", "RDA extraction failed. Check logs for details."
                    )
                    return
                logger.info("RDA extraction completed, now unpacking assets...")

            from .routines import unpack_assets

            result = unpack_assets.main(
                ["-a", str(self.assets_xml)] if not skip_rda else []
            )
            if result == 0:
                messagebox.showinfo(
                    "Success",
                    "RDA extraction and asset unpacking completed successfully!",
                )
                # Refresh asset list
                self.mapper_widget.refresh_asset_list()
            else:
                messagebox.showerror(
                    "Error", "Asset unpacking failed. Check logs for details."
                )
        except ModuleNotFoundError as e:
            logger.error(f"Module not found: {e}")
            messagebox.showerror("Error", f"Module not found: {e}")
        except Exception as e:
            logger.error(f"Error: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def run(self) -> None:
        """Start the UI application."""
        self.root.mainloop()

    def _on_closing(self) -> None:
        """Handle window close event."""
        logger.info("Closing application...")
        self.observer.stop()
        self.observer.join()
        self.root.destroy()
        sys.exit(0)


# ============================================================
# MAIN
# ============================================================


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the UI application.

    Args:
        args: Command-line arguments:
              [-a ASSETS_XML] [-ad ASSETS_DIR]

    Returns:
        Exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description="atayeb Assets Explorer UI")
    parser.add_argument(
        "-a",
        "--assets-xml",
        type=Path,
        default=ASSETS_XML,
        help=f"Custom path to assets.xml file (default: {ASSETS_XML})",
    )
    parser.add_argument(
        "-ad",
        "--assets-dir",
        type=Path,
        default=ASSETS_DIR,
        help=f"Custom path to assets directory (default: {ASSETS_DIR})",
    )

    try:
        parsed = parser.parse_args(args or [])

        root = tk.Tk()
        app = AssetExplorerUI(
            root, assets_xml=parsed.assets_xml, assets_dir=parsed.assets_dir
        )
        root.protocol("WM_DELETE_WINDOW", app._on_closing)
        app.run()
        return 0
    except Exception as e:
        logger.error(f"UI error: {e}")
        return 1


# Alias for compatibility
ui = main


if __name__ == "__main__":
    sys.exit(main())
