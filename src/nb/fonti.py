"""Scoperta dei .md indicizzabili e dei loro metadati (frontmatter + percorso)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from nb.config import CARTELLA_TIPO, TIPI

ESCLUSI_RADICE = {"README.md", "CLAUDE.md"}
RE_DATA = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


@dataclass(frozen=True)
class Metadati:
    tipo: str = "altro"
    progetto: str | None = None
    data: str | None = None
    partecipanti: tuple[str, ...] = ()


@dataclass(frozen=True)
class Fonte:
    percorso: str
    corpo: str
    meta: Metadati
    riga_corpo: int  # numero (1-based) della prima riga del corpo nel file
    avvisi: tuple[str, ...] = ()


def indicizzabile(percorso: str) -> bool:
    parti = PurePosixPath(percorso).parts
    if not parti or not percorso.endswith(".md"):
        return False
    if any(p.startswith(".") for p in parti[:-1]):
        return False
    return not (len(parti) == 1 and parti[0] in ESCLUSI_RADICE)


def elenca_md(root: Path) -> list[str]:
    trovati = []
    for p in root.rglob("*.md"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and indicizzabile(rel):
            trovati.append(rel)
    return sorted(trovati)


def separa_frontmatter(testo: str) -> tuple[dict | None, str, int, str | None]:
    """Restituisce (frontmatter, corpo, riga_corpo, errore)."""
    testo = testo.removeprefix("﻿")
    righe = testo.split("\n")
    if righe[0].strip() != "---":
        return None, testo, 1, None
    for i in range(1, len(righe)):
        if righe[i].strip() in ("---", "..."):
            grezzo = "\n".join(righe[1:i])
            corpo = "\n".join(righe[i + 1:])
            try:
                dati = yaml.safe_load(grezzo) or {}
            except yaml.YAMLError as e:
                return None, corpo, i + 2, f"frontmatter YAML non valido ({e.__class__.__name__})"
            if not isinstance(dati, dict):
                return None, corpo, i + 2, "frontmatter non è una mappa chiave: valore"
            return dati, corpo, i + 2, None
    return None, testo, 1, "frontmatter aperto con --- ma mai chiuso"


def meta_da_percorso(percorso: str) -> Metadati:
    parti = PurePosixPath(percorso).parts
    in_progetti = parti[0] == "progetti"
    progetto = parti[1] if in_progetti and len(parti) >= 3 else None
    tipo = CARTELLA_TIPO.get(parti[2], "altro") if in_progetti and len(parti) >= 4 else "altro"
    m = RE_DATA.match(parti[-1])
    return Metadati(tipo=tipo, progetto=progetto, data=m.group(1) if m else None)


def _unisci(base: Metadati, fm: dict) -> tuple[Metadati, list[str]]:
    avvisi = []
    tipo = fm.get("tipo", base.tipo)
    if tipo not in TIPI:
        avvisi.append(f"tipo '{tipo}' non ammesso (ammessi: {', '.join(TIPI)})")
        tipo = base.tipo
    progetto = fm.get("progetto", base.progetto)
    data = fm.get("data", base.data)
    partecipanti = fm.get("partecipanti", [])
    if isinstance(partecipanti, str):
        partecipanti = [partecipanti]
    if not isinstance(partecipanti, list):
        avvisi.append("partecipanti deve essere una lista")
        partecipanti = []
    meta = Metadati(
        tipo=tipo,
        progetto=None if progetto is None else str(progetto),
        data=None if data is None else str(data),
        partecipanti=tuple(str(p) for p in partecipanti),
    )
    return meta, avvisi


def analizza(percorso: str, testo: str) -> Fonte:
    fm, corpo, riga_corpo, errore = separa_frontmatter(testo)
    meta = meta_da_percorso(percorso)
    avvisi = [errore] if errore else []
    if fm:
        meta, extra = _unisci(meta, fm)
        avvisi += extra
    return Fonte(percorso, corpo, meta, riga_corpo, tuple(avvisi))


def leggi_fonte(root: Path, percorso: str) -> Fonte:
    return analizza(percorso, (root / percorso).read_text(encoding="utf-8", errors="replace"))
