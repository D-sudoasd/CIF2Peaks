from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
from zipfile import ZIP_DEFLATED, ZipFile


REQUIRED_RELATIVE_PATHS = (
    "XRD Atlas.exe",
    "XRD Atlas Quick Export.exe",
    "README_WINDOWS.txt",
    "windows_self_test.bat",
    "_internal/tcl86t.dll",
    "_internal/tk86t.dll",
    "_internal/_tcl_data/init.tcl",
    "_internal/_tk_data/tk.tcl",
    "examples/cif",
)


def _validate_portable_app(app_dir: Path) -> None:
    missing = [relative for relative in REQUIRED_RELATIVE_PATHS if not (app_dir / relative).exists()]
    if missing:
        raise FileNotFoundError("Missing portable app file(s): " + ", ".join(missing))


def package_portable_app(app_dir: str | Path, output_zip: str | Path) -> Path:
    app_path = Path(app_dir).resolve()
    zip_path = Path(output_zip).resolve()
    _validate_portable_app(app_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    root_name = app_path.name
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(app_path.rglob("*"), key=lambda item: str(item).lower()):
            if path.is_file():
                archive.write(path, Path(root_name) / path.relative_to(app_path))
    return zip_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package the XRD Atlas Windows portable folder as a zip file.")
    parser.add_argument("app_dir", nargs="?", default=Path("dist") / "XRD Atlas")
    parser.add_argument("output_zip", nargs="?", default=Path("dist") / "XRD_Atlas_Windows_Portable.zip")
    args = parser.parse_args(argv)

    try:
        output = package_portable_app(args.app_dir, args.output_zip)
    except Exception as exc:
        print(f"Portable zip failed: {exc}")
        return 1
    print(f"Portable zip created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
