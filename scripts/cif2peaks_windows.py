from __future__ import annotations

import os

from cif2peaks.gui import main


if __name__ == "__main__":
    if os.environ.get("XRD_ATLAS_SMOKE_TEST") == "1":
        import tkinter as tk

        original_tk = tk.Tk

        class AutoCloseTk(original_tk):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, **kwargs)
                self.after(300, self.destroy)

        tk.Tk = AutoCloseTk
    raise SystemExit(main())
