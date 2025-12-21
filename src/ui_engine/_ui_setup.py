"""
UI setup helper for Asset Explorer.

Handles all UI component creation and configuration.
"""

import tkinter as tk
from tkinter import ttk

from ..utils import setup_logging
from .mapper import AssetMapperWidget
from .browser import AssetBrowserWidget

logger = setup_logging()


class UISetup:
    """Helper class for setting up UI components."""

    @staticmethod
    def setup_main_ui(root: tk.Tk, assets_dir) -> tuple:
        """
        Set up the main UI components.

        Args:
            root: Tkinter root window
            assets_dir: Path to assets directory

        Returns:
            Tuple of (mapper_widget, browser_widget, current_guid_var)
        """
        # Title frame
        title_frame = ttk.Frame(root)
        title_frame.pack(pady=10)

        title_label = ttk.Label(
            title_frame,
            text="Explore assets",
            font=("Arial", 16, "bold"),
        )
        title_label.pack()

        # Initialization links
        UISetup._setup_init_links(root)

        # Separator
        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Main content: Mapper (left) + Browser (right)
        main_container = ttk.Frame(root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Asset Mapper (left side)
        mapper_widget = AssetMapperWidget(main_container, assets_dir)
        mapper_widget.pack(side="left", fill="both", padx=(0, 5))

        # Current GUID tracking for reactive updates
        current_guid_var = tk.StringVar()

        # Asset Browser (right side)
        browser_widget = AssetBrowserWidget(
            main_container, assets_dir, current_guid_var
        )
        browser_widget.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Separator
        ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)

        # Footer
        UISetup._setup_footer(root)

        return mapper_widget, browser_widget, current_guid_var

    @staticmethod
    def _setup_init_links(root: tk.Tk) -> None:
        """Set up initialization links (Unpack RDA / assets file)."""
        init_frame = ttk.Frame(root)
        init_frame.pack(pady=10)

        # Unpack from RDA link
        link = ttk.Label(init_frame, text="Unpack from RDA", style="Link.TLabel")
        link.pack(side="left", padx=10)
        link.bind("<Button-1>", lambda e: None)  # Callback set by main UI

        # Separator between links
        ttk.Separator(init_frame, orient="vertical").pack(side="left", fill="y", padx=5)

        # Unpack from Assets file link
        link = ttk.Label(
            init_frame, text="Unpack from assets file", style="Link.TLabel"
        )
        link.pack(side="left", padx=10)
        link.bind("<Button-1>", lambda e: None)  # Callback set by main UI

        # Configure link style
        style = ttk.Style()
        style.configure(
            "Link.TLabel",
            foreground="darkblue",
            font=("Arial", 10, "underline"),
            cursor="hand2",
        )
        style.map("Link.TLabel", foreground=[("active", "red")])

    @staticmethod
    def _setup_footer(root: tk.Tk) -> None:
        """Set up footer with description."""
        footer_frame = ttk.Frame(root)
        footer_frame.pack(pady=10)

        footer_label = ttk.Label(
            footer_frame,
            text="Assets extraction utility",
            font=("Arial", 9),
            foreground="gray",
        )
        footer_label.pack()
