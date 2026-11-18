# -*- coding: utf-8 -*-
"""Non-overlapping Chinese/English/Vietnamese menu for 2D station agents."""
import tkinter as tk

TEXT = {
    "检查": ("检查", "Check", "Kiểm tra"),
    "选择数据目录": ("选择数据目录", "Select data folder", "Chọn thư mục dữ liệu"),
    "部分测试（<8条）": ("部分测试（<8条）", "Partial test (<8)", "Kiểm tra một phần (<8)"),
    "确认复测": ("确认复测", "Confirm retest", "Xác nhận kiểm tra lại"),
    "解除报警 / ACKNOWLEDGE": ("解除报警", "Acknowledge alarm", "Tắt cảnh báo"),
    "刷新": ("刷新", "Refresh", "Làm mới"),
    "启动中": ("启动中", "Starting", "Đang khởi động"),
    "等待老化结果": ("等待老化结果", "Waiting for aging result", "Đang chờ kết quả lão hóa"),
    "SQL Server连接中": ("SQL Server连接中", "Connecting to SQL Server", "Đang kết nối SQL Server"),
}

TITLE = {
    "组装 ATE": ("组装 ATE", "Assembly ATE", "ATE lắp ráp"),
    "超声工站": ("超声工站", "Supersonic station", "Trạm siêu âm"),
    "成品老化": ("成品老化", "Aging cabinet", "Tủ lão hóa"),
    "高压 ATE": ("高压 ATE", "High-voltage ATE", "ATE điện áp cao"),
    "包装 ATE": ("包装 ATE", "Packaging ATE", "ATE đóng gói"),
}


def install_language_menu(root):
    locale = tk.StringVar(master=root, value="zh")
    index = {"zh": 0, "en": 1, "vi": 2}
    originals = {}
    original_title = root.title()

    def translated(value, lang):
        if value in TEXT:
            return TEXT[value][index[lang]]
        result = value
        for source, choices in TITLE.items():
            if source in result:
                result = result.replace(source, choices[index[lang]])
        return result

    def walk(widget):
        for child in widget.winfo_children():
            try:
                current = child.cget("text")
                if child not in originals:
                    originals[child] = current
                child.configure(text=translated(originals[child], locale.get()))
            except (tk.TclError, AttributeError):
                pass
            walk(child)

    def apply_language(*_):
        root.title(translated(original_title, locale.get()))
        walk(root)

    menu = tk.Menu(root)
    language = tk.Menu(menu, tearoff=False)
    language.add_radiobutton(label="中文", variable=locale, value="zh", command=apply_language)
    language.add_radiobutton(label="English", variable=locale, value="en", command=apply_language)
    language.add_radiobutton(label="Tiếng Việt", variable=locale, value="vi", command=apply_language)
    menu.add_cascade(label="语言 / Language / Ngôn ngữ", menu=language)
    root.configure(menu=menu)

    # A visible in-window language bar is used in addition to the native
    # menu. It is packed before the station content, so it never overlaps
    # scan, retest, or partial-test controls.
    existing = list(root.winfo_children())
    bar = tk.Frame(root, bg="#111827", height=38)
    bar.pack_propagate(False)
    pack_options = {"side": "top", "fill": "x"}
    if existing:
        pack_options["before"] = existing[0]
    try:
        bar.pack(**pack_options)
    except tk.TclError:
        bar.pack(side="top", fill="x")
    tk.Label(
        bar, text="语言 / Language / Ngôn ngữ", bg="#111827", fg="white",
        font=("Microsoft YaHei", 11, "bold"),
    ).pack(side="left", padx=(12, 18), pady=5)
    for label, value in (("中文", "zh"), ("English", "en"), ("Tiếng Việt", "vi")):
        tk.Radiobutton(
            bar, text=label, variable=locale, value=value,
            command=apply_language, indicatoron=False,
            bg="#334155", fg="white", selectcolor="#2563eb",
            activebackground="#475569", activeforeground="white",
            font=("Microsoft YaHei", 10, "bold"), padx=14, pady=3,
        ).pack(side="left", padx=4, pady=4)
    root.station_locale = locale
    root.station_apply_language = apply_language
    apply_language()
    return locale
