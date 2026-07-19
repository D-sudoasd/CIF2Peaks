<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="CIF2Peaks: CIF to indexed theoretical powder XRD peak tables.">
</p>

# CIF2Peaks

**CIF → indexed theoretical powder peak tables for Excel, Origin, and Python.**

Batch-export phase, hkl, d, 2θ, q, g, relative intensity, warnings, and optional hkl-normal Young’s modulus when Cij is available.

<p align="center">
  <img src="assets/readme/section-01-output.svg" width="100%" alt="01 Output: indexed peaks for Excel and Origin.">
</p>

### Install & GUI

Python **3.11+**

```powershell
py -3.11 -m pip install -e .[dev]
cif2peaks-gui
# or: py -3.11 -m cif2peaks.gui
# Windows: start_cif2peaks.bat · quick_export_cif2peaks.bat
```

1. Drag CIF files/folders · 2. Choose `Cu Kα` / `30 keV` / `83 keV` or manual energy · 3. Set d-range · 4. **Export Excel**

### PhaseScout bridge

```powershell
cif2peaks "D:\path\to\batch" -o hea_peaks.xlsx   # auto-elastic on
```

Pairs `{stem}_elasticity.json` / `elasticity_index.csv` · literature-only packs are not numerical Cij.

### CLI

```powershell
cif2peaks "C:\path\to\cif_folder" -o result.xlsx
cif2peaks folder -o result.xlsx --energy-keV 20
cif2peaks folder -o result.csv
```

<p align="center">
  <img src="assets/readme/section-02-scope.svg" width="100%" alt="02 Scope: theoretical references, not Rietveld.">
</p>

Theoretical peak **references** only — not experimental fitting, Rietveld, phase-ID DB, or instrument calibration.

```text
R_hkl_with_LP = I_unscaled / V_cell^2
R_hkl_no_LP   = (I_unscaled / LP) / V_cell^2
```

Use the R column that matches experimental LP handling. Default `e^-2M = 1` when no temperature factors. Cij-based moduli are not experimental.

Portable Windows build: `build_windows_app.bat` → `dist\CIF2Peaks_Windows_Portable.zip`

```powershell
py -3.11 -m pytest -q
```

MIT — [LICENSE](LICENSE).
