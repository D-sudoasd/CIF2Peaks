CIF2Peaks Windows 使用说明

本文件夹是便携版程序。目标电脑不需要安装 Python。

推荐分发方式：

把 CIF2Peaks_Windows_Portable.zip 发给目标电脑，解压后使用里面的 CIF2Peaks 文件夹。
不要只复制单独的 exe 文件，因为程序还需要 _internal 文件夹。

最简单用法：

1. 双击 CIF2Peaks.exe
   打开图形界面。可以把 CIF 文件或包含 CIF 的文件夹直接拖入窗口，也可以点击“添加文件”或“添加文件夹”，选择 CIF 后点击“导出 Excel”。

2. 把 CIF 文件或包含 CIF 的文件夹拖到 CIF2Peaks.exe
   程序会自动把这些 CIF 载入图形界面，并自动建议 Excel 保存位置。

3. 把 CIF 文件或包含 CIF 的文件夹拖到 CIF2Peaks Quick Export.exe
   程序会使用默认 Cu Kα、2θ 0-180°，直接在第一个 CIF 所在文件夹生成 Excel。

GUI 中的 X 射线参数会直接显示在主界面：可选 Cu Kα、30 keV、83 keV，也可以手动填写能量 keV。手动能量非空时优先生效；留空则使用所选预设。

第一次在新电脑上使用：

1. 双击 windows_self_test.bat。
2. 如果提示 Self-test passed，说明本机可以运行。
3. 自检会在同一文件夹生成 cif2peaks_self_test_report.txt。
4. 如果失败，请确认你复制的是整个 CIF2Peaks 文件夹，而不是只复制 exe 文件；需要求助时，把 cif2peaks_self_test_report.txt 一起发出。

输出说明：

- 使用说明：打开 Excel 时默认显示，说明常用工作表和列名。
- 推荐峰表：中文列名的常用峰表，适合直接查看、筛选和复制到 Origin。
- Summary：导出参数和每个 CIF 的状态。
- Combined Peaks：英文列名的完整合并峰表，适合程序读取。
- 每个相一个单独工作表。

如果某个 CIF 无法解析，程序仍会生成 Excel 诊断文件；请查看 Summary 中的错误提示。

注意：

CIF2Peaks 导出的是 CIF 晶体结构对应的理论粉末 XRD 峰表，不是实验谱拟合、物相检索数据库或 Rietveld 精修程序。
