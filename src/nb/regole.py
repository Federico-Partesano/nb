"""Regole di validazione condivise da hook git e caricamento."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from nb.config import CARTELLA_TIPO, TIPI
from nb.fonti import separa_frontmatter

RE_CALL = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
RE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
RE_CONFLITTO = re.compile(r"^(?:<{7}|>{7})(?: |$)", re.M)
SEGRETI_CERTI = (
    ("chiave privata", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("token GitLab", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("chiave Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("token Slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
)
RE_SEGRETO_PROBABILE = re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+")
ESTENSIONI_BINARIE = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi",
    ".png", ".jpg", ".jpeg", ".gif", ".heic", ".zip", ".7z", ".rar", ".tar", ".gz",
})
ESENTI = frozenset({"README.md", "CLAUDE.md", ".gitignore", ".mcp.json"})
PREFISSI_ESENTI = (".nb/", ".githooks/", ".claude/")


@dataclass(frozen=True)
class Esito:
    livello: str  # "blocco" | "avviso"
    percorso: str
    messaggio: str

    def __str__(self) -> str:
        simbolo = "✋" if self.livello == "blocco" else "⚠"
        return f"{simbolo} {self.percorso}: {self.messaggio}"


def bloccanti(esiti: list[Esito]) -> list[Esito]:
    return [e for e in esiti if e.livello == "blocco"]


def _esente(percorso: str) -> bool:
    return percorso in ESENTI or percorso.startswith(PREFISSI_ESENTI)


def controlla_percorso(percorso: str) -> list[Esito]:
    if _esente(percorso) or not percorso.endswith(".md"):
        return []
    parti = PurePosixPath(percorso).parts
    nome = parti[-1]
    in_progetto = len(parti) >= 4 and parti[0] == "progetti" and parti[2] in CARTELLA_TIPO
    in_generale = len(parti) >= 2 and parti[0] == "generale"
    esiti = []
    if not (in_progetto or in_generale):
        esiti.append(Esito("avviso", percorso,
            "fuori dalla struttura prevista: progetti/<progetto>/{analisi,documentazione,call}/ oppure generale/"))
    if in_progetto and parti[2] == "call":
        if not RE_CALL.match(nome):
            esiti.append(Esito("blocco", percorso,
                "le trascrizioni si chiamano AAAA-MM-GG-titolo.md (minuscolo, trattini)"))
    elif not RE_SLUG.match(nome):
        esiti.append(Esito("avviso", percorso, "nome consigliato: minuscolo-con-trattini.md"))
    return esiti


def controlla_md(percorso: str, testo: str) -> list[Esito]:
    esiti = []
    fm, _, _, errore = separa_frontmatter(testo)
    if errore:
        esiti.append(Esito("blocco", percorso, errore))
    elif fm and "tipo" in fm and fm["tipo"] not in TIPI:
        esiti.append(Esito("blocco", percorso, f"tipo '{fm['tipo']}' non ammesso (ammessi: {', '.join(TIPI)})"))
    if RE_CONFLITTO.search(testo):
        esiti.append(Esito("blocco", percorso, "marcatori di conflitto git (<<<<<<< / >>>>>>>) nel testo"))
    for nome, rx in SEGRETI_CERTI:
        if rx.search(testo):
            esiti.append(Esito("blocco", percorso, f"possibile segreto ({nome}): rimuovilo prima di committare"))
    if RE_SEGRETO_PROBABILE.search(testo):
        esiti.append(Esito("avviso", percorso, "possibile credenziale nel testo (password/token): controlla"))
    return esiti


def controlla_file(percorso: str, dati: bytes, max_file_mb: float) -> list[Esito]:
    if percorso.startswith(".nb/"):
        return []
    if PurePosixPath(percorso).suffix.lower() in ESTENSIONI_BINARIE:
        return [Esito("blocco", percorso, "file binario: nel repo vanno solo .md (gli originali restano fuori)")]
    esiti = []
    if len(dati) > max_file_mb * 1024 * 1024:
        esiti.append(Esito("blocco", percorso, f"file oltre {max_file_mb:g} MB"))
    if percorso.endswith(".md"):
        esiti += controlla_percorso(percorso)
        esiti += controlla_md(percorso, dati.decode("utf-8", errors="replace"))
    elif not _esente(percorso):
        esiti.append(Esito("avviso", percorso, "non è un .md: non verrà indicizzato"))
    return esiti
