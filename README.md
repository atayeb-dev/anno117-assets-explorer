# Atayeb Assets Explorer

CLI utility for exploring, extracting, and analyzing Anno game assets with smart caching and configuration reload.

If my work made your day better, consider [backing](https://ko-fi.com/atayeb) its creator.

**Version:** 0.2 | **Python:** 3.10+ | **Dependencies:** None (Standard Library only)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)

## Features

- ✅ **GUID Lookup** — Search assets by GUID
- ✅ **RDA Extraction** — Extract RDA archives using RdaConsole.exe
- ✅ **Asset Mapping** — Generate name-to-GUID mappings (Python or JSON)
- ✅ **Asset Unpacking** — Extract XML assets from game files

## Installation

### Prerequisites
- Python 3.10+
- RdaConsole.exe (optional, for RDA extraction)
  - Download: [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole)
  - Place in `rda_console/` directory

### Setup

```bash
git clone <repository-url>
cd atayeb-assets-explorer
python main.py --cli cache_manager --stats  # Test
```

## CLI Reference

### asset_finder — Find asset by GUID

```bash
python main.py --cli asset_finder [OPTIONS]

Options:
  --guid GUID, -g GUID            GUID to search for (required)
  --json, -j                      Output as JSON
  --related, -r                   Find related GUIDs
  --filter REGEX, -f REGEX        Filter related GUIDs by regex
  --assets-dir PATH, -ad PATH     Custom assets directory
```

### cache_manager — Manage cache

```bash
python main.py --cli cache_manager [OPTIONS]

Options:
  --stats                         Show cache statistics
  --clear                         Clear entire cache
  --clear-not-found               Clear only not-found entries
```

### extract_rda — Extract RDA archives

```bash
python main.py --cli extract_rda [OPTIONS]

Options:
  -i, --input PATH                RDA file to extract (interactive if omitted)
  -o, --output PATH               Output directory (default: unpacked/)
  --filter REGEX                  Only extract files matching regex
```

### unpack_assets — Unpack XML assets

```bash
python main.py --cli unpack_assets [OPTIONS]

Options:
  -a, --assets-file PATH          Assets XML file (default: from config)
  -o, --output PATH               Output directory (default: unpacked/assets/)
  --filter REGEX                  Filter asset names by regex
```

### assets_mapper — Generate name-to-GUID mappings

```bash
python main.py --cli assets_mapper [OPTIONS]

Options:
  -t, --template STRING           Asset template filename (required)
  -of, --output-format FORMAT     Output format: python or json (default: python)
  -o, --output PATH               Output file (auto-generated if omitted)
  --filter REGEX                  Filter asset names by regex
```

## Configuration

### Default config.json

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

### Path Resolution

- Relative paths → converted to absolute from project root
- Absolute paths → used as-is
- Resolution handled in `src/config.py`

### Custom Configuration (Partial Merge)

Override specific values without replacing entire config:

```bash
python main.py --cfg custom.json --cli asset_finder --guid 12345678
```

**custom.json:**
```json
{
    "partial": true,
    "paths": {
        "assets_xml": "/custom/path/assets.xml"
    }
}
```

The `"partial": true` flag merges with defaults instead of replacing them.

### Auto-Reload

- Edit `config.json` on disk
- Next CLI command automatically loads new configuration
- MTIME-based detection (like cache)

## License

See LICENSE file for details.
