# XRD Atlas

XRD Atlas is a lightweight GUI and CLI tool for converting CIF crystal
structures into theoretical powder XRD peak reference tables.

It is designed for materials researchers who need a practical way to batch
export phase, hkl, d-spacing, 2theta, q, g, relative intensity, and warnings
into Excel for follow-up work in Excel, Origin, Python, or lab notebooks.

## Features

- Load one CIF file, many CIF files, or a folder of CIF files.
- Export one combined Excel workbook with:
  - `Summary`
  - `Combined Peaks`
  - one sheet per phase
- Use the desktop GUI for non-programming workflows.
- Drag CIF files or CIF folders directly into the GUI window.
- Use the CLI for reproducible batch processing.
- Choose visible GUI X-ray presets (`Cu Kα`, `30 keV`, `83 keV`) or enter a manual energy.
- Keep going when one CIF fails; errors and warnings are written to `Summary`.
- Handles common multi-block CIF files by selecting the structural block.

## Install

Python 3.11 or newer is required.

```powershell
cd C:\Users\AORUS\Desktop\xrd_atlas
py -3.11 -m pip install -e .[dev]
```

## GUI Quick Start

Start the desktop app:

```powershell
xrd-atlas-gui
```

Or run it from the project folder:

```powershell
py -3.11 -m xrd_atlas.gui
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
xrd-atlas "C:\path\to\cif_folder" -o result.xlsx
```

Export several CIF files:

```powershell
xrd-atlas phase1.cif phase2.cif phase3.cif -o result.xlsx
```

Use a custom X-ray energy:

```powershell
xrd-atlas "C:\path\to\cif_folder" -o result.xlsx --energy-keV 20
```

Use a custom wavelength:

```powershell
xrd-atlas "C:\path\to\cif_folder" -o result.xlsx --wavelength-A 1.5406
```

Limit the 2theta range:

```powershell
xrd-atlas "C:\path\to\cif_folder" -o result.xlsx --source "Cu Ka" --two-theta-min 20 --two-theta-max 100
```

Export CSV instead of Excel:

```powershell
xrd-atlas "C:\path\to\cif_folder" -o result.csv
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
- `multiplicity`
- `family_label`
- `h`, `k`, `l`
- `g_1_over_A`
- `q_1_over_A`
- `theta_deg`
- `two_theta_cu_ka_deg`
- `warnings`

## Scientific Scope

XRD Atlas exports theoretical powder XRD peak references from CIF structures.

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
start_xrd_atlas.bat
```

首次运行时，脚本会自动检查 Python、修正 Tk/Tcl 路径，并尝试安装所需依赖。
打开 GUI 后，普通用户只需要：

1. 把 `.cif` 文件或包含 CIF 的文件夹直接拖入窗口，或点击 `添加文件` / `添加文件夹`。
2. 选择 X 射线预设（`Cu Kα`、`30 keV`、`83 keV`），必要时填写手动能量 keV。
3. 确认自动生成的 Excel 保存位置和 d 范围（Å）；任一边界留空表示不限制。
4. 点击 `导出 Excel`。

默认参数为 Cu Kα、d 范围不限制。手动能量非空时优先生效；留空则使用所选预设。

也可以把一个或多个 `.cif` 文件，或包含 CIF 的文件夹，直接拖到
`start_xrd_atlas.bat` 上。GUI 会自动载入这些 CIF，并自动建议 Excel 保存位置。
打开 GUI 后，也可以继续把 CIF 文件或文件夹拖入窗口追加加载；程序会自动去重并忽略非 CIF 文件。

如果只想直接得到 Excel，不需要打开 GUI，可以把 `.cif` 文件或 CIF 文件夹拖到：

```text
quick_export_xrd_atlas.bat
```

它会使用默认 Cu Kα、2θ 0-180°，并把结果保存到第一个 CIF 所在文件夹。

导出的 Excel 会默认打开 `使用说明` 工作表，普通用户先看这里即可。
最常用峰表在 `推荐峰表`，使用中文列名；完整英文列名峰表保留在 `Combined Peaks`，便于程序读取。
如果 CIF 无法解析，程序仍会生成 Excel 诊断文件；请查看 `Summary` 中的错误提示。

如果需要把程序发给没有 Python 环境的 Windows 电脑，先在开发电脑上双击：

```text
build_windows_app.bat
```

打包成功后，优先把 `dist\XRD_Atlas_Windows_Portable.zip` 发给目标电脑。
目标电脑解压后进入 `XRD Atlas` 文件夹，先双击 `windows_self_test.bat`。
目标电脑不需要安装 Python。

在目标电脑上：

- 双击 `XRD Atlas.exe` 打开 GUI。
- 把 CIF 文件或文件夹拖到 `XRD Atlas.exe` 上，会自动载入 GUI。
- 把 CIF 文件或文件夹拖到 `XRD Atlas Quick Export.exe` 上，会直接导出 Excel。

## Tests

```powershell
cd C:\Users\AORUS\Desktop\xrd_atlas
py -3.11 -m pytest -q
```

## License

MIT License. See [LICENSE](LICENSE).
