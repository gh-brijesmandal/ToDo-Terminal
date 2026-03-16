#!/usr/bin/env bash
# install.sh — installs `todo` as a global terminal command
# Usage: bash install.sh

set -e

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME="todo"
INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/terminal-todo"
SCRIPT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/todo.py"
INSTALL_PATH="$INSTALL_DIR/$APP_NAME"

# ── Colours ───────────────────────────────────────────────────────────────────
G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[34m"; D="\033[0m"; BOLD="\033[1m"

log()  { echo -e "${G}✓${D}  $*"; }
info() { echo -e "${B}→${D}  $*"; }
warn() { echo -e "${Y}!${D}  $*"; }
err()  { echo -e "${R}✗${D}  $*"; exit 1; }

echo ""
echo -e "${BOLD}  Terminal Todo — installer${D}"
echo    "  ─────────────────────────────"
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    err "python3 not found. Please install Python 3.6+ first."
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 6 ]; }; then
    err "Python 3.6+ required, found $PY_VERSION"
fi
log "Python $PY_VERSION found"

# ── Check source ──────────────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_SRC" ]; then
    err "todo.py not found at $SCRIPT_SRC\n   Run this script from the same folder as todo.py"
fi
log "todo.py found"

# ── Create dirs ───────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR"
mkdir -p "$APP_DIR"

# ── Install ───────────────────────────────────────────────────────────────────
cp "$SCRIPT_SRC" "$INSTALL_PATH"
chmod +x "$INSTALL_PATH"

# Patch shebang to use system python3
sed -i.bak "1s|.*|#!/usr/bin/env python3|" "$INSTALL_PATH" 2>/dev/null || true
rm -f "${INSTALL_PATH}.bak"

log "installed → $INSTALL_PATH"

# ── PATH check & auto-patch shell rc ─────────────────────────────────────────
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
ADDED_TO=""

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    warn "$INSTALL_DIR is not in your PATH — patching shell config…"

    # Detect shell config file
    SHELL_NAME="$(basename "${SHELL:-bash}")"
    case "$SHELL_NAME" in
        zsh)   RC="$HOME/.zshrc" ;;
        fish)  RC="$HOME/.config/fish/config.fish"
               PATH_LINE='fish_add_path $HOME/.local/bin' ;;
        *)     RC="$HOME/.bashrc" ;;
    esac

    # Only append if not already present
    if ! grep -qF "$HOME/.local/bin" "$RC" 2>/dev/null; then
        echo ""                   >> "$RC"
        echo "# terminal-todo"    >> "$RC"
        echo "$PATH_LINE"         >> "$RC"
        ADDED_TO="$RC"
        log "added PATH export to $RC"
    else
        warn "$RC already mentions ~/.local/bin — skipping"
    fi
else
    log "$INSTALL_DIR already in PATH"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  All done!${D}"
echo    "  ─────────────────────────────"

if [ -n "$ADDED_TO" ]; then
    echo -e "  Reload your shell first:"
    echo -e "    ${Y}source $ADDED_TO${D}"
    echo ""
fi

echo -e "  Then run from anywhere:"
echo -e "    ${G}todo${D}            open the app"
echo -e "    ${G}todo help${D}       print usage"
echo -e "    ${G}todo list${D}       print tasks in terminal (no TUI)"
echo -e "    ${G}todo add \"task\"${D} add a task directly from the shell"
echo ""
