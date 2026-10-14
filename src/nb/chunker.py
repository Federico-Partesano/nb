"""Spezza una Fonte in chunk: per titoli (documenti) o per battute (trascrizioni)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from nb.config import Config
from nb.fonti import Fonte, analizza

RE_TITOLO = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_SPEAKER = re.compile(
    r"^\s*(?:"
    r"\*\*(?P<a>[^*:\n]{1,60})\*\*\s*(?:\[[\d:]{4,8}\])?\s*:"
    r"|\*\*(?P<b>[^*:\n]{1,60}?)\s*(?:\[[\d:]{4,8}\])?\s*:\*\*"
    r"|(?P<c>[A-ZÀ-Ý][\w'.-]*(?: [A-ZÀ-Ý][\w'.-]*){0,3})\s*(?:\[[\d:]{4,8}\])?\s*:(?:\s|$)"
    r")"
)

Riga = tuple[int, str]  # (numero riga nel file, testo)


@dataclass(frozen=True)
class Chunk:
    percorso: str
    titoli: tuple[str, ...]
    testo: str
    riga_inizio: int
    riga_fine: int
    speaker: tuple[str, ...] = ()

    @property
    def testo_embed(self) -> str:
        if not self.titoli:
            return self.testo
        return " › ".join(self.titoli) + "\n" + self.testo


def _parole(s: str) -> int:
    return len(s.split())


def speaker_di(riga: str) -> str | None:
    m = RE_SPEAKER.match(riga)
    if not m:
        return None
    return next(v for v in (m.group("a"), m.group("b"), m.group("c")) if v).strip()


def _impacchetta(unita: list[list[Riga]], max_parole: int, overlap: int) -> list[list[Riga]]:
    """Raggruppa unità atomiche (paragrafi o battute) in finestre di circa max_parole."""
    piatte: list[list[Riga]] = []
    for u in unita:
        if sum(_parole(t) for _, t in u) > max_parole:
            piatte.extend([r] for r in u)
        else:
            piatte.append(u)
    finestre: list[list[Riga]] = []
    corrente: list[Riga] = []
    n = 0
    for u in piatte:
        pu = sum(_parole(t) for _, t in u)
        if corrente and n + pu > max_parole:
            finestre.append(corrente)
            coda: list[Riga] = []
            m = 0
            for r in reversed(corrente[1:]) if overlap else ():
                if m + _parole(r[1]) > overlap:
                    break
                coda.insert(0, r)
                m += _parole(r[1])
            corrente, n = coda, m
        corrente.extend(u)
        n += pu
    if corrente:
        finestre.append(corrente)
    return finestre


def _crea(percorso: str, titoli: tuple[str, ...], finestra: list[Riga], speaker: tuple[str, ...]) -> Chunk | None:
    righe = [r for r in finestra]
    while righe and not righe[0][1].strip():
        righe.pop(0)
    while righe and not righe[-1][1].strip():
        righe.pop()
    if not righe or not any(_parole(t) for _, t in righe):
        return None
    testo = "\n".join(t for _, t in righe)
    return Chunk(percorso, titoli, testo, righe[0][0], righe[-1][0], speaker)


def _paragrafi(righe: list[Riga]) -> list[list[Riga]]:
    out, par = [], []
    for r in righe:
        par.append(r)
        if not r[1].strip():
            out.append(par)
            par = []
    if par:
        out.append(par)
    return out


def _spezza_documento(fonte: Fonte, righe: list[Riga], max_parole: int, overlap: int) -> list[Chunk]:
    sezioni: list[tuple[tuple[str, ...], list[Riga]]] = []
    pila: list[tuple[int, str]] = []
    titoli: tuple[str, ...] = ()
    corrente: list[Riga] = []
    in_codice = False
    for n, riga in righe:
        if RE_FENCE.match(riga):
            in_codice = not in_codice
        m = None if in_codice else RE_TITOLO.match(riga)
        if m:
            sezioni.append((titoli, corrente))
            livello = len(m.group(1))
            pila = [(lv, t) for lv, t in pila if lv < livello] + [(livello, m.group(2))]
            titoli = tuple(t for _, t in pila)
            corrente = []
        else:
            corrente.append((n, riga))
    sezioni.append((titoli, corrente))
    chunks = []
    for tit, righe_sezione in sezioni:
        for finestra in _impacchetta(_paragrafi(righe_sezione), max_parole, overlap):
            c = _crea(fonte.percorso, tit, finestra, ())
            if c:
                chunks.append(c)
    return chunks


def _spezza_trascrizione(fonte: Fonte, righe: list[Riga], max_parole: int) -> list[Chunk]:
    battute: list[list[Riga]] = []
    corrente: list[Riga] = []
    for r in righe:
        if speaker_di(r[1]) and corrente:
            battute.append(corrente)
            corrente = []
        corrente.append(r)
    if corrente:
        battute.append(corrente)
    chunks = []
    for finestra in _impacchetta(battute, max_parole, 0):
        speaker = tuple(dict.fromkeys(s for s in (speaker_di(t) for _, t in finestra) if s))
        c = _crea(fonte.percorso, (), finestra, speaker)
        if c:
            chunks.append(c)
    return chunks


def spezza(fonte: Fonte, max_parole: int, overlap: int) -> list[Chunk]:
    if not fonte.corpo.strip():
        return []
    righe = [(fonte.riga_corpo + i, t) for i, t in enumerate(fonte.corpo.split("\n"))]
    if fonte.meta.tipo == "trascrizione":
        return _spezza_trascrizione(fonte, righe, max_parole)
    return _spezza_documento(fonte, righe, max_parole, overlap)


def chunk_di(config: Config, percorso: str, testo: str) -> tuple[Fonte, list[Chunk]]:
    fonte = analizza(percorso, testo)
    return fonte, spezza(fonte, config.max_parole, config.overlap)
