#!/usr/bin/env python3
"""
Terminal Todo — keyboard-driven todo app for the real terminal.
No external dependencies. Requires Python 3.6+ and a 256-colour terminal.

Usage:  python3 todo.py
Data:   ~/.local/share/terminal-todo/todos.json
Export: ~/todo-export.txt  (via :export)
"""

import curses
import json
import os
import platform
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

def _strftime_day(ts_ms):
    """Cross-platform date string without leading zero on day."""
    dt = datetime.fromtimestamp(ts_ms / 1000)
    month = dt.strftime("%b")
    day   = str(dt.day)          # no leading zero, works everywhere
    return f"{month} {day}"

# ── Storage ───────────────────────────────────────────────────────────────────

DATA_DIR  = Path.home() / ".local" / "share" / "terminal-todo"
DATA_FILE = DATA_DIR / "todos.json"

def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                d = json.load(f)
            return d.get("todos", []), d.get("sort", "default"), d.get("theme", "hacker")
        except Exception:
            pass
    return [], "default", "hacker"

def save_data(todos, sort_by, theme):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump({"todos": todos, "sort": sort_by, "theme": theme}, f, indent=2)

# ── Helpers ───────────────────────────────────────────────────────────────────

def new_id():
    return str(uuid.uuid4())[:8]

def today_ms():
    d = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp() * 1000)

def fmt_due(ts):
    if not ts:
        return None, None
    tod  = today_ms()
    diff = round((ts - tod) / 86_400_000)
    if diff < 0:
        return f"{-diff}d overdue", "danger"
    if diff == 0:
        return "today", "ok"
    if diff == 1:
        return "tomorrow", "warn"
    if diff < 7:
        return datetime.fromtimestamp(ts / 1000).strftime("%a"), "muted"
    return _strftime_day(ts), "muted"

def fmt_est(mins):
    if not mins:
        return None
    if mins >= 60:
        h = mins / 60
        return f"~{h:.0f}h" if h == int(h) else f"~{h:.1f}h"
    return f"~{mins}m"

def parse_task(raw):
    text     = raw
    priority = "med"
    tags     = []
    due      = None
    est      = None

    def _sub(pat, repl, s):
        return re.sub(pat, repl, s, flags=re.I)

    text, n = re.subn(r'!(high|h)\b',           '', text, flags=re.I); priority = "high" if n else priority
    text, n = re.subn(r'!(low|l)\b',            '', text, flags=re.I); priority = "low"  if n else priority
    text     = re.sub(r'!(med|medium|m)\b',     '', text, flags=re.I)

    found_tags = re.findall(r'#(\w+)', text)
    tags       = [t.lower() for t in found_tags]
    text       = re.sub(r'#\w+', '', text)

    def _est(m):
        nonlocal est
        n2, u = m.group(1), m.group(2).lower()
        est = round(float(n2) * 60) if u == 'h' else int(float(n2))
        return ''
    text = re.sub(r'~(\d+(?:\.\d+)?)(h|m)\b', _est, text, flags=re.I)

    tod = today_ms()

    def _set_due(ms):
        nonlocal due; due = ms; return ''

    text = re.sub(r'\btoday\b',      lambda m: _set_due(tod),                        text, flags=re.I)
    text = re.sub(r'\btomorrow\b',   lambda m: _set_due(tod + 86_400_000),           text, flags=re.I)
    text = re.sub(r'\bnext\s*week\b',lambda m: _set_due(tod + 7 * 86_400_000),       text, flags=re.I)

    curr_sun = (datetime.now().weekday() + 1) % 7   # Sun=0 … Sat=6
    for i, day in enumerate(['sun','mon','tue','wed','thu','fri','sat']):
        def _day(m, i=i):
            diff = ((i - curr_sun) % 7) or 7
            return _set_due(tod + diff * 86_400_000)
        text = re.sub(rf'\b{day}(?:day)?\b', _day, text, flags=re.I)

    text = re.sub(r'\s{2,}', ' ', text).strip()
    return {
        "id":       new_id(),
        "text":     text or raw,
        "priority": priority,
        "tags":     tags,
        "due":      due,
        "est":      est,
        "done":     False,
        "ca":       int(time.time() * 1000),
    }

# ── Themes ────────────────────────────────────────────────────────────────────
# 256-colour palette indices.  bg/fg are the base colours for each theme.

THEMES = {
    "hacker":    {"name": "Hacker",    "bg": 232, "sel_bg": 22,  "fg": 46,  "accent": 46,  "accent2": 34,  "ok": 34,  "warn": 214, "danger": 196, "muted": 28,  "dim": 238},
    "dracula":   {"name": "Dracula",   "bg": 234, "sel_bg": 236, "fg": 189, "accent": 141, "accent2": 204, "ok": 114, "warn": 228, "danger": 204, "muted": 60,  "dim": 237},
    "nord":      {"name": "Nord",      "bg": 234, "sel_bg": 236, "fg": 153, "accent": 110, "accent2": 109, "ok": 108, "warn": 221, "danger": 131, "muted": 61,  "dim": 237},
    "amber":     {"name": "Amber",     "bg": 232, "sel_bg": 52,  "fg": 214, "accent": 214, "accent2": 208, "ok": 178, "warn": 208, "danger": 196, "muted": 94,  "dim": 238},
    "monokai":   {"name": "Monokai",   "bg": 234, "sel_bg": 236, "fg": 253, "accent": 228, "accent2": 148, "ok": 148, "warn": 208, "danger": 197, "muted": 242, "dim": 238},
    "synthwave": {"name": "Synthwave", "bg": 232, "sel_bg": 53,  "fg": 183, "accent": 198, "accent2": 45,  "ok": 45,  "warn": 226, "danger": 198, "muted": 91,  "dim": 238},
    "ocean":     {"name": "Ocean",     "bg": 233, "sel_bg": 236, "fg": 153, "accent": 81,  "accent2": 43,  "ok": 71,  "warn": 214, "danger": 203, "muted": 24,  "dim": 237},
    "paper":     {"name": "Paper",     "bg": 255, "sel_bg": 252, "fg": 234, "accent": 26,  "accent2": 95,  "ok": 22,  "warn": 130, "danger": 160, "muted": 244, "dim": 250},
}
THEME_LIST = list(THEMES.keys())

# Colour pair IDs
_CP = {k: i+1 for i, k in enumerate(
    ["fg","accent","accent2","ok","warn","danger","muted","dim","sel",
     "cmd_inp","cmd_cmd","cmd_srch","header"]
)}

def _init_colors(theme_id):
    t  = THEMES[theme_id]
    bg = t["bg"]
    curses.init_pair(_CP["fg"],       t["fg"],       bg)
    curses.init_pair(_CP["accent"],   t["accent"],   bg)
    curses.init_pair(_CP["accent2"],  t["accent2"],  bg)
    curses.init_pair(_CP["ok"],       t["ok"],       bg)
    curses.init_pair(_CP["warn"],     t["warn"],     bg)
    curses.init_pair(_CP["danger"],   t["danger"],   bg)
    curses.init_pair(_CP["muted"],    t["muted"],    bg)
    curses.init_pair(_CP["dim"],      t["dim"],      bg)
    curses.init_pair(_CP["sel"],      t["fg"],       t["sel_bg"])
    curses.init_pair(_CP["cmd_inp"],  t["ok"],       bg)
    curses.init_pair(_CP["cmd_cmd"],  t["warn"],     bg)
    curses.init_pair(_CP["cmd_srch"], t["accent"],   bg)
    curses.init_pair(_CP["header"],   t["accent"],   bg)

# ── App ───────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, scr):
        self.scr = scr
        self.todos, self.sort_by, self.theme_id = load_data()

        if not self.todos:
            defaults = [
                "welcome — press ? for the full guide !high",
                "review pull request for auth module !high #work today ~1h",
                "buy groceries !low #personal ~30m",
                "read system design chapter 4 #learning ~45m",
            ]
            self.todos = [parse_task(d) for d in defaults]
            self.todos[3]["done"] = True
            save_data(self.todos, self.sort_by, self.theme_id)

        self.selected      = 0
        self.scroll        = 0
        self.filter        = "all"
        self.active_tag    = None
        self.search_q      = ""
        self.mode          = "nav"       # nav | input | command | search | help | theme
        self.input_buf     = ""
        self.cursor_pos    = 0
        self.editing_id    = None
        self.cmd_hist      = []
        self.cmd_hist_idx  = -1
        self.status_msg    = "ready — press ? for help"
        self.status_until  = time.time() + 4
        self._setup()

    def _setup(self):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        self.scr.keypad(True)
        self.scr.timeout(80)
        _init_colors(self.theme_id)

    def cp(self, name):
        return curses.color_pair(_CP[name])

    # ── Filtering / sorting ───────────────────────────────────────────────────

    def filtered(self):
        ft = list(self.todos)
        if self.search_q:
            q = self.search_q.lower()
            ft = [t for t in ft if q in t["text"].lower()
                  or any(q in tag for tag in t.get("tags", []))]
        if self.filter == "active":
            ft = [t for t in ft if not t["done"]]
        elif self.filter == "done":
            ft = [t for t in ft if t["done"]]
        elif self.filter == "high":
            ft = [t for t in ft if t["priority"] == "high"]
        if self.active_tag:
            ft = [t for t in ft if self.active_tag in t.get("tags", [])]
        if self.sort_by == "priority":
            order = {"high": 0, "med": 1, "low": 2}
            ft.sort(key=lambda t: order.get(t["priority"], 1))
        elif self.sort_by == "date":
            ft.sort(key=lambda t: (t.get("due") is None, t.get("due") or 0))
        elif self.sort_by == "alpha":
            ft.sort(key=lambda t: t["text"].lower())
        return ft

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self, msg, secs=2.5):
        self.status_msg   = msg
        self.status_until = time.time() + secs

    # ── Safe write ────────────────────────────────────────────────────────────

    def w(self, y, x, text, attr=0, clip=None):
        """Write text safely within screen bounds."""
        try:
            H, W = self.scr.getmaxyx()
            if y < 0 or y >= H or x < 0 or x >= W:
                return
            avail = (clip if clip is not None else W) - x
            if avail <= 0:
                return
            self.scr.addstr(y, x, text[:avail], attr)
        except curses.error:
            pass

    def fill(self, y, attr=0):
        try:
            _, W = self.scr.getmaxyx()
            self.scr.addstr(y, 0, " " * W, attr)
        except curses.error:
            pass

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        self.scr.erase()
        H, W = self.scr.getmaxyx()
        if   self.mode == "help":  self._draw_help(H, W)
        elif self.mode == "theme": self._draw_theme(H, W)
        else:                      self._draw_main(H, W)
        self.scr.refresh()

    def _draw_main(self, H, W):
        ft    = self.filtered()
        total = len(self.todos)
        done  = sum(1 for t in self.todos if t["done"])

        if self.selected >= len(ft):
            self.selected = max(0, len(ft) - 1)

        # ── Row 0: title bar ──────────────────────────────────────────────
        self.fill(0, self.cp("dim"))
        left  = f" TODO — TERMINAL v3"
        right = f"[T] {THEMES[self.theme_id]['name']} "
        bar_w = 14
        filled = int(bar_w * done / total) if total else 0
        bar   = "█" * filled + "░" * (bar_w - filled)
        mid   = f"{bar} {done}/{total}"
        self.w(0, 0,              left,  self.cp("dim"))
        self.w(0, W // 2 - len(mid) // 2, mid, self.cp("ok"))
        self.w(0, W - len(right), right, self.cp("muted"))

        # ── Row 1: app name + meta ────────────────────────────────────────
        meta = f"sort:{self.sort_by}"
        if self.active_tag: meta += f" #{self.active_tag}"
        if self.search_q:   meta += f" /{self.search_q}"
        self.w(1, 1, "TODO", self.cp("accent") | curses.A_BOLD)
        self.w(1, W - len(meta) - 1, meta, self.cp("dim"))

        # ── Row 2: divider ────────────────────────────────────────────────
        self.w(2, 0, "─" * W, self.cp("dim"))

        # ── Row 3: filter tabs + tag pills ────────────────────────────────
        tabs = [("all","ALL"),("active","ACTIVE"),("done","DONE"),("high","HIGH")]
        x = 1
        for fid, lbl in tabs:
            s = f" {lbl} "
            if fid == self.filter:
                self.w(3, x, s, self.cp("accent") | curses.A_REVERSE)
            else:
                self.w(3, x, s, self.cp("dim"))
            x += len(s) + 1

        x += 2
        all_tags = list(dict.fromkeys(
            tag for t in self.todos for tag in t.get("tags", [])))
        for tag in all_tags:
            lbl = f"#{tag}"
            if x + len(lbl) >= W - 2:
                break
            if tag == self.active_tag:
                self.w(3, x, lbl, self.cp("accent2") | curses.A_REVERSE)
            else:
                self.w(3, x, lbl, self.cp("dim"))
            x += len(lbl) + 2

        # ── Row 4: divider ────────────────────────────────────────────────
        self.w(4, 0, "─" * W, self.cp("dim"))

        # ── Rows 5…H-4: todo list ─────────────────────────────────────────
        list_top = 5
        list_bot = H - 4
        list_h   = max(0, list_bot - list_top)

        if self.selected < self.scroll:
            self.scroll = self.selected
        if self.selected >= self.scroll + list_h:
            self.scroll = self.selected - list_h + 1

        for i, todo in enumerate(ft[self.scroll : self.scroll + list_h]):
            row = list_top + i
            idx = i + self.scroll
            sel = (idx == self.selected)

            if sel:
                self.fill(row, self.cp("sel"))

            x = 1
            arrow = "▸ " if sel else "  "
            self.w(row, x, arrow,
                   self.cp("accent") if sel else self.cp("dim"))
            x += 2

            pri  = todo.get("priority", "med")
            dot  = "●"
            datr = {"high": self.cp("danger"),
                    "med":  self.cp("warn"),
                    "low":  self.cp("ok")}.get(pri, self.cp("warn"))
            self.w(row, x, dot, datr); x += 2

            cb   = "[✓]" if todo["done"] else "[ ]"
            catr = self.cp("ok") if todo["done"] else self.cp("dim")
            self.w(row, x, cb, catr); x += 4

            # Build suffix chips to know how much room text has
            chips = []
            for tag in todo.get("tags", [])[:2]:
                chips.append((f"#{tag}", "accent2"))
            ds, dc = fmt_due(todo.get("due"))
            if ds:
                chips.append((ds, dc or "muted"))
            es = fmt_est(todo.get("est"))
            if es:
                chips.append((es, "muted"))

            chip_len = sum(len(c) + 1 for c, _ in chips)
            max_txt  = W - x - chip_len - 2

            txt  = todo["text"]
            tatr = self.cp("dim") if todo["done"] else (
                   self.cp("sel") if sel else self.cp("fg"))

            if len(txt) > max_txt and max_txt > 3:
                txt = txt[:max_txt - 1] + "…"

            # Highlight search match
            if self.search_q:
                ql = self.search_q.lower()
                tl = todo["text"].lower()
                mi = tl.find(ql)
                if mi >= 0 and mi < len(txt):
                    self.w(row, x, txt[:mi], tatr)
                    self.w(row, x + mi, txt[mi:mi+len(ql)],
                           self.cp("accent") | curses.A_REVERSE)
                    self.w(row, x + mi + len(ql), txt[mi+len(ql):], tatr)
                else:
                    self.w(row, x, txt, tatr)
            else:
                self.w(row, x, txt, tatr)
            x += len(txt) + 1

            # Chips
            for chip_txt, chip_key in chips:
                self.w(row, x, chip_txt, self.cp(chip_key))
                x += len(chip_txt) + 1

        if not ft:
            mid = (list_top + list_bot) // 2
            msg = "no tasks — press n to add"
            self.w(mid, W // 2 - len(msg) // 2, msg, self.cp("dim"))

        # ── H-3: divider ──────────────────────────────────────────────────
        self.w(H - 3, 0, "─" * W, self.cp("dim"))

        # ── H-2: command line ─────────────────────────────────────────────
        if self.mode in ("input", "command", "search"):
            pfx, cpair = {
                "input":   (">", "cmd_inp"),
                "command": (":", "cmd_cmd"),
                "search":  ("/", "cmd_srch"),
            }[self.mode]
            self.w(H - 2, 0, f"{pfx} ", self.cp(cpair))
            self.w(H - 2, 2, self.input_buf, self.cp(cpair))
            # block cursor
            cx  = 2 + self.cursor_pos
            ch  = (self.input_buf[self.cursor_pos]
                   if self.cursor_pos < len(self.input_buf) else " ")
            try:
                if cx < W:
                    self.scr.addstr(H - 2, cx, ch,
                                    self.cp(cpair) | curses.A_REVERSE)
            except curses.error:
                pass
        else:
            hint = "n new  :cmd  /search  ?help  T theme  tab filter  spc done  e edit  d del"
            self.w(H - 2, 0, "— ", self.cp("dim"))
            self.w(H - 2, 2, hint, self.cp("dim"), W - 2)

        # ── H-1: status bar ───────────────────────────────────────────────
        if time.time() < self.status_until and self.status_msg:
            self.w(H - 1, 0, self.status_msg, self.cp("accent"), W - 1)
        else:
            info = (f"{len(ft)} task{'s' if len(ft)!=1 else ''}"
                    f"  {done}/{total} done")
            self.w(H - 1, 0, info, self.cp("muted"))

    def _draw_theme(self, H, W):
        title = " SELECT THEME "
        self.w(0, 0, "─" * W, self.cp("dim"))
        self.w(0, (W - len(title)) // 2, title,
               self.cp("accent") | curses.A_BOLD)
        self.w(1, 2, "press 1–8 to select  ·  esc to close",
               self.cp("dim"))
        self.w(2, 0, "─" * W, self.cp("dim"))

        for i, (tid, td) in enumerate(THEMES.items()):
            row    = 4 + i
            active = (tid == self.theme_id)
            prefix = "▸ " if active else "  "
            label  = f"{prefix}{i+1}.  {td['name']}"
            attr   = (self.cp("accent") | curses.A_BOLD) if active else self.cp("fg")
            self.w(row, 3, label, attr)

        self.w(4 + len(THEMES) + 1, 0, "─" * W, self.cp("dim"))

    def _draw_help(self, H, W):
        title = " -- HELP -- "
        self.w(0, 0, "─" * W, self.cp("dim"))
        self.w(0, (W - len(title)) // 2, title,
               self.cp("accent") | curses.A_BOLD)

        lines = [
            ("", None),
            ("NAVIGATION", "section"),
            ("  ↑/k   ↓/j       move up / down", "row"),
            ("  g / G            jump to top / bottom", "row"),
            ("  Tab              cycle ALL → ACTIVE → DONE → HIGH", "row"),
            ("  Esc              clear search or tag filter", "row"),
            ("", None),
            ("ACTIONS", "section"),
            ("  n                new task  (NLP input)", "row"),
            ("  Space            toggle done / undone", "row"),
            ("  e                edit selected task", "row"),
            ("  d / Delete       delete selected task", "row"),
            ("  :                command bar", "row"),
            ("  /                live search", "row"),
            ("  T  or  1–8       theme picker / quick-switch", "row"),
            ("  ?                toggle this help", "row"),
            ("", None),
            ("NATURAL LANGUAGE INPUT  (press n then type)", "section"),
            ("  !high  !med  !low           set priority", "detail"),
            ("  #work  #health              attach tags", "detail"),
            ("  today  tomorrow  friday     due date", "detail"),
            ("  next week                   7 days from now", "detail"),
            ("  ~2h  ~30m                   time estimate", "detail"),
            ("", None),
            ("  example:   fix auth bug !high #work tomorrow ~2h", "example"),
            ("", None),
            ("COMMAND BAR  (press :)", "section"),
            ("  :sort priority|date|alpha|default", "cmd"),
            ("  :search <query>             filter by keyword", "cmd"),
            ("  :filter #tag                filter by tag", "cmd"),
            ("  :clear done                 delete all completed", "cmd"),
            ("  :export                     save tasks → ~/todo-export.txt", "cmd"),
            ("", None),
            ("THEMES  (press T or 1–8)", "section"),
            ("  1 Hacker   2 Dracula   3 Nord   4 Amber", "detail"),
            ("  5 Monokai  6 Synthwave  7 Ocean  8 Paper", "detail"),
            ("", None),
            ("  press ? or q to close", "dim"),
        ]

        row = 1
        for text, style in lines:
            if row >= H - 1:
                break
            if style == "section":
                self.w(row, 2, text, self.cp("ok") | curses.A_BOLD)
            elif style == "row":
                parts = text.split("  ", 2)
                # parts[0] spaces, parts[1] key, parts[2] desc
                if len(parts) >= 3:
                    key  = "  ".join(parts[:2])
                    desc = parts[2].lstrip()
                    self.w(row, 2, key,  self.cp("warn"))
                    kx   = 2 + len(key) + 2
                    self.w(row, kx, desc, self.cp("muted"))
                else:
                    self.w(row, 2, text, self.cp("muted"))
            elif style == "detail":
                self.w(row, 2, text, self.cp("accent2"))
            elif style == "example":
                self.w(row, 2, text, self.cp("accent"))
            elif style == "cmd":
                self.w(row, 2, text, self.cp("warn"))
            elif style == "dim":
                self.w(row, 2, text, self.cp("dim"))
            row += 1

        self.w(H - 1, 0, "─" * W, self.cp("dim"))

    # ── Input handling ────────────────────────────────────────────────────────

    def run(self):
        while True:
            self.draw()
            try:
                key = self.scr.getch()
            except KeyboardInterrupt:
                break
            if key == -1:
                continue
            if   self.mode == "theme":  self._key_theme(key)
            elif self.mode == "help":   self._key_help(key)
            elif self.mode in ("input", "command", "search"):
                self._key_text(key)
            else:
                self._key_nav(key)

    # ── Theme picker ──────────────────────────────────────────────────────────

    def _key_theme(self, key):
        if key == 27 or key == ord('q'):
            self.mode = "nav"
        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST):
                self._apply_theme(THEME_LIST[i])
                self.mode = "nav"

    def _apply_theme(self, theme_id):
        self.theme_id = theme_id
        _init_colors(theme_id)
        save_data(self.todos, self.sort_by, self.theme_id)
        self.status(f"theme: {THEMES[theme_id]['name']}")

    # ── Help screen ───────────────────────────────────────────────────────────

    def _key_help(self, key):
        if key in (27, ord('?'), ord('q')):
            self.mode = "nav"
        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST):
                self._apply_theme(THEME_LIST[i])

    # ── Text input (input / command / search) ─────────────────────────────────

    def _key_text(self, key):
        if key == 27:                          # Esc
            if self.mode == "search":
                self.search_q = ""
                self.selected = 0
            self.mode       = "nav"
            self.input_buf  = ""
            self.cursor_pos = 0
            self.editing_id = None
            return

        if key in (curses.KEY_ENTER, 10, 13): # Enter
            if   self.mode == "input":   self._commit_input()
            elif self.mode == "command": self._exec_cmd(self.input_buf)
            elif self.mode == "search":  self.mode = "nav"
            self.input_buf  = ""
            self.cursor_pos = 0
            return

        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_buf  = (self.input_buf[:self.cursor_pos - 1]
                                   + self.input_buf[self.cursor_pos:])
                self.cursor_pos -= 1
                if self.mode == "search":
                    self.search_q = self.input_buf
                    self.selected = 0
            return

        if key == curses.KEY_LEFT:
            if self.cursor_pos > 0: self.cursor_pos -= 1
            return
        if key == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.input_buf): self.cursor_pos += 1
            return

        if key == curses.KEY_UP and self.mode == "command":
            if self.cmd_hist_idx < len(self.cmd_hist) - 1:
                self.cmd_hist_idx += 1
                self.input_buf   = self.cmd_hist[self.cmd_hist_idx]
                self.cursor_pos  = len(self.input_buf)
            return
        if key == curses.KEY_DOWN and self.mode == "command":
            if self.cmd_hist_idx > 0:
                self.cmd_hist_idx -= 1
                self.input_buf   = self.cmd_hist[self.cmd_hist_idx]
                self.cursor_pos  = len(self.input_buf)
            elif self.cmd_hist_idx == 0:
                self.cmd_hist_idx = -1
                self.input_buf   = ""
                self.cursor_pos  = 0
            return

        if 32 <= key <= 126:
            ch             = chr(key)
            self.input_buf = (self.input_buf[:self.cursor_pos]
                              + ch
                              + self.input_buf[self.cursor_pos:])
            self.cursor_pos += 1
            if self.mode == "search":
                self.search_q = self.input_buf
                self.selected = 0

    def _commit_input(self):
        v = self.input_buf.strip()
        if v:
            if self.editing_id:
                for t in self.todos:
                    if t["id"] == self.editing_id:
                        t["text"] = v
                        break
                self.status(f'edited: "{v}"')
                self.editing_id = None
            else:
                p = parse_task(v)
                self.todos.insert(0, p)
                self.filter     = "all"
                self.active_tag = None
                self.selected   = 0
                self.scroll     = 0
                meta = []
                if p["priority"] != "med": meta.append(p["priority"])
                if p["tags"]:              meta.append(" ".join(f"#{t}" for t in p["tags"]))
                if p["due"]:
                    ds, _ = fmt_due(p["due"])
                    if ds: meta.append(ds)
                if p["est"]:               meta.append(fmt_est(p["est"]))
                detail = f' [{" · ".join(meta)}]' if meta else ""
                self.status(f'+ "{p["text"]}"{detail}')
            save_data(self.todos, self.sort_by, self.theme_id)
        self.mode = "nav"

    def _exec_cmd(self, raw):
        parts = raw.strip().split(None, 1)
        name  = parts[0].lower() if parts else ""
        args  = parts[1] if len(parts) > 1 else ""

        if name == "sort":
            v = args.lower()
            if v in ("priority", "date", "alpha", "default"):
                self.sort_by = v
                save_data(self.todos, self.sort_by, self.theme_id)
                self.status(f"sort: {v}")
            else:
                self.status("sort: priority | date | alpha | default")

        elif name == "search":
            self.search_q = args
            self.selected = 0
            self.status(f'search: "{args}"' if args else "search cleared")

        elif name == "export":
            lines = []
            for t in self.todos:
                mark  = "x" if t["done"] else " "
                tags  = " ".join(f"#{g}" for g in t.get("tags", []))
                due_s = ""
                if t.get("due"):
                    try:
                        due_s = " due:" + _strftime_day(t["due"])
                    except Exception:
                        pass
                est_s = f' {fmt_est(t["est"])}' if t.get("est") else ""
                lines.append(f'[{mark}] {t["text"]} {tags}{due_s}{est_s}'.strip())
            path = Path.home() / "todo-export.txt"
            try:
                with open(path, "w") as f:
                    f.write("\n".join(lines) + "\n")
                self.status(f"exported {len(self.todos)} tasks → {path}")
            except Exception as e:
                self.status(f"export failed: {e}")

        elif name == "clear":
            if args.lower() == "done":
                n          = sum(1 for t in self.todos if t["done"])
                self.todos = [t for t in self.todos if not t["done"]]
                save_data(self.todos, self.sort_by, self.theme_id)
                self.status(f"cleared {n} completed task{'s' if n != 1 else ''}")
            else:
                self.status("usage: clear done")

        elif name == "filter":
            if args.startswith("#"):
                self.active_tag = args[1:] or None
                self.status(f"tag filter: {args}")
            else:
                self.filter = args or "all"
                self.status(f"filter: {self.filter}")

        elif name in ("help", "?"):
            self.mode = "help"
            self.input_buf = ""
            self.cursor_pos = 0
            return

        elif name == "":
            pass

        else:
            self.status(f'unknown: "{name}" — try :help')

        if raw.strip():
            self.cmd_hist.insert(0, raw.strip())
            self.cmd_hist_idx = -1
        self.mode = "nav"

    # ── Navigation ────────────────────────────────────────────────────────────

    def _key_nav(self, key):
        ft = self.filtered()

        if   key in (curses.KEY_DOWN, ord('j')):
            if self.selected < len(ft) - 1:
                self.selected += 1

        elif key in (curses.KEY_UP, ord('k')):
            if self.selected > 0:
                self.selected -= 1

        elif key == ord('g'):
            self.selected = 0
            self.scroll    = 0

        elif key == ord('G'):
            self.selected = max(0, len(ft) - 1)

        elif key == ord(' '):
            if ft and self.selected < len(ft):
                t = ft[self.selected]
                t["done"] = not t["done"]
                save_data(self.todos, self.sort_by, self.theme_id)
                self.status("✓ marked done" if t["done"] else "↩ marked active")

        elif key in (ord('n'), ord('N')):
            self.mode       = "input"
            self.input_buf  = ""
            self.cursor_pos = 0
            self.editing_id = None

        elif key == ord(':'):
            self.mode           = "command"
            self.input_buf      = ""
            self.cursor_pos     = 0
            self.cmd_hist_idx   = -1

        elif key == ord('/'):
            self.mode       = "search"
            self.input_buf  = self.search_q
            self.cursor_pos = len(self.input_buf)

        elif key in (ord('d'), ord('D'), curses.KEY_DC):
            if ft and self.selected < len(ft):
                tid        = ft[self.selected]["id"]
                self.todos = [t for t in self.todos if t["id"] != tid]
                self.selected = min(self.selected, len(self.filtered()) - 1)
                save_data(self.todos, self.sort_by, self.theme_id)
                self.status("deleted")

        elif key in (ord('e'), ord('E')):
            if ft and self.selected < len(ft):
                t               = ft[self.selected]
                self.editing_id = t["id"]
                self.mode       = "input"
                self.input_buf  = t["text"]
                self.cursor_pos = len(self.input_buf)

        elif key == 9:  # Tab
            fl = ["all", "active", "done", "high"]
            self.filter   = fl[(fl.index(self.filter) + 1) % len(fl)]
            self.selected = 0
            self.scroll   = 0

        elif key == ord('?'):
            self.mode = "help"

        elif key in (ord('T'), ord('t')):
            self.mode = "theme"

        elif key == 27:  # Esc
            if self.search_q:
                self.search_q = ""
                self.selected = 0
            elif self.active_tag:
                self.active_tag = None

        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST):
                self._apply_theme(THEME_LIST[i])

# ── CLI helpers (non-TUI) ─────────────────────────────────────────────────────

def cli_list():
    todos, _, _ = load_data()
    if not todos:
        print("No tasks.  Run: todo add \"your task\"")
        return
    active = [t for t in todos if not t["done"]]
    done   = [t for t in todos if t["done"]]
    order  = {"high": 0, "med": 1, "low": 2}
    active.sort(key=lambda t: order.get(t["priority"], 1))
    SYM = {"high": "●", "med": "◐", "low": "○"}
    COL = {"high": "\033[31m", "med": "\033[33m", "low": "\033[32m"}
    RST = "\033[0m"; DIM = "\033[2m"; BLU = "\033[34m"
    print(f"\n  \033[1mTODO\033[0m  {len(active)} active  {DIM}{len(done)} done{RST}\n")
    for t in active:
        sym  = SYM.get(t["priority"], "◐")
        col  = COL.get(t["priority"], "")
        tags = "  ".join(f"{BLU}#{g}{RST}" for g in t.get("tags", []))
        ds, _= fmt_due(t.get("due"))
        due  = f"{DIM}{ds}{RST}" if ds else ""
        es   = fmt_est(t.get("est"))
        est  = f"{DIM}{es}{RST}" if es else ""
        extra = "  ".join(x for x in [tags, due, est] if x)
        print(f"  {col}{sym}{RST}  [ ]  {t['text']}" + (f"  {extra}" if extra else ""))
    if done:
        print(f"\n  {DIM}── {len(done)} completed ──{RST}")
        for t in done[:5]:
            tags = "  ".join(f"#{g}" for g in t.get("tags", []))
            print(f"  {DIM}●  [✓]  {t['text']}" + (f"  {tags}" if tags else "") + RST)
        if len(done) > 5:
            print(f"  {DIM}  … and {len(done)-5} more{RST}")
    print()

def cli_add(text):
    if not text.strip():
        print('Usage: todo add "fix auth bug !high #work tomorrow ~2h"')
        return
    todos, sort_by, theme = load_data()
    task = parse_task(text)
    todos.insert(0, task)
    save_data(todos, sort_by, theme)
    meta = []
    if task["priority"] != "med": meta.append(task["priority"])
    if task["tags"]:               meta.append(" ".join(f"#{g}" for g in task["tags"]))
    if task["due"]:
        ds, _ = fmt_due(task["due"])
        if ds: meta.append(ds)
    if task["est"]:                meta.append(fmt_est(task["est"]))
    detail = f'  [{" · ".join(meta)}]' if meta else ""
    print(f'  \033[32m+\033[0m  "{task["text"]}"{detail}')

def cli_help():
    print("""
  Usage
    todo               open the TUI app
    todo open          open the TUI app
    todo list          print tasks (no TUI)
    todo add "text"    add a task from the shell
    todo help          show this message

  NLP syntax for add:
    !high !med !low        priority
    #tag                   attach a tag
    today tomorrow friday  due date
    next week              7 days from now
    ~2h ~30m               time estimate

  Example:
    todo add "fix auth bug !high #work tomorrow ~2h"

  Data: ~/.local/share/terminal-todo/todos.json
""")

# ── Entry point ───────────────────────────────────────────────────────────────

def main(stdscr):
    App(stdscr).run()

def _ensure_curses():
    """On Windows, curses requires the windows-curses package."""
    if not IS_WINDOWS:
        return True
    try:
        import curses as _c  # noqa: already imported, just test
        return True
    except ImportError:
        pass
    print("\n  windows-curses is required on Windows.")
    print("  Install it with:\n")
    print("    pip install windows-curses\n")
    answer = input("  Install now? [Y/n] ").strip().lower()
    if answer in ("", "y", "yes"):
        import subprocess
        ret = subprocess.call([sys.executable, "-m", "pip", "install", "windows-curses"])
        if ret == 0:
            print("  Installed! Please run `todo` again.\n")
        else:
            print("  Install failed. Run manually: pip install windows-curses\n")
    return False

def launch_tui():
    if not _ensure_curses():
        return
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    argv = sys.argv[1:]
    cmd  = argv[0].lower() if argv else "open"

    if cmd in ("open", ""):
        launch_tui()
    elif cmd == "list":
        cli_list()
    elif cmd == "add":
        cli_add(" ".join(argv[1:]))
    elif cmd in ("help", "--help", "-h"):
        cli_help()
    else:
        # Bare args treated as implicit add: todo "fix bug !high"
        cli_add(" ".join(argv))
