# RdaConsole

This directory contains the RdaConsole.exe utility for extracting assets from RDA archives.

## Installation

Download the RdaConsole release from [https://github.com/anno-mods/RdaConsole](https://github.com/anno-mods/RdaConsole) and extract the contents into this folder.

**Expected structure:**
```
rda_console/
├── RdaConsole.exe          # Main executable
├── ... other RdaConsole files
└── README.md               # This file
```

## Configuration

The `extract_rda` module uses the RdaConsole path from `config.json`:

```json
{
    "paths": {
        "rda_console_exec": "rda_console/RdaConsole.exe"
    }
}
```

**To customize:**
1. Edit `config.json` and change the `rda_console_exec` path
2. Or use the `--rdaconsole-path` parameter when running extract_rda:
   ```bash
   python main.py --cli extract_rda -i "data.rda" --rdaconsole-path "/custom/path/RdaConsole.exe"
   ```

## Usage

The `extract_rda` module will automatically invoke RdaConsole.exe to extract files from RDA archives:

```bash
# Interactive mode (GUI file picker)
python main.py --cli extract_rda

# Specify RDA file
python main.py --cli extract_rda -i "annodata_00.rda" -o "unpacked/"
```

Output files are extracted to the configured `unpacked_dir` path.

## Notes

- RdaConsole requires Windows (uses .exe)
- The tool runs in a separate console window (CREATE_NEW_CONSOLE flag)
- For path resolution, see the main [README.md](../README.md#configuration)
- This is only required if you want to also extracts rda with this project. You can use it from an anno assets.xml file otherwise.
