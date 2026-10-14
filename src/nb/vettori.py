"""Vettori committati: un file immutabile per chunk, nominato con l'hash del contenuto."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import numpy as np

from nb.embedder import Embedder


def chiave(model_id: str, testo: str) -> str:
    return hashlib.sha256(f"{model_id}\n{testo}".encode()).hexdigest()


def percorso(emb_dir: Path, h: str) -> Path:
    return emb_dir / h[:2] / f"{h}.bin"


def percorso_rel(h: str) -> str:
    return f".nb/emb/{h[:2]}/{h}.bin"


def leggi(emb_dir: Path, h: str, dim: int) -> np.ndarray | None:
    try:
        dati = percorso(emb_dir, h).read_bytes()
    except FileNotFoundError:
        return None
    if len(dati) != dim * 2:
        return None
    return np.frombuffer(dati, dtype="<f2").astype(np.float32)


def scrivi(emb_dir: Path, h: str, vettore: np.ndarray) -> Path:
    p = percorso(emb_dir, h)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f"{h}.", suffix=".tmp")  # nome unico: più scrittori insieme
    with os.fdopen(fd, "wb") as f:
        f.write(np.asarray(vettore, dtype="<f2").tobytes())
    os.replace(tmp, p)
    return p


def assicura(emb_dir: Path, embedder: Embedder, testi: dict[str, str]) -> tuple[dict[str, np.ndarray], list[Path]]:
    """Carica i vettori esistenti, calcola e scrive solo i mancanti."""
    trovati: dict[str, np.ndarray] = {}
    mancanti: list[str] = []
    for h in testi:
        v = leggi(emb_dir, h, embedder.dim)
        if v is None:
            mancanti.append(h)
        else:
            trovati[h] = v
    nuovi: list[Path] = []
    if mancanti:
        calcolati = embedder.embed([testi[h] for h in mancanti])
        for h, v in zip(mancanti, calcolati):
            nuovi.append(scrivi(emb_dir, h, v))
            trovati[h] = v.astype("<f2").astype(np.float32)
    return trovati, nuovi


def tutte(emb_dir: Path) -> set[str]:
    return {p.stem for p in emb_dir.glob("*/*.bin")}


def gc(emb_dir: Path, vivi: set[str]) -> list[Path]:
    rimossi = []
    for p in sorted(emb_dir.glob("*/*.bin")):
        if p.stem not in vivi:
            p.unlink()
            rimossi.append(p)
    for d in emb_dir.glob("*"):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return rimossi
