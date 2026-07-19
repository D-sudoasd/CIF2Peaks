# AGENTS.md

Maintenance rules and context for AI agents and reviewers working on this
repository. Read this before changing code. This file complements Git history:
Git records what changed; this file records why risky changes were made, how
they were validated, and what future agents must not infer incorrectly.

Last repository scan for this document: 2026-06-13.

## Project Overview

CIF2Peaks is a Python package and Windows-friendly desktop utility for
converting CIF crystal structures into indexed theoretical powder XRD peak
tables and simulated pattern exports.

Primary functions:

- Load one CIF, multiple CIFs, or a folder of CIFs.
- Simulate theoretical powder XRD peaks with pymatgen.
- Export peak references to Excel, CSV, and JSON.
- Export optional continuous pattern workbooks and publication figure sidecars.
- Provide a Tkinter GUI with drag-and-drop, Chinese/English labels, d-spacing
  range filtering, X-ray presets, manual energy input, and optional elastic
  constants.
- Provide Windows batch scripts and PyInstaller packaging for non-Python users.

Scientific scope:

- Outputs are theoretical reference data from CIF structures.
- This is not a Rietveld refinement tool, phase identification database,
  experimental fitting program, or replacement for instrument calibration.
- Relative intensity and `R_hkl` fields are model-derived reference values.
  Treat formula or convention changes as high-risk scientific changes.

Typical use cases:

- Materials researchers export peak tables for Excel, Origin, Python, or lab
  notebooks.
- GUI users drag CIF files/folders and export Excel workbooks.
- CLI users batch-process CIF folders reproducibly.
- Windows maintainers build and distribute a portable app bundle.

## Repository Map

### User-Facing Entrypoints

- `pyproject.toml`
  - Package metadata, dependencies, pytest config, and console scripts.
  - Console scripts:
    - `cif2peaks` and `cif2peaks-peaks` -> `cif2peaks.batch:main`
    - `cif2peaks-gui` -> `cif2peaks.gui:main`
    - `cif2peaks-quick-export` -> `cif2peaks.quick_export:main`
- `src/cif2peaks/__main__.py`
  - `python -m cif2peaks` wrapper.
- `src/cif2peaks/app.py`
  - Exposes the batch CLI `main`.
- `src/cif2peaks/batch.py`
  - CLI CIF collection, settings conversion, peak/pattern export orchestration.
- `src/cif2peaks/gui.py`
  - Main Tkinter GUI, GUI settings parsing, drag/drop helpers, preview/export
    wrappers, completion messages, and open-result behavior.
- `src/cif2peaks/quick_export.py`
  - One-step export path used by CLI and Windows drag-to-export wrapper.
- `start_cif2peaks.bat`, `quick_export_cif2peaks.bat`, `启动CIF2Peaks.bat`
  - Windows launchers for GUI and quick export.
- `build_windows_app.bat`, `windows_self_test.bat`
  - Windows packaging and portable-app validation scripts.
- `scripts/cif2peaks_windows.py`,
  `scripts/cif2peaks_quick_export_windows.py`
  - PyInstaller-facing Windows entry scripts.
- `scripts/package_windows_portable.py`
  - Validates and zips the portable Windows app folder.
- `scripts/pyinstaller_hooks/hook-tkinterdnd2.py`
  - PyInstaller hook for drag-and-drop runtime files.

### Core Runtime Modules

- `src/cif2peaks/constants.py`
  - X-ray energy/wavelength conversion constant, default Cu Kalpha wavelength,
    scan defaults, and source presets.
- `src/cif2peaks/models.py`
  - Dataclasses for structures, XRD requests/results, peak row schema, settings,
    experimental patterns, and export payloads.
- `src/cif2peaks/structure.py`
  - CIF loading with gemmi/pymatgen/spglib, structural block selection,
    occupancy fallback, space-group detection, and validation warnings.
- `src/cif2peaks/xrd.py`
  - XRD simulation with pymatgen `XRDCalculator`, wavelength resolution, scan
    validation, peak profiles, `R_hkl`/no-LP metrics, rankings, warnings, and
    result caching.
- `src/cif2peaks/service.py`
  - Orchestrates CIF loading, phase simulation, and conversion of XRD peaks into
    export row dataclasses.
- `src/cif2peaks/hkl.py`
  - HKL normalization/formatting, including three-index and four-index
    Miller-Bravais handling.
- `src/cif2peaks/elastic.py`
  - Elastic stiffness matrix validation and hkl-normal Young's modulus
    calculation from user-provided Cij values.
- `src/cif2peaks/elastic_io.py`
  - Auto-load PhaseScout `*_elasticity.json` / `elasticity_index.csv` sidecars
    next to CIFs (`load_elastic_for_cif`). Default on in service/GUI/CLI.
- `src/cif2peaks/exporters.py`
  - Hand-written CSV, JSON, XLSX, peak workbook, pattern workbook, sheet names,
    headers, styles, user-guide sheet, and beginner Chinese peak table.
- `src/cif2peaks/plotting.py`
  - Publication figure presets and SVG/PDF/EPS/PNG/TIFF export. Includes a
    custom raster/vector fallback and optional matplotlib path.
- `src/cif2peaks/experimental.py`
  - Numeric experimental pattern loader for `ExperimentalPattern`.
  - TODO: confirm the intended public workflow; README does not document a
    direct CLI/GUI path for loading experimental patterns.
- `src/cif2peaks/utils.py`
  - Hashing, timestamps, dependency versions, and friendly CIF issue messages.

### Tests, Fixtures, and Docs

- `tests/test_cif2peaks.py`
  - Main regression suite. Covers CLI, GUI helpers, CIF parsing, R_hkl/no-LP
    fields, hkl handling, elastic constants, Excel/XML content, pattern
    workbooks, publication figure export, Windows packaging scripts, and
    diagnostic workbook behavior.
- `examples/cif/`
  - Small tracked CIF fixtures used by tests and manual smoke checks.
- `README.md`
  - User-facing overview, install, GUI/CLI usage, scientific scope, output
    columns, Windows guidance, and test command.
- `README_WINDOWS.txt`
  - Portable Windows app instructions for end users.
- `cif2peaks_self_test_report.txt`
  - Generated Windows self-test report. Do not treat it as current project
    health without rerunning the self-test.
- `.gitignore`
  - Ignores build outputs, virtualenv, caches, generated exports, and data
    outputs. Some `.spec` files exist in the repo; confirm whether tracked spec
    files or `build_windows_app.bat` are the current packaging source of truth
    before editing either.

### Main Data Flow

```text
CIF files/folders
  -> batch.collect_cif_paths() or gui.initial_gui_cif_paths()
  -> structure.load_crystal_model()
  -> service.Cif2PeaksService.load_phases()
  -> xrd.XRDService.simulate()
  -> service.phase_peak_rows() / exporters.combined_peak_rows()
  -> exporters.export_cif2peaks_workbook()
     exporters.export_peak_reference_csv()
     exporters.export_cif2peaks_json()
     exporters.export_cif2peaks_pattern_workbook()
  -> GUI / CLI / Windows quick-export completion messages
```

## Agent Working Rules

Before editing:

- Read this file, `README.md`, `pyproject.toml`, and the modules/tests directly
  related to the requested change.
- Run `git status --short` and preserve unrelated user changes.
- Search with `rg` before assuming a function or field is unused.
- Check `tests/test_cif2peaks.py` for existing behavior contracts before
  changing schemas, formulas, GUI labels, or Windows scripts.
- If touching user-facing behavior, inspect both English and Chinese GUI/text
  paths.

While editing:

- Keep changes narrow. Do not refactor adjacent scientific, GUI, or export code
  unless the request requires it.
- Preserve existing public column names, sheet names, CLI options, script names,
  and Windows drag/drop behavior unless the change explicitly requires a
  breaking change.
- Use structured parsing/writers already present in the codebase. Do not replace
  the hand-written XLSX exporter or plotting stack casually.
- Do not remove warnings just because they are inconvenient; many warnings are
  part of the user-facing diagnosis path.
- Do not put private machine paths, account names, tokens, or local-only data
  locations into docs, tests, or exports.
- Keep Windows batch files compatible with their tested encoding/line-ending
  expectations. Tests currently assert CRLF details for `windows_self_test.bat`.

After editing:

- Run the narrowest meaningful checks first, then broaden when touching shared
  behavior.
- For documentation-only changes, at minimum inspect the rendered Markdown
  mentally and verify the file is present in `git diff`.
- For code changes, prefer `py -3.11 -m pytest -q` when dependencies are
  installed.
- Update `Recent Change Log for Agents` in this file for changes that affect
  architecture, scientific formulas, output schema, GUI workflow, packaging, or
  non-obvious bug fixes.

Forbidden high-risk operations:

- Do not delete or rename exported columns/sheets without compatibility notes
  and tests.
- Do not change scientific formulas, default wavelength/energy, or `R_hkl`
  semantics without documenting the scientific rationale.
- Do not convert diagnostic failures into hard crashes unless requested.
- Do not remove Windows packaging/self-test coverage while changing packaging.
- Do not treat skipped local-fixture tests as proof that all external datasets
  are covered.

## Change Recording Protocol

Use this file for context that Git log cannot explain: rationale, compatibility
impact, risk, verification, and rollback. Do not duplicate every tiny code line.
Append entries under `Recent Change Log for Agents` for meaningful changes.

Required fields for each meaningful change:

- Date.
- Agent / author.
- Branch / commit if known.
- Files changed.
- Change type.
- What changed.
- Why it changed.
- Impact scope.
- Risk level.
- Compatibility notes.
- Validation performed.
- Known limitations.
- Rollback notes.
- Follow-up needed.

## Change Entry Template

```markdown
### YYYY-MM-DD — Short Change Title

- **Agent / Author**:
- **Branch / Commit**:
- **Files Changed**:
- **Change Type**:
  - [ ] Bug fix
  - [ ] Refactor
  - [ ] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**:
- **Why It Changed**:
- **Impact Scope**:
- **Risk Level**: Low / Medium / High
- **Compatibility Notes**:
- **Validation Performed**:
- **Known Limitations**:
- **Rollback Notes**:
- **Follow-up Needed**:
```

Keep entries concise. If the reasoning is long, link to the issue/PR or commit
instead of turning this file into a full design document.

## High-Risk Areas

### Scientific Computation

Files:

- `src/cif2peaks/xrd.py`
- `src/cif2peaks/constants.py`
- `src/cif2peaks/service.py`
- `src/cif2peaks/hkl.py`
- `src/cif2peaks/elastic.py`

Risks:

- Energy/wavelength conversion affects every peak position.
- Scan window validation controls whether invalid settings fail early.
- `pymatgen.analysis.diffraction.xrd.XRDCalculator(..., scaled=False)` is part
  of the current `R_hkl` convention.
- `R_hkl`, `R_hkl_no_LP`, inverse fields, ranks, multiplicity, and family
  metrics are exported and tested. Changing one usually requires updates to
  `README.md`, tests, and workbook/CSV/JSON assertions.
- Four-index Miller-Bravais conversion affects hkl labels and elastic modulus
  calculations.
- Elastic constants assume `crystal_cartesian_from_cif_lattice` coordinate
  frame. Do not silently rotate or reinterpret Cij matrices.

### CIF Parsing and Validation

Files:

- `src/cif2peaks/structure.py`
- `src/cif2peaks/utils.py`

Risks:

- Multi-block CIF selection prefers structural blocks and has tests for
  standardized/published cells.
- Occupancy fallback uses pymatgen `occupancy_tolerance=4.0`; warning text is
  user-visible.
- spglib uses dominant species for symmetry detection on disordered sites, while
  XRD still uses the pymatgen structure. Do not conflate these.
- Error messages are surfaced in CLI summaries, GUI preview/export rows, and
  diagnostic workbooks.

### Export Schema and Workbooks

Files:

- `src/cif2peaks/exporters.py`
- `src/cif2peaks/models.py`

Risks:

- XLSX is written manually through XML in a zip file. Small XML, escaping,
  relationship, style, or activeTab changes can break Excel compatibility.
- Sheet names such as `Summary`, `Combined Peaks`, `推荐峰表`,
  `Elastic Constants`, `Experimental Data`, and `使用说明` are user-facing.
- Header lists (`PEAK_HEADERS`, `PEAK_REFERENCE_HEADERS`,
  `PATTERN_PROFILE_HEADERS`, `ELASTIC_CONSTANTS_HEADERS`,
  `BEGINNER_PEAK_HEADERS`) are compatibility contracts.
- `BEGINNER_KEY_COLUMN_INDEXES` must stay aligned with inserted beginner-table
  columns.
- `combined_peak_rows()` is the bridge between scientific data and export
  schema; changes here can affect Excel, CSV, JSON, GUI, and tests.

### GUI Layout and Workflow

Files:

- `src/cif2peaks/gui.py`

Risks:

- GUI uses Tkinter/ttk with optional `tkinterdnd2`; drag/drop must degrade
  gracefully if `tkinterdnd2` is unavailable.
- `GUI_TEXT`, `GUI_TOOLTIP_KEYS`, and language switching are tested contracts.
- `GUI_WORKBENCH_LAYOUT` controls minimum window size and scroll behavior.
- Manual energy overrides selected preset; blank manual energy uses the preset.
- d-spacing range conversion must use the resolved wavelength/energy.
- Output overwrite confirmation and open-result fallback are part of the user
  workflow.
- GUI changes require visual checks for clipping, disabled buttons, overlapping
  controls, language switching, scroll behavior, and resized windows.

### Windows Packaging and Distribution

Files:

- `build_windows_app.bat`
- `windows_self_test.bat`
- `README_WINDOWS.txt`
- `scripts/cif2peaks_windows.py`
- `scripts/cif2peaks_quick_export_windows.py`
- `scripts/package_windows_portable.py`
- `scripts/pyinstaller_hooks/hook-tkinterdnd2.py`
- `XRD Atlas.spec`, `XRD Atlas Quick Export.spec`, `AddDataProbe.spec`

Risks:

- Portable app users may not have Python installed.
- The app must ship `_internal`, Tcl/Tk runtime data, examples, README, and
  self-test script.
- `CIF2PEAKS_SMOKE_TEST=1` is used by automated Windows-entry smoke tests.
- Batch/script changes can break drag-to-exe workflows even when Python CLI
  tests still pass.

### Publication Figure Export

Files:

- `src/cif2peaks/plotting.py`
- `src/cif2peaks/gui.py`

Risks:

- SVG/PDF/EPS/PNG/TIFF outputs are tested for headers, labels, dimensions, and
  non-rainbow styling.
- matplotlib is optional for raster export; fallback rendering must still work.
- Preset names and formats are GUI-visible and test-covered.

## Testing and Validation Checklist

Baseline command from README:

```powershell
py -3.11 -m pytest -q
```

Use this when dependencies are installed and the change is more than docs.

Minimum smoke checks by change type:

- CLI/data path:
  - Run the full pytest command above when practical.
  - Manually export from `examples/cif/` to a temporary ignored `.xlsx` or
    `.csv` if the change touches CLI output behavior.
  - Confirm peak count is nonzero for valid CIFs and that invalid CIFs still
    produce useful diagnostics when expected.
- XRD/math changes:
  - Check tests covering energy shifts, invalid scan ranges/steps, `R_hkl`,
    quant columns, hkl labels, and elastic constants.
  - Verify units: Angstrom, degrees, `q_1_over_A`, `g_1_over_A`, GPa.
- Export/schema changes:
  - Verify workbook sheets, headers, Chinese beginner table, styles, and JSON/CSV
    fields.
  - Confirm no expected sheet/column was renamed by accident.
- GUI changes:
  - Launch the GUI when a display is available:

    ```powershell
    py -3.11 -m cif2peaks.gui
    ```

  - Check add-file, add-folder, drag/drop if available, remove/clear, preview,
    language toggle, d-range fields, energy preset/manual override, export
    checkboxes, publication figure checkbox, output path picker, export button,
    open-result behavior, scrollbars, and window resizing.
  - Check Chinese and English text for clipping or missing labels.
- Windows packaging changes:
  - Run the pytest suite or at least the packaging-related tests in
    `tests/test_cif2peaks.py`.
  - After building, run `windows_self_test.bat` from the portable folder.
  - Confirm the zip contains the complete `CIF2Peaks` folder, not only EXE files.
- Documentation-only changes:
  - Verify links and relative paths are accurate.
  - Do not run pytest unless the documentation embeds runnable examples that
    changed behavior.

If a check cannot be run, record exactly what was skipped and why in the change
entry.

## Bug Investigation Checklist

Start with symptom classification:

- No CIFs found:
  - Check `batch.collect_cif_paths()`, `gui.add_gui_cif_inputs()`,
    suffix filtering, recursion, and path resolution.
- CIF parse failure:
  - Check `structure.load_crystal_model()`, structural block selection,
    occupancy fallback, and `friendly_cif_issue_message()`.
- Wrong peak positions:
  - Check `constants.py`, `XRDService.resolve_wavelength()`, d-range to
    two-theta conversion in `gui.py`, and scan window settings.
- Wrong intensities or `R_hkl` fields:
  - Check `xrd.py` formulas, LP factor, cell volume, multiplicity/family data,
    ranking, and `exporters.combined_peak_rows()`.
- Missing or shifted export columns:
  - Check `models.Cif2PeaksPeakRow`, exporter header lists,
    `_beginner_peak_rows_for_sheet()`, and schema tests.
- Excel opens incorrectly:
  - Check manual XLSX XML generation, workbook relationships, styles, sheet
    names, XML escaping, and zip contents in `exporters.py`.
- GUI button/layout issue:
  - Check `GUI_TEXT`, `GUI_WORKBENCH_LAYOUT`, widget grid configuration,
    callbacks inside `_launch_tk_app()`, and tooltip key coverage.
- Windows portable app issue:
  - Check Tcl/Tk path configuration, PyInstaller hook, package validator,
    `_internal` contents, and self-test report.
- Dependency/import issue:
  - Check `pyproject.toml`, `requirements.txt`, optional matplotlib behavior,
    and whether the failure is inside editable install vs packaged EXE.

For every bug fix, record:

- Reproduction input and command/workflow.
- Root cause module/function.
- Why the fix does not break existing valid CIFs or exports.
- Regression test or manual smoke check.
- Remaining unsupported cases.

## Do Not Change Without Review

Do not change these without an explicit rationale, compatibility note, and
validation plan:

- `X_RAY_ENERGY_WAVELENGTH_KEV_A`, default Cu Kalpha wavelength, default scan
  range, or energy/wavelength precedence.
- `R_HKL_MODEL_NOTE` and the formulas behind `material_scattering_factor_R_hkl`
  and `material_scattering_factor_R_hkl_no_lp`.
- Use of `scaled=False` in pymatgen XRD simulation.
- HKL/family label semantics, especially four-index Miller-Bravais handling.
- `ElasticConstants` matrix validation and coordinate-frame assumptions.
- Exported sheet names and header lists in `exporters.py`.
- `BEGINNER_PEAK_HEADERS` and `BEGINNER_KEY_COLUMN_INDEXES` alignment.
- Diagnostic workbook behavior for bad CIFs.
- GUI language-pack keys and tooltip key coverage.
- Windows script names, PyInstaller hook, Tcl/Tk runtime packaging, and
  `windows_self_test.bat` CRLF-sensitive behavior.
- Console script names in `pyproject.toml`.

If such a change is required, the change entry must include:

- Scientific or product reason.
- Backward-compatibility impact.
- Files and user workflows affected.
- Tests updated or added.
- Manual validation performed.
- Rollback plan.

## Known Issues / Technical Debt

- TODO: Confirm the release/versioning policy. `pyproject.toml` and
  `src/cif2peaks/__init__.py` currently show version `0.1.0`.
- TODO: Confirm whether tracked `.spec` files are still authoritative or legacy,
  because `.gitignore` ignores `*.spec` while spec files are present.
- TODO: Confirm the public workflow for `src/cif2peaks/experimental.py`; it is
  present and integrated with export payloads but not documented in README as a
  user entrypoint.
- GUI visual regression is mostly manual. Unit tests cover many helpers but do
  not prove all controls render without clipping on every Windows display scale.
- Some tests reference optional local datasets and skip when those files are not
  available. Passing tests on one machine may not cover those external fixtures.
- XLSX generation is custom XML. There is no separate schema document beyond
  code, tests, and README output-column documentation.
- `cif2peaks_self_test_report.txt` appears to be generated diagnostic output.
  Treat it as stale unless regenerated in the current portable app.
- Non-ASCII filenames, sheet names, and GUI text are intentional user-facing
  behavior. Do not "normalize" them away for ASCII-only convenience.

## Recent Change Log for Agents

### 2026-07-12 — Fix Publication Figure Overwrite Confirmation

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/gui.py`, `tests/test_cif2peaks.py`, `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Made multi-output overwrite confirmation resolve each
  planned path without forcing a `.xlsx` suffix, and added a regression test
  for an existing publication SVG sidecar.
- **Why It Changed**: Publication sidecars were planned with `.svg`, `.pdf`,
  `.eps`, `.png`, and `.tif` suffixes, but the confirmation helper converted
  them to `.xlsx` before checking existence; an existing figure could therefore
  be overwritten without a confirmation prompt.
- **Impact Scope**: GUI pre-export overwrite confirmation for workbook,
  pattern-workbook, and publication-figure outputs. Scientific calculations,
  export schemas, sheet names, CLI behavior, and figure contents are unchanged.
- **Risk Level**: Low
- **Compatibility Notes**: Workbook-only confirmation continues to normalize
  extensionless GUI output paths to `.xlsx`; multi-output confirmation now
  preserves the exact planned extension.
- **Validation Performed**: Added a failing regression test, confirmed the
  previous implementation failed it, then passed the focused test. The full
  test file was then covered in safe segments: 109 passed and 5 skipped;
  compileall, pip check, GUI smoke startup, CLI export smoke, and diff checks
  also passed.
- **Known Limitations**: Existing publication sidecars are checked
  conservatively for every selected CIF before simulation; a failed CIF may
  still prompt for a sidecar that will not be regenerated.
- **Rollback Notes**: Revert the path-resolution line in
  `should_overwrite_gui_outputs()` and its regression assertion.
- **Follow-up Needed**: None for this fix; manual high-DPI GUI review remains
  useful before a public Windows release.

### 2026-06-29 — Improve GUI Result Guidance and Workbook Reading Hints

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/gui.py`,
  `src/cif2peaks/exporters.py`, `tests/test_cif2peaks.py`, `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [ ] Data processing change
  - [x] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Added GUI export diagnostics for failed, warning, and
  zero-peak phases, backed by explicit per-phase error flags from
  `phase.error`; expanded completion/status/activity guidance; grouped visible
  GUI settings into required parameters, output content, optional outputs, and
  optional Cij elastic constants; and added workbook reading, warning,
  `R_hkl`, and Cij guidance rows to `Summary` and `使用说明`.
- **Why It Changed**: Ordinary GUI users needed clearer next steps after
  export and clearer separation between mandatory settings and optional
  advanced outputs without changing the scientific calculation path.
- **Impact Scope**: GUI text/layout hierarchy and workbook guidance only.
  XRD formulas, wavelength defaults, `R_hkl` semantics, exported peak columns,
  sheet names, CLI options, and Windows launcher names are unchanged.
- **Risk Level**: Low
- **Compatibility Notes**: Existing sheet names and exported field headers are
  preserved. `Summary` and `使用说明` gain additional explanatory rows, so users
  parsing those sheets by fixed row number should switch to key/name-based
  lookup.
- **Validation Performed**: Added failing tests for GUI diagnostics,
  completion guidance, workbook reading guidance, language-pack coverage, and
  simulation-stage export failures where CIF metadata exists but XRD
  calculation fails, then passed them. Ran `py -3.11 -m pytest
  tests\test_cif2peaks.py -k "gui or guide or Summary or beginner" -q`,
  `py -3.11 -m compileall -q src tests scripts`, `py -3.11 -m pytest -q`,
  and GUI smoke startup with `CIF2PEAKS_SMOKE_TEST=1 py -3.11 -m cif2peaks.gui`.
- **Known Limitations**: GUI smoke startup does not replace manual high-DPI
  visual review. No new persisted export status schema was added; the explicit
  GUI error flags are scoped to completion/status reporting.
- **Rollback Notes**: Revert the GUI diagnostics/text/layout changes, the
  added workbook guidance rows, and the associated tests to restore the
  previous concise completion messages and workbook guide content.
- **Follow-up Needed**: Consider a manual visual QA pass on common Windows
  display scaling settings before a public portable-app release.

### 2026-06-18 — Guard GUI Figure Sidecar Overwrites

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/gui.py`, `tests/test_cif2peaks.py`,
  `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Added `planned_gui_output_paths()` so GUI overwrite
  confirmation checks planned publication SVG/PDF/EPS/PNG/TIFF sidecars in
  addition to workbook outputs, and generalized the overwrite dialog copy from
  “Excel workbook” to “output file”.
- **Why It Changed**: GUI export previously warned only for the main workbook
  and optional pattern workbook, so enabling publication figures could silently
  overwrite existing sidecar plots without confirmation.
- **Impact Scope**: GUI export overwrite confirmation only. XRD formulas, CIF
  parsing, export schemas, CLI options, workbook naming, and figure content are
  unchanged.
- **Risk Level**: Low
- **Compatibility Notes**: Existing workbook and figure filenames are
  preserved. Confirmation is now more conservative because it plans figure
  paths from the selected CIF list before the background export begins.
- **Validation Performed**: Added a failing regression test first, confirmed it
  failed from the missing helper import, then passed after the fix. Ran
  `.\.venv\Scripts\python.exe -m compileall -q src tests scripts`,
  `.\.venv\Scripts\python.exe -m pytest tests\test_cif2peaks.py -k "gui_defines_tooltips_and_clear_confirmation_contract or simple_gui_export_can_write_publication_vector_sidecars or simple_gui_export_can_write_only_patterns_or_both_outputs" -q`,
  `.\.venv\Scripts\python.exe -m pytest -q`,
  `.\.venv\Scripts\python.exe -m pip check`, and GUI smoke startup with
  `CIF2PEAKS_SMOKE_TEST=1`.
- **Known Limitations**: The pre-export overwrite plan is conservative for CIFs
  that later fail to simulate, so users may occasionally confirm a figure path
  that ends up not being regenerated in that run.
- **Rollback Notes**: Revert `planned_gui_output_paths()`, the export dialog
  call-site update, the generic overwrite-dialog copy, and the regression test
  if workbook-only overwrite confirmation is preferred.
- **Follow-up Needed**: Consider whether stale figure sidecars from older runs
  should be surfaced separately when the current export contains fewer phases.

### 2026-06-17 — Align Selected CIF Block With Pymatgen Structure

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/structure.py`,
  `src/cif2peaks/gui.py`, `tests/test_cif2peaks.py`, `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [x] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Pymatgen now parses the same Gemmi-selected structural
  CIF block used for metadata, including the occupancy-tolerance fallback.
  GUI export now snapshots Tk variable values before starting the background
  export thread.
- **Why It Changed**: A reordered multi-block CIF could choose
  `standardized_unitcell` for metadata while pymatgen simulated the first
  structural block, making exported metadata and peak positions come from
  different CIF blocks. Tkinter variables should not be read from background
  worker threads during GUI export.
- **Impact Scope**: CIF parsing consistency for multi-block files and GUI
  export-thread stability. XRD formulas, wavelength defaults, exported column
  names, sheet names, CLI options, and quick-export defaults are unchanged.
- **Risk Level**: Medium
- **Compatibility Notes**: Existing single-block and standardized-first
  multi-block behavior is preserved. The changed multi-block behavior aligns
  simulated structures with the repository's documented structural-block
  selection policy.
- **Validation Performed**: Added a failing regression test with
  `published_cell` before `standardized_unitcell`, confirmed it failed on the
  previous path, then passed after the fix. Ran targeted multi-block,
  occupancy, GUI, quick-export, batch, and pattern tests; GUI smoke startup;
  `compileall`; `pip check`; and the full pytest suite in the local `.venv`
  Python 3.13 runtime.
- **Known Limitations**: GUI smoke startup does not replace manual high-DPI
  visual review or full Windows portable-app testing. Publication figure
  sidecars are still not included in the GUI overwrite confirmation set.
- **Rollback Notes**: Revert the `_load_pymatgen_structure` block-argument
  change, the GUI export snapshot block, and the new regression test if the
  previous file-order-based pymatgen parsing behavior is required.
- **Follow-up Needed**: Consider adding overwrite confirmation for existing
  publication figure sidecars before public release.

### 2026-06-13 — Tighten GUI Export Option States

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/gui.py`, `tests/test_cif2peaks.py`,
  `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Shortened two English settings labels that clipped at the
  minimum window width, added GUI export-state logic, disabled the pattern-axis
  selector unless pattern export is enabled, disabled the figure preset selector
  unless publication figures are enabled, and disabled export when no output
  type is selected.
- **Why It Changed**: GUI review from a materials-research workflow found that
  English users could lose key text at the minimum window size and that inactive
  advanced output controls looked editable, increasing the chance of
  misunderstanding which settings affect the export.
- **Impact Scope**: GUI layout and control-state behavior only. Core XRD
  calculations, CIF parsing, export schemas, CLI options, and quick-export
  defaults are unchanged.
- **Risk Level**: Low
- **Compatibility Notes**: Existing output flags still map to the same export
  functions. Old workflows that export peak tables by default are unchanged.
  No persistent GUI configuration format exists in this repository, so no saved
  config migration was needed.
- **Validation Performed**: Added failing GUI regression tests first, then
  passed them after the change. Ran `.\.venv\Scripts\python.exe -m compileall
  -q src tests scripts`, `.\.venv\Scripts\python.exe -m pytest
  tests\test_cif2peaks.py -k "gui" -q`, `.\.venv\Scripts\python.exe -m
  pytest -q`, GUI smoke startup with `CIF2PEAKS_SMOKE_TEST=1`, Tk layout
  measurements for Chinese and English at `1200x760` and `1040x680`, Tk
  control-state measurement for the dependent comboboxes, and CLI/quick-export
  smoke exports from `examples/cif`. The local `py -3.11` launcher was not
  available, so validation used the project `.venv` Python 3.13 runtime.
- **Known Limitations**: Automated Tk measurements do not replace manual
  high-DPI and multi-monitor visual review. Advanced Cij inputs remain visible
  in the main workflow and may deserve a future collapsible expert section.
- **Rollback Notes**: Revert the `gui_export_control_states` helper, related
  Tk state refresh calls, and the English label shortening if the previous
  always-enabled controls are preferred.
- **Follow-up Needed**: Consider a separate UX pass for an explicit Advanced /
  Expert section and, if requested, a real save/load settings workflow.

### 2026-06-13 — Add Preview Table Horizontal Scrollbar

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `src/cif2peaks/gui.py`, `AGENTS.md`
- **Change Type**:
  - [x] Bug fix
  - [ ] Refactor
  - [x] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [ ] Documentation only
- **What Changed**: Added a horizontal scrollbar to the GUI preview
  `Treeview` and moved the activity log rows down to keep the preview table,
  activity log, and scrollbars from overlapping.
- **Why It Changed**: Pre-release GUI layout measurement showed that the
  preview table columns can be wider than the default right-side preview area,
  especially after language switching, so trailing columns were only reachable
  by resizing the whole window.
- **Impact Scope**: GUI preview layout only. Export schemas, sheet names,
  scientific formulas, CLI behavior, and data-processing paths are unchanged.
- **Risk Level**: Low
- **Compatibility Notes**: Existing preview column names and widths are
  preserved; the new scrollbar only improves access to clipped columns.
- **Validation Performed**: Ran `.\.venv\Scripts\python.exe -m compileall -q
  src tests scripts`, `.\.venv\Scripts\python.exe -m pytest -q`, GUI smoke
  startup with `CIF2PEAKS_SMOKE_TEST=1`, CLI/quick-export smoke exports from
  `examples/cif`, Tk layout measurement for Chinese and English UI states, and
  `.\.venv\Scripts\python.exe -m pip check` after installing the declared local
  drag-and-drop dependency.
- **Known Limitations**: Manual inspection was limited to the current Windows
  desktop environment and automated Tk layout metrics; high-DPI and every
  external monitor scale still require human visual confirmation before a
  public Windows release.
- **Rollback Notes**: Revert the `Treeview` horizontal scrollbar addition and
  restore the activity log grid rows if the extra scrollbar is not desired.
- **Follow-up Needed**: Consider broader GUI visual regression coverage if
  future layout changes add more long controls or additional preview columns.

### 2026-06-13 — Add Agent Maintenance Guide

- **Agent / Author**: Codex
- **Branch / Commit**: `main` / not committed at time of entry
- **Files Changed**: `AGENTS.md`
- **Change Type**:
  - [ ] Bug fix
  - [ ] Refactor
  - [ ] GUI change
  - [ ] Data processing change
  - [ ] Export / reporting change
  - [ ] Dependency / config change
  - [x] Documentation only
- **What Changed**: Added the repository-specific agent maintenance guide,
  including project map, working rules, change-recording protocol, high-risk
  areas, testing checklist, bug investigation checklist, protected areas,
  known issues, and this change log.
- **Why It Changed**: Future AI agents and reviewers need stable context for
  scientific formulas, GUI behavior, export schemas, and Windows packaging
  before modifying the project.
- **Impact Scope**: Documentation only. No runtime behavior changed.
- **Risk Level**: Low
- **Compatibility Notes**: Does not replace README or Git log. It supplements
  them with maintenance intent and validation expectations.
- **Validation Performed**: Inspected root files, README documents,
  `pyproject.toml`, core modules, scripts, tests, recent Git log, and created
  this file without changing code.
- **Known Limitations**: GUI was not launched and pytest was not run because
  this was a documentation-only change.
- **Rollback Notes**: Remove `AGENTS.md` to revert this documentation addition.
- **Follow-up Needed**: Confirm TODO items in Known Issues / Technical Debt and
  update this log after future meaningful changes.
