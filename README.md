# atayeb Assets Explorer

GUI utility for exploring Anno game assets by GUID lookup with intelligent caching.

If my work made your day better, consider [backing](https://ko-fi.com/atayeb) its creator.

**Version:** 0.2 | **Python:** 3.10+ | **Dependencies:** Standard Library Only

## Features

- **GUID Lookup** — Search for assets by GUID with cached results
- **Asset Browser** — Navigate related assets through template references
- **Blacklist Filter** — Filter out noise with config-based keyword blacklisting
- **Smart Cache** — Auto-reload when cache file changes (MTIME-based detection)
- **Smart Config** — Auto-reload when config changes (like cache)
- **CLI & GUI** — Both interfaces with shared caching and config
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

1. Search for assets by GUID
2. Browse related assets by clicking links
3. Blacklist keywords by clicking disabled (gray) links
4. Edit `config.json` to add/remove keywords from blacklist

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

Edit `config.json` to customize paths and blacklist keywords:

```json
{
    "paths": {
        "workdir": ".",
        "unpacked_dir": "unpacked",
        "rda_console_exec": "rda_console/RdaConsole.exe",
        "assets_xml": "unpacked/data/base/config/export/assets.xml",
        "assets_unpack_dir": "unpacked/assets",
        "gen_dir": "gen"
    },
    "ui": {
        "related_filter_keywords": [
            "BuildModeRandomRotation",
            "Value",
            "Amount"
        ]
    }
}
```

All paths are relative to the project directory and automatically converted to absolute paths.

## How It Works

**Caching** — Smart cache with MTIME-based auto-reload. Stores found assets and not-found markers. Automatically reloads when the cache file changes.

**Config Reload** — Configuration also supports MTIME-based auto-reload, just like cache. Reflects external changes instantly.

**Blacklist Filter** — Related GUIDs are filtered using keywords from config. Click disabled links in the UI to add keywords.

**UI Architecture** — Reactive interface that updates immediately when keywords are added. Single source of truth: config.json

## Troubleshooting

**GUID not found** — Results are cached. Use `python main.py --cli cache_manager --clear-not-found` to retry.

**RdaConsole missing** — Download from [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole) and place in `rda_console/`

**assets.xml missing** — Run `python main.py --cli extract_rda` first, or verify path in `config.json`

**Blacklist not updating** — Make sure config.json is saved. UI reloads automatically when file changes on disk.

## Resources

- [RdaConsole](https://github.com/anno-mods/RdaConsole) — Asset extraction tool
- [Python pathlib](https://docs.python.org/3/library/pathlib.html) — Path handling
- [Python xml.etree](https://docs.python.org/3/library/xml.etree.elementtree.html) — XML processing

## License

See LICENSE file for details.
