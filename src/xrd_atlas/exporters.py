from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from .models import ExperimentalPattern, XrdAtlasExportPayload, XrdAtlasPeakRow, XrdPhase
from .service import phase_peak_rows
from .utils import friendly_cif_issue_message, now_iso, package_versions


PEAK_HEADERS = [
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
    "family_label",
    "h",
    "k",
    "l",
    "g_1_over_A",
    "q_1_over_A",
    "theta_deg",
    "two_theta_cu_ka_deg",
]

PEAK_REFERENCE_HEADERS = [
    "phase_name",
    "cif_name",
    "formula",
    "space_group",
    "hkl",
    "family_label",
    "d_A",
    "two_theta_deg",
    "two_theta_cu_ka_deg",
    "relative_intensity",
    "multiplicity",
    "warnings",
]

BEGINNER_PEAK_HEADERS = [
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


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _row_to_dict(row: XrdAtlasPeakRow) -> dict[str, Any]:
    return asdict(row)


def combined_peak_rows(phases: list[XrdPhase]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in phases:
        crystal = phase.crystal
        warnings_text = " | ".join(phase.warning_messages)
        for row in phase_peak_rows(phase):
            values = _row_to_dict(row)
            values.update(
                {
                    "formula": "" if crystal is None else crystal.formula,
                    "space_group": phase.display_space_group,
                    "hkl": f"({row.h} {row.k} {row.l})",
                    "warnings": warnings_text,
                }
            )
            rows.append(values)
    return rows


def peak_reference_rows(phases: list[XrdPhase]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in phases:
        crystal = phase.crystal
        warnings_text = " | ".join(phase.warning_messages)
        for row in phase_peak_rows(phase):
            rows.append(
                {
                    "phase_name": phase.phase_name,
                    "cif_name": phase.cif_path.name,
                    "formula": "" if crystal is None else crystal.formula,
                    "space_group": phase.display_space_group,
                    "hkl": f"({row.h} {row.k} {row.l})",
                    "family_label": row.family_label,
                    "d_A": row.d_A,
                    "two_theta_deg": row.two_theta_current_deg,
                    "two_theta_cu_ka_deg": row.two_theta_cu_ka_deg,
                    "relative_intensity": row.relative_intensity,
                    "multiplicity": row.multiplicity,
                    "warnings": warnings_text,
                }
            )
    return rows


def export_peak_reference_csv(payload: XrdAtlasExportPayload, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PEAK_REFERENCE_HEADERS)
        writer.writeheader()
        writer.writerows(peak_reference_rows(payload.phases))


def _summary_rows(payload: XrdAtlasExportPayload) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["XRD Atlas export", "theoretical powder XRD simulation; not experimental fitting"],
        ["exported_at", now_iso()],
        ["xray_input_mode", payload.settings.input_mode],
        ["source_preset", payload.settings.source_preset],
        ["energy_keV", payload.settings.energy_keV],
        ["wavelength_A", payload.settings.wavelength_A],
        ["two_theta_min_deg", payload.settings.two_theta_min_deg],
        ["two_theta_max_deg", payload.settings.two_theta_max_deg],
        ["step_deg", payload.settings.step_deg],
        ["fwhm_deg", payload.settings.fwhm_deg],
        ["display_axis_mode", payload.settings.axis_mode],
        ["q_definition", "q = 4*pi*sin(theta)/lambda"],
        ["g_definition", "g = 1/d"],
        [],
        ["phase_name", "cif_name", "cif_hash", "formula", "space_group", "enabled", "peak_count", "error", "warnings"],
    ]
    for phase in payload.phases:
        crystal = phase.crystal
        rows.append(
            [
                phase.phase_name,
                phase.cif_path.name,
                "" if crystal is None else crystal.cif_hash,
                "" if crystal is None else crystal.formula,
                phase.display_space_group,
                phase.enabled,
                0 if phase.result is None else len(phase.result.peaks),
                friendly_cif_issue_message(phase.error, []),
                " | ".join(phase.warning_messages),
            ]
        )
    return rows


def _experimental_rows(patterns: list[ExperimentalPattern]) -> list[list[Any]]:
    rows: list[list[Any]] = [["pattern_label", "source_file", "axis_mode", "x", "relative_intensity"]]
    for pattern in patterns:
        for x_value, intensity in zip(pattern.x_values, pattern.intensity, strict=True):
            rows.append([pattern.label, str(pattern.path), pattern.axis_mode, float(x_value), float(intensity)])
    return rows


def _user_guide_rows(payload: XrdAtlasExportPayload) -> list[list[Any]]:
    return [
        ["XRD Atlas 使用说明", ""],
        ["这是什么", "从 CIF 晶体结构计算理论粉末 XRD 峰表，便于在 Excel、Origin 或 Python 中继续分析。"],
        ["默认参数", f"{payload.settings.source_preset}，2θ {payload.settings.two_theta_min_deg:g}-{payload.settings.two_theta_max_deg:g}°"],
        ["最快使用", "普通用户先看 推荐峰表；需要英文列名或完整字段时再看 Combined Peaks。"],
        ["注意", "这是理论峰表，不是实验谱拟合、物相检索数据库或 Rietveld 精修。"],
        [],
        ["工作表", "内容"],
        ["Summary", "导出参数、每个 CIF 的读取状态、错误和警告。"],
        ["推荐峰表", "中文列名的常用峰表，适合直接查看、筛选和复制到 Origin。"],
        ["Combined Peaks", "英文列名的完整合并峰表，适合程序读取或后续批处理。"],
        ["各相工作表", "单个 CIF/相的峰表，名称来自 CIF 文件名。"],
        [],
        ["常用列名", "含义"],
        ["phase_name", "相名，默认来自 CIF 文件名。"],
        ["cif_name", "原始 CIF 文件名。"],
        ["formula", "程序从 CIF 读取到的化学式。"],
        ["space_group", "空间群。"],
        ["hkl", "晶面指数。"],
        ["d_A", "晶面间距 d，单位 Å。"],
        ["two_theta_current_deg", "当前设置下的 2θ 位置，单位 °。"],
        ["two_theta_cu_ka_deg", "Cu Kα 条件下的 2θ 位置，单位 °。"],
        ["relative_intensity", "归一化相对强度，最强峰为 100。"],
        ["warnings", "CIF 读取或计算过程中的提示；为空通常表示无明显问题。"],
    ]


def export_xrd_atlas_json(payload: XrdAtlasExportPayload, output_path: str | Path) -> None:
    data = {
        "metadata": {
            "exported_at": now_iso(),
            "application": "XRD Atlas",
            "coordinate_definitions": {
                "q_1_over_A": "4*pi*sin(theta)/lambda",
                "g_1_over_A": "1/d",
            },
            "software_versions": package_versions(),
        },
        "settings": _to_jsonable(asdict(payload.settings)),
        "phases": [
            {
                "phase_name": phase.phase_name,
                "cif_path": str(phase.cif_path),
                "enabled": phase.enabled,
                "error": phase.error,
                "crystal": None
                if phase.crystal is None
                else {
                    "cif_hash": phase.crystal.cif_hash,
                    "formula": phase.crystal.formula,
                    "space_group": phase.display_space_group,
                    "cell_parameters": phase.crystal.cell_parameters,
                },
                "metadata": {} if phase.result is None else _to_jsonable(phase.result.metadata),
                "peaks": [_to_jsonable(row) for row in combined_peak_rows([phase])],
            }
            for phase in payload.phases
        ],
        "experimental_patterns": [
            {
                "label": pattern.label,
                "path": str(pattern.path),
                "axis_mode": pattern.axis_mode,
                "point_count": int(len(pattern.x_values)),
            }
            for pattern in payload.experimental_patterns
        ],
    }
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(ref: str, value: Any) -> str:
    if value is None:
        return f'<c r="{ref}" t="inlineStr"><is><t></t></is></c>'
    if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(float(value)):
        return f'<c r="{ref}"><v>{float(value):.12g}</v></c>'
    text = html.escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _table_column_widths(headers: list[Any]) -> list[int]:
    default_widths = {
        "phase_name": 24,
        "cif_name": 28,
        "formula": 16,
        "space_group": 16,
        "hkl": 12,
        "d_A": 12,
        "two_theta_current_deg": 20,
        "two_theta_deg": 16,
        "two_theta_cu_ka_deg": 20,
        "relative_intensity": 18,
        "multiplicity": 14,
        "warnings": 42,
        "family_label": 18,
        "g_1_over_A": 14,
        "q_1_over_A": 14,
        "theta_deg": 12,
        "相名": 22,
        "CIF 文件": 28,
        "化学式": 16,
        "空间群": 16,
        "晶面 hkl": 12,
        "d 间距 (Å)": 14,
        "2θ 当前设置 (°)": 20,
        "2θ Cu Kα (°)": 18,
        "相对强度": 14,
        "多重性": 12,
        "提示": 42,
    }
    return [default_widths.get(str(header), max(10, min(24, len(str(header)) + 2))) for header in headers]


def _is_table_sheet(rows: list[list[Any]]) -> bool:
    if not rows:
        return False
    headers = [str(value) for value in rows[0]]
    return (
        headers == PEAK_HEADERS
        or headers == BEGINNER_PEAK_HEADERS
        or headers == ["pattern_label", "source_file", "axis_mode", "x", "relative_intensity"]
    )


def _is_user_guide_sheet(rows: list[list[Any]]) -> bool:
    return bool(rows and rows[0] and rows[0][0] == "XRD Atlas 使用说明")


def _table_sheet_preamble(rows: list[list[Any]]) -> str:
    if _is_user_guide_sheet(rows):
        return (
            '<cols>'
            '<col min="1" max="1" width="24" customWidth="1"/>'
            '<col min="2" max="2" width="88" customWidth="1"/>'
            "</cols>"
        )
    if not _is_table_sheet(rows):
        return ""
    widths = _table_column_widths(rows[0])
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    return (
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft"/>'
        "</sheetView></sheetViews>"
        f"<cols>{cols}</cols>"
    )


def _table_sheet_postamble(rows: list[list[Any]]) -> str:
    if not _is_table_sheet(rows):
        return ""
    last_column = _xlsx_column_name(len(rows[0]))
    last_row = max(1, len(rows))
    return f'<autoFilter ref="A1:{last_column}{last_row}"/>'


def _sheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            cells.append(_xlsx_cell(f"{_xlsx_column_name(col_index)}{row_index}", value))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{_table_sheet_preamble(rows)}<sheetData>{"".join(xml_rows)}</sheetData>{_table_sheet_postamble(rows)}'
        "</worksheet>"
    )


def _safe_sheet_name(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", "_", name).strip() or "Sheet"
    cleaned = cleaned[:31]
    base = cleaned
    suffix = 1
    while cleaned in used:
        tail = f"_{suffix}"
        cleaned = (base[: 31 - len(tail)] + tail)[:31]
        suffix += 1
    used.add(cleaned)
    return cleaned


def _peak_rows_for_sheet(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [PEAK_HEADERS, *[[row.get(header, "") for header in PEAK_HEADERS] for row in rows]]


def _beginner_peak_rows_for_sheet(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        BEGINNER_PEAK_HEADERS,
        *[
            [
                row.get("phase_name", ""),
                row.get("cif_name", ""),
                row.get("formula", ""),
                row.get("space_group", ""),
                row.get("hkl", ""),
                row.get("d_A", ""),
                row.get("two_theta_current_deg", ""),
                row.get("two_theta_cu_ka_deg", ""),
                row.get("relative_intensity", ""),
                row.get("multiplicity", ""),
                row.get("warnings", ""),
            ]
            for row in rows
        ],
    ]


def export_xrd_atlas_workbook(payload: XrdAtlasExportPayload, output_path: str | Path) -> None:
    sheets: list[tuple[str, list[list[Any]]]] = []
    used: set[str] = set()
    combined_rows = combined_peak_rows(payload.phases)
    sheets.append((_safe_sheet_name("Summary", used), _summary_rows(payload)))
    sheets.append((_safe_sheet_name("Combined Peaks", used), _peak_rows_for_sheet(combined_rows)))
    sheets.append((_safe_sheet_name("推荐峰表", used), _beginner_peak_rows_for_sheet(combined_rows)))
    for phase in payload.phases:
        sheets.append((_safe_sheet_name(phase.phase_name, used), _peak_rows_for_sheet(combined_peak_rows([phase]))))
    if payload.experimental_patterns:
        sheets.append((_safe_sheet_name("Experimental Data", used), _experimental_rows(payload.experimental_patterns)))
    sheets.append((_safe_sheet_name("使用说明", used), _user_guide_rows(payload)))

    with ZipFile(Path(output_path), "w", ZIP_DEFLATED) as archive:
        content_overrides = [
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
        ]
        for index in range(1, len(sheets) + 1):
            content_overrides.append(
                f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'{"".join(content_overrides)}'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>",
        )
        sheet_defs = []
        rel_defs = []
        for index, (name, rows) in enumerate(sheets, start=1):
            sheet_defs.append(f'<sheet name="{html.escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
            rel_defs.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<bookViews><workbookView activeTab="{len(sheets) - 1}"/></bookViews>'
            f'<sheets>{"".join(sheet_defs)}</sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rel_defs)}</Relationships>',
        )
        archive.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>XRD Atlas export</dc:title></cp:coreProperties>',
        )
        archive.writestr(
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>XRD Atlas</Application></Properties>",
        )
