from __future__ import annotations

import os
import sys

from xrd_atlas.gui import _configure_tcl_tk_environment
from xrd_atlas.quick_export import quick_export_message_lines, quick_export_xrd_atlas


def _show_message(title: str, message: str, *, error: bool = False) -> None:
    print(message)
    if os.environ.get("XRD_ATLAS_SMOKE_TEST") == "1":
        return

    _configure_tcl_tk_environment()
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        if error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
    finally:
        root.destroy()


def main(argv: list[str] | None = None) -> int:
    inputs = sys.argv[1:] if argv is None else argv
    if not inputs:
        _show_message("XRD Atlas Quick Export", "请把 .cif 文件或包含 CIF 的文件夹拖到本程序上。", error=True)
        return 1

    try:
        result = quick_export_xrd_atlas(inputs)
    except Exception as exc:
        _show_message("导出失败", str(exc), error=True)
        return 1

    _show_message("导出完成", "\n".join(quick_export_message_lines(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
