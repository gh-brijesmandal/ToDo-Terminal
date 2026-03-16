#!/usr/bin/env python3
"""
Terminal Todo v5 — premium TUI as close to the HTML version as curses allows.
Two-row task cards · left accent bars · live NLP preview · 8 themes · flash animations

Usage:   python3 todo.py
         todo              (after install.sh / install.ps1)
         todo add "task !high #work tomorrow ~2h"
         todo list
Data:    ~/.local/share/terminal-todo/todos.json
"""

import curses
import json
import platform
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"

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
    if diff < 0:  return f"{-diff}d overdue", "danger"
    if diff == 0: return "today",    "ok"
    if diff == 1: return "tomorrow", "warn"
    if diff < 7:  return datetime.fromtimestamp(ts / 1000).strftime("%a"), "warn"
    dt = datetime.fromtimestamp(ts / 1000)
    return f"{dt.strftime('%b')} {dt.day}", "muted"

def fmt_est(mins):
    if not mins: return None
    if mins >= 60:
        h = mins / 60
        return f"~{h:.0f}h" if h == int(h) else f"~{h:.1f}h"
    return f"~{mins}m"

def parse_task(raw):
    text = raw; priority = "med"; tags = []; due = None; est = None
    text, n = re.subn(r'!(high|h)\b', '', text, flags=re.I)
    if n: priority = "high"
    text, n = re.subn(r'!(low|l)\b', '', text, flags=re.I)
    if n: priority = "low"
    text = re.sub(r'!(med|medium|m)\b', '', text, flags=re.I)
    tags = [t.lower() for t in re.findall(r'#(\w+)', text)]
    text = re.sub(r'#\w+', '', text)
    def _est(m):
        nonlocal est
        n2, u = m.group(1), m.group(2).lower()
        est = round(float(n2) * 60) if u == 'h' else int(float(n2))
        return ''
    text = re.sub(r'~(\d+(?:\.\d+)?)(h|m)\b', _est, text, flags=re.I)
    tod  = today_ms()
    def _due(ms):
        nonlocal due; due = ms; return ''
    text = re.sub(r'\btoday\b',       lambda m: _due(tod),               text, flags=re.I)
    text = re.sub(r'\btomorrow\b',    lambda m: _due(tod + 86_400_000),  text, flags=re.I)
    text = re.sub(r'\bnext\s*week\b', lambda m: _due(tod+7*86_400_000),  text, flags=re.I)
    curr = (datetime.now().weekday() + 1) % 7
    for i, day in enumerate(['sun','mon','tue','wed','thu','fri','sat']):
        def _day(m, i=i):
            diff = ((i - curr) % 7) or 7
            return _due(tod + diff * 86_400_000)
        text = re.sub(rf'\b{day}(?:day)?\b', _day, text, flags=re.I)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return {"id": new_id(), "text": text or raw, "priority": priority,
            "tags": tags, "due": due, "est": est, "done": False,
            "ca": int(time.time() * 1000)}

def live_parse(raw):
    """Return list of (label, role) NLP token chips from partial input."""
    tokens = []
    if   re.search(r'!(high|h)\b', raw, re.I): tokens.append(("HIGH",  "danger"))
    elif re.search(r'!(low|l)\b',  raw, re.I): tokens.append(("LOW",   "ok"))
    elif re.search(r'!(med|m)\b',  raw, re.I): tokens.append(("MED",   "warn"))
    for tag in re.findall(r'#(\w+)', raw):
        tokens.append((f"#{tag}", "info"))
    m = re.search(r'~(\d+(?:\.\d+)?)(h|m)\b', raw, re.I)
    if m:
        n2, u = m.group(1), m.group(2).lower()
        mins  = round(float(n2)*60) if u=='h' else int(float(n2))
        tokens.append((fmt_est(mins), "muted"))
    if   re.search(r'\btoday\b',      raw, re.I): tokens.append(("today",    "ok"))
    elif re.search(r'\btomorrow\b',   raw, re.I): tokens.append(("tomorrow", "warn"))
    elif re.search(r'\bnext\s*week\b',raw, re.I): tokens.append(("next wk",  "muted"))
    else:
        for day in ['sun','mon','tue','wed','thu','fri','sat']:
            if re.search(rf'\b{day}(?:day)?\b', raw, re.I):
                tokens.append((day, "warn")); break
    return tokens

# ── Themes ────────────────────────────────────────────────────────────────────
# Each theme defines colour roles mapped to 256-colour palette indices.
# bg  = main background
# bg2 = titlebar / statusbar background
# sel = selected row background
# Roles: fg fg2 fg3 fg4 ac ac2 ok warn danger info muted
#        pri_h pri_m pri_l border

THEMES = {
    "hacker": {
        "name": "Hacker",
        "bg":232,"bg2":233,"sel":22,
        "fg":83,"fg2":34,"fg3":22,"fg4":236,
        "ac":46,"ac2":34,
        "ok":83,"warn":214,"danger":196,"info":75,"muted":240,
        "pri_h":196,"pri_m":214,"pri_l":83,"border":236,
    },
    "obsidian": {
        "name": "Obsidian",
        "bg":232,"bg2":233,"sel":54,
        "fg":189,"fg2":61,"fg3":238,"fg4":236,
        "ac":141,"ac2":99,
        "ok":114,"warn":221,"danger":204,"info":75,"muted":240,
        "pri_h":204,"pri_m":221,"pri_l":114,"border":237,
    },
    "arctic": {
        "name": "Arctic",
        "bg":234,"bg2":235,"sel":24,
        "fg":153,"fg2":68,"fg3":238,"fg4":236,
        "ac":117,"ac2":75,
        "ok":114,"warn":221,"danger":210,"info":141,"muted":240,
        "pri_h":210,"pri_m":221,"pri_l":114,"border":237,
    },
    "ember": {
        "name": "Ember",
        "bg":232,"bg2":52,"sel":88,
        "fg":229,"fg2":136,"fg3":94,"fg4":236,
        "ac":214,"ac2":172,
        "ok":148,"warn":220,"danger":196,"info":75,"muted":240,
        "pri_h":196,"pri_m":220,"pri_l":148,"border":237,
    },
    "sakura": {
        "name": "Sakura",
        "bg":232,"bg2":53,"sel":90,
        "fg":219,"fg2":97,"fg3":238,"fg4":236,
        "ac":213,"ac2":170,
        "ok":122,"warn":227,"danger":204,"info":117,"muted":240,
        "pri_h":204,"pri_m":227,"pri_l":122,"border":237,
    },
    "steel": {
        "name": "Steel",
        "bg":233,"bg2":234,"sel":24,
        "fg":152,"fg2":67,"fg3":238,"fg4":236,
        "ac":74,"ac2":68,
        "ok":78,"warn":179,"danger":167,"info":104,"muted":240,
        "pri_h":167,"pri_m":179,"pri_l":78,"border":237,
    },
    "void": {
        "name": "Void",
        "bg":232,"bg2":233,"sel":234,
        "fg":255,"fg2":245,"fg3":240,"fg4":236,
        "ac":255,"ac2":250,
        "ok":120,"warn":214,"danger":196,"info":117,"muted":240,
        "pri_h":196,"pri_m":214,"pri_l":120,"border":237,
    },
    "rose": {
        "name": "Rose",
        "bg":231,"bg2":255,"sel":224,
        "fg":52,"fg2":131,"fg3":181,"fg4":254,
        "ac":124,"ac2":88,
        "ok":28,"warn":130,"danger":124,"info":25,"muted":245,
        "pri_h":124,"pri_m":130,"pri_l":28,"border":253,
    },
}
THEME_LIST = list(THEMES.keys())

# ── Colour pair cache ─────────────────────────────────────────────────────────

_PAIRS: dict = {}

def _pair(fg: int, bg: int) -> int:
    key = (fg, bg)
    if key not in _PAIRS:
        pid = len(_PAIRS) + 1
        if pid >= curses.COLOR_PAIRS:
            pid = (pid % (curses.COLOR_PAIRS - 1)) + 1
        curses.init_pair(pid, fg, bg)
        _PAIRS[key] = pid
    return _PAIRS[key]

def init_theme(tid: str):
    _PAIRS.clear()
    t = THEMES[tid]
    for role in ("fg","fg2","fg3","fg4","ac","ac2","ok","warn",
                 "danger","info","muted","border","pri_h","pri_m","pri_l"):
        _pair(t[role], t["bg"])
        _pair(t[role], t["sel"])
        _pair(t[role], t["bg2"])

# Helper: colour-pair attribute for a role on a given background surface
def A(tid, role, surf="bg"):
    t = THEMES[tid]
    bg = {"bg": t["bg"], "sel": t["sel"], "bg2": t["bg2"]}.get(surf, t["bg"])
    return curses.color_pair(_pair(t[role], bg))

# ── Priority glyphs ───────────────────────────────────────────────────────────

PRI_GLYPH = {"high": ("▲", "pri_h"), "med": ("◆", "pri_m"), "low": ("▽", "pri_l")}

# ── App ───────────────────────────────────────────────────────────────────────

TASK_HEIGHT = 2   # rows per task card

class App:
    FLASH_FRAMES = 6

    def __init__(self, scr):
        self.scr = scr
        self.todos, self.sort_by, self.theme_id = load_data()
        if not self.todos:
            self._seed()

        self.selected     = 0
        self.scroll       = 0
        self.filter       = "all"
        self.active_tag   = None
        self.search_q     = ""
        self.mode         = "nav"
        self.input_buf    = ""
        self.cursor_pos   = 0
        self.editing_id   = None
        self.cmd_hist     = []
        self.cmd_hist_idx = -1
        self.status_msg   = "ready — press ? for help"
        self.status_role  = "muted"
        self.status_until = time.time() + 5
        self.flash_id     = None
        self.flash_count  = 0

        self._setup()

    def _seed(self):
        seeds = [
            "welcome — press ? for the full guide !high",
            "review pull request for auth module !high #work today ~1h",
            "fix payment gateway bug !high #work #backend ~2h",
            "write unit tests for api !med #work ~90m",
            "update dependencies #work #devops next week ~30m",
            "buy groceries !low #personal ~30m",
        ]
        self.todos = [parse_task(s) for s in seeds]
        done = parse_task("read system design chapter 4 #learning ~45m")
        done["done"] = True
        self.todos.append(done)
        save_data(self.todos, self.sort_by, self.theme_id)

    def _setup(self):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        self.scr.keypad(True)
        self.scr.timeout(60)
        init_theme(self.theme_id)

    def _apply_theme(self, tid):
        self.theme_id = tid
        init_theme(tid)
        save_data(self.todos, self.sort_by, self.theme_id)
        self.set_status(f"theme  {THEMES[tid]['name']}", "ac")

    # ── Data ──────────────────────────────────────────────────────────────────

    def filtered(self):
        ft = list(self.todos)
        if self.search_q:
            q  = self.search_q.lower()
            ft = [t for t in ft if q in t["text"].lower()
                  or any(q in g for g in t.get("tags", []))]
        if   self.filter == "active": ft = [t for t in ft if not t["done"]]
        elif self.filter == "done":   ft = [t for t in ft if t["done"]]
        elif self.filter == "high":   ft = [t for t in ft if t["priority"] == "high"]
        if self.active_tag:
            ft = [t for t in ft if self.active_tag in t.get("tags", [])]
        o = {"high": 0, "med": 1, "low": 2}
        if   self.sort_by == "priority": ft.sort(key=lambda t: o.get(t["priority"], 1))
        elif self.sort_by == "date":     ft.sort(key=lambda t: (t.get("due") is None, t.get("due") or 0))
        elif self.sort_by == "alpha":    ft.sort(key=lambda t: t["text"].lower())
        return ft

    def counts(self):
        return {
            "all":    len(self.todos),
            "active": sum(1 for t in self.todos if not t["done"]),
            "done":   sum(1 for t in self.todos if t["done"]),
            "high":   sum(1 for t in self.todos if t["priority"]=="high" and not t["done"]),
        }

    def chips_for(self, todo):
        """Build chip list: [(label, role), ...]"""
        chips = []
        lbl  = {"high":"HIGH","med":"MED","low":"LOW"}[todo["priority"]]
        role = {"high":"pri_h","med":"pri_m","low":"pri_l"}[todo["priority"]]
        chips.append((lbl, role))
        for tag in todo.get("tags", [])[:3]:
            chips.append((f"#{tag}", "info"))
        ds, dr = fmt_due(todo.get("due"))
        if ds: chips.append((ds, dr or "muted"))
        es = fmt_est(todo.get("est"))
        if es: chips.append((es, "muted"))
        return chips

    # ── Status ────────────────────────────────────────────────────────────────

    def set_status(self, msg, role="muted", secs=2.5):
        self.status_msg   = msg
        self.status_role  = role
        self.status_until = time.time() + secs

    # ── Safe drawing helpers ──────────────────────────────────────────────────

    def w(self, y, x, text, attr=0, maxw=None):
        try:
            H, W = self.scr.getmaxyx()
            if y < 0 or y >= H - 1 or x < 0 or x >= W: return
            avail = (W if maxw is None else maxw) - x
            if avail <= 0: return
            self.scr.addstr(y, x, str(text)[:avail], attr)
        except curses.error:
            pass

    def fill(self, y, attr=0):
        try:
            _, W = self.scr.getmaxyx()
            self.scr.addstr(y, 0, " " * W, attr)
        except curses.error:
            pass

    def hline(self, y, char="─", role="border"):
        try:
            _, W = self.scr.getmaxyx()
            self.scr.addstr(y, 0, char * W, A(self.theme_id, role))
        except curses.error:
            pass

    # ── Main draw dispatcher ──────────────────────────────────────────────────

    def draw(self):
        self.scr.erase()
        H, W = self.scr.getmaxyx()
        try:
            if   self.mode == "help":  self._draw_help(H, W)
            elif self.mode == "theme": self._draw_theme(H, W)
            else:                      self._draw_main(H, W)
            self.scr.refresh()
        except curses.error:
            pass

    # ── Main screen ───────────────────────────────────────────────────────────

    def _draw_main(self, H, W):
        th = self.theme_id
        ft = self.filtered()
        if self.selected >= len(ft):
            self.selected = max(0, len(ft) - 1)

        # ── Row 0  titlebar ───────────────────────────────────────────────
        self.fill(0, A(th, "fg3", "bg2"))
        done_n = sum(1 for t in self.todos if t["done"])
        tot    = len(self.todos)
        bw     = 18
        filled = int(bw * done_n / tot) if tot else 0
        bar    = "█" * filled + "░" * (bw - filled)
        prog   = f"{bar}  {done_n}/{tot}"
        title  = f" TODO  v5"
        rlbl   = f"[T] {THEMES[th]['name']} "
        self.w(0, 1,              title, A(th, "ac",  "bg2") | curses.A_BOLD)
        self.w(0, (W-len(prog))//2, prog, A(th, "ok",  "bg2"))
        self.w(0, W-len(rlbl),    rlbl,  A(th, "fg3", "bg2"))

        # ── Row 1  meta strip ─────────────────────────────────────────────
        meta = f" sort:{self.sort_by}"
        if self.active_tag: meta += f"  #{self.active_tag}"
        if self.search_q:   meta += f"  /{self.search_q}"
        self.w(1, 1, "TODO", A(th, "ac") | curses.A_BOLD)
        self.w(1, 6, meta,   A(th, "fg3"))

        # ── Row 2  divider ────────────────────────────────────────────────
        self.hline(2)

        # ── Row 3  tab bar ────────────────────────────────────────────────
        c = self.counts()
        tabs = [("all","all","ALL"), ("active","active","ACTIVE"),
                ("done","done","DONE"), ("high","high","▲ HIGH")]
        x = 2
        for fid, key, lbl in tabs:
            cnt   = c[key]
            label = f" {lbl} {cnt} "
            if fid == self.filter:
                self.w(3, x, label, A(th, "ac") | curses.A_REVERSE | curses.A_BOLD)
            else:
                self.w(3, x, label, A(th, "fg3"))
            x += len(label) + 1

        # tag pills
        x += 2
        all_tags = list(dict.fromkeys(g for t in self.todos for g in t.get("tags",[])))
        for tag in all_tags:
            pill = f"#{tag}"
            if x + len(pill) >= W - 2: break
            if tag == self.active_tag:
                self.w(3, x, pill, A(th, "ac2") | curses.A_REVERSE)
            else:
                self.w(3, x, pill, A(th, "fg3"))
            x += len(pill) + 2

        # ── Row 4  divider ────────────────────────────────────────────────
        self.hline(4)

        # ── Rows 5…H-6  task list ─────────────────────────────────────────
        list_top = 5
        list_bot = H - 6
        list_h   = max(0, list_bot - list_top)
        visible  = list_h // TASK_HEIGHT  # how many tasks fit

        if self.selected < self.scroll:
            self.scroll = self.selected
        if self.selected >= self.scroll + visible:
            self.scroll = self.selected - visible + 1

        if not ft:
            mid = (list_top + list_bot) // 2
            msg = "  no tasks  —  press n to add  "
            self.w(mid, (W-len(msg))//2, msg, A(th,"fg4") | curses.A_REVERSE)
        else:
            for slot in range(visible):
                idx  = self.scroll + slot
                if idx >= len(ft): break
                todo = ft[idx]
                row  = list_top + slot * TASK_HEIGHT
                self._draw_task_card(row, todo, idx, W, th)

        # ── H-5  divider ──────────────────────────────────────────────────
        self.hline(H - 5)

        # ── H-4  command / input line ─────────────────────────────────────
        self._draw_input_line(H - 4, W, th)

        # ── H-3  NLP preview / hint row ───────────────────────────────────
        self._draw_preview_row(H - 3, W, th)

        # ── H-2  divider ──────────────────────────────────────────────────
        self.hline(H - 2)

        # ── H-1  status bar ───────────────────────────────────────────────
        self._draw_statusbar(H - 1, W, th, ft)

    # ── Task card  (2 rows) ───────────────────────────────────────────────────

    def _draw_task_card(self, row, todo, idx, W, th):
        sel     = (idx == self.selected)
        flashing = (todo["id"] == self.flash_id and self.flash_count % 2 == 0)

        surf = "sel" if sel else "bg"

        # Fill both rows with background
        if flashing:
            self.fill(row,   A(th, "ac")  | curses.A_REVERSE)
            self.fill(row+1, A(th, "ac2") | curses.A_REVERSE)
        elif sel:
            self.fill(row,   A(th, "fg", "sel"))
            self.fill(row+1, A(th, "fg", "sel"))

        # ── Left accent bar ───────────────────────────────────────────────
        if flashing:
            bar_attr = A(th, "ac") | curses.A_REVERSE
        elif sel:
            bar_attr = A(th, "ac", "sel") | curses.A_BOLD
        elif todo["priority"] == "high" and not todo["done"]:
            bar_attr = A(th, "pri_h") | curses.A_BOLD
        elif todo["priority"] == "low":
            bar_attr = A(th, "pri_l")
        else:
            bar_attr = A(th, "border")

        self.w(row,   0, "▌", bar_attr)
        self.w(row+1, 0, "▌", bar_attr)

        x = 2

        # ── Selection arrow ───────────────────────────────────────────────
        if sel:
            self.w(row, x, "›", A(th, "ac", surf) | curses.A_BOLD)
        else:
            self.w(row, x, " ")
        x += 2

        # ── Priority glyph ────────────────────────────────────────────────
        glyph, grole = PRI_GLYPH.get(todo["priority"], ("◆","pri_m"))
        ga = A(th, grole, surf) | curses.A_BOLD
        if todo["done"]: ga = A(th, "fg3", surf) | curses.A_DIM
        if flashing:     ga = A(th, "ac") | curses.A_REVERSE | curses.A_BOLD
        self.w(row, x, glyph, ga)
        x += 2

        # ── Checkbox ──────────────────────────────────────────────────────
        cb_sym  = "✓" if todo["done"] else " "
        cb_role = "ok" if todo["done"] else "fg3"
        cb_attr = A(th, cb_role, surf)
        if flashing: cb_attr = A(th, "ac") | curses.A_REVERSE
        self.w(row, x, f"[{cb_sym}]", cb_attr)
        x += 5

        TEXT_X = x   # remember indent for chips row

        # ── Task text ─────────────────────────────────────────────────────
        max_txt  = W - x - 2
        txt      = todo["text"]
        if len(txt) > max_txt > 3:
            txt = txt[:max_txt - 1] + "…"

        if todo["done"]:
            ta = A(th, "fg3", surf) | curses.A_DIM
        elif flashing:
            ta = A(th, "ac") | curses.A_REVERSE | curses.A_BOLD
        else:
            ta = A(th, "fg", surf)

        # Search highlight
        if self.search_q and not todo["done"]:
            q  = self.search_q.lower()
            tl = todo["text"].lower()
            mi = tl.find(q)
            if 0 <= mi < len(txt):
                self.w(row, x,          txt[:mi],            ta)
                self.w(row, x+mi,       txt[mi:mi+len(q)],   A(th,"ac")|curses.A_REVERSE|curses.A_BOLD)
                self.w(row, x+mi+len(q),txt[mi+len(q):],     ta)
            else:
                self.w(row, x, txt, ta)
        else:
            self.w(row, x, txt, ta)

        # ── Chips row (row+1) ─────────────────────────────────────────────
        cx = TEXT_X
        for chip_lbl, chip_role in self.chips_for(todo):
            rendered = f"[{chip_lbl}]"
            if cx + len(rendered) >= W - 1: break
            ca = A(th, chip_role, surf)
            if todo["done"]: ca = A(th, "fg3", surf) | curses.A_DIM
            if flashing:     ca = A(th, "ac")  | curses.A_REVERSE
            self.w(row+1, cx, rendered, ca)
            cx += len(rendered) + 1

    # ── Input / preview rows ──────────────────────────────────────────────────

    def _draw_input_line(self, y, W, th):
        if self.mode in ("input", "command", "search", "edit_inline"):
            pfx_role = {"input":"ok","command":"warn","search":"ac","edit_inline":"ac2"}
            role = pfx_role.get(self.mode, "fg3")
            sym  = {"input":">","command":":","search":"/","edit_inline":"~"}
            self.w(y, 1, sym.get(self.mode,"-") + " ", A(th, role))
            self.w(y, 3, self.input_buf, A(th, role))
            # Block cursor
            cx = 3 + self.cursor_pos
            ch = self.input_buf[self.cursor_pos] if self.cursor_pos < len(self.input_buf) else " "
            try:
                if cx < W - 1:
                    self.scr.addstr(y, cx, ch, A(th, role) | curses.A_REVERSE)
            except curses.error:
                pass
        else:
            hint = " n new   : cmd   / search   ? help   T theme   1-8 quick theme"
            self.w(y, 0, "—", A(th, "border"))
            self.w(y, 1, hint, A(th, "fg4"))

    def _draw_preview_row(self, y, W, th):
        if self.mode == "input" and self.input_buf.strip():
            tokens = live_parse(self.input_buf)
            if tokens:
                self.w(y, 3, "parsed ", A(th, "fg3"))
                x = 10
                self.w(y, x-1, "› ", A(th, "ac") | curses.A_BOLD)
                for lbl, role in tokens:
                    rendered = f"[{lbl}]"
                    if x + len(rendered) >= W - 1: break
                    self.w(y, x, rendered, A(th, role) | curses.A_BOLD)
                    x += len(rendered) + 1
            else:
                self.w(y, 3, "type !high #tag today ~2h to enrich your task", A(th, "fg4"))
        else:
            hints = " spc done   e edit   d del   ↑↓ / jk nav   g G top/bot   tab filter"
            self.w(y, 0, "—", A(th, "border"))
            self.w(y, 1, hints, A(th, "fg4"))

    def _draw_statusbar(self, y, W, th, ft):
        self.fill(y, A(th, "fg3", "bg2"))
        if time.time() < self.status_until:
            self.w(y, 2, self.status_msg, A(th, self.status_role, "bg2") | curses.A_BOLD)
        else:
            done = sum(1 for t in self.todos if t["done"])
            info = f"{len(ft)} shown   {done}/{len(self.todos)} done   {THEMES[th]['name']}"
            self.w(y, 2, info, A(th, "fg3", "bg2"))

    # ── Theme picker screen ───────────────────────────────────────────────────

    def _draw_theme(self, H, W):
        th = self.theme_id
        self.fill(0, A(th, "fg3", "bg2"))
        title = " SELECT THEME "
        self.w(0, (W-len(title))//2, title, A(th, "ac", "bg2") | curses.A_BOLD)
        self.w(0, W-12, " esc close ", A(th, "fg3", "bg2"))
        self.hline(1)
        self.w(2, 3, "press 1–8 to apply, or click a row", A(th, "fg3"))
        self.hline(3)

        for i, (tid, td) in enumerate(THEMES.items()):
            row    = 5 + i * 2
            active = (tid == th)
            g_h    = A(th, "pri_h") | (curses.A_REVERSE if active else 0)
            g_m    = A(th, "pri_m") | (curses.A_REVERSE if active else 0)
            g_l    = A(th, "pri_l") | (curses.A_REVERSE if active else 0)
            lbl    = f"  {i+1}.  {td['name']}"
            attr   = (A(th,"ac") | curses.A_BOLD) if active else A(th,"fg")
            prefix = "  ▸  " if active else "     "
            self.w(row, 2, prefix, A(th,"ac") if active else A(th,"fg4"))
            self.w(row, 2+len(prefix), f"{i+1}.  {td['name']:<14}", attr)
            # swatch glyphs
            sx = 2 + len(prefix) + 18
            self.w(row, sx,   "▲", g_h)
            self.w(row, sx+2, "◆", g_m)
            self.w(row, sx+4, "▽", g_l)
            if active:
                self.w(row, sx+7, "← current", A(th,"ok"))

        bot = 5 + len(THEMES)*2 + 1
        self.hline(min(bot, H-2))

    # ── Help screen ───────────────────────────────────────────────────────────

    def _draw_help(self, H, W):
        th = self.theme_id
        self.fill(0, A(th, "fg3", "bg2"))
        title = " ── HELP ── "
        self.w(0, (W-len(title))//2, title, A(th,"ac","bg2") | curses.A_BOLD)
        self.w(0, W-12, " esc close ", A(th,"fg3","bg2"))
        self.hline(1)

        sections = [
            ("NAVIGATION", [
                ("↑/k   ↓/j",            "move between tasks"),
                ("g / G",                 "jump to top / bottom"),
                ("Tab",                   "cycle  ALL → ACTIVE → DONE → HIGH"),
                ("Esc",                   "clear search or tag filter"),
            ]),
            ("TASK ACTIONS", [
                ("n",                     "new task  (NLP input — tokens shown live)"),
                ("Space",                 "toggle done → moves to done tab with flash"),
                ("e",                     "edit selected task text inline"),
                ("d / Delete",            "delete selected task"),
                (":",                     "command bar  (↑↓ recalls history)"),
                ("/",                     "live search with highlighted matches"),
                ("T  or  1–8",            "theme picker  /  quick-switch theme"),
                ("?",                     "this help screen"),
            ]),
            ("NLP INPUT TOKENS — press n then type freely", [
                ("!high  !med  !low",     "priority flag  →  chips shown live as you type"),
                ("#tagname",              "attach tag  →  click pill in tab bar to filter"),
                ("today  tomorrow",       "set due date"),
                ("monday … sunday",       "due next occurrence of that day"),
                ("next week",             "due in 7 days"),
                ("~2h  ~30m  ~1.5h",      "time estimate"),
                ("example:",              "fix auth bug !high #work tomorrow ~2h"),
            ]),
            ("COMMAND BAR — press :", [
                (":sort priority",        "high → med → low"),
                (":sort date",            "soonest due first"),
                (":sort alpha",           "alphabetical"),
                (":sort default",         "restore original order"),
                (":search <query>",       "keyword filter (text + tags)"),
                (":filter #tag",          "filter by tag"),
                (":clear done",           "delete all completed tasks"),
                (":export",              "write all tasks → ~/todo-export.txt"),
            ]),
        ]

        row = 2
        for sec_title, items in sections:
            if row >= H - 3: break
            self.w(row, 2, sec_title, A(th,"ok") | curses.A_BOLD)
            row += 1
            for key, desc in items:
                if row >= H - 3: break
                col2 = 36
                self.w(row, 4,    key,  A(th,"warn"))
                self.w(row, col2, desc, A(th,"fg2"))
                row += 1
            row += 1

        self.hline(H - 2)
        self.w(H-1, 2, "? or q or esc to close", A(th,"fg4"))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            self.draw()
            if self.flash_id:
                self.flash_count += 1
                if self.flash_count >= self.FLASH_FRAMES:
                    self.flash_id = None; self.flash_count = 0
            try:
                key = self.scr.getch()
            except KeyboardInterrupt:
                break
            if key == -1: continue
            if   self.mode == "theme": self._key_theme(key)
            elif self.mode == "help":  self._key_help(key)
            elif self.mode in ("input","command","search","edit_inline"):
                self._key_text(key)
            else:
                self._key_nav(key)

    # ── Key: theme picker ─────────────────────────────────────────────────────

    def _key_theme(self, key):
        if key in (27, ord('q')): self.mode = "nav"
        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST):
                self._apply_theme(THEME_LIST[i]); self.mode = "nav"

    def _key_help(self, key):
        if key in (27, ord('?'), ord('q')): self.mode = "nav"
        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST): self._apply_theme(THEME_LIST[i])

    # ── Key: text input modes ─────────────────────────────────────────────────

    def _key_text(self, key):
        if key == 27:
            if self.mode == "search": self.search_q = ""; self.selected = 0
            self.mode = "nav"; self.input_buf = ""; self.cursor_pos = 0
            self.editing_id = None; return

        if key in (curses.KEY_ENTER, 10, 13):
            if   self.mode == "input":       self._commit_input()
            elif self.mode == "command":     self._exec_cmd(self.input_buf)
            elif self.mode == "search":      self.mode = "nav"
            elif self.mode == "edit_inline": self._commit_edit()
            self.input_buf = ""; self.cursor_pos = 0; return

        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_buf  = (self.input_buf[:self.cursor_pos-1]
                                   + self.input_buf[self.cursor_pos:])
                self.cursor_pos -= 1
                if self.mode == "search": self.search_q = self.input_buf; self.selected = 0
            return

        if key == curses.KEY_LEFT:
            if self.cursor_pos > 0: self.cursor_pos -= 1; return
        if key == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.input_buf): self.cursor_pos += 1; return
        if key == curses.KEY_HOME: self.cursor_pos = 0; return
        if key == curses.KEY_END:  self.cursor_pos = len(self.input_buf); return

        if key == curses.KEY_UP and self.mode == "command":
            if self.cmd_hist_idx < len(self.cmd_hist)-1:
                self.cmd_hist_idx += 1
                self.input_buf    = self.cmd_hist[self.cmd_hist_idx]
                self.cursor_pos   = len(self.input_buf)
            return
        if key == curses.KEY_DOWN and self.mode == "command":
            if self.cmd_hist_idx > 0:
                self.cmd_hist_idx -= 1
                self.input_buf    = self.cmd_hist[self.cmd_hist_idx]
                self.cursor_pos   = len(self.input_buf)
            elif self.cmd_hist_idx == 0:
                self.cmd_hist_idx = -1; self.input_buf = ""; self.cursor_pos = 0
            return

        if 32 <= key <= 126:
            ch = chr(key)
            self.input_buf  = self.input_buf[:self.cursor_pos] + ch + self.input_buf[self.cursor_pos:]
            self.cursor_pos += 1
            if self.mode == "search": self.search_q = self.input_buf; self.selected = 0

    def _commit_input(self):
        v = self.input_buf.strip()
        if v:
            p = parse_task(v)
            self.todos.insert(0, p)
            self.filter = "all"; self.active_tag = None
            self.selected = 0; self.scroll = 0
            meta = []
            if p["priority"] != "med": meta.append(p["priority"])
            if p["tags"]:              meta.append(" ".join(f"#{g}" for g in p["tags"]))
            if p["due"]:
                ds, _ = fmt_due(p["due"])
                if ds: meta.append(ds)
            if p["est"]:               meta.append(fmt_est(p["est"]))
            detail = f'  [{" · ".join(meta)}]' if meta else ""
            self.set_status(f'+ "{p["text"]}"{detail}', "ok")
            self.flash_id = p["id"]; self.flash_count = 0
            save_data(self.todos, self.sort_by, self.theme_id)
        self.mode = "nav"

    def _commit_edit(self):
        v = self.input_buf.strip()
        if v and self.editing_id:
            for t in self.todos:
                if t["id"] == self.editing_id:
                    t["text"] = v; break
            self.set_status(f'edited: "{v}"', "ok")
            save_data(self.todos, self.sort_by, self.theme_id)
        self.editing_id = None; self.mode = "nav"

    def _exec_cmd(self, raw):
        parts = raw.strip().split(None, 1)
        name  = parts[0].lower() if parts else ""
        args  = parts[1] if len(parts) > 1 else ""

        if name == "sort":
            v = args.lower()
            if v in ("priority","date","alpha","default"):
                self.sort_by = v
                save_data(self.todos, self.sort_by, self.theme_id)
                self.set_status(f"sort: {v}", "ac")
            else:
                self.set_status("sort: priority | date | alpha | default", "warn")

        elif name == "search":
            self.search_q = args; self.selected = 0
            self.set_status(f'search: "{args}"' if args else "search cleared", "ac")

        elif name == "export":
            lines = []
            for t in self.todos:
                mark  = "x" if t["done"] else " "
                tags  = " ".join(f"#{g}" for g in t.get("tags",[]))
                due_s = ""
                if t.get("due"):
                    dt    = datetime.fromtimestamp(t["due"]/1000)
                    due_s = f" due:{dt.strftime('%b')} {dt.day}"
                est_s = f' {fmt_est(t["est"])}' if t.get("est") else ""
                lines.append(f'[{mark}] {t["text"]} {tags}{due_s}{est_s}'.strip())
            path = Path.home() / "todo-export.txt"
            try:
                with open(path, "w") as f:
                    f.write("\n".join(lines)+"\n")
                self.set_status(f"exported {len(self.todos)} tasks → {path}", "ok", 4)
            except Exception as e:
                self.set_status(f"export failed: {e}", "danger")

        elif name == "clear":
            if args.lower() == "done":
                n          = sum(1 for t in self.todos if t["done"])
                self.todos = [t for t in self.todos if not t["done"]]
                save_data(self.todos, self.sort_by, self.theme_id)
                self.set_status(f"cleared {n} completed task{'s' if n!=1 else ''}", "ok")
            else:
                self.set_status("usage: clear done", "warn")

        elif name == "filter":
            if args.startswith("#"):
                self.active_tag = args[1:] or None
                self.set_status(f"tag filter: {args}", "ac")
            else:
                self.filter = args or "all"
                self.set_status(f"filter: {self.filter}", "ac")

        elif name in ("help","?"):
            self.mode = "help"; self.input_buf = ""; self.cursor_pos = 0; return

        elif name == "":
            self.mode = "nav"; return

        else:
            self.set_status(f'unknown: "{name}" — try :help', "warn")

        if raw.strip():
            self.cmd_hist.insert(0, raw.strip()); self.cmd_hist_idx = -1
        self.mode = "nav"

    # ── Key: navigation ───────────────────────────────────────────────────────

    def _key_nav(self, key):
        ft = self.filtered()

        if key in (curses.KEY_DOWN, ord('j')):
            if self.selected < len(ft)-1: self.selected += 1

        elif key in (curses.KEY_UP, ord('k')):
            if self.selected > 0: self.selected -= 1

        elif key == ord('g'):
            self.selected = 0; self.scroll = 0

        elif key == ord('G'):
            self.selected = max(0, len(ft)-1)

        elif key == ord(' '):
            if ft and self.selected < len(ft):
                todo         = ft[self.selected]
                todo["done"] = not todo["done"]
                self.flash_id = todo["id"]; self.flash_count = 0
                if todo["done"]:
                    self.set_status(f'✓  "{todo["text"][:45]}"  →  done tab', "ok")
                else:
                    self.set_status(f'↩  moved back to active', "warn")
                save_data(self.todos, self.sort_by, self.theme_id)
                new_ft = self.filtered()
                if self.selected >= len(new_ft):
                    self.selected = max(0, len(new_ft)-1)

        elif key in (ord('n'), ord('N')):
            self.mode = "input"; self.input_buf = ""; self.cursor_pos = 0

        elif key == ord(':'):
            self.mode = "command"; self.input_buf = ""; self.cursor_pos = 0
            self.cmd_hist_idx = -1

        elif key == ord('/'):
            self.mode = "search"
            self.input_buf = self.search_q; self.cursor_pos = len(self.input_buf)

        elif key in (ord('d'), ord('D'), curses.KEY_DC):
            if ft and self.selected < len(ft):
                tid        = ft[self.selected]["id"]
                txt        = ft[self.selected]["text"]
                self.todos = [t for t in self.todos if t["id"] != tid]
                self.selected = min(self.selected, len(self.filtered())-1)
                save_data(self.todos, self.sort_by, self.theme_id)
                self.set_status(f'deleted: "{txt[:45]}"', "danger")

        elif key in (ord('e'), ord('E')):
            if ft and self.selected < len(ft):
                t               = ft[self.selected]
                self.editing_id = t["id"]
                self.mode       = "edit_inline"
                self.input_buf  = t["text"]
                self.cursor_pos = len(self.input_buf)

        elif key == 9:   # Tab
            fl = ["all","active","done","high"]
            self.filter   = fl[(fl.index(self.filter)+1) % len(fl)]
            self.selected = 0; self.scroll = 0

        elif key == ord('?'): self.mode = "help"

        elif key in (ord('T'), ord('t')): self.mode = "theme"

        elif key == 27:
            if self.search_q:   self.search_q = ""; self.selected = 0
            elif self.active_tag: self.active_tag = None

        elif ord('1') <= key <= ord('8'):
            i = key - ord('1')
            if i < len(THEME_LIST): self._apply_theme(THEME_LIST[i])

# ── CLI helpers ───────────────────────────────────────────────────────────────

def cli_list():
    todos, _, _ = load_data()
    if not todos:
        print("No tasks.  Run: todo add \"your task\""); return
    active = [t for t in todos if not t["done"]]
    done   = [t for t in todos if t["done"]]
    active.sort(key=lambda t: {"high":0,"med":1,"low":2}.get(t["priority"],1))
    SYM = {"high":"▲","med":"◆","low":"▽"}
    COL = {"high":"\033[31m","med":"\033[33m","low":"\033[32m"}
    R = "\033[0m"; D="\033[2m"; B="\033[34m"
    print(f"\n  \033[1mTODO\033[0m  {len(active)} active  {D}{len(done)} done{R}\n")
    for t in active:
        sym   = SYM.get(t["priority"],"◆")
        col   = COL.get(t["priority"],"")
        tags  = "  ".join(f"{B}#{g}{R}" for g in t.get("tags",[]))
        ds, _ = fmt_due(t.get("due"))
        due   = f"{D}{ds}{R}" if ds else ""
        es    = fmt_est(t.get("est"))
        est   = f"{D}{es}{R}" if es else ""
        extra = "  ".join(x for x in [tags,due,est] if x)
        print(f"  {col}{sym}{R}  [ ]  {t['text']}" + (f"  {extra}" if extra else ""))
    if done:
        print(f"\n  {D}── {len(done)} completed ──{R}")
        for t in done[:5]:
            tags = "  ".join(f"#{g}" for g in t.get("tags",[]))
            print(f"  {D}▽  [✓]  {t['text']}" + (f"  {tags}" if tags else "") + R)
        if len(done) > 5:
            print(f"  {D}  … and {len(done)-5} more{R}")
    print()

def cli_add(text):
    if not text.strip():
        print('Usage: todo add "fix bug !high #work tomorrow ~2h"'); return
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
    if task["est"]: meta.append(fmt_est(task["est"]))
    detail = f'  [{" · ".join(meta)}]' if meta else ""
    print(f'  \033[32m+\033[0m  "{task["text"]}"{detail}')

def cli_help():
    print("""
  \033[1mUsage\033[0m
    todo               open the TUI
    todo open          open the TUI
    todo list          print tasks (no TUI)
    todo add "text"    add a task from the shell
    todo help          this message

  \033[1mNLP syntax\033[0m
    !high !med !low        priority
    #tag                   attach tag
    today tomorrow friday  due date
    next week              7 days from now
    ~2h ~30m               time estimate

  \033[1mExample\033[0m
    todo add "fix auth bug !high #work tomorrow ~2h"

  \033[1mData\033[0m   ~/.local/share/terminal-todo/todos.json
""")

# ── Entry point ───────────────────────────────────────────────────────────────

def main(stdscr):
    App(stdscr).run()

def _ensure_curses():
    if not IS_WINDOWS: return True
    try: import curses as _; return True
    except ImportError: pass
    print("\n  windows-curses required on Windows.")
    print("  Install:  pip install windows-curses\n")
    ans = input("  Install now? [Y/n] ").strip().lower()
    if ans in ("","y","yes"):
        import subprocess
        if subprocess.call([sys.executable,"-m","pip","install","windows-curses"]) == 0:
            print("  Done! Run `todo` again.\n")
        else:
            print("  Failed. Run manually: pip install windows-curses\n")
    return False

def launch_tui():
    if not _ensure_curses(): return
    try: curses.wrapper(main)
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    argv = sys.argv[1:]
    cmd  = argv[0].lower() if argv else "open"
    if   cmd in ("open",""): launch_tui()
    elif cmd == "list":      cli_list()
    elif cmd == "add":       cli_add(" ".join(argv[1:]))
    elif cmd in ("help","--help","-h"): cli_help()
    else:                    cli_add(" ".join(argv))