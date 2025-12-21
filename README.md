# atayeb Assets Explorer

GUI utility for exploring Anno game assets by GUID lookup with intelligent caching.

If my work made your day better, consider [backing](https://ko-fi.com/atayeb) its creator.

**Version:** 0.2 | **Python:** 3.10+ | **Dependencies:** Standard Library Only

## Features

- **GUID Lookup** — Search for assets by GUID with instant cached results
- **Asset Browser** — Navigate related assets through template references
- **Smart Cache** — Caches found/not-found GUIDs to avoid redundant searches
- **CLI & GUI** — Both interfaces with shared caching
- **Asset Management** — Extract RDA archives, unpack assets, generate mappings

## Requirements

- Python 3.10+
- RdaConsole.exe (download from [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole)) (optional)

## Installation

```bash
# Clone repository
git clone <repository-url>
cd atayeb-assets-explorer

# Download RdaConsole.exe from https://github.com/anno-mods/RdaConsole
# Place it in rda_console/ directory
```

## Quick Start

### GUI Mode (Recommended)

```bash
python main.py --ui
```

Search for assets by GUID. The app caches results automatically.

### CLI Mode

```bash
# Search for a GUID
python main.py --cli asset_finder --guid 12345678 --json

# Extract RDA files
python main.py --cli extract_rda -i "annodata_00.rda"

# Unpack XML assets
python main.py --cli unpack_assets -a "assets.xml"

# Generate asset mappings
python main.py --cli assets_mapper -t "AssetPool.xml"

# Manage cache
python main.py --cli cache_manager --clear-not-found
```

## Commands

### asset_finder (GUID Search)

```bash
python main.py --cli asset_finder [OPTIONS]
  --guid GUID                     GUID to search for (required)
  --json                          Output as JSON
```

### cache_manager

```bash
python main.py --cli cache_manager [OPTIONS]
  --clear-not-found              Clear only not-found entries
  --clear-all                    Clear entire cache
```

### extract_rda

```bash
python main.py --cli extract_rda [OPTIONS]
  -i, --input PATH               RDA file to extract
  -o, --output PATH              Output directory (default: unpacked)
  --filter REGEX                 Filter by regex
```

### unpack_assets

```bash
python main.py --cli unpack_assets [OPTIONS]
  -a, --assets-file PATH         Path to assets.xml
  -o, --output PATH              Output directory (default: unpacked/assets)
  --filter REGEX                 Filter by regex
```

### assets_mapper

```bash
python main.py --cli assets_mapper [OPTIONS]
  -t, --template STRING          Asset XML filename (required)
  -of, --output-format FORMAT    python or json (default: python)
  --filter REGEX                 Filter asset names
```

## Configuration

Edit `config.json` to customize paths:

```json
{
    "paths": {
        "workdir": ".",
        "unpacked_dir": "unpacked",
        "rda_console_exec": "rda_console/RdaConsole.exe",
        "assets_xml": "unpacked/data/base/config/export/assets.xml",
        "assets_unpack_dir": "unpacked/assets",
        "gen_dir": "gen"
    }
}
```

All paths are relative to the project directory and automatically converted to absolute paths.

## Architecture

**Caching System** — Unified cache stores found assets and not-found markers. Auto-reloads when CLI modifies the cache file.

**UI Layer** — Central data manager coordinating GUID searches, browser navigation, and cache interactions.

**CLI Modules** — Separate routines (asset_finder, extract_rda, etc.) using shared cache and configuration.

## Project Structure

```
src/
├── ui.py                      # GUI: GUID search, asset browser
├── cache.py                   # Unified cache with auto-reload
├── config.py                  # Configuration loader
├── utils.py                   # Shared utilities
├── routines/
│   ├── asset_finder.py       # GUID search CLI
│   ├── cache_manager.py      # Cache management CLI
│   ├── extract_rda.py        # RDA extraction
│   ├── unpack_assets.py      # XML unpacking
│   └── assets_mapper.py       # Name→GUID mapping
└── ui_components/
    ├── browser.py            # Asset browser widget
    └── mapper.py             # Asset mapper widget

.cache/assets.json            # Cache file (auto-created)
```

## Troubleshooting

**GUID not found** — Results are cached. Use `python main.py --cli cache_manager --clear-not-found` to retry.

**RdaConsole missing** — Download from [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole) and place in `rda_console/`

**assets.xml missing** — Run `python main.py --cli extract_rda` first, or verify path in `config.json`

## Resources

- [RdaConsole](https://github.com/anno-mods/RdaConsole) — Asset extraction tool
- [Python pathlib](https://docs.python.org/3/library/pathlib.html) — Path handling
- [Python xml.etree](https://docs.python.org/3/library/xml.etree.elementtree.html) — XML processing

## License

See LICENSE file for details.
