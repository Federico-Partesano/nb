"""`nb init`: prepara un knowledge repo (config, gitignore, hook, template per Claude Code)."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from nb.config import scrivi_default
from nb.gitutil import git, in_repo
from nb.hooks import installa

RIGA_GITIGNORE = ".nb/index.db*"
MODELLI = {
    "README.md": "README.md",
    "CLAUDE.md": "CLAUDE.md",
    ".claude/skills/nb-carica/SKILL.md": "skill-nb-carica.md",
    ".claude/settings.json": "settings.json",
    ".mcp.json": "mcp.json",
}


class InitError(RuntimeError):
    pass


def _gitignore(root: Path) -> bool:
    p = root / ".gitignore"
    testo = p.read_text(encoding="utf-8") if p.exists() else ""
    if RIGA_GITIGNORE in testo.splitlines():
        return False
    p.write_text(testo + ("" if not testo or testo.endswith("\n") else "\n") + RIGA_GITIGNORE + "\n", encoding="utf-8")
    return True


def inizializza(dove: Path) -> list[str]:
    if not in_repo(dove):
        raise InitError("non è un repo git: clona il knowledge repo (o esegui `git init`) e riprova")
    root = Path(git(dove, "rev-parse", "--show-toplevel").strip()).resolve()
    messaggi = []
    if scrivi_default(root):
        messaggi.append("creato .nb/config.toml")
    if _gitignore(root):
        messaggi.append(f"aggiunto {RIGA_GITIGNORE} a .gitignore")
    installa(root)
    messaggi.append("hook git attivi (.githooks, core.hooksPath)")
    for dest, modello in MODELLI.items():
        p = root / dest
        if p.exists():
            messaggi.append(f"{dest} esiste già: non toccato")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(files("nb.modelli").joinpath(modello).read_text(encoding="utf-8"), encoding="utf-8")
        messaggi.append(f"creato {dest}")
    messaggi.append("Se è il primo init del repo: git add -A && git commit -m 'nb init' && git push. "
                    "Ogni collega, dopo il clone, esegue solo `nb init`.")
    return messaggi
