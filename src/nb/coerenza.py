"""Quali vettori servono a una revisione git, e quali mancano."""
from __future__ import annotations

from pathlib import Path

from nb.chunker import chunk_di
from nb.config import Config
from nb.fonti import indicizzabile
from nb.gitutil import GitError, git, git_bytes, lista_z
from nb.vettori import chiave, percorso_rel


def richiesti_a(config: Config, rev: str, percorsi: list[str]) -> dict[str, tuple[str, str]]:
    """hash -> (percorso md, testo da embeddare). rev="" legge dallo staging."""
    out: dict[str, tuple[str, str]] = {}
    for p in percorsi:
        if not indicizzabile(p):
            continue
        try:
            testo = git_bytes(config.root, "show", f"{rev}:{p}").decode("utf-8", errors="replace")
        except GitError:
            continue  # file cancellato in quella revisione
        _, chunks = chunk_di(config, p, testo)
        for c in chunks:
            out[chiave(config.model_id, c.testo_embed)] = (p, c.testo_embed)
    return out


def emb_tracciati(root: Path, rev: str) -> set[str]:
    return set(lista_z(git(root, "ls-tree", "-r", "--name-only", "-z", rev, "--", ".nb/emb")))


def mancanti_a(config: Config, rev: str, percorsi: list[str]) -> dict[str, tuple[str, str]]:
    tracciati = emb_tracciati(config.root, rev)
    return {h: v for h, v in richiesti_a(config, rev, percorsi).items() if percorso_rel(h) not in tracciati}


def md_tracciati(root: Path, rev: str = "HEAD") -> list[str]:
    return [p for p in lista_z(git(root, "ls-tree", "-r", "--name-only", "-z", rev)) if indicizzabile(p)]
