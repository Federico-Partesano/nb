"""Ricerca ibrida (vettoriale + BM25, fusione RRF) e documenti simili."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

import numpy as np

from nb.chunker import chunk_di
from nb.indice import Indice

RRF_K = 60
CANDIDATI = 50
SOGLIA_COPERTURA = 0.9


@dataclass(frozen=True)
class Filtri:
    progetto: str | None = None
    tipo: str | None = None
    da: str | None = None
    a: str | None = None


@dataclass(frozen=True)
class Risultato:
    percorso: str
    titoli: tuple[str, ...]
    testo: str
    riga_inizio: int
    riga_fine: int
    speaker: tuple[str, ...]
    tipo: str
    progetto: str | None
    data: str | None
    punteggio: float

    @property
    def citazione(self) -> str:
        return " › ".join((self.percorso, *self.titoli))

    def to_dict(self) -> dict:
        return {**asdict(self), "citazione": self.citazione}


@dataclass(frozen=True)
class Simile:
    percorso: str
    similarita: float
    copertura: float


def _condizioni(f: Filtri) -> tuple[str, list[str]]:
    cond, par = [], []
    for colonna, op, valore in (("progetto", "=", f.progetto), ("tipo", "=", f.tipo),
                                ("data", ">=", f.da), ("data", "<=", f.a)):
        if valore:
            cond.append(f"f.{colonna} {op} ?")
            par.append(valore)
    return " AND ".join(cond), par


def _query_fts(query: str) -> str:
    return " OR ".join(f'"{p}"' for p in re.findall(r"\w+", query.lower()))


def _vettoriale(indice: Indice, query: str, ammessi: set[int] | None) -> list[int]:
    m = indice.matrice()
    if not len(m.ids):
        return []
    sim = m.vettori @ indice.embedder.embed_query(query)
    if ammessi is not None:
        sim = np.where(np.isin(m.ids, list(ammessi)), sim, -np.inf)
    n = min(CANDIDATI, len(m.ids))
    top = np.argpartition(-sim, n - 1)[:n]
    top = top[np.argsort(-sim[top])]
    return [int(m.ids[i]) for i in top if np.isfinite(sim[i])]


def _bm25(indice: Indice, query: str, cond: str, par: list[str]) -> list[int]:
    fts = _query_fts(query)
    if not fts:
        return []
    sql = ("SELECT chunk_fts.rowid FROM chunk_fts JOIN chunk c ON c.id = chunk_fts.rowid "
           "JOIN file f ON f.percorso = c.percorso WHERE chunk_fts MATCH ?"
           + (f" AND {cond}" if cond else "") + " ORDER BY bm25(chunk_fts) LIMIT ?")
    return [r[0] for r in indice.db.execute(sql, [fts, *par, CANDIDATI])]


def _carica(indice: Indice, cid: int, punteggio: float) -> Risultato:
    r = indice.db.execute(
        "SELECT c.percorso, c.titoli, c.testo, c.riga_inizio, c.riga_fine, c.speaker, f.tipo, f.progetto, f.data "
        "FROM chunk c JOIN file f ON f.percorso = c.percorso WHERE c.id = ?", (cid,)).fetchone()
    return Risultato(r[0], tuple(json.loads(r[1])), r[2], r[3], r[4], tuple(json.loads(r[5])),
                     r[6], r[7], r[8], round(punteggio, 4))


def cerca(indice: Indice, query: str, filtri: Filtri = Filtri(), k: int = 8) -> list[Risultato]:
    cond, par = _condizioni(filtri)
    ammessi = None
    if cond:
        sql = f"SELECT c.id FROM chunk c JOIN file f ON f.percorso = c.percorso WHERE {cond}"
        ammessi = {r[0] for r in indice.db.execute(sql, par)}
        if not ammessi:
            return []
    punteggi: dict[int, float] = {}
    for classifica in (_vettoriale(indice, query, ammessi), _bm25(indice, query, cond, par)):
        for rank, cid in enumerate(classifica):
            punteggi[cid] = punteggi.get(cid, 0.0) + 1 / (RRF_K + rank + 1)
    migliori = sorted(punteggi, key=punteggi.__getitem__, reverse=True)[:k]
    return [_carica(indice, cid, punteggi[cid]) for cid in migliori]


def simili(indice: Indice, nome: str, testo: str, k: int = 5) -> list[Simile]:
    _, chunks = chunk_di(indice.config, nome, testo)
    m = indice.matrice()
    if not chunks or not len(m.ids):
        return []
    s = indice.embedder.embed([c.testo_embed for c in chunks]) @ m.vettori.T
    inizi = np.flatnonzero(np.r_[True, m.percorsi[1:] != m.percorsi[:-1]])
    blocchi = np.maximum.reduceat(s, inizi, axis=1)  # (chunk nuovi, gruppi di file)
    per_file: dict[str, np.ndarray] = {}
    for j, i in enumerate(inizi):
        p = m.percorsi[i]
        per_file[p] = np.maximum(per_file[p], blocchi[:, j]) if p in per_file else blocchi[:, j]
    risultati = [Simile(p, round(float(b.max()), 4), round(float((b >= SOGLIA_COPERTURA).mean()), 4))
                 for p, b in per_file.items()]
    return sorted(risultati, key=lambda x: x.similarita, reverse=True)[:k]


def formatta_risultati(risultati: list[Risultato]) -> str:
    blocchi = []
    for i, r in enumerate(risultati, 1):
        info = [r.tipo, r.progetto, r.data, " + ".join(r.speaker) if r.speaker else None]
        dettagli = "; ".join(x for x in info if x)
        blocchi.append(f"[{i}] {r.citazione}  (righe {r.riga_inizio}-{r.riga_fine}; {dettagli})\n{r.testo}")
    return "\n\n---\n\n".join(blocchi)
