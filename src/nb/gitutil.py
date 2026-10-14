"""Wrapper minimi su git via subprocess."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

_ENV = {"GIT_LITERAL_PATHSPECS": "1", "GIT_TERMINAL_PROMPT": "0"}


class GitError(RuntimeError):
    pass


def _esegui(root: Path, args: tuple[str, ...], timeout: float | None) -> bytes:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                           timeout=timeout, env={**os.environ, **_ENV})
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]}: timeout dopo {timeout}s") from None
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args[:2])}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def git(root: Path, *args: str, timeout: float | None = None) -> str:
    return _esegui(root, args, timeout).decode("utf-8", errors="replace")


def git_bytes(root: Path, *args: str, timeout: float | None = None) -> bytes:
    return _esegui(root, args, timeout)


def lista_z(uscita: str) -> list[str]:
    return [x for x in uscita.split("\0") if x]


def in_repo(root: Path) -> bool:
    try:
        git(root, "rev-parse", "--is-inside-work-tree")
        return True
    except GitError:
        return False


def upstream(root: Path) -> str | None:
    try:
        return git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    except GitError:
        return None


def fetch(root: Path, timeout: float = 3.0) -> str | None:
    try:
        git(root, "fetch", "--quiet", timeout=timeout)
        return None
    except GitError as e:
        return str(e)


def in_staging(root: Path) -> list[str]:
    return lista_z(git(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"))


def git_add(root: Path, percorsi: list[str]) -> None:
    for i in range(0, len(percorsi), 200):
        git(root, "add", "--", *percorsi[i:i + 200])


@dataclass(frozen=True)
class Commit:
    hash: str
    autore: str
    quando: str
    messaggio: str


def commit_che_toccano(root: Path, intervallo: str, percorso: str) -> list[Commit]:
    uscita = git(root, "log", intervallo, "--format=%h%x1f%an%x1f%ar%x1f%s", "--", percorso)
    return [Commit(*riga.split("\x1f", 3)) for riga in uscita.splitlines() if riga]


def remoti_cambiati(root: Path) -> list[str]:
    return lista_z(git(root, "diff", "--name-only", "-z", "HEAD...@{u}"))
