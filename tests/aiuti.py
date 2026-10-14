"""Helper condivisi dai test."""
import subprocess
from pathlib import Path


def scrivi(root: Path, rel: str, testo: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return p


def g(cwd: Path, *args: str) -> str:
    """git per i test (senza le variabili d'ambiente di nb)."""
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def commit_e_push(cwd: Path, rel: str, testo: str, messaggio: str) -> None:
    scrivi(cwd, rel, testo)
    g(cwd, "add", "-A")
    g(cwd, "commit", "-qm", messaggio)
    g(cwd, "push", "-q")
