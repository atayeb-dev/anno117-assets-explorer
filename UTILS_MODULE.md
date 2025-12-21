# Utils Module Documentation

## Overview

The `src/utils.py` module provides reusable utility functions for the Atayeb Assets Explorer project. It centralizes common operations across all modules to reduce code duplication and improve maintainability.

## Exported Functions

### Logging

#### `setup_logging(level: int = logging.INFO) -> logging.Logger`

Configure logging with a standard format across all modules.

**Usage:**
```python
from src.utils import setup_logging
logger = setup_logging()
logger.info("Application started")
```

**Notes:**
- Replaces manual `logging.basicConfig()` calls
- Returns a configured logger instance
- Default level is `INFO`

---

### File & Directory Operations

#### `validate_file_exists(file_path: Path, description: str = "File") -> bool`

Validate that a file exists and is readable.

**Usage:**
```python
from src.utils import validate_file_exists
from pathlib import Path

if validate_file_exists(Path("assets.xml"), "Assets file"):
    # Process file
    pass
```

**Returns:**
- `True` if file exists and is valid
- `False` otherwise (logs error automatically)

---

#### `ensure_dir_exists(dir_path: Path) -> bool`

Ensure a directory exists, creating it if necessary.

**Usage:**
```python
from src.utils import ensure_dir_exists

if ensure_dir_exists(Path("output")):
    # Directory ready
    pass
```

**Returns:**
- `True` if directory exists or was created successfully
- `False` on error

---

### String Manipulation

#### `sanitize_filename(name: str, strict: bool = False) -> str`

Remove/replace forbidden filename characters.

**Usage:**
```python
from src.utils import sanitize_filename

safe_name = sanitize_filename("Asset<Pool>")  # "Asset_Pool_"
strict_name = sanitize_filename("test-file", strict=True)  # "test_file"
```

**Modes:**
- `strict=False` (default): Removes only Windows forbidden chars: `< > : " / \ | ? *`
- `strict=True`: Removes all special chars except underscores and dots

**Returns:** Sanitized string safe for use as filename

---

#### `generate_constant_name(template_name: str) -> str`

Generate a Python constant name from a template filename.

**Usage:**
```python
from src.utils import generate_constant_name

const_name = generate_constant_name("AssetPoolNamed.xml")
# Returns: "ASSET_POOL_NAMED_MAP"
```

**Transformation Rules:**
1. Removes `.xml` extension
2. Converts CamelCase to UPPER_SNAKE_CASE
3. Appends `_MAP` suffix

**Returns:** Python-safe constant name

---

### XML Processing

#### `indent_xml(elem: ET.Element, level: int = 0) -> None`

Pretty-print an XML element tree with proper indentation.

**Usage:**
```python
import xml.etree.ElementTree as ET
from src.utils import indent_xml

root = ET.Element("Root")
# ... add child elements ...
indent_xml(root)
ET.ElementTree(root).write("output.xml", encoding="utf-8", xml_declaration=True)
```

**Notes:**
- Modifies the element tree in-place
- Uses 2-space indentation per level
- Handles recursion automatically

---

### Pattern Matching

#### `match_pattern(name: str, patterns: list[str]) -> bool`

Check if a string matches any pattern in a list (wildcard support).

**Usage:**
```python
from src.utils import match_pattern

if match_pattern("AssetPool", ["Asset*", "Building*"]):
    # Pattern matched
    pass

if not match_pattern("Road", ["Asset*", "Building*"]):
    # Pattern not matched
    pass
```

**Pattern Syntax:** Supports fnmatch wildcards:
- `*` - matches any sequence
- `?` - matches single character
- `[seq]` - matches character in sequence
- `[!seq]` - matches character not in sequence

**Returns:**
- `True` if name matches any pattern
- `False` otherwise

---

### Configuration Loading

#### `load_json_config(config_path: Path, defaults: dict | None = None) -> dict`

Load a JSON configuration file with fallback to defaults.

**Usage:**
```python
from src.utils import load_json_config
from pathlib import Path

defaults = {"whitelist": [], "blacklist": []}
config = load_json_config(Path("config.json"), defaults)
```

**Behavior:**
- If file exists: loads and returns JSON content
- If file missing: logs info message and returns defaults
- If JSON malformed: logs error and raises `ValueError`

**Returns:** Configuration dictionary

**Raises:**
- `ValueError` if JSON is malformed

---

## Integration Examples

### Before (Duplicated Code)

Multiple modules had similar implementations:

```python
# extract_rda.py
def _validate_input_file(file_path: Path) -> bool:
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return False
    if not file_path.is_file():
        logger.error(f"Not a file: {file_path}")
        return False
    return True

# template_reader.py  
def _sanitize_filename(filename: str) -> str:
    return filename.replace(" ", "_").replace("-", "_")

# unpack_templates.py
def _sanitize_filename(name: str) -> str:
    forbidden = '<>:"/\\|?*'
    for char in forbidden:
        name = name.replace(char, "_")
    return name
```

### After (Centralized in Utils)

```python
# All modules
from src.utils import validate_file_exists, sanitize_filename

# Single, consistent implementation
if validate_file_exists(file_path, "Assets file"):
    pass

safe_name = sanitize_filename(template_name)
```

---

## Migration Checklist

When refactoring to use utils:

1. ✅ Import required utilities: `from .utils import function_names`
2. ✅ Replace duplicate function definitions with imports
3. ✅ Update all function calls to use public names (no leading `_`)
4. ✅ Update logging setup: `logger = setup_logging()`
5. ✅ Verify no errors: `get_errors()` and run tests
6. ✅ Update module docstrings if needed

---

## File Statistics

**Lines Saved Through Refactoring:**
- `extract_rda.py`: -10 lines (removed duplicate validation)
- `unpack_templates.py`: -60 lines (removed 3 duplicate functions)
- `template_reader.py`: -30 lines (removed 2 duplicate functions)
- **Total Reduction:** ~100 lines of duplicate code

**New Centralized Module:** +190 lines in `utils.py`
**Net Saving:** 100 - 190 = -90 (but with much better maintainability)

---

## Design Principles

1. **No Module-Specific Logic**: Utils contains only general-purpose functions
2. **Public Interface**: All exported functions lack leading underscores
3. **Documentation**: Every function has docstring with usage examples
4. **Error Handling**: Functions log errors automatically where appropriate
5. **Type Hints**: Full type annotations on all functions
6. **Extensibility**: Easy to add new utility functions as project grows
