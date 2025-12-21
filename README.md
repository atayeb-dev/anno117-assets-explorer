# atayeb Assets Explorer

Utility for exploring and managing Anno game assets from RDA archives and assets files.

If my work made your day better, consider [backing](https://ko-fi.com/atayeb) its creator.

**Version:** 0.1 | **Python:** 3.10+ | **Dependencies:** Standard Library Only

## Features

- Extract RDA archives using RdaConsole.exe
- Unpack XML assets from assets.xml by template type
- Generate Name→GUID mappings (Python/JSON format)
- GUI and CLI interfaces

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

### GUI Mode

```bash
python main.py --ui
```

### CLI Mode

```bash
# Extract RDA files
python main.py --cli extract_rda -i "annodata_00.rda"

# Unpack assets from assets.xml
python main.py --cli unpack_assets -a "assets.xml"

# Generate asset mappings
python main.py --cli assets_mapper -t "AssetPool.xml" -of python
```

## Commands

### extract_rda

```bash
python main.py --cli extract_rda [OPTIONS]
  -i, --input PATH                RDA file to extract
  -o, --output PATH               Output directory (default: unpacked)
  --filter REGEX                  Filter extracted files by regex
  --rdaconsole-path PATH          Path to RdaConsole.exe
```

### unpack_assets

```bash
python main.py --cli unpack_assets [OPTIONS]
  -a, --assets-file PATH          Path to assets.xml
  -o, --output PATH               Output directory (default: unpacked/assets)
  --filter REGEX                  Filter assets by regex pattern
```

### assets_mapper

```bash
python main.py --cli assets_mapper [OPTIONS]
  -t, --template STRING           Asset XML filename (required)
  -ad, --assets-dir PATH          Assets directory (default: unpacked/assets)
  -of, --output-format FORMAT     Output format: python or json (default: python)
  -od, --output-dir PATH          Output directory (default: gen)
  --filter REGEX                  Filter asset names by regex
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

## Project Structure

```
src/
├── ui.py                    # GUI interface
├── shared/
│   ├── config.py           # Configuration loader
│   └── utils.py            # Shared utilities
└── routines/
    ├── extract_rda.py
    ├── unpack_assets.py
    └── assets_mapper.py

gen/                        # Generated output files
unpacked/                   # Extracted RDA contents
rda_console/               # RdaConsole utility
```

## Troubleshooting

**RdaConsole not found:**
- Download from [anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole)
- Place in `rda_console/` directory
- Or edit `config.json` with correct path

**assets.xml not found:**
- Run extraction first: `python main.py --cli extract_rda`
- Verify path in `config.json`

**Asset file not found:**
- Run unpack first: `python main.py --cli unpack_assets`
- Verify file exists in `unpacked/assets/`

## Resources

- [RdaConsole](https://github.com/anno-mods/RdaConsole) — Asset extraction tool
- [Python pathlib](https://docs.python.org/3/library/pathlib.html) — Path handling
- [Python xml.etree](https://docs.python.org/3/library/xml.etree.elementtree.html) — XML processing

## License

See LICENSE file for details.
