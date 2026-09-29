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
        # Label-only tooltips are intentionally mouse-hover based.
        # Do not bind focus events: keyboard focus should not cause surprise popups.

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
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        palette = getattr(self.widget.winfo_toplevel(), "_astro_palette", {})
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=9,
            pady=7,
            wraplength=430,
            background=palette.get("card_alt", "#1E293B"),
            foreground=palette.get("text", "#E5ECF6"),
            highlightbackground=palette.get("border", "#2A3A52"),
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
        self._detail_window = None
        self._detail_title = None
        self._detail_text = None

    def tooltip(self, widget, topic_id: str):
        """Attach a short tooltip. v0.5.1 policy: call this on labels only."""
        topic = self.catalog.get(topic_id)
        return ToolTip(widget, topic.get("tooltip", ""))

    def _ensure_window(self):
        if self._detail_window and self._detail_window.winfo_exists():
            return self._detail_window

        win = tk.Toplevel(self.root)
        win.title("AstroSirilAssistant 도움말")
        win.geometry("700x560")
        win.minsize(560, 420)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self._close_window)

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)

        self._detail_title = ttk.Label(frame, text="", font=("", 14, "bold"))
        self._detail_title.pack(anchor="w", pady=(0, 10))

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)
        palette = getattr(self.root, "_astro_palette", {})
        self._detail_text = tk.Text(
            text_frame,
            wrap="word",
            padx=10,
            pady=10,
            background=palette.get("input_bg", "#0F1A2B"),
            foreground=palette.get("text", "#E5ECF6"),
            insertbackground=palette.get("text", "#E5ECF6"),
            selectbackground=palette.get("select_bg", "#244463"),
            selectforeground=palette.get("text", "#E5ECF6"),
            relief="flat",
            borderwidth=0,
        )
        scroll = ttk.Scrollbar(text_frame, command=self._detail_text.yview)
        self._detail_text.configure(yscrollcommand=scroll.set)
        self._detail_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(frame, text="닫기", command=self._close_window).pack(anchor="e", pady=(10,0))
        self._detail_window = win
        return win

    def _close_window(self):
        if self._detail_window and self._detail_window.winfo_exists():
            self._detail_window.destroy()
        self._detail_window = None
        self._detail_title = None
        self._detail_text = None

    def _set_content(self, title: str, body: str):
        win = self._ensure_window()
        self._detail_title.configure(text=title)
        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        self._detail_text.insert("1.0", body)
        self._detail_text.configure(state="disabled")
        win.deiconify()
        win.lift()
        try:
            win.focus_force()
        except Exception:
            pass

    def show_detail(self, topic_id: str):
        topic = self.catalog.get(topic_id)
        self._set_content(topic.get("title", topic_id), topic.get("detail", ""))

    def show_section(self, section_title: str, topic_ids: list[str]):
        blocks = []
        for topic_id in topic_ids:
            topic = self.catalog.get(topic_id)
            blocks.append(
                f"■ {topic.get('title', topic_id)}\n\n"
                f"{topic.get('detail', '')}".rstrip()
            )
        self._set_content(section_title, "\n\n" + ("\n\n" + "─" * 48 + "\n\n").join(blocks))

    def section_help_button(self, parent, section_title: str, topic_ids: list[str]):
        return ttk.Button(
            parent,
            text="도움말  ?",
            command=lambda: self.show_section(section_title, topic_ids)
        )
