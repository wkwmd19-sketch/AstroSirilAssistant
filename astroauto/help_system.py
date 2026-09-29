from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import yaml

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HELP_FILE = PACKAGE_ROOT / "help" / "topics.yaml"

class HelpCatalog:
    def __init__(self, path: Path = DEFAULT_HELP_FILE):
        with Path(path).open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self.topics = raw.get("topics", {})

    def get(self, topic_id: str):
        return self.topics.get(topic_id, {
            "title": topic_id,
            "tooltip": "도움말이 아직 등록되지 않았습니다.",
            "detail": "이 항목의 상세 도움말은 이후 추가됩니다.",
        })

class ToolTip:
    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id = None
        self.tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<FocusIn>", self._schedule, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")

    def _schedule(self, *_):
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=7,
            pady=5,
            wraplength=420,
        )
        label.pack()

    def _hide(self, *_):
        self._cancel()
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None

class HelpSystem:
    def __init__(self, root):
        self.root = root
        self.catalog = HelpCatalog()

    def tooltip(self, widget, topic_id: str):
        topic = self.catalog.get(topic_id)
        return ToolTip(widget, topic.get("tooltip", ""))

    def help_button(self, parent, topic_id: str):
        btn = ttk.Button(parent, text="?", width=2, command=lambda: self.show_detail(topic_id))
        self.tooltip(btn, topic_id)
        return btn

    def show_detail(self, topic_id: str):
        topic = self.catalog.get(topic_id)
        win = tk.Toplevel(self.root)
        win.title(f"도움말 - {topic.get('title', topic_id)}")
        win.geometry("620x480")
        win.transient(self.root)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=topic.get("title", topic_id),
            font=("", 13, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        text = tk.Text(frame, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", topic.get("detail", ""))
        text.configure(state="disabled")

        ttk.Button(frame, text="닫기", command=win.destroy).pack(anchor="e", pady=(8,0))
