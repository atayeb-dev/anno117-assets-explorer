"""
Asset Mapper Widget - Left panel of the Asset Explorer UI.

Handles asset template selection, filtering, and mapper execution.
"""

# ============================================================
# IMPORTS
# ============================================================

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..config import load_config
from ..utils import setup_logging

# ============================================================
# CONFIGURATION
# ============================================================

logger = setup_logging()
config = load_config()
ASSETS_DIR = config["paths"]["assets_unpack_dir"]

# ============================================================
# ASSET MAPPER WIDGET
# ============================================================


class AssetMapperWidget:
    """Widget for Assets Mapper - template selection and processing."""

    def __init__(self, parent, assets_dir: Path):
        """
        Initialize Asset Mapper widget.

        Args:
            parent: Parent tkinter widget.
            assets_dir: Path to assets directory.
        """
        self.parent = parent
        self.assets_dir = assets_dir
        self.all_assets = []

        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Assets Mapper", padding=10)

        self._setup_ui()
        self._update_asset_list()

    # ============================================================
    # UI SETUP
    # ============================================================

    def _setup_ui(self) -> None:
        """Set up the asset mapper UI components."""
        # Template Selection Frame
        template_frame = ttk.LabelFrame(
            self.frame, text="Template Selection", padding=10
        )
        template_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(template_frame, text="Template file:").pack(anchor="w", pady=(0, 5))

        self.asset_combo = ttk.Combobox(template_frame, state="readonly", width=30)
        self.asset_combo.pack(fill="x", pady=(0, 10))

        # Search/filter section - horizontal layout
        search_frame = ttk.Frame(template_frame)
        search_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(search_frame, text="Filter:").pack(side="left", padx=(0, 5))
        self.asset_filter_entry = ttk.Entry(search_frame)
        self.asset_filter_entry.pack(side="left", fill="x", expand=True)
        self.asset_filter_entry.bind("<KeyRelease>", lambda e: self._filter_assets())

        # Output Configuration Frame
        config_frame = ttk.LabelFrame(
            self.frame, text="Output Configuration", padding=10
        )
        config_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(config_frame, text="Output format:").pack(anchor="w", pady=(0, 5))
        self.format_combo = ttk.Combobox(
            config_frame, values=["python", "json"], state="readonly", width=30
        )
        self.format_combo.pack(fill="x", pady=(0, 10))
        self.format_combo.current(0)

        # CLI Filter frame - horizontal layout
        cli_frame = ttk.Frame(config_frame)
        cli_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(cli_frame, text="cli Filter:").pack(side="left", padx=(0, 5))
        self.filter_entry = ttk.Entry(cli_frame)
        self.filter_entry.pack(side="left", fill="x", expand=True)

        # Execution Frame
        execution_frame = ttk.LabelFrame(self.frame, text="Execution", padding=10)
        execution_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(
            execution_frame,
            text="Run Mapper",
            command=self._run_mapper,
        ).pack(side="left", padx=5, pady=5)

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
    # MAPPER EXECUTION
    # ============================================================

    def _run_mapper(self) -> None:
        """Run assets mapper with selected options."""
        selected_asset = self.asset_combo.get()
        selected_format = self.format_combo.get()
        filter_pattern = self.filter_entry.get().strip()

        if not selected_asset or not selected_format:
            messagebox.showerror("Error", "Please select an asset and output format.")
            return

        try:
            logger.info(f"Running Assets Mapper: {selected_asset} ({selected_format})")
            from ..routines import assets_mapper

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
                    "Error", "Assets mapper failed. Check logs for details."
                )
        except ModuleNotFoundError:
            logger.error("assets_mapper module not found")
            messagebox.showerror("Error", "assets_mapper module not found")
        except Exception as e:
            logger.error(f"Error running assets_mapper: {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")

    # ============================================================
    # PUBLIC INTERFACE
    # ============================================================

    def pack(self, **kwargs) -> None:
        """Pack the widget frame."""
        self.frame.pack(**kwargs)

    def refresh_asset_list(self) -> None:
        """Refresh the asset list (called when files change)."""
        self._update_asset_list()
