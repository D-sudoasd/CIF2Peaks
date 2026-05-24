from __future__ import annotations

import os
from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    os.environ.setdefault("TCL_LIBRARY", str(base / "_tcl_data"))
    os.environ.setdefault("TK_LIBRARY", str(base / "_tk_data"))
