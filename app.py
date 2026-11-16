"""TERMINAL 404 - a text-based hacking adventure.

Flask is the game engine. The browser sends each typed command to
/api/command, the engine updates the player's state, and replies with JSON.
"""
import json
import posixpath
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = "change-me-before-sharing"  # signs the session cookie

GAME = json.loads((Path(__file__).parent / "game_data.json").read_text(encoding="utf-8"))
HOME = "/home/investigator"

HELP = [
    "COMMANDS",
    "  help                     show this list",
    "  ls [path]                list files",
    "  cd <path>                change directory",
    "  pwd                      show where you are",
    "  cat <file>               read a file",
    "  unlock <file> <key>      decrypt a locked file",
    "  notes                    review logged clues",
    "  hint                     get a nudge (one per use)",
    "  accuse <last name>       name the culprit",
    "  clear                    clear the screen (or Ctrl+L)",
    "  reset                    restart the case",
]


# ---------- helpers ----------
def new_state():
    return {"cwd": HOME, "unlocked": [], "clues": [], "hints": 0, "solved": False}


def get_state():
    if "game" not in session:
        session["game"] = new_state()
    return session["game"]


def L(text, kind="out"):
    return {"text": text, "kind": kind}


def resolve(cwd, arg):
    """Turn a typed path into a clean absolute path like /mail/01_vet.txt."""
    if arg.startswith("~"):
        arg = HOME + arg[1:]
    return posixpath.normpath(arg if arg.startswith("/") else posixpath.join(cwd, arg))


def lookup(path):
    """Walk the fake file system. Dict = folder, list = file, None = missing."""
    node = GAME["fs"]
    for part in (p for p in path.split("/") if p):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def prompt(st):
    cwd = "~" + st["cwd"][len(HOME):] if st["cwd"].startswith(HOME) else st["cwd"]
    return f"investigator@halcyon:{cwd}$"


# ---------- commands ----------
def cmd_ls(st, args):
    path = resolve(st["cwd"], args[0]) if args else st["cwd"]
    node = lookup(path)
    if node is None:
        return [L(f"ls: cannot access '{path}': no such file or directory", "err")]
    if not isinstance(node, dict):
        return [L(path)]
    names = []
    for name in sorted(node):
        full = posixpath.join(path, name)
        if isinstance(node[name], dict):
            names.append(name + "/")
        elif full in GAME["locks"] and full not in st["unlocked"]:
            names.append(name + " [LOCKED]")
        else:
            names.append(name)
    return [L("  ".join(names) or "(empty)")]


def cmd_cd(st, args):
    path = resolve(st["cwd"], args[0]) if args else HOME
    node = lookup(path)
    if not isinstance(node, dict):
        return [L(f"cd: {path}: not a directory", "err")]
    st["cwd"] = path
    return []


def cmd_cat(st, args):
    if not args:
        return [L("usage: cat <file>", "warn")]
    path = resolve(st["cwd"], args[0])
    node = lookup(path)
    if node is None:
        return [L(f"cat: {path}: no such file", "err")]
    if isinstance(node, dict):
        return [L(f"cat: {path}: is a directory", "err")]
    if path in GAME["locks"] and path not in st["unlocked"]:
        return [L("ACCESS DENIED: file is encrypted.", "warn"),
                L("Use: unlock <file> <key>", "warn")]
    out = [L(line) for line in node]
    clue = GAME["clues"].get(path)
    if clue and clue not in st["clues"]:
        st["clues"].append(clue)
        out += [L(""), L(f"[+] Clue logged: {clue}", "good")]
    return out


def cmd_unlock(st, args):
    if len(args) < 2:
        return [L("usage: unlock <file> <key>", "warn")]
    path = resolve(st["cwd"], args[0])
    if path not in GAME["locks"]:
        return [L(f"unlock: {path}: nothing to unlock", "err")]
    if path in st["unlocked"]:
        return [L("Already decrypted.", "sys")]
    if args[1].lower() != GAME["locks"][path]:
        return [L("KEY REJECTED. This attempt has been logged.", "warn")]
    st["unlocked"].append(path)
    return [L("KEY ACCEPTED. Decrypting ...", "good"), L(f"Run: cat {path}", "sys")]


def cmd_notes(st, args):
    if not st["clues"]:
        return [L("No clues yet. Read files with 'cat'.", "sys")]
    return [L("CLUES")] + [L(f"  {i}. {c}") for i, c in enumerate(st["clues"], 1)]


def cmd_hint(st, args):
    hints = GAME["hints"]
    i = min(st["hints"], len(hints) - 1)
    st["hints"] += 1
    return [L(f"HINT {i + 1}/{len(hints)}: {hints[i]}", "sys")]


def cmd_accuse(st, args):
    if not args:
        return [L("usage: accuse <last name>", "warn")]
    name = args[0].lower()
    if name not in GAME["suspects"]:
        return [L(f"'{args[0]}' is not on the suspect list.", "warn")]
    if "/vault/ledger.enc" not in st["unlocked"]:
        return [L("Not enough proof. Mara said the answer is in the vault.", "warn")]
    if name != GAME["culprit"]:
        return [L("The evidence does not support that. Review 'notes'.", "warn")]
    st["solved"] = True
    return [L("CASE CLOSED", "good"),
            L("Kessler was arrested at dawn. Mara Voss was found safe", "good"),
            L("and the Northgate fraud is now in the hands of the police.", "good"),
            L(""), L("Well done, investigator. Type 'reset' to play again.", "sys")]


COMMANDS = {
    "ls": cmd_ls, "cd": cmd_cd, "cat": cmd_cat, "unlock": cmd_unlock,
    "notes": cmd_notes, "hint": cmd_hint, "accuse": cmd_accuse,
}


def run(raw, st):
    parts = raw.split()
    cmd, args = parts[0].lower(), parts[1:]
    if cmd == "help":
        return [L(t, "sys" if i == 0 else "out") for i, t in enumerate(HELP)], False
    if cmd == "pwd":
        return [L(st["cwd"])], False
    if cmd == "whoami":
        return [L("investigator (guest, read-only)")], False
    if cmd == "clear":
        return [], True
    if cmd in COMMANDS:
        return COMMANDS[cmd](st, args), False
    return [L(f"{cmd}: command not found. Type 'help'.", "err")], False


# ---------- routes ----------
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/start")
def start():
    session["game"] = new_state()
    st = get_state()
    return jsonify(lines=[L(t, k) for t, k in GAME["intro"]], prompt=prompt(st), clues=0)


@app.post("/api/command")
def command():
    st = get_state()
    raw = (request.get_json(silent=True) or {}).get("command", "").strip()
    if not raw:
        return jsonify(lines=[], prompt=prompt(st), clues=len(st["clues"]))
    if raw.lower() == "reset":
        return start()
    lines, clear = run(raw, st)
    session["game"] = st
    session.modified = True
    return jsonify(lines=lines, clear=clear, prompt=prompt(st), clues=len(st["clues"]))


if __name__ == "__main__":
    app.run(debug=True)
