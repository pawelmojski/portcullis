# PyRDP Patches for MP4 Conversion

This document describes manual patches required in `venv-pyrdp-converter` for MP4 conversion to work properly.

## Overview

PyRDP 2.1.0 requires three patches for:
1. **Windows 11 compatibility** - RDP version 0x80011 support
2. **Python 3.13 compatibility** - BinaryIO import fix
3. **Performance optimization** - FPS=10 for faster conversion

## Patch 1: RDP Version Support (enum/rdp.py)

**File**: `venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py`

**Problem**: Windows 11 clients use RDP version 0x80011 which causes `ValueError: 524305 is not a valid RDPVersion`

**Solution**: Add unknown version handler and RDP10_12 constant

### Location: Inside `class RDPVersion(IntEnum):`

Add this method after all existing RDP version constants (around line 41):

```python
    @classmethod
    def _missing_(cls, value):
        """Handle unknown RDP versions gracefully"""
        other = RDPVersion(0x80001)
        other._name_ = "RDP_UNKNOWN"
        other._value_ = value
        return other
```

### Location: After `RDP10_11 = 0x80010`

Add new version constant:

```python
    RDP10_12 = 0x80011  # Windows 11 / Server 2022
```

### Complete Example:

```python
class RDPVersion(IntEnum):
    """
    RDP protocol version
    https://msdn.microsoft.com/en-us/library/cc240510.aspx
    """
    RDP4 = 0x00080001
    RDP5 = 0x00080004
    RDP10 = 0x00080005
    RDP10_1 = 0x00080006
    RDP10_2 = 0x00080007
    RDP10_3 = 0x00080008
    RDP10_4 = 0x00080009
    RDP10_5 = 0x0008000a
    RDP10_6 = 0x0008000b
    RDP10_7 = 0x0008000c
    RDP10_8 = 0x0008000d
    RDP10_9 = 0x0008000e
    RDP10_10 = 0x0008000f
    RDP10_11 = 0x00080010
    RDP10_12 = 0x80011  # Windows 11 / Server 2022 - ADDED

    @classmethod
    def _missing_(cls, value):  # ADDED
        """Handle unknown RDP versions gracefully"""
        other = RDPVersion(0x80001)
        other._name_ = "RDP_UNKNOWN"
        other._value_ = value
        return other
```

---

## Patch 2: Python 3.13 Compatibility (mitm/FileMapping.py)

**File**: `venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py`

**Problem**: `from typing import io` is deprecated in Python 3.13

**Solution**: Import BinaryIO directly

### Location: Line 10

Change:
```python
from typing import io
```

To:
```python
from typing import BinaryIO
```

### Complete Import Section:

```python
from logging import LoggerAdapter
from pathlib import Path
from typing import BinaryIO  # CHANGED from 'from typing import io'

from pyrdp.core import Uint32LE, Uint64LE
from pyrdp.enum import CreateOption, FileAccessMask, FileAttributes, FileCreateDisposition, FileCreateOptions, \
    FileShareAccess, FileSystemInformationClass, MajorFunction
```

---

## Patch 3: FPS Optimization (convert/utils.py)

**File**: `venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py`

**Problem**: Default conversion is slow (realtime speed)

**Solution**: Set FPS=10 for 3x faster conversion with acceptable quality

### Location: Function `createHandler()`, around line 138

Change:
```python
    if format == "mp4" and HandlerClass:
        return HandlerClass(outputFileBase, progress=progress), outputFileBase
```

To:
```python
    if format == "mp4" and HandlerClass:
        return HandlerClass(outputFileBase, fps=10, progress=progress), outputFileBase
```

### Complete Function Context:

```python
def createHandler(format: str, outputFileBase: str, exportText: bool, progress: ProgressObserver = NullObserver()):
    """
    Create the proper handler for an output format.
    :param format: the output file format.
    :param outputFileBase: base name for output files.
    :param exportText: whether text should be exported to a file or not.
    :param progress: progress observer
    """
    if format == "json":
        return JSONEventHandler(outputFileBase, progress), outputFileBase + ".json"
    elif format == "replay":
        return ReplayWriter(outputFileBase + ".replay", progress), outputFileBase + ".replay"
    elif format == "mp4" and HandlerClass:
        return HandlerClass(outputFileBase, fps=10, progress=progress), outputFileBase  # ADDED fps=10
    elif format is None:
        return None, None
    else:
        raise ValueError(f"Invalid format: {format}")
```

---

## Testing Patches

After applying all patches, test with:

```bash
source /opt/jumphost/venv-pyrdp-converter/bin/activate
pyrdp-convert --version
pyrdp-convert -f mp4 -o /tmp/test.mp4 /path/to/recording.pyrdp
```

Expected results:
- No `ValueError` for RDP versions
- No import errors
- Conversion ~3x faster than realtime (FPS=10)
- MP4 file playable in browser

---

## Verification

Check if patches are applied:

```bash
# Check RDP10_12 constant
grep -n "RDP10_12" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py

# Check _missing_ method
grep -n "_missing_" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py

# Check BinaryIO import
grep -n "from typing import BinaryIO" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py

# Check FPS parameter
grep -n "fps=10" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py
```

All commands should return results. If any command returns nothing, that patch is missing.

---

## Automated Backup

Before applying patches, backup original files:

```bash
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py{,.orig}
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py{,.orig}
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py{,.orig}
```

Restore if needed:

```bash
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py{.orig,}
```

---

## Performance Impact

- **FPS=10**: ~40 seconds for 3.5MB file (tested)
- **FPS=25 (default)**: ~120 seconds for same file
- **Quality**: Acceptable for security audit, smooth video playback
- **File size**: ~20% of original .pyrdp file

---

## Notes

- Patches are required AFTER every `pip install --upgrade pyrdp-mitm`
- Consider forking PyRDP and maintaining patched version
- Submit upstream PRs for RDP10_12 and Python 3.13 compatibility
- FPS can be made configurable via environment variable in future
