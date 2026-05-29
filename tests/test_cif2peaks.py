from __future__ import annotations

import csv
import os
import subprocess
import sys
import textwrap
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest

from cif2peaks.batch import batch_export_peak_reference
from cif2peaks.exporters import combined_peak_rows, export_peak_reference_csv, export_cif2peaks_workbook
from cif2peaks.models import Cif2PeaksExportPayload, Cif2PeaksSettings
from cif2peaks.service import Cif2PeaksService


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_CIF_DIR = ROOT / "examples" / "cif"
TI_BETA_CIF = EXAMPLES_CIF_DIR / "ti_beta_bcc_im3m.cif"
TI_NB_HCP_CIF = EXAMPLES_CIF_DIR / "ti_nb_hcp_p63mmc.cif"

NI_OCCUPANCY_CIF = """
#======================================================================
# CRYSTAL DATA
#----------------------------------------------------------------------
data_VESTA_phase_1

_chemical_name_common                  'Ni                                   '
_cell_length_a                         3.598240
_cell_length_b                         3.598240
_cell_length_c                         3.598240
_cell_angle_alpha                      90.000000
_cell_angle_beta                       90.000000
_cell_angle_gamma                      90.000000
_cell_volume                           46.587601
_space_group_name_H-M_alt              'P 2 3'
_space_group_IT_number                 195

loop_
_space_group_symop_operation_xyz
   'x, y, z'
   '-x, -y, z'
   '-x, y, -z'
   'x, -y, -z'
   'z, x, y'
   'z, -x, -y'
   '-z, -x, y'
   '-z, x, -y'
   'y, z, x'
   '-y, z, -x'
   'y, -z, -x'
   '-y, -z, x'

loop_
   _atom_site_label
   _atom_site_occupancy
   _atom_site_fract_x
   _atom_site_fract_y
   _atom_site_fract_z
   _atom_site_adp_type
   _atom_site_U_iso_or_equiv
   _atom_site_type_symbol
   Ni1        1.0     0.000000     0.000000     -0.000000    Uiso  ? Ni
   Ni2        1.0     0.500000     0.500000     0.000000    Uiso  ? Ni
   Ni3        1.0     -0.000000     0.500000     0.500000    Uiso  ? Ni
   Ni4        1.0     0.500000     -0.000000     0.500000    Uiso  ? Ni
"""

MULTI_BLOCK_STANDARDIZED_CIF = """
data_sm_global
_audit_creation_method 'metadata only'

data_probe-standardized_unitcell
_cell_length_a 3.0
_cell_length_b 3.0
_cell_length_c 3.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
_symmetry_Int_Tables_number 1
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0 0 0 1

data_probe-published_cell
_cell_length_a 4.0
_cell_length_b 4.0
_cell_length_c 4.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 2 3'
_symmetry_Int_Tables_number 195
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si 0 0 0 1

data_probe-niggli_reduced_cell
_cell_length_a 2.0
_cell_length_b 2.0
_cell_length_c 2.0
_cell_angle_alpha 60
_cell_angle_beta 60
_cell_angle_gamma 60
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
? ? ? ? ? ?
"""


def _write_ni_occupancy_cif(path: Path) -> Path:
    path.write_text(textwrap.dedent(NI_OCCUPANCY_CIF).strip() + "\n", encoding="utf-8")
    return path


def _write_multi_block_standardized_cif(path: Path) -> Path:
    path.write_text(textwrap.dedent(MULTI_BLOCK_STANDARDIZED_CIF).strip() + "\n", encoding="utf-8")
    return path


def _nb_hea_cif_paths() -> list[Path]:
    root = Path.home() / "Desktop" / "Nb_HEA_peak_separation"
    names = ["AlNi.cif", "Cr2Nb.cif", "FeCr.cif", "Ni.cif", "Ni3Al.cif"]
    found = {path.name: path for path in root.rglob("*.cif")} if root.exists() else {}
    paths = [found.get(name) for name in names]
    if any(path is None for path in paths):
        pytest.skip("Nb_HEA_peak_separation CIF fixtures are not available on this machine.")
    return [path for path in paths if path is not None]


def _zr_hydride_cif_paths() -> list[Path]:
    root = Path.home() / "Desktop" / "ZrNb_SXRD_deformation" / "Cif"
    names = [
        "\N{GREEK SMALL LETTER ALPHA}-Zr.cif",
        "\N{GREEK SMALL LETTER BETA}-Zr.cif",
        "\N{GREEK SMALL LETTER GAMMA}-ZrH.cif",
        "\N{GREEK SMALL LETTER DELTA}-ZrH1.66.cif",
    ]
    paths = [root / name for name in names]
    if any(not path.exists() for path in paths):
        pytest.skip("Zr/ZrH CIF fixtures are not available on this machine.")
    return paths


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(ROOT / "src")
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    return env


def _worksheet_rows(workbook_path: Path, sheet_index: int) -> list[list[str]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(workbook_path) as archive:
        xml = archive.read(f"xl/worksheets/sheet{sheet_index}.xml")
    root = ET.fromstring(xml)
    rows: list[list[str]] = []
    for row in root.findall(".//main:row", namespace):
        values: list[str] = []
        for cell in row.findall("main:c", namespace):
            inline = cell.find("main:is/main:t", namespace)
            numeric = cell.find("main:v", namespace)
            values.append("" if inline is None and numeric is None else ((inline.text or "") if inline is not None else numeric.text or ""))
        rows.append(values)
    return rows


def _worksheet_cell_styles(workbook_path: Path, sheet_index: int) -> list[list[str]]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(workbook_path) as archive:
        xml = archive.read(f"xl/worksheets/sheet{sheet_index}.xml")
    root = ET.fromstring(xml)
    styles: list[list[str]] = []
    for row in root.findall(".//main:row", namespace):
        styles.append([cell.attrib.get("s", "0") for cell in row.findall("main:c", namespace)])
    return styles


def test_project_is_cli_only_without_gui_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(project["project"]["dependencies"])
    scripts = project["project"]["scripts"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "PySide6" not in dependencies
    assert "matplotlib" not in dependencies
    assert "tkinterdnd2-universal" in dependencies
    assert "PySide6" not in requirements
    assert "matplotlib" not in requirements
    assert "tkinterdnd2-universal" in requirements
    assert scripts["cif2peaks"] == "cif2peaks.batch:main"
    assert scripts["cif2peaks-peaks"] == "cif2peaks.batch:main"
    assert scripts["cif2peaks-gui"] == "cif2peaks.gui:main"
    assert scripts["cif2peaks-quick-export"] == "cif2peaks.quick_export:main"


def test_windows_build_includes_gui_and_quick_export_apps() -> None:
    build_script = (ROOT / "build_windows_app.bat").read_text(encoding="ascii")

    assert '--name "CIF2Peaks"' in build_script
    assert "--name \"CIF2Peaks Quick Export\"" in build_script
    assert "--additional-hooks-dir scripts\\pyinstaller_hooks" in build_script
    assert "--hidden-import tkinterdnd2" in build_script
    assert (ROOT / "scripts" / "pyinstaller_hooks" / "hook-tkinterdnd2.py").exists()
    assert "scripts\\cif2peaks_windows.py" in build_script
    assert "scripts\\cif2peaks_quick_export_windows.py" in build_script


def test_windows_build_packages_readme_examples_and_self_test() -> None:
    build_script = (ROOT / "build_windows_app.bat").read_text(encoding="ascii")
    self_test_bytes = (ROOT / "windows_self_test.bat").read_bytes()
    self_test = (ROOT / "windows_self_test.bat").read_text(encoding="ascii")

    assert b"\r\n" in self_test_bytes
    assert b"\n" not in self_test_bytes.replace(b"\r\n", b"")
    assert "README_WINDOWS.txt" in build_script
    assert "windows_self_test.bat" in build_script
    assert "examples\\cif" in build_script
    assert (ROOT / "README_WINDOWS.txt").exists()
    assert (ROOT / "windows_self_test.bat").exists()
    assert "_internal\\_tcl_data\\init.tcl" in self_test
    assert "_internal\\_tk_data\\tk.tcl" in self_test
    assert "cif2peaks_self_test_report.txt" in self_test
    assert "Windows version" in self_test
    assert "CIF2Peaks folder" in self_test
    assert "Report saved to" in self_test
    assert "Checking generated workbook content" in self_test
    assert "Checking diagnostic workbook for invalid CIF" in self_test
    assert "xl/workbook.xml" in self_test
    assert 'if "%~1"=="" (' in self_test
    assert "[char]34" in self_test
    assert r"\u4f7f\u7528\u8bf4\u660e" in self_test
    assert r"\u63a8\u8350\u5cf0\u8868" in self_test
    assert r"CIF \u683c\u5f0f\u4e0d\u5b8c\u6574\u6216\u65e0\u6cd5\u89e3\u6790" in self_test


def test_windows_build_creates_portable_zip() -> None:
    build_script = (ROOT / "build_windows_app.bat").read_text(encoding="ascii")

    assert "scripts\\package_windows_portable.py" in build_script
    assert "CIF2Peaks_Windows_Portable.zip" in build_script


def test_windows_portable_zip_contains_complete_folder(tmp_path: Path) -> None:
    from scripts.package_windows_portable import package_portable_app

    app_dir = tmp_path / "CIF2Peaks"
    internal = app_dir / "_internal"
    examples = app_dir / "examples" / "cif"
    internal.mkdir(parents=True)
    examples.mkdir(parents=True)
    for relative in (
        "CIF2Peaks.exe",
        "CIF2Peaks Quick Export.exe",
        "README_WINDOWS.txt",
        "windows_self_test.bat",
        "_internal/tcl86t.dll",
        "_internal/tk86t.dll",
        "_internal/_tcl_data/init.tcl",
        "_internal/_tk_data/tk.tcl",
        "examples/cif/demo.cif",
    ):
        path = app_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    zip_path = package_portable_app(app_dir, tmp_path / "CIF2Peaks_Windows_Portable.zip")

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "CIF2Peaks/CIF2Peaks.exe" in names
    assert "CIF2Peaks/CIF2Peaks Quick Export.exe" in names
    assert "CIF2Peaks/README_WINDOWS.txt" in names
    assert "CIF2Peaks/windows_self_test.bat" in names
    assert "CIF2Peaks/examples/cif/demo.cif" in names
    assert "CIF2Peaks/_internal/tcl86t.dll" in names
    assert "CIF2Peaks/_internal/tk86t.dll" in names
    assert "CIF2Peaks/_internal/_tcl_data/init.tcl" in names
    assert "CIF2Peaks/_internal/_tk_data/tk.tcl" in names


def test_windows_portable_zip_requires_tcl_tk_runtime_data(tmp_path: Path) -> None:
    from scripts.package_windows_portable import package_portable_app

    app_dir = tmp_path / "CIF2Peaks"
    for relative in (
        "CIF2Peaks.exe",
        "CIF2Peaks Quick Export.exe",
        "README_WINDOWS.txt",
        "windows_self_test.bat",
        "_internal/tcl86t.dll",
        "_internal/tk86t.dll",
        "examples/cif/demo.cif",
    ):
        path = app_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError) as exc_info:
        package_portable_app(app_dir, tmp_path / "CIF2Peaks_Windows_Portable.zip")

    message = str(exc_info.value)
    assert "_internal/_tcl_data/init.tcl" in message
    assert "_internal/_tk_data/tk.tcl" in message


def test_windows_quick_export_entry_exports_without_python_gui(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "cif2peaks_quick_export_windows.py"
    cif_path = tmp_path / TI_BETA_CIF.name
    cif_path.write_bytes(TI_BETA_CIF.read_bytes())

    result = subprocess.run(
        [sys.executable, str(script), str(cif_path)],
        cwd=ROOT,
        env={**_subprocess_env(), "CIF2PEAKS_SMOKE_TEST": "1"},
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    expected_output = tmp_path / f"{cif_path.stem}_CIF2Peaks峰表.xlsx"
    assert expected_output.name in result.stdout
    assert expected_output.exists()


def test_windows_quick_export_entry_treats_diagnostic_workbook_as_success(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "cif2peaks_quick_export_windows.py"
    bad_cif = tmp_path / "bad.cif"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), str(bad_cif)],
        cwd=ROOT,
        env={**_subprocess_env(), "CIF2PEAKS_SMOKE_TEST": "1"},
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    expected_output = tmp_path / "bad_CIF2Peaks峰表.xlsx"
    assert result.returncode == 0, result.stderr
    assert expected_output.exists()
    assert "未得到可用峰记录" in result.stdout
    assert "Summary" in result.stdout


def test_cif2peaks_single_cif_peak_table_and_energy_shift() -> None:
    service = Cif2PeaksService()
    phase = service.load_phase(TI_BETA_CIF)
    settings = Cif2PeaksSettings(input_mode="energy", energy_keV=8.0478, wavelength_A=1.5406)
    service.simulate_phase(phase, settings)
    assert phase.result is not None
    rows = combined_peak_rows([phase])
    assert rows
    first = rows[0]
    for key in ("d_A", "two_theta_current_deg", "q_1_over_A", "g_1_over_A", "multiplicity"):
        assert key in first

    high_energy_phase = service.load_phase(TI_BETA_CIF)
    service.simulate_phase(
        high_energy_phase,
        Cif2PeaksSettings(input_mode="energy", energy_keV=20.0, wavelength_A=1.5406),
    )
    assert high_energy_phase.result is not None
    assert high_energy_phase.result.peaks[0].two_theta_deg < phase.result.peaks[0].two_theta_deg
    assert np.isclose(high_energy_phase.result.peaks[0].d_spacing_A, phase.result.peaks[0].d_spacing_A)


def test_hexagonal_hkl_labels_preserve_four_index_notation(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phase = service.load_phase(TI_NB_HCP_CIF)
    settings = Cif2PeaksSettings()
    service.simulate_phase(phase, settings)

    rows = combined_peak_rows([phase])

    assert rows[0]["hkl"] == "(1 0 -1 0)"
    assert rows[0]["family_label"] == "{1 0 -1 0}"
    assert rows[0]["h"] == 1
    assert rows[0]["k"] == 0
    assert rows[0]["i"] == -1
    assert rows[0]["l"] == 0
    assert "(0 0 0)" not in {row["hkl"] for row in rows}
    assert "(0 0 0 2)" in {row["hkl"] for row in rows}
    assert "(1 0 -1 1)" in {row["hkl"] for row in rows}

    csv_output = tmp_path / "hcp_hkl.csv"
    export_peak_reference_csv(Cif2PeaksExportPayload([phase], settings), csv_output)

    with csv_output.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["hkl"] == "(1 0 -1 0)"

    workbook_output = tmp_path / "hcp_hkl.xlsx"
    export_cif2peaks_workbook(Cif2PeaksExportPayload([phase], settings), workbook_output)

    combined_sheet = _worksheet_rows(workbook_output, 2)
    headers = combined_sheet[0]
    assert "i" in headers
    assert combined_sheet[1][headers.index("hkl")] == "(1 0 -1 0)"
    assert combined_sheet[1][headers.index("i")] == "-1"
    assert combined_sheet[1][headers.index("l")] == "0"


def test_cubic_hkl_labels_remain_three_index_notation() -> None:
    service = Cif2PeaksService()
    phase = service.load_phase(TI_BETA_CIF)
    service.simulate_phase(phase, Cif2PeaksSettings())

    rows = combined_peak_rows([phase])
    first = rows[0]

    assert first["hkl"] == "(1 1 0)"
    assert first["family_label"] == "{1 1 0}"
    assert first["h"] == 1
    assert first["k"] == 1
    assert first["i"] is None
    assert first["l"] == 0


def test_cif2peaks_loads_occupancy_conflict_cif_with_warning(tmp_path: Path) -> None:
    cif_path = _write_ni_occupancy_cif(tmp_path / "Ni.cif")
    service = Cif2PeaksService()

    phase = service.load_phase(cif_path)
    service.simulate_phase(phase, Cif2PeaksSettings())

    assert phase.error is None
    assert phase.result is not None
    assert len(phase.result.peaks) == 8
    assert any("occupancy" in warning.lower() for warning in phase.warning_messages)


def test_cif2peaks_loads_standardized_unitcell_from_multi_block_cif(tmp_path: Path) -> None:
    cif_path = _write_multi_block_standardized_cif(tmp_path / "multi_block.cif")
    service = Cif2PeaksService()

    phase = service.load_phase(cif_path)

    assert phase.error is None
    assert phase.crystal is not None
    assert phase.display_space_group == "P 1"
    assert phase.crystal.cell_parameters[:3] == (3.0, 3.0, 3.0)


def test_cif2peaks_batch_loads_real_cifs_and_keeps_occupancy_warning() -> None:
    service = Cif2PeaksService()
    phases = service.load_phases(_nb_hea_cif_paths())
    service.simulate_phases(phases, Cif2PeaksSettings())

    by_name = {phase.cif_path.name: phase for phase in phases}
    assert list(by_name) == ["AlNi.cif", "Cr2Nb.cif", "FeCr.cif", "Ni.cif", "Ni3Al.cif"]
    expected_peak_counts = {
        "AlNi.cif": 12,
        "Cr2Nb.cif": 22,
        "FeCr.cif": 7,
        "Ni.cif": 8,
        "Ni3Al.cif": 86,
    }
    for name, expected_count in expected_peak_counts.items():
        phase = by_name[name]
        assert phase.error is None
        assert phase.result is not None
        assert len(phase.result.peaks) == expected_count
    assert any("occupancy" in warning.lower() for warning in by_name["Ni.cif"].warning_messages)


def test_cif2peaks_exports_simple_phase_hkl_d_two_theta_csv(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = service.load_phases(_nb_hea_cif_paths())
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "phase_hkl_d_2theta.csv"

    export_peak_reference_csv(Cif2PeaksExportPayload(phases, settings), output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {"phase_name", "cif_name", "formula", "space_group", "hkl", "d_A", "two_theta_deg"}.issubset(rows[0])
    assert {row["cif_name"] for row in rows} == {"AlNi.cif", "Cr2Nb.cif", "FeCr.cif", "Ni.cif", "Ni3Al.cif"}
    assert any(row["cif_name"] == "Ni.cif" and row["hkl"] == "(1 1 1)" for row in rows)
    assert all(float(row["d_A"]) > 0 and float(row["two_theta_deg"]) > 0 for row in rows)


def test_cif2peaks_batch_export_defaults_to_excel_from_many_cifs(tmp_path: Path) -> None:
    output = tmp_path / "many_cif_reference.xlsx"

    phases = batch_export_peak_reference(_nb_hea_cif_paths(), output)

    assert len(phases) == 5
    assert output.exists()
    headers = _worksheet_rows(output, 2)[0]
    expected_front = [
        "phase_name",
        "cif_name",
        "formula",
        "space_group",
        "hkl",
        "d_A",
        "two_theta_current_deg",
        "relative_intensity",
        "multiplicity",
        "warnings",
    ]
    assert headers[: len(expected_front)] == expected_front
    data_rows = _worksheet_rows(output, 2)[1:]
    assert len(data_rows) == sum(len(phase.result.peaks) for phase in phases if phase.result is not None)
    assert all(float(row[5]) > 0 and float(row[6]) > 0 for row in data_rows)


def test_cif2peaks_batch_export_zr_hydride_multi_block_cifs(tmp_path: Path) -> None:
    output = tmp_path / "zr_hydride_reference.xlsx"

    phases = batch_export_peak_reference(_zr_hydride_cif_paths(), output)

    assert len(phases) == 4
    assert output.exists()
    assert all(phase.error is None for phase in phases)
    assert all(phase.result is not None and len(phase.result.peaks) > 0 for phase in phases)
    headers = _worksheet_rows(output, 2)[0]
    for header in ("hkl", "d_A", "two_theta_current_deg", "relative_intensity"):
        assert header in headers
    data_rows = _worksheet_rows(output, 2)[1:]
    assert len(data_rows) == sum(len(phase.result.peaks) for phase in phases if phase.result is not None)
    assert {row[1] for row in data_rows} == {path.name for path in _zr_hydride_cif_paths()}
    assert all(float(row[5]) > 0 and float(row[6]) > 0 for row in data_rows)


def test_cif2peaks_batch_export_can_still_write_csv(tmp_path: Path) -> None:
    output = tmp_path / "many_cif_reference.csv"

    phases = batch_export_peak_reference(_nb_hea_cif_paths(), output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(phases) == 5
    assert output.exists()
    assert len(rows) == sum(len(phase.result.peaks) for phase in phases if phase.result is not None)
    assert {row["phase_name"] for row in rows} >= {"AlNi", "Cr2Nb", "FeCr", "Ni", "Ni3Al"}


def test_cif2peaks_batch_load_isolates_unrecoverable_bad_cif(tmp_path: Path) -> None:
    bad_cif = tmp_path / "bad.cif"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")
    service = Cif2PeaksService()

    phases = service.load_phases([TI_BETA_CIF, bad_cif])
    service.simulate_phases(phases, Cif2PeaksSettings())
    output = tmp_path / "with_bad_cif.xlsx"
    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, Cif2PeaksSettings()), output)

    assert len(phases) == 2
    assert phases[0].result is not None
    assert phases[0].error is None
    assert phases[1].result is None
    assert phases[1].error
    assert not phases[1].enabled
    summary_text = "\n".join("|".join(row) for row in _worksheet_rows(output, 1))
    assert "bad.cif" in summary_text
    assert "CIF 格式不完整或无法解析" in summary_text
    assert "Traceback" not in summary_text
    assert "[Errno" not in summary_text


def test_cif2peaks_multi_phase_workbook_export(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "cif2peaks_export.xlsx"
    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)
    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        combined = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
    assert "Summary" in workbook
    assert "Combined Peaks" in workbook
    assert "ti_beta_bcc_im3m" in workbook
    assert "ti_nb_hcp_p63mmc" in workbook
    assert combined.count("<row ") > 2


def test_cif2peaks_workbook_peak_sheets_are_excel_friendly(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "friendly.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)

    with ZipFile(output) as archive:
        combined = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert '<pane ySplit="1" topLeftCell="A2"' in combined
    assert '<autoFilter ref="A1:S' in combined
    assert '<cols>' in combined
    assert 'width="24"' in combined


def test_cif2peaks_workbook_opens_with_chinese_user_guide(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phase = service.load_phase(TI_BETA_CIF)
    settings = Cif2PeaksSettings()
    service.simulate_phase(phase, settings)
    output = tmp_path / "guide.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload([phase], settings), output)

    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        guide_xml = archive.read("xl/worksheets/sheet5.xml").decode("utf-8")

    assert 'name="使用说明"' in workbook
    assert 'activeTab="4"' in workbook
    assert "默认参数" in guide_xml
    assert "推荐峰表" in guide_xml
    assert "Combined Peaks" in guide_xml
    assert "two_theta_current_deg" in guide_xml


def test_cif2peaks_workbook_includes_beginner_chinese_peak_table(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "beginner_table.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)

    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
    rows = _worksheet_rows(output, 3)

    assert 'name="推荐峰表"' in workbook
    with ZipFile(output) as archive:
        guide_xml = archive.read("xl/worksheets/sheet6.xml").decode("utf-8")
    assert rows[0] == [
        "相名",
        "CIF 文件",
        "化学式",
        "空间群",
        "晶面 hkl",
        "d 间距 (Å)",
        "2θ 当前设置 (°)",
        "2θ Cu Kα (°)",
        "相对强度",
        "多重性",
        "提示",
    ]
    assert len(rows) > 2
    assert "推荐峰表" in guide_xml
    assert "中文列名" in guide_xml


def test_cif2peaks_workbook_registers_stylesheet_for_export_polish(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "styled.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)

    with ZipFile(output) as archive:
        content_types = archive.read("[Content_Types].xml").decode("utf-8")
        workbook_rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        styles_xml = archive.read("xl/styles.xml").decode("utf-8")

    assert 'PartName="/xl/styles.xml"' in content_types
    assert "spreadsheetml.styles+xml" in content_types
    assert "relationships/styles" in workbook_rels
    assert 'Target="styles.xml"' in workbook_rels
    assert "<cellXfs" in styles_xml
    assert "FFF2CC" in styles_xml


def test_cif2peaks_combined_peak_sheets_color_rows_by_phase(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "phase_colors.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)

    combined_rows = _worksheet_rows(output, 2)
    combined_styles = _worksheet_cell_styles(output, 2)
    beginner_styles = _worksheet_cell_styles(output, 3)
    first_phase = combined_rows[1][0]
    second_phase_row = next(index for index, row in enumerate(combined_rows[1:], start=1) if row[0] != first_phase)

    assert combined_styles[0][0] == "1"
    assert beginner_styles[0][0] == "2"
    assert beginner_styles[0][2] == "1"
    assert combined_styles[1][0] != "0"
    assert combined_styles[1][0] == beginner_styles[1][0]
    assert all(
        combined_styles[index][0] == combined_styles[1][0]
        for index, row in enumerate(combined_rows[1:], start=1)
        if row[0] == first_phase
    )
    assert combined_styles[second_phase_row][0] != combined_styles[1][0]


def test_cif2peaks_user_guide_explains_beginner_columns_and_limits(tmp_path: Path) -> None:
    service = Cif2PeaksService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = Cif2PeaksSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "guide_detail.xlsx"

    export_cif2peaks_workbook(Cif2PeaksExportPayload(phases, settings), output)

    guide_text = "\n".join("|".join(row) for row in _worksheet_rows(output, 6))

    assert "新手先看哪几列" in guide_text
    assert "two_theta_current_deg" in guide_text
    assert "d_A" in guide_text
    assert "相对强度" in guide_text
    assert "不是实验定量强度" in guide_text
    assert "warnings" in guide_text


def test_batch_module_help_and_package_main_cli(tmp_path: Path) -> None:
    help_result = subprocess.run(
        [sys.executable, "-m", "cif2peaks.batch", "--help"],
        cwd=ROOT,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert help_result.returncode == 0
    assert "Batch-export" in help_result.stdout

    output = tmp_path / "package_main.xlsx"
    run_result = subprocess.run(
        [sys.executable, "-m", "cif2peaks", str(TI_BETA_CIF), "-o", str(output)],
        cwd=ROOT,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert run_result.returncode == 0, run_result.stderr
    assert output.exists()
    assert "Exported" in run_result.stdout


def test_batch_cli_default_output_is_excel(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "cif2peaks.batch", str(TI_BETA_CIF)],
        cwd=tmp_path,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "cif2peaks_peak_reference.xlsx").exists()
    assert not (tmp_path / "cif2peaks_peak_reference.csv").exists()


def test_simple_gui_builds_energy_settings_from_user_inputs() -> None:
    from cif2peaks.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from cif2peaks.gui import build_gui_settings

    settings = build_gui_settings("20.0", "5", "120")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert np.isclose(settings.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 20.0)
    assert settings.two_theta_min_deg == 5.0
    assert settings.two_theta_max_deg == 120.0


def test_beginner_gui_defaults_to_cu_ka_without_user_parameters() -> None:
    from cif2peaks.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings()

    assert settings.input_mode == "source"
    assert settings.source_preset == "Cu Ka"
    assert settings.two_theta_min_deg == 0.0
    assert settings.two_theta_max_deg == 180.0


def test_beginner_gui_d_range_defaults_to_unrestricted_cu_ka() -> None:
    from cif2peaks.gui import build_beginner_gui_settings_from_d_range

    settings = build_beginner_gui_settings_from_d_range()

    assert settings.input_mode == "source"
    assert settings.source_preset == "Cu Ka"
    assert settings.d_min_A is None
    assert settings.d_max_A is None
    assert settings.two_theta_min_deg == 0.0
    assert settings.two_theta_max_deg == 180.0


def test_beginner_gui_d_range_converts_boundaries_for_cu_ka() -> None:
    from cif2peaks.constants import DEFAULT_XRD_WAVELENGTH_A
    from cif2peaks.gui import build_beginner_gui_settings_from_d_range

    lower_bound = build_beginner_gui_settings_from_d_range(d_min_A=str(DEFAULT_XRD_WAVELENGTH_A))
    upper_bound = build_beginner_gui_settings_from_d_range(d_max_A=str(DEFAULT_XRD_WAVELENGTH_A))
    bounded = build_beginner_gui_settings_from_d_range(d_min_A="1.0", d_max_A="2.0")

    assert np.isclose(lower_bound.two_theta_min_deg, 0.0)
    assert np.isclose(lower_bound.two_theta_max_deg, 60.0)
    assert np.isclose(upper_bound.two_theta_min_deg, 60.0)
    assert np.isclose(upper_bound.two_theta_max_deg, 180.0)
    assert np.isclose(bounded.two_theta_min_deg, 45.3061, atol=1e-4)
    assert np.isclose(bounded.two_theta_max_deg, 100.7617, atol=1e-4)


def test_beginner_gui_d_range_uses_manual_energy_before_conversion() -> None:
    from cif2peaks.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from cif2peaks.gui import build_beginner_gui_settings_from_d_range

    settings = build_beginner_gui_settings_from_d_range(d_min_A="1.0", energy_keV="20.0", xray_preset="83 keV")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert np.isclose(settings.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 20.0)
    assert np.isclose(settings.two_theta_max_deg, 36.1137, atol=1e-4)


def test_beginner_gui_d_range_uses_visible_energy_presets_before_conversion() -> None:
    from cif2peaks.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from cif2peaks.gui import build_beginner_gui_settings_from_d_range

    low_energy = build_beginner_gui_settings_from_d_range(d_min_A="1.0", xray_preset="30 keV")
    high_energy = build_beginner_gui_settings_from_d_range(d_min_A="1.0", xray_preset="83 keV")

    assert np.isclose(low_energy.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 30.0)
    assert np.isclose(high_energy.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 83.0)
    assert low_energy.two_theta_max_deg > high_energy.two_theta_max_deg


@pytest.mark.parametrize(
    ("d_min_A", "d_max_A", "expected_error"),
    [
        ("bad", "", "must be a number"),
        ("-1", "", "must be greater than 0"),
        ("2.0", "1.0", "d range"),
        ("", "0.1", "no observable"),
    ],
)
def test_beginner_gui_d_range_rejects_invalid_inputs(d_min_A: str, d_max_A: str, expected_error: str) -> None:
    from cif2peaks.gui import build_beginner_gui_settings_from_d_range

    with pytest.raises(ValueError, match=expected_error):
        build_beginner_gui_settings_from_d_range(d_min_A=d_min_A, d_max_A=d_max_A)


def test_beginner_gui_keeps_cu_ka_when_energy_is_blank() -> None:
    from cif2peaks.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings(energy_keV=" ")

    assert settings.input_mode == "source"
    assert settings.source_preset == "Cu Ka"


def test_beginner_gui_uses_custom_energy_when_provided() -> None:
    from cif2peaks.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings(energy_keV="20.0", two_theta_min="5", two_theta_max="120")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert settings.two_theta_min_deg == 5.0
    assert settings.two_theta_max_deg == 120.0


def test_beginner_gui_uses_visible_energy_presets() -> None:
    from cif2peaks.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from cif2peaks.gui import build_beginner_gui_settings

    low_energy = build_beginner_gui_settings(xray_preset="30 keV")
    high_energy = build_beginner_gui_settings(xray_preset="83 keV")

    assert low_energy.input_mode == "energy"
    assert low_energy.energy_keV == 30.0
    assert np.isclose(low_energy.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 30.0)
    assert high_energy.input_mode == "energy"
    assert high_energy.energy_keV == 83.0
    assert np.isclose(high_energy.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 83.0)


def test_beginner_gui_manual_energy_overrides_selected_preset() -> None:
    from cif2peaks.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from cif2peaks.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings(energy_keV="20.0", xray_preset="83 keV")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert np.isclose(settings.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 20.0)


def test_beginner_gui_suggests_clear_output_path(tmp_path: Path) -> None:
    from cif2peaks.gui import suggest_output_path

    single = suggest_output_path([tmp_path / "Ti.cif"])
    many = suggest_output_path([tmp_path / "Ti.cif", tmp_path / "TiB.cif"])

    assert single == tmp_path / "Ti_CIF2Peaks峰表.xlsx"
    assert many == tmp_path / "CIF2Peaks峰表_2个CIF.xlsx"


def test_beginner_gui_turns_common_errors_into_chinese_guidance() -> None:
    from cif2peaks.gui import friendly_error_message

    assert "请先添加" in friendly_error_message(ValueError("Select at least one CIF file."))
    assert "数字" in friendly_error_message(ValueError("2theta min must be a number."))
    assert "能量" in friendly_error_message(ValueError("X-ray energy keV must be greater than 0."))
    assert "d 范围" in friendly_error_message(ValueError("d range has no observable first-order Bragg peaks for this wavelength."))
    assert "被 Excel 打开" in friendly_error_message(PermissionError("locked"))


def test_beginner_gui_previews_cif_metadata_before_export(tmp_path: Path) -> None:
    from cif2peaks.gui import preview_simple_gui_inputs

    good_cif = tmp_path / TI_BETA_CIF.name
    bad_cif = tmp_path / "bad.cif"
    good_cif.write_bytes(TI_BETA_CIF.read_bytes())
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = preview_simple_gui_inputs([good_cif, bad_cif])

    assert result.ready_count == 1
    assert result.failed_count == 1
    assert result.phase_rows[0][0] == good_cif.name
    assert result.phase_rows[0][1] == "Ti"
    assert result.phase_rows[0][2] != "-"
    assert result.phase_rows[0][3] == "待导出"
    assert result.phase_rows[0][4] == ""
    assert result.phase_rows[1][0] == bad_cif.name
    assert result.phase_rows[1][1] == "-"
    assert result.phase_rows[1][3] == "无法读取"
    assert "CIF" in result.phase_rows[1][4]
    assert "格式" in result.phase_rows[1][4]
    assert "Traceback" not in result.phase_rows[1][4]
    assert "[Errno" not in result.phase_rows[1][4]

    folder_result = preview_simple_gui_inputs([tmp_path])
    assert folder_result.ready_count == 1
    assert folder_result.failed_count == 1
    assert [row[0] for row in folder_result.phase_rows] == [bad_cif.name, good_cif.name]


def test_gui_startup_collects_dragged_cif_files_and_folders(tmp_path: Path) -> None:
    from cif2peaks.gui import initial_gui_cif_paths

    cif = tmp_path / "Ti.cif"
    uppercase_suffix_cif = tmp_path / "Ti_copy.CIF"
    notes = tmp_path / "notes.txt"
    nested = tmp_path / "nested"
    nested_cif = nested / "TiB.cif"
    for path in (cif, uppercase_suffix_cif, notes):
        path.write_text("data_test\n", encoding="utf-8")
    nested.mkdir()
    nested_cif.write_text("data_nested\n", encoding="utf-8")

    paths = initial_gui_cif_paths([cif, notes, nested, uppercase_suffix_cif, cif, tmp_path / "missing.cif"])

    assert paths == [cif.resolve(), nested_cif.resolve(), uppercase_suffix_cif.resolve()]


def test_gui_splits_drop_event_paths_with_spaces(tmp_path: Path) -> None:
    from cif2peaks.gui import split_drop_event_paths

    spaced_cif = tmp_path / "Ti beta.cif"
    folder = tmp_path / "folder with spaces"
    drop_data = f"{{{spaced_cif}}} {{{folder}}}"

    paths = split_drop_event_paths(drop_data, lambda value: (str(spaced_cif), str(folder)))

    assert paths == [str(spaced_cif), str(folder)]


def test_gui_drop_adds_cifs_and_reports_ignored_inputs(tmp_path: Path) -> None:
    from cif2peaks.gui import add_gui_cif_inputs

    cif = tmp_path / "Ti beta.cif"
    uppercase_cif = tmp_path / "Ti copy.CIF"
    notes = tmp_path / "notes.txt"
    folder = tmp_path / "folder"
    nested_cif = folder / "nested.cif"
    empty_folder = tmp_path / "empty"
    for path in (cif, uppercase_cif, notes):
        path.write_text("data_test\n", encoding="utf-8")
    folder.mkdir()
    empty_folder.mkdir()
    nested_cif.write_text("data_nested\n", encoding="utf-8")
    selected_paths = [cif.resolve()]

    result = add_gui_cif_inputs(selected_paths, [cif, uppercase_cif, notes, folder, empty_folder, tmp_path / "missing.cif"])

    assert result.added_count == 2
    assert result.ignored_count == 4
    assert selected_paths == [cif.resolve(), uppercase_cif.resolve(), nested_cif.resolve()]


def test_gui_language_pack_covers_primary_controls() -> None:
    from cif2peaks.gui import GUI_TEXT, SUPPORTED_GUI_LANGUAGES

    required_keys = {
        "window_title",
        "app_title",
        "app_subtitle",
        "developer_credit",
        "toggle_language",
        "files_panel",
        "display_name_label",
        "apply_display_name",
        "reset_display_name",
        "add_files",
        "add_folder",
        "remove_selected",
        "clear_files",
        "settings_panel",
        "output_file",
        "choose_output",
        "xray_preset",
        "manual_energy",
        "d_range",
        "preview_panel",
        "tree_display_name",
        "tree_formula",
        "tree_space_group",
        "tree_status",
        "tree_warning",
        "export_excel",
        "open_excel",
    }

    assert set(SUPPORTED_GUI_LANGUAGES) == {"zh", "en"}
    for language in SUPPORTED_GUI_LANGUAGES:
        missing = [key for key in sorted(required_keys) if not GUI_TEXT[language].get(key)]
        assert not missing


def test_gui_export_uses_custom_cif_display_names_and_preserves_original_cif_trace(tmp_path: Path) -> None:
    from cif2peaks.gui import run_simple_gui_export

    cif1 = tmp_path / TI_BETA_CIF.name
    cif2 = tmp_path / TI_NB_HCP_CIF.name
    cif1.write_bytes(TI_BETA_CIF.read_bytes())
    cif2.write_bytes(TI_NB_HCP_CIF.read_bytes())
    output = tmp_path / "custom_names.xlsx"

    result = run_simple_gui_export(
        [cif1, cif2],
        output,
        display_names={
            cif1: "Beta Ti sample A",
            str(cif2.resolve()): "HCP Ti-Nb reference",
        },
    )

    assert [row[0] for row in result.phase_rows] == ["Beta Ti sample A", "HCP Ti-Nb reference"]

    combined_rows = _worksheet_rows(output, 2)
    headers = combined_rows[0]
    phase_index = headers.index("phase_name")
    cif_name_index = headers.index("cif_name")
    assert "Beta Ti sample A" in {row[phase_index] for row in combined_rows[1:]}
    assert "HCP Ti-Nb reference" in {row[phase_index] for row in combined_rows[1:]}
    assert {row[cif_name_index] for row in combined_rows[1:]} == {cif1.name, cif2.name}

    summary_rows = _worksheet_rows(output, 1)
    summary_header_index = next(index for index, row in enumerate(summary_rows) if row and row[0] == "phase_name")
    summary_header = summary_rows[summary_header_index]
    summary_data = summary_rows[summary_header_index + 1 : summary_header_index + 3]
    assert "cif_path" in summary_header
    assert [row[0] for row in summary_data] == ["Beta Ti sample A", "HCP Ti-Nb reference"]
    assert {row[summary_header.index("cif_name")] for row in summary_data} == {cif1.name, cif2.name}
    assert {row[summary_header.index("cif_path")] for row in summary_data} == {str(cif1.resolve()), str(cif2.resolve())}

    with ZipFile(output) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
    assert "Beta Ti sample A" in workbook_xml
    assert "HCP Ti-Nb reference" in workbook_xml


def test_quick_export_uses_dragged_cifs_and_smart_default_output(tmp_path: Path) -> None:
    from cif2peaks.quick_export import quick_export_cif2peaks

    cif1 = tmp_path / TI_BETA_CIF.name
    cif2 = tmp_path / TI_NB_HCP_CIF.name
    cif1.write_bytes(TI_BETA_CIF.read_bytes())
    cif2.write_bytes(TI_NB_HCP_CIF.read_bytes())

    result = quick_export_cif2peaks([cif1, cif2])

    assert result.output_path == tmp_path / "CIF2Peaks峰表_2个CIF.xlsx"
    assert result.output_path.exists()
    assert result.total_peaks > 0


def test_quick_export_accepts_output_override(tmp_path: Path) -> None:
    from cif2peaks.quick_export import quick_export_cif2peaks

    output = tmp_path / "custom_result.xlsx"

    result = quick_export_cif2peaks([TI_BETA_CIF], output_path=output)

    assert result.output_path == output.resolve()
    assert output.exists()
    assert result.total_peaks > 0


def test_quick_export_cli_treats_diagnostic_workbook_as_success(tmp_path: Path) -> None:
    bad_cif = tmp_path / "bad.cif"
    output = tmp_path / "diagnostic.xlsx"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "cif2peaks.quick_export", str(bad_cif), "-o", str(output)],
        cwd=ROOT,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert "未得到可用峰记录" in result.stdout
    assert "Summary" in result.stdout


def test_gui_completion_message_explains_diagnostic_workbook(tmp_path: Path) -> None:
    from cif2peaks.gui import gui_export_completion_text, run_simple_gui_export

    bad_cif = tmp_path / "bad.cif"
    output = tmp_path / "diagnostic.xlsx"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = run_simple_gui_export([bad_cif], output)
    status_text, dialog_text = gui_export_completion_text(result)

    assert result.total_peaks == 0
    assert "诊断 Excel" in status_text
    assert "未得到可用峰记录" in dialog_text
    assert "Summary" in dialog_text
    assert str(output) in dialog_text


def test_gui_open_result_prefers_excel_file(tmp_path: Path) -> None:
    from cif2peaks.gui import open_export_result

    output = tmp_path / "result.xlsx"
    opened: list[str] = []

    opened_path = open_export_result(output, opener=lambda target: opened.append(target))

    assert opened_path == output
    assert opened == [str(output)]


def test_gui_open_result_falls_back_to_folder_when_file_open_fails(tmp_path: Path) -> None:
    from cif2peaks.gui import open_export_result

    output = tmp_path / "result.xlsx"
    opened: list[str] = []

    def opener(target: str) -> None:
        opened.append(target)
        if target == str(output):
            raise OSError("no app associated")

    opened_path = open_export_result(output, opener=opener)

    assert opened_path == output.parent
    assert opened == [str(output), str(output.parent)]


def test_gui_export_summarizes_bad_cif_with_friendly_chinese_message(tmp_path: Path) -> None:
    from cif2peaks.gui import run_simple_gui_export

    bad_cif = tmp_path / "bad.cif"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = run_simple_gui_export([TI_BETA_CIF, bad_cif], tmp_path / "with_bad.xlsx")

    assert result.total_peaks > 0
    assert result.phase_rows[1][0] == bad_cif.name
    assert result.phase_rows[1][3] == 0
    assert "CIF" in result.phase_rows[1][4]
    assert "格式" in result.phase_rows[1][4]
    assert "Traceback" not in result.phase_rows[1][4]
    assert "[Errno" not in result.phase_rows[1][4]


def test_gui_configures_tcl_tk_environment_from_python_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cif2peaks.gui import _configure_tcl_tk_environment

    tcl_dir = tmp_path / "tcl" / "tcl8.6"
    tk_dir = tmp_path / "tcl" / "tk8.6"
    tcl_dir.mkdir(parents=True)
    tk_dir.mkdir(parents=True)
    (tcl_dir / "init.tcl").write_text("", encoding="utf-8")
    (tk_dir / "tk.tcl").write_text("", encoding="utf-8")
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)

    _configure_tcl_tk_environment(tmp_path)

    assert os.environ["TCL_LIBRARY"] == str(tcl_dir)
    assert os.environ["TK_LIBRARY"] == str(tk_dir)


def test_simple_gui_export_writes_xlsx_without_json_sidecar(tmp_path: Path) -> None:
    from cif2peaks.gui import run_simple_gui_export

    output_without_suffix = tmp_path / "gui_reference"

    result = run_simple_gui_export([TI_BETA_CIF], output_without_suffix, energy_keV="20.0")

    assert result.output_path == output_without_suffix.with_suffix(".xlsx")
    assert result.output_path.exists()
    assert not result.output_path.with_suffix(".json").exists()
    assert result.total_peaks > 0
    assert result.phase_rows[0][0] == "ti_beta_bcc_im3m.cif"
    assert result.phase_rows[0][1] == "Ti"
    assert result.phase_rows[0][3] == result.total_peaks
    assert result.phase_rows[0][4] == ""


def test_simple_gui_export_filters_by_d_range_and_records_summary(tmp_path: Path) -> None:
    from cif2peaks.gui import run_simple_gui_export

    output = tmp_path / "d_filtered.xlsx"

    result = run_simple_gui_export([TI_BETA_CIF], output, d_min_A="1.0", d_max_A="2.0")

    assert result.output_path == output
    assert result.total_peaks > 0
    combined_rows = _worksheet_rows(output, 2)
    d_values = [float(row[5]) for row in combined_rows[1:]]
    assert d_values
    assert all(1.0 <= value <= 2.0 for value in d_values)
    summary = {row[0]: row[1] for row in _worksheet_rows(output, 1) if len(row) >= 2}
    assert summary["d_min_A"] == "1"
    assert summary["d_max_A"] == "2"
    assert float(summary["two_theta_min_deg"]) > 0.0
    assert float(summary["two_theta_max_deg"]) < 180.0
