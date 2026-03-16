# Terminal Todo

A keyboard-driven todo app for the real terminal — and the browser. Single Python file, zero external dependencies on macOS/Linux.
This is a raw version (v: 1.0.0) of the Product which was vibe coded through Claude. Open to use this and further improve the application which additional NLP features, more flags and features, or even other cloud APIs for multi task syncing.
There is a browser version as well, discussed in the later part which looks more clean compared to terminal version (cuz JS>Py for UI), which you can use as well.

```
todo              → opens the full TUI
todo list         → prints tasks inline
todo add "text"   → add without opening the app
todo help         → usage reference
```

---

## Files

```
todo.py        terminal TUI app  (Python 3.6+, all platforms)
todo.html      browser version   (open in any browser, no server needed)
install.sh     installer for macOS / Linux
install.ps1    installer for Windows
README.md      this file
```

---

## Installation

### macOS / Linux

**Requirements:** Python 3.6+. No pip installs needed — uses only the standard library.

```bash
# Put todo.py and install.sh in the same folder, then:
bash install.sh
```

The script will:

- Check Python version
- Copy `todo.py` to `~/.local/bin/todo` and make it executable
- Add `~/.local/bin` to your `$PATH` in your shell rc file if needed (`.zshrc`, `.bashrc`, or fish config)

After install, reload your shell:

```bash
source ~/.zshrc    # zsh
source ~/.bashrc   # bash
```

Then from any directory:

```bash
todo
```

---

### Windows

**Requirements:** Python 3.6+ from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install.

**Recommended terminal:** [Windows Terminal](https://aka.ms/terminal) — best 256-colour support and clean rendering.

Open **PowerShell** in the folder containing `todo.py` and `install.ps1`, then run:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

The script will:

- Detect Python (`python`, `python3`, or `py` launcher — whichever exists)
- Run `pip install windows-curses` automatically (`curses` is not bundled with Python on Windows)
- Copy `todo.py` to `%USERPROFILE%\.local\bin\todo.py`
- Create a `todo.bat` wrapper so `todo` works in both `cmd.exe` and PowerShell
- Add the bin folder to your **user PATH** via the registry (no admin rights needed)

Open a **new terminal window** after install, then:

```
todo
```

> **ExecutionPolicy error?** Run this in PowerShell first, then retry:
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

### WSL (Windows Subsystem for Linux)

Treat WSL exactly like Linux. Use `bash install.sh` — no `windows-curses` needed inside WSL.

---

### Manual install (no installer)

If you'd rather skip the install scripts:

**macOS / Linux:**

```bash
chmod +x todo.py
./todo.py

# or always via python3
python3 todo.py
```

**Windows (PowerShell or cmd):**

```powershell
pip install windows-curses
python todo.py
```

---

## CLI usage

Once installed, `todo` works as a shell command from any directory:

| Command           | Description                             |
| ----------------- | --------------------------------------- |
| `todo`            | Open the TUI app                        |
| `todo open`       | Open the TUI app (explicit)             |
| `todo list`       | Print all tasks in the terminal, no TUI |
| `todo add "text"` | Add a task directly from the shell      |
| `todo help`       | Print usage reference                   |

The `add` command supports the full NLP syntax:

```bash
todo add "fix auth bug !high #work tomorrow ~2h"
todo add "buy milk !low #personal"
todo add "team standup friday #work ~15m"
```

---

## Data location

Tasks are stored as JSON and shared between all commands (`todo`, `todo add`, `todo list`).

| Platform      | Path                                                  |
| ------------- | ----------------------------------------------------- |
| macOS / Linux | `~/.local/share/terminal-todo/todos.json`             |
| Windows       | `%USERPROFILE%\.local\share\terminal-todo\todos.json` |

Export to plain text: inside the TUI press `:` then type `export`. Writes `~/todo-export.txt` (or `%USERPROFILE%\todo-export.txt` on Windows).

---

## TUI — keyboard reference

| Key            | Action                                        |
| -------------- | --------------------------------------------- |
| `n`            | new task (opens NLP input)                    |
| `↑` / `↓`      | navigate (or `k` / `j` vim-style)             |
| `Space`        | toggle done / undone                          |
| `e`            | edit selected task inline                     |
| `d` / `Delete` | delete selected task                          |
| `:`            | open command bar                              |
| `/`            | live search                                   |
| `Tab`          | cycle filter tabs: All → Active → Done → High |
| `g` / `G`      | jump to top / bottom                          |
| `T` / `1–8`    | open theme picker / quick-switch theme        |
| `?`            | open help screen                              |
| `Esc`          | cancel / clear search / clear tag filter      |

---

## Natural language input

Press `n` and type naturally. The parser extracts structured data automatically:

| Token                     | Effect                             | Example                   |
| ------------------------- | ---------------------------------- | ------------------------- |
| `!high` / `!med` / `!low` | priority                           | `fix bug !high`           |
| `#tag`                    | attach a tag                       | `call dentist #health`    |
| `today` / `tomorrow`      | due date                           | `submit report tomorrow`  |
| `monday` – `sunday`       | due on next occurrence of that day | `review PR friday`        |
| `next week`               | due in 7 days                      | `retrospective next week` |
| `~2h` / `~30m`            | time estimate                      | `refactor auth ~2h`       |

Multiple tokens combine freely:

```
fix auth bug !high #work tomorrow ~2h
→  text="fix auth bug"  priority=high  tag=#work  due=tomorrow  est=2h
```

---

## Command bar

Press `:` to enter command mode. Use `↑` / `↓` to recall command history.

```
:sort priority       high → med → low
:sort date           soonest due first
:sort alpha          alphabetical
:sort default        original add order

:search <query>      filter by keyword (text and tags)
:filter #work        filter by tag
:clear done          delete all completed tasks
:export              write all tasks to ~/todo-export.txt
:help                open help screen
```

---

## Themes

8 built-in colour themes. Switch with `T` (picker overlay) or press `1`–`8` directly anywhere in the app. Selection is persisted to disk.

| Key | Theme     | Style                           |
| --- | --------- | ------------------------------- |
| `1` | Hacker    | green phosphor on black         |
| `2` | Dracula   | purple & pink on deep dark      |
| `3` | Nord      | arctic blue-grey                |
| `4` | Amber     | classic amber terminal          |
| `5` | Monokai   | yellow & green on charcoal      |
| `6` | Synthwave | neon pink & cyan on deep purple |
| `7` | Ocean     | cyan on midnight blue           |
| `8` | Paper     | dark ink on off-white (light)   |

---

## Browser version (todo.html)

The `todo.html` file is a fully self-contained browser app with all the same features — no server, no installs, just open it.

```bash
open todo.html        # macOS
xdg-open todo.html    # Linux
start todo.html       # Windows cmd / PowerShell
```

Browser data is stored in `localStorage`. Use `:export` inside the TUI to copy tasks to the clipboard.
Deployed at todoterminal.netlify.app

---

## Platform support

| Platform        | Terminal TUI                                     | Browser |
| --------------- | ------------------------------------------------ | ------- |
| macOS           | ✅ built-in Python, zero pip installs            | ✅      |
| Linux           | ✅ built-in Python, zero pip installs            | ✅      |
| Windows 10 / 11 | ✅ needs `windows-curses` (installer handles it) | ✅      |
| WSL             | ✅ treat as Linux                                | ✅      |

**Minimum terminal size:** 80 × 24. Works best at 100+ columns.

**Colour support:** requires a 256-colour terminal.

| macOS                                        | Linux                                           | Windows                                    |
| -------------------------------------------- | ----------------------------------------------- | ------------------------------------------ |
| Terminal.app, iTerm2, Warp, Alacritty, Kitty | GNOME Terminal, Konsole, Alacritty, Kitty, tmux | Windows Terminal ⭐, PowerShell 7+, ConEmu |

---

## Data format (JSON)

```json
{
  "todos": [
    {
      "id": "a1b2c3",
      "text": "fix auth bug",
      "priority": "high",
      "tags": ["work"],
      "due": 1710288000000,
      "est": 120,
      "done": false,
      "ca": 1710201600000
    }
  ],
  "sort": "default",
  "theme": "hacker"
}
```

| Field      | Type                         | Description                   |
| ---------- | ---------------------------- | ----------------------------- |
| `id`       | string                       | unique identifier             |
| `text`     | string                       | task content                  |
| `priority` | `"high"` / `"med"` / `"low"` | priority level                |
| `tags`     | string[]                     | list of tag strings           |
| `due`      | number (ms) / null           | due date as unix milliseconds |
| `est`      | number (minutes) / null      | time estimate in minutes      |
| `done`     | boolean                      | completion state              |
| `ca`       | number (ms)                  | created-at timestamp          |

---

## Adding a custom theme

In `todo.py`, add an entry to the `THEMES` dict:

```python
"my-theme": {
    "name":    "My Theme",
    "bg":      232,   # main background       (256-colour index)
    "sel_bg":  22,    # selected row bg
    "fg":      46,    # primary text
    "accent":  46,    # highlights, cursor, borders
    "accent2": 34,    # tags, chips, secondary accent
    "ok":      34,    # done / success
    "warn":    214,   # due today / med priority
    "danger":  196,   # overdue / high priority
    "muted":   28,    # dim body text
    "dim":     238,   # very dim (borders, hints)
},
```

256-colour palette reference: [en.wikipedia.org/wiki/ANSI_escape_code#8-bit](https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit)

---

## License

MIT — do whatever you want with it.
