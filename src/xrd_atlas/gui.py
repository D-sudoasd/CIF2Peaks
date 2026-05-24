from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from collections.abc import Callable
from typing import Sequence

from .constants import DEFAULT_XRD_SOURCE, X_RAY_ENERGY_WAVELENGTH_KEV_A
from .exporters import export_xrd_atlas_workbook
from .models import XrdAtlasExportPayload, XrdAtlasSettings
from .service import XrdAtlasService
from .utils import friendly_cif_issue_message


@dataclass(frozen=True)
class SimpleGuiExportResult:
    output_path: Path
    total_peaks: int
    phase_rows: list[tuple[str, str, str, int, str]]


@dataclass(frozen=True)
class SimpleGuiPreviewResult:
    ready_count: int
    failed_count: int
    phase_rows: list[tuple[str, str, str, str, str]]


def _configure_tcl_tk_environment(python_base: str | Path | None = None) -> None:
    base = Path(sys.base_prefix if python_base is None else python_base)
    tcl_dir = base / "tcl" / "tcl8.6"
    tk_dir = base / "tcl" / "tk8.6"

    current_tcl = Path(os.environ.get("TCL_LIBRARY", ""))
    current_tk = Path(os.environ.get("TK_LIBRARY", ""))
    if not (current_tcl / "init.tcl").exists() and (tcl_dir / "init.tcl").exists():
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if not (current_tk / "tk.tcl").exists() and (tk_dir / "tk.tcl").exists():
        os.environ["TK_LIBRARY"] = str(tk_dir)


def _parse_float(value: str | float | int, field_name: str) -> float:
    try:
        number = float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    return number


def build_gui_settings(
    energy_keV: str | float,
    two_theta_min: str | float = 0.0,
    two_theta_max: str | float = 180.0,
) -> XrdAtlasSettings:
    energy = _parse_float(energy_keV, "X-ray energy keV")
    min_deg = _parse_float(two_theta_min, "2theta min")
    max_deg = _parse_float(two_theta_max, "2theta max")
    if energy <= 0:
        raise ValueError("X-ray energy keV must be greater than 0.")
    if min_deg < 0 or max_deg > 180 or min_deg >= max_deg:
        raise ValueError("2theta range must satisfy 0 <= min < max <= 180.")
    return XrdAtlasSettings(
        input_mode="energy",
        energy_keV=energy,
        wavelength_A=X_RAY_ENERGY_WAVELENGTH_KEV_A / energy,
        two_theta_min_deg=min_deg,
        two_theta_max_deg=max_deg,
    )


def build_beginner_gui_settings(
    two_theta_min: str | float = 0.0,
    two_theta_max: str | float = 180.0,
    energy_keV: str | float | None = None,
) -> XrdAtlasSettings:
    if energy_keV is not None and str(energy_keV).strip():
        return build_gui_settings(energy_keV, two_theta_min, two_theta_max)

    min_deg = _parse_float(two_theta_min, "2theta min")
    max_deg = _parse_float(two_theta_max, "2theta max")
    if min_deg < 0 or max_deg > 180 or min_deg >= max_deg:
        raise ValueError("2theta range must satisfy 0 <= min < max <= 180.")
    return XrdAtlasSettings(
        input_mode="source",
        source_preset=DEFAULT_XRD_SOURCE,
        two_theta_min_deg=min_deg,
        two_theta_max_deg=max_deg,
    )


def normalize_xlsx_output_path(output_path: str | Path) -> Path:
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".xlsx":
        path = path.with_suffix(".xlsx")
    return path


def initial_gui_cif_paths(inputs: Sequence[str | Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for item in inputs:
        candidate = Path(item).expanduser()
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        if resolved.is_dir():
            candidates = sorted(
                (path for path in resolved.rglob("*") if path.is_file() and path.suffix.lower() == ".cif"),
                key=lambda value: str(value).lower(),
            )
        elif resolved.is_file() and resolved.suffix.lower() == ".cif":
            candidates = [resolved]
        else:
            candidates = []

        for path in candidates:
            resolved_path = path.resolve()
            if resolved_path not in seen:
                paths.append(resolved_path)
                seen.add(resolved_path)
    return paths


def suggest_output_path(cif_paths: Sequence[str | Path]) -> Path:
    paths = [Path(path).expanduser() for path in cif_paths]
    if not paths:
        return Path.home() / "Desktop" / "XRD峰表.xlsx"
    parent = paths[0].parent if paths[0].parent != Path("") else Path.cwd()
    if len(paths) == 1:
        return parent / f"{paths[0].stem}_XRD峰表.xlsx"
    return parent / f"XRD峰表_{len(paths)}个CIF.xlsx"


def friendly_error_message(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if isinstance(exc, PermissionError):
        return "无法写入结果文件。请确认 Excel 文件没有被 Excel 打开，然后重新导出。"
    if "select at least one cif" in lower:
        return "请先添加至少一个 CIF 文件。"
    if "must be a number" in lower:
        return "参数需要填写数字。也可以直接使用默认设置。"
    if "x-ray energy kev must be greater than 0" in lower:
        return "X 射线能量需要大于 0 keV。也可以留空使用默认 Cu Kα。"
    if "2theta range" in lower:
        return "2θ 范围需要满足 0 <= 最小值 < 最大值 <= 180。"
    if isinstance(exc, FileNotFoundError) or "missing cif" in lower:
        return "找不到某些 CIF 文件。请重新选择文件或文件夹。"
    return f"处理失败：{message}"


def preview_simple_gui_inputs(cif_paths: Sequence[str | Path]) -> SimpleGuiPreviewResult:
    resolved_cifs = initial_gui_cif_paths(cif_paths)
    service = XrdAtlasService()
    phases = service.load_phases(resolved_cifs)

    phase_rows: list[tuple[str, str, str, str, str]] = []
    ready_count = 0
    failed_count = 0
    for phase in phases:
        if phase.error:
            status = "无法读取"
            failed_count += 1
        else:
            status = "待导出"
            ready_count += 1
        phase_rows.append(
            (
                phase.cif_path.name,
                phase.display_formula,
                phase.display_space_group,
                status,
                friendly_cif_issue_message(phase.error, phase.warning_messages),
            )
        )

    return SimpleGuiPreviewResult(
        ready_count=ready_count,
        failed_count=failed_count,
        phase_rows=phase_rows,
    )


def run_simple_gui_export(
    cif_paths: Sequence[str | Path],
    output_path: str | Path,
    *,
    energy_keV: str | float | None = None,
    two_theta_min: str | float = 0.0,
    two_theta_max: str | float = 180.0,
) -> SimpleGuiExportResult:
    resolved_cifs = [Path(path).expanduser().resolve() for path in cif_paths]
    if not resolved_cifs:
        raise ValueError("Select at least one CIF file.")
    missing = [str(path) for path in resolved_cifs if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing CIF file(s): " + "; ".join(missing))

    settings = build_beginner_gui_settings(two_theta_min, two_theta_max, energy_keV)
    service = XrdAtlasService()
    phases = service.load_phases(resolved_cifs)
    service.simulate_phases(phases, settings)

    output = normalize_xlsx_output_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    export_xrd_atlas_workbook(XrdAtlasExportPayload(phases, settings), output)

    phase_rows: list[tuple[str, str, str, int, str]] = []
    for phase in phases:
        peak_count = 0 if phase.result is None else len(phase.result.peaks)
        phase_rows.append(
            (
                phase.cif_path.name,
                phase.display_formula,
                phase.display_space_group,
                peak_count,
                friendly_cif_issue_message(phase.error, phase.warning_messages),
            )
        )
    return SimpleGuiExportResult(
        output_path=output,
        total_peaks=sum(row[3] for row in phase_rows),
        phase_rows=phase_rows,
    )


def simple_export_message_lines(result: SimpleGuiExportResult) -> list[str]:
    if result.total_peaks:
        summary_lines = [f"已导出 {result.total_peaks} 条峰记录。"]
    else:
        summary_lines = [
            "未得到可用峰记录，但已生成诊断 Excel。",
            "请打开 Summary 和 使用说明 查看 CIF 问题。",
        ]
    return [*summary_lines, "", str(result.output_path)]


def gui_export_completion_text(result: SimpleGuiExportResult) -> tuple[str, str]:
    if result.total_peaks:
        status_text = f"完成：已导出 {result.total_peaks} 条峰记录。"
    else:
        status_text = "完成：已生成诊断 Excel；未得到可用峰记录。"
    return status_text, "\n".join(simple_export_message_lines(result))


def open_export_result(output_path: str | Path, opener: Callable[[str], object] | None = None) -> Path:
    path = Path(output_path)
    open_target = os.startfile if opener is None else opener  # type: ignore[attr-defined]
    try:
        open_target(str(path))
        return path
    except OSError:
        open_target(str(path.parent))
        return path.parent


def _launch_tk_app(initial_paths: Sequence[str | Path] = ()) -> None:
    import threading

    _configure_tcl_tk_environment()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    if os.environ.get("XRD_ATLAS_SMOKE_TEST") == "1":
        root.after(300, root.destroy)
    root.title("XRD Atlas - CIF 转 Excel")
    root.geometry("980x680")
    root.minsize(880, 600)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
    style.configure("Subtitle.TLabel", font=("Microsoft YaHei UI", 10))
    style.configure("Step.TLabelframe.Label", font=("Microsoft YaHei UI", 11, "bold"))
    style.configure("Primary.TButton", font=("Microsoft YaHei UI", 12, "bold"), padding=(18, 10))
    style.configure("Action.TButton", padding=(10, 6))

    selected_paths: list[Path] = initial_gui_cif_paths(initial_paths)
    last_output_path: Path | None = None
    preview_generation = 0
    advanced_visible = tk.BooleanVar(value=False)
    energy_var = tk.StringVar(value="")
    min_var = tk.StringVar(value="0")
    max_var = tk.StringVar(value="180")
    output_var = tk.StringVar(value=str(suggest_output_path(selected_paths)))
    status_var = tk.StringVar(
        value="可以导出：确认保存位置后点击“导出 Excel”。"
        if selected_paths
        else "准备就绪：添加 CIF 文件后，直接点击“导出 Excel”。"
    )
    input_summary_var = tk.StringVar(
        value="尚未添加 CIF 文件" if not selected_paths else f"已添加 {len(selected_paths)} 个 CIF 文件"
    )
    settings_summary_var = tk.StringVar(value="默认设置：Cu Kα，2θ 0-180°")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root, padding=(18, 16, 18, 8))
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text="XRD Atlas 一键导出", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        header,
        text="把 CIF 晶体结构批量转换为理论粉末 XRD 峰表，结果可直接用 Excel、Origin 或 Python 继续处理。",
        style="Subtitle.TLabel",
    ).grid(
        row=1,
        column=0,
        sticky="w",
        pady=(4, 0),
    )

    main = ttk.Frame(root, padding=(18, 8, 18, 10))
    main.grid(row=1, column=0, sticky="nsew")
    main.columnconfigure(0, weight=1)
    main.columnconfigure(1, weight=1)
    main.rowconfigure(0, weight=1)
    main.rowconfigure(1, weight=1)

    files_panel = ttk.LabelFrame(main, text="1. 添加 CIF 文件", padding=12, style="Step.TLabelframe")
    files_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
    files_panel.columnconfigure(0, weight=1)
    files_panel.rowconfigure(2, weight=1)

    file_buttons = ttk.Frame(files_panel)
    file_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    file_buttons.columnconfigure(3, weight=1)

    ttk.Label(files_panel, textvariable=input_summary_var).grid(row=1, column=0, sticky="w", pady=(0, 8))

    listbox = tk.Listbox(files_panel, height=14, selectmode=tk.EXTENDED)
    listbox.grid(row=2, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(files_panel, orient="vertical", command=listbox.yview)
    scrollbar.grid(row=2, column=1, sticky="ns")
    listbox.configure(yscrollcommand=scrollbar.set)

    def refresh_list() -> None:
        listbox.delete(0, tk.END)
        for path in selected_paths:
            listbox.insert(tk.END, path.name)
        count = len(selected_paths)
        input_summary_var.set("尚未添加 CIF 文件" if count == 0 else f"已添加 {count} 个 CIF 文件")
        output_var.set(str(suggest_output_path(selected_paths)))
        export_button.configure(state=tk.NORMAL if selected_paths else tk.DISABLED)
        status_var.set("可以导出：确认保存位置后点击“导出 Excel”。" if selected_paths else "准备就绪：添加 CIF 文件后，直接点击“导出 Excel”。")
        schedule_preview()

    def add_files() -> None:
        paths = filedialog.askopenfilenames(title="选择 CIF 文件", filetypes=[("CIF files", "*.cif")])
        known = {path.resolve() for path in selected_paths}
        for item in paths:
            path = Path(item).resolve()
            if path not in known:
                selected_paths.append(path)
                known.add(path)
        refresh_list()

    def add_folder() -> None:
        folder = filedialog.askdirectory(title="选择包含 CIF 文件的文件夹")
        if not folder:
            return
        known = {path.resolve() for path in selected_paths}
        for path in sorted(Path(folder).rglob("*.cif"), key=lambda value: str(value).lower()):
            resolved = path.resolve()
            if resolved not in known:
                selected_paths.append(resolved)
                known.add(resolved)
        refresh_list()

    def clear_files() -> None:
        selected_paths.clear()
        tree.delete(*tree.get_children())
        refresh_list()

    def remove_selected() -> None:
        selected = set(listbox.curselection())
        if not selected:
            return
        selected_paths[:] = [path for index, path in enumerate(selected_paths) if index not in selected]
        refresh_list()

    ttk.Button(file_buttons, text="添加文件", command=add_files, style="Action.TButton").grid(row=0, column=0, padx=(0, 6))
    ttk.Button(file_buttons, text="添加文件夹", command=add_folder, style="Action.TButton").grid(row=0, column=1, padx=(0, 6))
    ttk.Button(file_buttons, text="移除选中", command=remove_selected, style="Action.TButton").grid(row=0, column=2, padx=(0, 6))
    ttk.Button(file_buttons, text="清空", command=clear_files, style="Action.TButton").grid(row=0, column=3, sticky="w")

    settings_panel = ttk.LabelFrame(main, text="2. 保存位置和默认参数", padding=12, style="Step.TLabelframe")
    settings_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
    settings_panel.columnconfigure(1, weight=1)

    ttk.Label(settings_panel, textvariable=settings_summary_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
    ttk.Label(settings_panel, text="结果文件").grid(row=1, column=0, sticky="w", pady=4)

    output_frame = ttk.Frame(settings_panel)
    output_frame.grid(row=1, column=1, sticky="ew", pady=4)
    output_frame.columnconfigure(0, weight=1)
    ttk.Entry(output_frame, textvariable=output_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def choose_output() -> None:
        path = filedialog.asksaveasfilename(
            title="保存 Excel 结果",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialfile=Path(output_var.get()).name or "XRD峰表.xlsx",
        )
        if path:
            output_var.set(path)

    ttk.Button(output_frame, text="另存为", command=choose_output, style="Action.TButton").grid(row=0, column=1)

    advanced_frame = ttk.Frame(settings_panel)

    def update_settings_summary() -> None:
        energy_text = energy_var.get().strip()
        source_text = f"自定义能量：{energy_text} keV" if energy_text else "默认设置：Cu Kα"
        settings_summary_var.set(f"{source_text}，2θ {min_var.get()}-{max_var.get()}°")

    def toggle_advanced() -> None:
        if advanced_visible.get():
            advanced_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        else:
            advanced_frame.grid_remove()

    ttk.Checkbutton(settings_panel, text="显示高级参数", variable=advanced_visible, command=toggle_advanced).grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(8, 0),
    )
    advanced_frame.columnconfigure(1, weight=1)
    ttk.Label(advanced_frame, text="X 射线能量 keV").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(advanced_frame, textvariable=energy_var, width=10).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(advanced_frame, text="2θ 最小值").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(advanced_frame, textvariable=min_var, width=10).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(advanced_frame, text="2θ 最大值").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(advanced_frame, textvariable=max_var, width=10).grid(row=2, column=1, sticky="w", pady=4)
    ttk.Label(advanced_frame, text="能量留空则使用默认 Cu Kα。").grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
    energy_var.trace_add("write", lambda *_: update_settings_summary())
    min_var.trace_add("write", lambda *_: update_settings_summary())
    max_var.trace_add("write", lambda *_: update_settings_summary())

    preview_panel = ttk.LabelFrame(main, text="3. CIF 预览 / 导出结果", padding=12, style="Step.TLabelframe")
    preview_panel.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))
    preview_panel.columnconfigure(0, weight=1)
    preview_panel.rowconfigure(0, weight=1)

    columns = ("cif", "formula", "space_group", "peaks", "warning")
    tree = ttk.Treeview(preview_panel, columns=columns, show="headings", height=9)
    for column, label, width in (
        ("cif", "CIF 文件", 180),
        ("formula", "化学式", 90),
        ("space_group", "空间群", 90),
        ("peaks", "状态 / 峰数", 80),
        ("warning", "错误 / 警告", 240),
    ):
        tree.heading(column, text=label)
        tree.column(column, width=width, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")
    tree_scroll = ttk.Scrollbar(preview_panel, orient="vertical", command=tree.yview)
    tree_scroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=tree_scroll.set)

    footer = ttk.Frame(root, padding=(18, 6, 18, 16))
    footer.grid(row=2, column=0, sticky="ew")
    footer.columnconfigure(1, weight=1)

    export_button = ttk.Button(footer, text="导出 Excel", style="Primary.TButton")
    export_button.grid(row=0, column=0, sticky="w", padx=(0, 12))
    ttk.Label(footer, textvariable=status_var).grid(row=0, column=1, sticky="w")
    open_button = ttk.Button(footer, text="打开 Excel", state=tk.DISABLED)
    open_button.grid(row=0, column=2, sticky="e")

    def set_busy(is_busy: bool) -> None:
        export_button.configure(state=tk.DISABLED if is_busy or not selected_paths else tk.NORMAL)

    def schedule_preview() -> None:
        nonlocal preview_generation
        preview_generation += 1
        generation = preview_generation
        tree.delete(*tree.get_children())
        if not selected_paths:
            return

        paths_snapshot = list(selected_paths)
        status_var.set("正在读取 CIF 基本信息...")

        def worker() -> None:
            result = preview_simple_gui_inputs(paths_snapshot)

            def finish() -> None:
                if generation != preview_generation:
                    return
                tree.delete(*tree.get_children())
                for row in result.phase_rows:
                    tree.insert("", tk.END, values=row)
                if result.failed_count:
                    status_var.set(
                        f"已识别 {result.ready_count} 个 CIF；{result.failed_count} 个无法读取，"
                        "仍可导出其它可用文件。"
                    )
                else:
                    status_var.set(f"已识别 {result.ready_count} 个 CIF：确认保存位置后点击“导出 Excel”。")

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def export_now() -> None:
        nonlocal last_output_path
        set_busy(True)
        open_button.configure(state=tk.DISABLED)
        status_var.set("正在计算 XRD 峰表并写入 Excel，请稍候...")
        tree.delete(*tree.get_children())

        def worker() -> None:
            try:
                result = run_simple_gui_export(
                    selected_paths,
                    output_var.get(),
                    energy_keV=energy_var.get(),
                    two_theta_min=min_var.get(),
                    two_theta_max=max_var.get(),
                )
            except Exception as exc:
                root.after(
                    0,
                    lambda: (
                        set_busy(False),
                        status_var.set("导出失败。"),
                        messagebox.showerror("导出失败", friendly_error_message(exc)),
                    ),
                )
                return

            def finish() -> None:
                nonlocal last_output_path
                for row in result.phase_rows:
                    tree.insert("", tk.END, values=row)
                last_output_path = result.output_path
                set_busy(False)
                open_button.configure(state=tk.NORMAL)
                status_text, dialog_text = gui_export_completion_text(result)
                status_var.set(status_text)
                messagebox.showinfo("导出完成", dialog_text)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def open_output_folder() -> None:
        if last_output_path is not None:
            open_export_result(last_output_path)

    export_button.configure(command=export_now)
    export_button.configure(state=tk.NORMAL if selected_paths else tk.DISABLED)
    open_button.configure(command=open_output_folder)
    refresh_list()
    root.mainloop()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        _launch_tk_app(sys.argv[1:] if argv is None else argv)
    except Exception as exc:
        if exc.__class__.__name__ == "TclError" and "init.tcl" in str(exc):
            print(
                "XRD Atlas 无法启动图形界面：当前 Python 的 Tcl/Tk 组件不可用。\n"
                "请优先双击 start_xrd_atlas.bat；如果仍失败，请修复 Python 安装中的 Tcl/Tk，"
                "或使用 dist\\XRD Atlas\\XRD Atlas.exe。"
            )
            return 1
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
