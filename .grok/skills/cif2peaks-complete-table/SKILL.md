---
name: cif2peaks-complete-table
description: >
  Export a complete CIF2Peaks peak workbook from a CIF folder (auto-bind
  PhaseScout *_elasticity.json). Use after CIFs are on disk, or when the user
  wants 完整峰表 / Excel / 工作峰表 without opening the GUI.
---

# CIF2Peaks complete table (Agent)

Finish at the **xlsx path**. Do not tell the user to open `cif2peaks-gui`.

## Run

cwd = this CIF2Peaks repo (`src/cif2peaks/batch.py` exists):

```powershell
py -3.12 -m cif2peaks "<folder-with-cifs>" -o "<folder-with-cifs>\cif2peaks_complete.xlsx"
```

`--auto-elastic` is the default. Pairing: `{stem}_elasticity.json`, then `paired_cif` / unique `mp-####`, then `elasticity_index.csv`.

## Do not

- Invent a 6×6 Cij or fill modulus when status is missing/invalid.
- Print API keys.
- Treat relative intensity as experimental phase fraction.
- Stop after “drag the folder into the GUI”.

## Expected workbook

工作峰表, Structure, Overlap (only if ≥2 phases exported peaks), 推荐峰表, Combined Peaks, Elastic Constants, 使用说明.
