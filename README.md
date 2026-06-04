# CIF2Peaks: a lightweight CIF-to-indexed-powder-diffraction peak table generator for materials research

CIF2Peaks converts CIF crystal structures into indexed theoretical powder XRD
peak reference tables for materials research.

It is designed for materials researchers who need a practical way to batch
export phase, hkl, d-spacing, 2theta, q, g, relative intensity, and warnings
into Excel for follow-up work in Excel, Origin, Python, or lab notebooks.

## Features

- Load one CIF file, many CIF files, or a folder of CIF files.
- Export one combined Excel workbook with:
  - `Summary`
  - `Combined Peaks`
  - `Elastic Constants`
  - one sheet per phase
- Use the desktop GUI for non-programming workflows.
- Drag CIF files or CIF folders directly into the GUI window.
- Optionally enter per-phase elastic constants (`C11,C12,C44` or a full 6x6
  `Cij` matrix) and export hkl-normal Young's modulus columns.
- Use the CLI for reproducible batch processing.
- Choose visible GUI X-ray presets (`Cu Kα`, `30 keV`, `83 keV`) or enter a manual energy.
- Keep going when one CIF fails; errors and warnings are written to `Summary`.
- Handles common multi-block CIF files by selecting the structural block.

## Install

Python 3.11 or newer is required.

```powershell
cd C:\path\to\CIF2Peaks
py -3.11 -m pip install -e .[dev]
```

## GUI Quick Start

Start the desktop app:

```powershell
cif2peaks-gui
```

Or run it from the project folder:

```powershell
py -3.11 -m cif2peaks.gui
```

Basic workflow:

1. Drag `.cif` files or a CIF folder into the window, or click `Add files` / `Add folder`.
2. Choose an X-ray preset (`Cu Kα`, `30 keV`, `83 keV`) or enter a manual energy in keV.
3. Confirm the d range in Angstrom and output `.xlsx` path. Leave either d boundary blank to keep it unrestricted.
4. Click `Export Excel`.

Manual energy has priority over the selected preset. Leave the manual energy
field blank to use the preset.

## CLI Examples

Export all CIF files in a folder:

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.xlsx
```

Export several CIF files:

```powershell
cif2peaks phase1.cif phase2.cif phase3.cif -o result.xlsx
```

Use a custom X-ray energy:

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.xlsx --energy-keV 20
```

Use a custom wavelength:

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.xlsx --wavelength-A 1.5406
```

Limit the 2theta range:

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.xlsx --source "Cu Ka" --two-theta-min 20 --two-theta-max 100
```

Export CSV instead of Excel:

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.csv
```

## Output Columns

The peak tables include:

- `phase_name`
- `cif_name`
- `formula`
- `space_group`
- `hkl`
- `d_A`
- `two_theta_current_deg`
- `relative_intensity`
- `material_scattering_factor_R_hkl`
- `theoretical_intensity_unscaled`
- `cell_volume_A3`
- `lp_factor`
- `multiplicity_structure_factor_sq`
- `r_hkl_model_note`
- `multiplicity`
- `family_label`
- `h`, `k`, `l`
- `g_1_over_A`
- `q_1_over_A`
- `theta_deg`
- `two_theta_cu_ka_deg`
- `warnings`
- `young_modulus_hkl_normal_GPa`
- `elastic_status`
- `elastic_warning`
- `elastic_hkl_used`
- `elastic_family_count`
- `elastic_family_moduli_GPa`
- `elastic_modulus_note`

## Scientific Scope

CIF2Peaks exports theoretical powder XRD peak references from CIF structures.
For direct comparison phase-fraction workflows, CIF2Peaks also exports a
per-peak material scattering factor:

```text
R_hkl = I_unscaled / V_cell^2
I_unscaled ≈ p_hkl |F_hkl|^2 LP
```

Here `I_unscaled` comes from `pymatgen`'s unscaled theoretical powder
intensity, `V_cell` is the CIF/Pymatgen unit-cell volume, `p_hkl` is the
multiplicity term, and `LP` is the Lorentz-polarization factor. If no reliable
temperature-factor data are supplied, CIF2Peaks assumes `e^-2M = 1`.
Experimental absorption, detector geometry, and synchrotron polarization
corrections are not included.

In Excel, an experimental integrated peak intensity `I_exp,j` can be corrected
as `I_exp,j / material_scattering_factor_R_hkl,j`. Average those corrected
values over the chosen peaks for each phase, then use the phase averages to
estimate volume fractions, for example `f_B2 = S_B2 / (S_B2 + S_gamma)`.
This `R_hkl` is not a Rietveld refinement residual such as `Rp`, `Rwp`, or
`Rexp`.

When Cij values are supplied, `young_modulus_hkl_normal_GPa` is calculated
from the user-provided stiffness matrix and the CIF lattice-derived hkl plane
normal. It is not an experimental modulus and is not inferred from the CIF
alone.
For four-index Miller-Bravais plane labels, the elastic calculation only uses
valid plane indices satisfying `i = -(h + k)` and reports the three-index
`elastic_hkl_used`. If one simulated powder peak contains multiple hkl
families, the primary modulus follows the representative hkl and
`elastic_family_moduli_GPa` lists the family-level values.
The default Cij coordinate-frame assumption is
`crystal_cartesian_from_cif_lattice`; CIF2Peaks does not rotate literature Cij
matrices between alternate crystallographic settings.

It is not:

- an experimental pattern fitting program
- a phase identification database
- a Rietveld refinement tool
- a replacement for instrument calibration

For phase and peak-position comparison, prioritize `phase_name`, `hkl`, `d_A`,
and `two_theta_current_deg`. Treat relative intensity as a theoretical
reference, not as a refined experimental quantity.

## Windows 普通用户

推荐把整个项目文件夹放在一个固定位置，然后双击：

```text
start_cif2peaks.bat
```

首次运行时，脚本会自动检查 Python、修正 Tk/Tcl 路径，并尝试安装所需依赖。
打开 GUI 后，普通用户只需要：

1. 把 `.cif` 文件或包含 CIF 的文件夹直接拖入窗口，或点击 `添加文件` / `添加文件夹`。
2. 选择 X 射线预设（`Cu Kα`、`30 keV`、`83 keV`），必要时填写手动能量 keV。
3. 确认自动生成的 Excel 保存位置和 d 范围（Å）；任一边界留空表示不限制。
4. 点击 `导出 Excel`。

默认参数为 Cu Kα、d 范围不限制。手动能量非空时优先生效；留空则使用所选预设。

也可以把一个或多个 `.cif` 文件，或包含 CIF 的文件夹，直接拖到
`start_cif2peaks.bat` 上。GUI 会自动载入这些 CIF，并自动建议 Excel 保存位置。
打开 GUI 后，也可以继续把 CIF 文件或文件夹拖入窗口追加加载；程序会自动去重并忽略非 CIF 文件。

如果只想直接得到 Excel，不需要打开 GUI，可以把 `.cif` 文件或 CIF 文件夹拖到：

```text
quick_export_cif2peaks.bat
```

它会使用默认 Cu Kα、2θ 0-180°，并把结果保存到第一个 CIF 所在文件夹。

导出的 Excel 会默认打开 `使用说明` 工作表，普通用户先看这里即可。
最常用峰表在 `推荐峰表`，使用中文列名；完整英文列名峰表保留在 `Combined Peaks`，便于程序读取。
如果 CIF 无法解析，程序仍会生成 Excel 诊断文件；请查看 `Summary` 中的错误提示。

如果需要把程序发给没有 Python 环境的 Windows 电脑，先在开发电脑上双击：

```text
build_windows_app.bat
```

打包成功后，优先把 `dist\CIF2Peaks_Windows_Portable.zip` 发给目标电脑。
目标电脑解压后进入 `CIF2Peaks` 文件夹，先双击 `windows_self_test.bat`。
目标电脑不需要安装 Python。

在目标电脑上：

- 双击 `CIF2Peaks.exe` 打开 GUI。
- 把 CIF 文件或文件夹拖到 `CIF2Peaks.exe` 上，会自动载入 GUI。
- 把 CIF 文件或文件夹拖到 `CIF2Peaks Quick Export.exe` 上，会直接导出 Excel。

## Tests

```powershell
cd C:\path\to\CIF2Peaks
py -3.11 -m pytest -q
```

## License

MIT License. See [LICENSE](LICENSE).
