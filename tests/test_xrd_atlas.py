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

from xrd_atlas.batch import batch_export_peak_reference
from xrd_atlas.exporters import combined_peak_rows, export_peak_reference_csv, export_xrd_atlas_workbook
from xrd_atlas.models import XrdAtlasExportPayload, XrdAtlasSettings
from xrd_atlas.service import XrdAtlasService


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


def test_project_is_cli_only_without_gui_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(project["project"]["dependencies"])
    scripts = project["project"]["scripts"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "PySide6" not in dependencies
    assert "matplotlib" not in dependencies
    assert "PySide6" not in requirements
    assert "matplotlib" not in requirements
    assert scripts["xrd-atlas"] == "xrd_atlas.batch:main"
    assert scripts["xrd-atlas-peaks"] == "xrd_atlas.batch:main"
    assert scripts["xrd-atlas-gui"] == "xrd_atlas.gui:main"
    assert scripts["xrd-atlas-quick-export"] == "xrd_atlas.quick_export:main"


def test_windows_build_includes_gui_and_quick_export_apps() -> None:
    build_script = (ROOT / "build_windows_app.bat").read_text(encoding="ascii")

    assert '--name "XRD Atlas"' in build_script
    assert "--name \"XRD Atlas Quick Export\"" in build_script
    assert "scripts\\xrd_atlas_windows.py" in build_script
    assert "scripts\\xrd_atlas_quick_export_windows.py" in build_script


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
    assert "xrd_atlas_self_test_report.txt" in self_test
    assert "Windows version" in self_test
    assert "XRD Atlas folder" in self_test
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
    assert "XRD_Atlas_Windows_Portable.zip" in build_script


def test_windows_portable_zip_contains_complete_folder(tmp_path: Path) -> None:
    from scripts.package_windows_portable import package_portable_app

    app_dir = tmp_path / "XRD Atlas"
    internal = app_dir / "_internal"
    examples = app_dir / "examples" / "cif"
    internal.mkdir(parents=True)
    examples.mkdir(parents=True)
    for relative in (
        "XRD Atlas.exe",
        "XRD Atlas Quick Export.exe",
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

    zip_path = package_portable_app(app_dir, tmp_path / "XRD_Atlas_Windows_Portable.zip")

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "XRD Atlas/XRD Atlas.exe" in names
    assert "XRD Atlas/XRD Atlas Quick Export.exe" in names
    assert "XRD Atlas/README_WINDOWS.txt" in names
    assert "XRD Atlas/windows_self_test.bat" in names
    assert "XRD Atlas/examples/cif/demo.cif" in names
    assert "XRD Atlas/_internal/tcl86t.dll" in names
    assert "XRD Atlas/_internal/tk86t.dll" in names
    assert "XRD Atlas/_internal/_tcl_data/init.tcl" in names
    assert "XRD Atlas/_internal/_tk_data/tk.tcl" in names


def test_windows_portable_zip_requires_tcl_tk_runtime_data(tmp_path: Path) -> None:
    from scripts.package_windows_portable import package_portable_app

    app_dir = tmp_path / "XRD Atlas"
    for relative in (
        "XRD Atlas.exe",
        "XRD Atlas Quick Export.exe",
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
        package_portable_app(app_dir, tmp_path / "XRD_Atlas_Windows_Portable.zip")

    message = str(exc_info.value)
    assert "_internal/_tcl_data/init.tcl" in message
    assert "_internal/_tk_data/tk.tcl" in message


def test_windows_quick_export_entry_exports_without_python_gui(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "xrd_atlas_quick_export_windows.py"
    cif_path = tmp_path / TI_BETA_CIF.name
    cif_path.write_bytes(TI_BETA_CIF.read_bytes())

    result = subprocess.run(
        [sys.executable, str(script), str(cif_path)],
        cwd=ROOT,
        env={**_subprocess_env(), "XRD_ATLAS_SMOKE_TEST": "1"},
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    expected_output = tmp_path / f"{cif_path.stem}_XRD峰表.xlsx"
    assert expected_output.name in result.stdout
    assert expected_output.exists()


def test_windows_quick_export_entry_treats_diagnostic_workbook_as_success(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "xrd_atlas_quick_export_windows.py"
    bad_cif = tmp_path / "bad.cif"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), str(bad_cif)],
        cwd=ROOT,
        env={**_subprocess_env(), "XRD_ATLAS_SMOKE_TEST": "1"},
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    expected_output = tmp_path / "bad_XRD峰表.xlsx"
    assert result.returncode == 0, result.stderr
    assert expected_output.exists()
    assert "未得到可用峰记录" in result.stdout
    assert "Summary" in result.stdout


def test_xrd_atlas_single_cif_peak_table_and_energy_shift() -> None:
    service = XrdAtlasService()
    phase = service.load_phase(TI_BETA_CIF)
    settings = XrdAtlasSettings(input_mode="energy", energy_keV=8.0478, wavelength_A=1.5406)
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
        XrdAtlasSettings(input_mode="energy", energy_keV=20.0, wavelength_A=1.5406),
    )
    assert high_energy_phase.result is not None
    assert high_energy_phase.result.peaks[0].two_theta_deg < phase.result.peaks[0].two_theta_deg
    assert np.isclose(high_energy_phase.result.peaks[0].d_spacing_A, phase.result.peaks[0].d_spacing_A)


def test_xrd_atlas_loads_occupancy_conflict_cif_with_warning(tmp_path: Path) -> None:
    cif_path = _write_ni_occupancy_cif(tmp_path / "Ni.cif")
    service = XrdAtlasService()

    phase = service.load_phase(cif_path)
    service.simulate_phase(phase, XrdAtlasSettings())

    assert phase.error is None
    assert phase.result is not None
    assert len(phase.result.peaks) == 8
    assert any("occupancy" in warning.lower() for warning in phase.warning_messages)


def test_xrd_atlas_loads_standardized_unitcell_from_multi_block_cif(tmp_path: Path) -> None:
    cif_path = _write_multi_block_standardized_cif(tmp_path / "multi_block.cif")
    service = XrdAtlasService()

    phase = service.load_phase(cif_path)

    assert phase.error is None
    assert phase.crystal is not None
    assert phase.display_space_group == "P 1"
    assert phase.crystal.cell_parameters[:3] == (3.0, 3.0, 3.0)


def test_xrd_atlas_batch_loads_real_cifs_and_keeps_occupancy_warning() -> None:
    service = XrdAtlasService()
    phases = service.load_phases(_nb_hea_cif_paths())
    service.simulate_phases(phases, XrdAtlasSettings())

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


def test_xrd_atlas_exports_simple_phase_hkl_d_two_theta_csv(tmp_path: Path) -> None:
    service = XrdAtlasService()
    phases = service.load_phases(_nb_hea_cif_paths())
    settings = XrdAtlasSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "phase_hkl_d_2theta.csv"

    export_peak_reference_csv(XrdAtlasExportPayload(phases, settings), output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {"phase_name", "cif_name", "formula", "space_group", "hkl", "d_A", "two_theta_deg"}.issubset(rows[0])
    assert {row["cif_name"] for row in rows} == {"AlNi.cif", "Cr2Nb.cif", "FeCr.cif", "Ni.cif", "Ni3Al.cif"}
    assert any(row["cif_name"] == "Ni.cif" and row["hkl"] == "(1 1 1)" for row in rows)
    assert all(float(row["d_A"]) > 0 and float(row["two_theta_deg"]) > 0 for row in rows)


def test_xrd_atlas_batch_export_defaults_to_excel_from_many_cifs(tmp_path: Path) -> None:
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


def test_xrd_atlas_batch_export_zr_hydride_multi_block_cifs(tmp_path: Path) -> None:
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


def test_xrd_atlas_batch_export_can_still_write_csv(tmp_path: Path) -> None:
    output = tmp_path / "many_cif_reference.csv"

    phases = batch_export_peak_reference(_nb_hea_cif_paths(), output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(phases) == 5
    assert output.exists()
    assert len(rows) == sum(len(phase.result.peaks) for phase in phases if phase.result is not None)
    assert {row["phase_name"] for row in rows} >= {"AlNi", "Cr2Nb", "FeCr", "Ni", "Ni3Al"}


def test_xrd_atlas_batch_load_isolates_unrecoverable_bad_cif(tmp_path: Path) -> None:
    bad_cif = tmp_path / "bad.cif"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")
    service = XrdAtlasService()

    phases = service.load_phases([TI_BETA_CIF, bad_cif])
    service.simulate_phases(phases, XrdAtlasSettings())
    output = tmp_path / "with_bad_cif.xlsx"
    export_xrd_atlas_workbook(XrdAtlasExportPayload(phases, XrdAtlasSettings()), output)

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


def test_xrd_atlas_multi_phase_workbook_export(tmp_path: Path) -> None:
    service = XrdAtlasService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = XrdAtlasSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "xrd_atlas_export.xlsx"
    export_xrd_atlas_workbook(XrdAtlasExportPayload(phases, settings), output)
    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        combined = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
    assert "Summary" in workbook
    assert "Combined Peaks" in workbook
    assert "ti_beta_bcc_im3m" in workbook
    assert "ti_nb_hcp_p63mmc" in workbook
    assert combined.count("<row ") > 2


def test_xrd_atlas_workbook_peak_sheets_are_excel_friendly(tmp_path: Path) -> None:
    service = XrdAtlasService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = XrdAtlasSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "friendly.xlsx"

    export_xrd_atlas_workbook(XrdAtlasExportPayload(phases, settings), output)

    with ZipFile(output) as archive:
        combined = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert '<pane ySplit="1" topLeftCell="A2"' in combined
    assert '<autoFilter ref="A1:R' in combined
    assert '<cols>' in combined
    assert 'width="24"' in combined


def test_xrd_atlas_workbook_opens_with_chinese_user_guide(tmp_path: Path) -> None:
    service = XrdAtlasService()
    phase = service.load_phase(TI_BETA_CIF)
    settings = XrdAtlasSettings()
    service.simulate_phase(phase, settings)
    output = tmp_path / "guide.xlsx"

    export_xrd_atlas_workbook(XrdAtlasExportPayload([phase], settings), output)

    with ZipFile(output) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        guide_xml = archive.read("xl/worksheets/sheet5.xml").decode("utf-8")

    assert 'name="使用说明"' in workbook
    assert 'activeTab="4"' in workbook
    assert "默认参数" in guide_xml
    assert "推荐峰表" in guide_xml
    assert "Combined Peaks" in guide_xml
    assert "two_theta_current_deg" in guide_xml


def test_xrd_atlas_workbook_includes_beginner_chinese_peak_table(tmp_path: Path) -> None:
    service = XrdAtlasService()
    phases = [service.load_phase(TI_BETA_CIF), service.load_phase(TI_NB_HCP_CIF)]
    settings = XrdAtlasSettings()
    service.simulate_phases(phases, settings)
    output = tmp_path / "beginner_table.xlsx"

    export_xrd_atlas_workbook(XrdAtlasExportPayload(phases, settings), output)

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


def test_batch_module_help_and_package_main_cli(tmp_path: Path) -> None:
    help_result = subprocess.run(
        [sys.executable, "-m", "xrd_atlas.batch", "--help"],
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
        [sys.executable, "-m", "xrd_atlas", str(TI_BETA_CIF), "-o", str(output)],
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
        [sys.executable, "-m", "xrd_atlas.batch", str(TI_BETA_CIF)],
        cwd=tmp_path,
        env=_subprocess_env(),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "xrd_peak_reference.xlsx").exists()
    assert not (tmp_path / "xrd_peak_reference.csv").exists()


def test_simple_gui_builds_energy_settings_from_user_inputs() -> None:
    from xrd_atlas.constants import X_RAY_ENERGY_WAVELENGTH_KEV_A
    from xrd_atlas.gui import build_gui_settings

    settings = build_gui_settings("20.0", "5", "120")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert np.isclose(settings.wavelength_A, X_RAY_ENERGY_WAVELENGTH_KEV_A / 20.0)
    assert settings.two_theta_min_deg == 5.0
    assert settings.two_theta_max_deg == 120.0


def test_beginner_gui_defaults_to_cu_ka_without_user_parameters() -> None:
    from xrd_atlas.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings()

    assert settings.input_mode == "source"
    assert settings.source_preset == "Cu Ka"
    assert settings.two_theta_min_deg == 0.0
    assert settings.two_theta_max_deg == 180.0


def test_beginner_gui_keeps_cu_ka_when_energy_is_blank() -> None:
    from xrd_atlas.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings(energy_keV=" ")

    assert settings.input_mode == "source"
    assert settings.source_preset == "Cu Ka"


def test_beginner_gui_uses_custom_energy_when_provided() -> None:
    from xrd_atlas.gui import build_beginner_gui_settings

    settings = build_beginner_gui_settings(energy_keV="20.0", two_theta_min="5", two_theta_max="120")

    assert settings.input_mode == "energy"
    assert settings.energy_keV == 20.0
    assert settings.two_theta_min_deg == 5.0
    assert settings.two_theta_max_deg == 120.0


def test_beginner_gui_suggests_clear_output_path(tmp_path: Path) -> None:
    from xrd_atlas.gui import suggest_output_path

    single = suggest_output_path([tmp_path / "Ti.cif"])
    many = suggest_output_path([tmp_path / "Ti.cif", tmp_path / "TiB.cif"])

    assert single == tmp_path / "Ti_XRD峰表.xlsx"
    assert many == tmp_path / "XRD峰表_2个CIF.xlsx"


def test_beginner_gui_turns_common_errors_into_chinese_guidance() -> None:
    from xrd_atlas.gui import friendly_error_message

    assert "请先添加" in friendly_error_message(ValueError("Select at least one CIF file."))
    assert "数字" in friendly_error_message(ValueError("2theta min must be a number."))
    assert "能量" in friendly_error_message(ValueError("X-ray energy keV must be greater than 0."))
    assert "被 Excel 打开" in friendly_error_message(PermissionError("locked"))


def test_beginner_gui_previews_cif_metadata_before_export(tmp_path: Path) -> None:
    from xrd_atlas.gui import preview_simple_gui_inputs

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
    from xrd_atlas.gui import initial_gui_cif_paths

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


def test_quick_export_uses_dragged_cifs_and_smart_default_output(tmp_path: Path) -> None:
    from xrd_atlas.quick_export import quick_export_xrd_atlas

    cif1 = tmp_path / TI_BETA_CIF.name
    cif2 = tmp_path / TI_NB_HCP_CIF.name
    cif1.write_bytes(TI_BETA_CIF.read_bytes())
    cif2.write_bytes(TI_NB_HCP_CIF.read_bytes())

    result = quick_export_xrd_atlas([cif1, cif2])

    assert result.output_path == tmp_path / "XRD峰表_2个CIF.xlsx"
    assert result.output_path.exists()
    assert result.total_peaks > 0


def test_quick_export_accepts_output_override(tmp_path: Path) -> None:
    from xrd_atlas.quick_export import quick_export_xrd_atlas

    output = tmp_path / "custom_result.xlsx"

    result = quick_export_xrd_atlas([TI_BETA_CIF], output_path=output)

    assert result.output_path == output.resolve()
    assert output.exists()
    assert result.total_peaks > 0


def test_quick_export_cli_treats_diagnostic_workbook_as_success(tmp_path: Path) -> None:
    bad_cif = tmp_path / "bad.cif"
    output = tmp_path / "diagnostic.xlsx"
    bad_cif.write_text("data_bad\n_cell_length_a 3\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "xrd_atlas.quick_export", str(bad_cif), "-o", str(output)],
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
    from xrd_atlas.gui import gui_export_completion_text, run_simple_gui_export

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
    from xrd_atlas.gui import open_export_result

    output = tmp_path / "result.xlsx"
    opened: list[str] = []

    opened_path = open_export_result(output, opener=lambda target: opened.append(target))

    assert opened_path == output
    assert opened == [str(output)]


def test_gui_open_result_falls_back_to_folder_when_file_open_fails(tmp_path: Path) -> None:
    from xrd_atlas.gui import open_export_result

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
    from xrd_atlas.gui import run_simple_gui_export

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
    from xrd_atlas.gui import _configure_tcl_tk_environment

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
    from xrd_atlas.gui import run_simple_gui_export

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
