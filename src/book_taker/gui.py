from __future__ import annotations

import sys
import threading
from pathlib import Path

from .client import ClientForm, form_to_options, validate_form
from .pipeline import run_book_taker


def _missing_tkinter_message() -> str:
    return (
        "error: the desktop client requires Tkinter. Install a Python build that "
        "includes tkinter, or use the book-taker CLI."
    )


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        print(_missing_tkinter_message(), file=sys.stderr)
        return 2

    root = tk.Tk()
    root.title("Book Taker 客户端")
    root.minsize(640, 560)
    root.geometry("720x640")

    book_var = tk.StringVar()
    output_var = tk.StringVar()
    api_key_var = tk.StringVar()
    model_var = tk.StringVar()
    base_url_var = tk.StringVar()
    dry_run_var = tk.BooleanVar(value=False)
    overwrite_var = tk.BooleanVar(value=False)
    busy = {"value": False}

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Book Taker 客户端", font=("", 16, "bold")).grid(
        row=0, column=0, columnspan=3, sticky=tk.W
    )
    ttk.Label(frame, text="选择本地书籍，生成可回源校验的拆书笔记。无需先安装 Python。").grid(
        row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 12)
    )

    def add_row(
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        browse=None,
        show: str | None = None,
    ):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        entry = ttk.Entry(frame, textvariable=variable, show=show or "")
        entry.grid(row=row, column=1, sticky=tk.EW, padx=8, pady=4)
        if browse is not None:
            ttk.Button(frame, text="浏览", command=browse).grid(row=row, column=2, sticky=tk.E)

    def choose_book() -> None:
        path = filedialog.askopenfilename(
            title="选择书籍",
            filetypes=[
                ("Books", "*.pdf *.epub *.txt *.md"),
                ("PDF", "*.pdf"),
                ("EPUB", "*.epub"),
                ("Text", "*.txt *.md"),
                ("All files", "*.*"),
            ],
        )
        if path:
            book_var.set(path)
            if not output_var.get().strip():
                output_var.set(str(Path(path).parent / "book-taker-output"))

    def choose_output() -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            output_var.set(path)

    add_row(2, "书籍文件", book_var, browse=choose_book)
    add_row(3, "输出目录", output_var, browse=choose_output)
    add_row(4, "API 密钥", api_key_var, show="*")
    add_row(5, "模型", model_var)
    add_row(6, "API 地址", base_url_var)

    options = ttk.Frame(frame)
    options.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(8, 4))
    ttk.Checkbutton(
        options, text="仅本地提取（不调用模型）", variable=dry_run_var
    ).pack(anchor=tk.W)
    ttk.Checkbutton(options, text="覆盖上次输出", variable=overwrite_var).pack(anchor=tk.W)
    ttk.Label(
        frame,
        text="密钥只保存在本次会话内存中，不会写入磁盘或命令行参数。",
    ).grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))

    log = tk.Text(frame, height=16, wrap=tk.WORD, state=tk.DISABLED)
    log.grid(row=10, column=0, columnspan=3, sticky=tk.NSEW, pady=(8, 0))
    frame.rowconfigure(10, weight=1)
    start_button = ttk.Button(frame, text="开始拆书")
    start_button.grid(row=9, column=0, columnspan=3, sticky=tk.EW, pady=8)

    def append_log(message: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, message + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    def current_form() -> ClientForm:
        return ClientForm(
            book=book_var.get(),
            output=output_var.get(),
            api_key=api_key_var.get(),
            model=model_var.get(),
            base_url=base_url_var.get(),
            dry_run=dry_run_var.get(),
            overwrite=overwrite_var.get(),
        )

    def set_busy(value: bool) -> None:
        busy["value"] = value
        start_button.configure(state=tk.DISABLED if value else tk.NORMAL)

    def confirm_usage() -> bool:
        result = {"ok": False}
        done = threading.Event()

        def ask() -> None:
            result["ok"] = bool(
                messagebox.askokcancel(
                    "确认调用模型",
                    "即将按估算用量调用已配置的模型接口。密钥不会写入磁盘。是否继续？",
                    parent=root,
                )
            )
            done.set()

        root.after(0, ask)
        done.wait()
        return result["ok"]

    def run_job() -> None:
        form = current_form()
        errors = validate_form(form)
        if errors:
            root.after(0, lambda: messagebox.showerror("无法开始", "\n".join(errors), parent=root))
            root.after(0, lambda: set_busy(False))
            return
        options = form_to_options(form)

        def progress(message: str) -> None:
            root.after(0, lambda: append_log(message))

        code = run_book_taker(
            options,
            progress=progress,
            error=progress,
            confirm=None if options.dry_run else confirm_usage,
        )
        if code == 0:
            progress("客户端运行结束。")
        root.after(0, lambda: set_busy(False))

    def start() -> None:
        if busy["value"]:
            return
        log.configure(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.configure(state=tk.DISABLED)
        set_busy(True)
        threading.Thread(target=run_job, daemon=True).start()

    start_button.configure(command=start)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
