"""
Main UI module for Atayeb Assets Explorer.

Data manager - coordinates between UI widgets and data sources.
Handles GUID searches, caching, and navigation history.

Architecture:
- ui.py: Main data manager - UI coordination and GUID requests
- ui_engine/: UI components, setup, and CLI management
  - browser.py: Asset browser widget
  - mapper.py: Asset mapper widget
  - _cli_manager.py: Subprocess CLI interactions
  - _ui_setup.py: UI component initialization
- cache.py: Asset and not-found GUID persistence
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .ui_engine._cli_manager import CLIManager
from .ui_engine._ui_setup import UISetup
from .cache import get_cached_asset, set_guid_not_found
from .config import load_config
from .utils import setup_logging

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
# MAIN UI CLASS
# ============================================================


class AssetExplorerUI:
    """
    Main UI application for atayeb Assets Explorer.

    Responsibilities:
    - Coordinate GUID searches through cache or CLI
    - Manage browser history and navigation
    - Update widgets based on search results
    - Handle file system changes
    """

    def __init__(
        self,
        root: tk.Tk,
        assets_xml: Path,
        assets_dir: Path,
        config: dict,
    ):
        """
        Initialize the UI application.

        Args:
            root: Tkinter root window.
            assets_xml: Path to assets.xml.
            assets_dir: Path to assets directory.
            config: Shared config dict instance (loaded once at app startup).
        """
        self.root = root
        self.root.title(APP_TITLE)

        # Store paths and config
        self.assets_xml = assets_xml
        self.assets_dir = assets_dir
        self.config = config  # Shared config instance

        # CLI manager for subprocess calls
        self.cli_manager = CLIManager(assets_dir)

        # ============================================================
        # UI STATE
        # ============================================================

        # GUID history for back button navigation
        self.guid_history = []
        self.history_index = -1

        # Setup UI and get widgets - pass shared config
        (
            self.mapper_widget,
            self.browser_widget,
            self.current_guid_var,
        ) = UISetup.setup_main_ui(root, assets_dir, config)

        # Setup file system watcher
        self.observer = Observer()
        self.observer.schedule(
            AssetWatcher(self._on_assets_changed),
            path=str(self.assets_dir),
            recursive=True,
        )
        self.observer.start()

        # Hook browser widget callbacks
        self.browser_widget.on_guid_requested = self._handle_new_guid_search
        self.browser_widget.on_related_guid_clicked = self._handle_related_guid_clicked
        self.browser_widget.on_back_clicked = self.handle_back_clicked

        # Setup initialization links
        self._setup_init_link_callbacks()

        # Auto-size window with minimum of 960x600
        self.root.update_idletasks()
        width = max(960, self.root.winfo_reqwidth())
        height = max(600, self.root.winfo_reqheight())
        self.root.geometry(f"{width}x{height}")

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def _setup_init_link_callbacks(self) -> None:
        """Set up callbacks for initialization links."""
        # Find the init frame links and bind callbacks
        for widget in self.root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Label) and "Unpack from RDA" in child.cget(
                        "text"
                    ):
                        child.bind(
                            "<Button-1>",
                            lambda e: self._on_initialization_clicked(skip_rda=False),
                        )
                    elif isinstance(
                        child, ttk.Label
                    ) and "Unpack from assets file" in child.cget("text"):
                        child.bind(
                            "<Button-1>",
                            lambda e: self._on_initialization_clicked(True),
                        )

    # ============================================================
    # GUID REQUEST HANDLING
    # ============================================================

    def _handle_new_guid_search(self, guid: str) -> None:
        """Handle a new GUID search (resets history)."""
        logger.info(f"New GUID search: {guid}")
        self.guid_history = []
        self.history_index = -1
        self._process_guid_request(guid)

    def _handle_related_guid_clicked(self, guid: str) -> None:
        """Handle a related GUID click (continues history)."""
        logger.info(f"Related GUID clicked: {guid}")
        self._process_guid_request(guid)

    def _process_guid_request(self, guid: str) -> None:
        """Process a GUID search request."""
        guid = guid.strip()
        logger.debug(f"Processing GUID: {guid}")

        # Check cache first (for asset info only)
        cached = get_cached_asset(guid)
        if cached is not None:
            if cached.get("not_found", False):
                logger.debug(f"Cache hit: {guid} marked as not found")
                self.browser_widget.display_not_found(guid)
            else:
                logger.debug(f"Cache hit: displaying {guid}")
                # Get related GUIDs fresh (takes ~5ms, not worth caching)
                related_guids = self.cli_manager.fetch_related_guids(guid)
                self.browser_widget.display_asset_info(guid, cached, related_guids)
            self._add_to_history(guid)
            return

        # Not cached, call CLI to fetch asset info and related GUIDs
        asset_info, related_guids = self.cli_manager.fetch_asset_info(guid)

        if asset_info is None:
            logger.info(f"CLI: {guid} not found, caching...")
            set_guid_not_found(guid)
            self.browser_widget.display_not_found(guid)
            self._add_to_history(guid)
            return

        logger.debug(f"CLI success: {guid} found with {len(related_guids)} related")
        # Cache the asset info (related_guids are calculated on demand)
        from .cache import set_cached_asset

        set_cached_asset(guid, asset_info)
        self.browser_widget.display_asset_info(guid, asset_info, related_guids)
        self._add_to_history(guid)

    def _display_guid_from_history(self, guid: str) -> None:
        """Display a GUID from history without modifying it."""
        guid = guid.strip()
        logger.debug(f"Displaying from history: {guid}")

        # Check cache for asset info
        asset_info = get_cached_asset(guid)
        if asset_info is not None:
            if asset_info.get("not_found", False):
                logger.debug(f"Cache hit: {guid} marked as not found")
                self.browser_widget.display_not_found(guid)
            else:
                logger.debug(f"Cache hit: displaying {guid} from history")
                # Get related GUIDs fresh (takes ~5ms, not worth caching)
                related_guids = self.cli_manager.fetch_related_guids(guid)
                self.browser_widget.display_asset_info(guid, asset_info, related_guids)
            return

        # Not cached, call CLI to fetch asset info and related GUIDs
        asset_info, related_guids = self.cli_manager.fetch_asset_info(guid)

        if asset_info is None:
            logger.debug(f"CLI: {guid} not found")
            self.browser_widget.display_not_found(guid)
            return

        logger.debug(
            f"Displaying {guid} from history with {len(related_guids)} related"
        )
        self.browser_widget.display_asset_info(guid, asset_info, related_guids)

    def _add_to_history(self, guid: str) -> None:
        """Add GUID to history and update back button."""
        if self.history_index == len(self.guid_history) - 1:
            # At end of history, append
            self.guid_history.append(guid)
            self.history_index += 1
        elif self.history_index < len(self.guid_history) - 1:
            # In middle of history, truncate and add
            self.guid_history = self.guid_history[: self.history_index + 1]
            self.guid_history.append(guid)
            self.history_index += 1
        else:
            # First GUID
            self.guid_history = [guid]
            self.history_index = 0

        self.browser_widget.set_back_button_enabled(self.history_index > 0)

    def handle_back_clicked(self) -> None:
        """Handle back button click."""
        if self.history_index <= 0:
            logger.info("No history to go back")
            return

        self.history_index -= 1
        previous_guid = self.guid_history[self.history_index]
        logger.info(f"Back to GUID: {previous_guid}")

        self._display_guid_from_history(previous_guid)
        self.browser_widget.set_back_button_enabled(self.history_index > 0)

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_assets_changed(self) -> None:
        """Handle assets directory changes."""
        logger.info("Assets directory changed")
        self.mapper_widget.refresh_asset_list()

    def _on_initialization_clicked(self, skip_rda: bool) -> None:
        """Handle initialization button click."""
        try:
            if not skip_rda:
                logger.info("Extracting RDA...")
                from .routines import extract_rda

                if extract_rda.main([]) != 0:
                    messagebox.showerror("Error", "RDA extraction failed")
                    return
                logger.info("RDA extraction done, unpacking assets...")

            from .routines import unpack_assets

            result = unpack_assets.main(
                ["-a", str(self.assets_xml)] if not skip_rda else []
            )
            if result == 0:
                messagebox.showinfo(
                    "Success",
                    "RDA extraction and asset unpacking completed!",
                )
                self.mapper_widget.refresh_asset_list()
            else:
                messagebox.showerror("Error", "Asset unpacking failed")
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

    CONFIG LOADING & SHARING:
    The config is loaded exactly ONCE at app startup and then shared across
    all UI components (browser widget, mapper, etc.). This ensures:
    - Single source of truth in RAM (not re-read from file on every operation)
    - All modifications (save/load/add of filters) work with shared config
    - Custom config files (with --config from main.py) are merged before UI starts

    All save/load/add operations:
    - SAVE: Updates RAM config AND writes to config.json
    - ADD: Merges new keywords in RAM config AND writes to config.json
    - LOAD: Reads from RAM config (never re-reads from file)

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

        # Load config once at startup (shared across all UI components)
        app_config = load_config()

        root = tk.Tk()
        app = AssetExplorerUI(
            root,
            assets_xml=parsed.assets_xml,
            assets_dir=parsed.assets_dir,
            config=app_config,
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
