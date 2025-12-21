"""
Main UI module for Atayeb Assets Explorer.

Provides a tkinter-based graphical interface with buttons to launch various
extraction and processing utilities.
"""

# ============================================================
# IMPORTS
# ============================================================

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
# UI CLASS
# ============================================================


class AssetExplorerUI:
    """Main UI application for atayeb Assets Explorer."""

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

        # Configure styles for link-like buttons
        style = ttk.Style()
        style.configure(
            "Link.TLabel",
            foreground="darkblue",
            font=("Arial", 10, "underline"),
            cursor="hand2",
        )
        style.map("Link.TLabel", foreground=[("active", "red")])

        # Asset list storage for filtering
        self.all_assets = []

        # Start file system watcher
        self.observer = Observer()
        self.observer.schedule(
            AssetWatcher(self._update_asset_list),
            path=str(self.assets_dir),
            recursive=True,
        )
        self.observer.start()

        self._setup_ui()

        # Auto-size window to fit content
        self.root.update_idletasks()  # Force calculation of widget sizes
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

        # Initialization features.
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

        # Separator
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Assets Exporter frame
        reader_frame = ttk.LabelFrame(self.root, text="Assets Mapper", padding=10)
        reader_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(reader_frame, text="Template file:", font=("Arial", 9)).pack(
            anchor="w", pady=(5, 0)
        )

        self.asset_combo = ttk.Combobox(reader_frame, state="readonly", width=50)
        self.asset_combo.pack(fill="x", pady=5)

        # Search frame for asset filtering
        search_frame = ttk.Frame(reader_frame)
        ttk.Label(search_frame, text="Search:", font=("Arial", 9)).pack(
            side="left", padx=(0, 5)
        )
        self.asset_filter_entry = ttk.Entry(search_frame, width=30)
        self.asset_filter_entry.pack(side="left", fill="x", expand=True)
        self.asset_filter_entry.bind("<KeyRelease>", lambda e: self._filter_assets())

        search_frame.pack(fill="x", pady=(0, 5))
        self._update_asset_list()

        ttk.Label(reader_frame, text="Output format:", font=("Arial", 9)).pack(
            anchor="w", pady=(5, 0)
        )
        self.format_combo = ttk.Combobox(
            reader_frame, values=["python", "json"], state="readonly", width=50
        )
        self.format_combo.pack(fill="x", pady=5)
        self.format_combo.current(0)

        cli_frame = ttk.Frame(reader_frame)
        ttk.Label(cli_frame, text="cli Filter:", font=("Arial", 9)).pack(
            side="left", padx=(0, 5)
        )
        self.filter_entry = ttk.Entry(cli_frame)
        self.filter_entry.pack(fill="x", expand=True)
        cli_frame.pack(fill="x", pady=(0, 5))

        reader_button_frame = ttk.Frame(reader_frame)
        reader_button_frame.pack(fill="x", pady=10)

        ttk.Button(
            reader_button_frame,
            text="Run Assets Mapper",
            command=self._run_assets_mapper,
        ).pack(side="left", padx=5)

        # Separator
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Footer
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
    # EVENT HANDLERS
    # ============================================================

    def _on_initialization_clicked(self, skip_rda: bool) -> None:
        """Handle Extract RDA & Unpack Assets button click."""
        try:
            if not skip_rda:
                logger.info("Launching Extract RDA module...")

                from .routines import extract_rda

                # Call extract_rda.main([]) with empty args to ignore sys.argv
                result = extract_rda.main([])
                if result != 0:
                    messagebox.showerror(
                        "Error", "RDA extraction failed. Check logs for details."
                    )
                    return
                logger.info("RDA extraction completed, now unpacking assets...")

            from .routines import unpack_assets

            # Unpack assets with default regex (empty = all assets)
            result = unpack_assets.main(
                ["-a", str(self.assets_xml)] if not skip_rda else []
            )
            if result == 0:
                messagebox.showinfo(
                    "Success",
                    "RDA extraction and asset unpacking completed successfully!",
                )
                # Refresh asset list
                self._update_asset_list()
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
    # ASSET MANAGEMENT
    # ============================================================

    def _update_asset_list(self) -> None:
        """Update the list of available assets from unpacked/assets/."""
        if self.assets_dir.exists():
            self.all_assets = sorted([f.name for f in self.assets_dir.glob("*.xml")])
            self.asset_combo["values"] = self.all_assets
            if self.all_assets:
                self.asset_combo.current(0)
                logger.info(f"Loaded {len(self.all_assets)} assets files")
        else:
            self.all_assets = []
            self.asset_combo["values"] = []
            logger.warning("Assets directory not found")

        # Clear filter when refreshing
        self.asset_filter_entry.delete(0, tk.END)

    def _filter_assets(self) -> None:
        """Filter asset list based on search input."""
        filter_text = self.asset_filter_entry.get().lower()

        if not filter_text:
            # Show all assets if filter is empty
            self.asset_combo["values"] = self.all_assets
        else:
            # Filter assets that contain the search text
            filtered = [t for t in self.all_assets if filter_text in t.lower()]
            self.asset_combo["values"] = filtered

        # Auto-select first result if available
        if self.asset_combo["values"]:
            self.asset_combo.current(0)

    # ============================================================
    # ASSET MAPPER
    # ============================================================

    def _run_assets_mapper(self) -> None:
        """Run assets mapper with selected options."""
        selected_asset = self.asset_combo.get()
        selected_format = self.format_combo.get()
        filter_pattern = self.filter_entry.get().strip()

        if not selected_asset or not selected_format:
            messagebox.showerror("Error", "Please select an asset and output format.")
            return

        try:
            logger.info(
                f"Running Assets Exporter: {selected_asset} ({selected_format})"
            )
            from .routines import assets_mapper

            args = ["-t", selected_asset, "-of", selected_format]
            if filter_pattern:
                args.extend(["--filter", filter_pattern])

            result = assets_mapper.main(args)

            if result == 0:
                messagebox.showinfo(
                    "Success",
                    f"Asset mapping generated to gen/ ({selected_format} format)!",
                )
            else:
                messagebox.showerror(
                    "Error", "Assets exporter failed. Check logs for details."
                )
        except ModuleNotFoundError:
            logger.error("assets_mapper module not found")
            messagebox.showerror("Error", "assets_mapper module not found")
        except Exception as e:
            logger.error(f"Error running assets_mapper: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")

    def run(self) -> None:
        """Start the UI application."""
        self.root.mainloop()

    # ============================================================
    # LIFECYCLE
    # ============================================================

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
        app.run()
        return 0
    except Exception as e:
        logger.error(f"UI error: {e}")
        return 1


# Alias for compatibility
ui = main


if __name__ == "__main__":
    sys.exit(main())
