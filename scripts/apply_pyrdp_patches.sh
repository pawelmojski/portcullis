#!/bin/bash
# Apply patches to PyRDP in venv-pyrdp-converter
# These patches are required for MP4 conversion to work properly

set -e

VENV_DIR="/opt/jumphost/venv-pyrdp-converter"
PYRDP_DIR="$VENV_DIR/lib/python3.13/site-packages/pyrdp"

echo "Applying PyRDP patches for MP4 conversion..."

# Patch 1: Add RDP version support (Windows 11 compatibility)
echo "1. Patching enum/rdp.py - Add RDP10_12 version support"
cat > /tmp/rdp_enum_patch.py << 'EOF'
# Add after existing RDP version definitions (around line 41)
# Add this at the end of the RDPVersion class:

    @classmethod
    def _missing_(cls, value):
        """Handle unknown RDP versions gracefully"""
        other = RDPVersion(0x80001)
        other._name_ = "RDP_UNKNOWN"
        other._value_ = value
        return other

# Add this after RDP10_11 definition:
    RDP10_12 = 0x80011  # Windows 11 / Server 2022
EOF

# Patch 2: Python 3.13 compatibility fix
echo "2. Patching mitm/FileMapping.py - Python 3.13 compatibility"
cat > /tmp/filemapping_patch.py << 'EOF'
# Change line 10 from:
# from typing import io
# To:
from typing import BinaryIO
EOF

# Patch 3: Set FPS for MP4 conversion
echo "3. Patching convert/utils.py - Set FPS=10 for faster conversion"
cat > /tmp/utils_patch.py << 'EOF'
# In createHandler() function, around line 138:
# Change:
#     if format == "mp4" and HandlerClass:
#         return HandlerClass(outputFileBase, progress=progress), outputFileBase
# To:
    if format == "mp4" and HandlerClass:
        return HandlerClass(outputFileBase, fps=10, progress=progress), outputFileBase
EOF

echo ""
echo "Patch files created in /tmp/"
echo ""
echo "IMPORTANT: These patches must be applied manually after 'pip install pyrdp-mitm'"
echo ""
echo "Manual patch steps:"
echo "1. Edit $PYRDP_DIR/enum/rdp.py"
echo "   - Add _missing_() method to RDPVersion class"
echo "   - Add RDP10_12 = 0x80011 constant"
echo ""
echo "2. Edit $PYRDP_DIR/mitm/FileMapping.py"
echo "   - Change 'from typing import io' to 'from typing import BinaryIO'"
echo ""
echo "3. Edit $PYRDP_DIR/convert/utils.py"
echo "   - Add 'fps=10' parameter to HandlerClass() call for mp4 format"
echo ""
echo "Patch reference files saved to /tmp/"

# Clean up
rm -f /tmp/rdp_enum_patch.py /tmp/filemapping_patch.py /tmp/utils_patch.py
