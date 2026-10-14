"""Caricamento guidato: proposta di collocazione (contesto per Claude) ed esecuzione del piano."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

import yaml

from nb.chunker import RE_TITOLO, chunk_di
from nb.config import CARTELLA_TIPO, Config
from nb.fonti import indicizzabile, separa_frontmatter
from nb.gitutil import GitError, git, git_add, in_staging, lista_z, upstream
from nb.guardia import controlla
from nb.indice import Indice
from nb.regole import bloccanti, controlla_md, controlla_percorso
from nb.ricerca import simili
from nb.vettori import chiave, percorso_rel

SOGLIA_DUPLICATO = 0.8
CONVENZIONI = (
    "Cartelle: progetti/<progetto>/analisi|documentazione|call/ oppure generale/. "
    "Nomi: minuscolo-con-trattini.md; trascrizioni AAAA-MM-GG-titolo.md dentro call/. "
    "Frontmatter: tipo (analisi|documentazione|trascrizione|altro), progetto, data AAAA-MM-GG, "
    "partecipanti (solo trascrizioni). Preferisci la cartella dei documenti più simili; "
    "probabile duplicato → proponi aggiorna=true sul file esistente; nuovo progetto solo con conferma esplicita."
)


class CaricamentoError(RuntimeError):
    pass


@dataclass(frozen=True)
class VocePiano:
    sorgente: str
    destinazione: str
    frontmatter: dict = field(default_factory=dict)
    aggiorna: bool = False


def componi(originale: str, frontmatter: dict) -> str:
    fm, corpo, _, _ = separa_frontmatter(originale)
    unito = {k: v for k, v in {**(fm or {}), **frontmatter}.items() if v not in (None, "", [])}
    corpo = corpo.lstrip("\n")
    if not corpo.endswith("\n"):
        corpo += "\n"
    if not unito:
        return corpo
    return "---\n" + yaml.safe_dump(unito, allow_unicode=True, sort_keys=False) + "---\n" + corpo


def _titolo(corpo: str) -> str | None:
    for riga in corpo.split("\n"):
        m = RE_TITOLO.match(riga)
        if m:
            return m.group(2)
    return None


def proponi(indice: Indice, sorgenti: list[str]) -> dict:
    indice.sync()
    cartella_progetti = indice.config.root / "progetti"
    progetti = sorted(p.name for p in cartella_progetti.iterdir() if p.is_dir()) if cartella_progetti.is_dir() else []
    proposte = []
    for s in sorgenti:
        percorso = Path(s).expanduser()
        try:
            testo = percorso.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            proposte.append({"sorgente": s, "errore": f"illeggibile: {e}"})
            continue
        fm, corpo, _, _ = separa_frontmatter(testo)
        sim = simili(indice, percorso.name, corpo)
        proposte.append({
            "sorgente": s,
            "titolo": _titolo(corpo) or percorso.stem,
            "parole": len(corpo.split()),
            "frontmatter_presente": json.loads(json.dumps(fm or {}, default=str)),
            "simili": [asdict(x) for x in sim],
            "probabile_duplicato": next((x.percorso for x in sim if x.copertura >= SOGLIA_DUPLICATO), None),
        })
    return {"proposte": proposte, "progetti": progetti, "cartelle": list(CARTELLA_TIPO), "convenzioni": CONVENZIONI}


def _vettori_richiesti(config: Config, contenuti: dict[str, str]) -> list[str]:
    rel = set()
    for dest, testo in contenuti.items():
        _, chunks = chunk_di(config, dest, testo)
        rel.update(percorso_rel(chiave(config.model_id, c.testo_embed)) for c in chunks)
    return sorted(rel)


def _messaggio(contenuti: dict[str, str]) -> str:
    if len(contenuti) == 1:
        return f"nb: carica {next(iter(contenuti))}"
    return f"nb: carica {len(contenuti)} fonti"


def _pota(root: Path, p: Path) -> None:
    d = p.parent
    while d != root and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def _ripristina(indice: Indice, base: str, contenuti: dict[str, str], creati: list[str],
                vettori: list[str], nuovi: list[Path]) -> None:
    root = indice.config.root
    try:
        git(root, "reset", "--quiet")  # lo staging era vuoto prima di iniziare
    except GitError:
        pass
    for d in contenuti:
        if d in creati:
            (root / d).unlink(missing_ok=True)
            _pota(root, root / d)
        else:
            git(root, "restore", "--source", base, "--worktree", "--", d)
    nuovi_set = set(nuovi)
    for rel in vettori:
        p = root / rel
        if p in nuovi_set:
            p.unlink(missing_ok=True)
    indice.sync()


def _valida(indice: Indice, piano: list[VocePiano]) -> tuple[dict[str, str], dict[str, bool], list]:
    contenuti: dict[str, str] = {}
    aggiorna: dict[str, bool] = {}
    esiti = []
    for v in piano:
        dest = v.destinazione.strip()
        if dest.startswith("/") or ".." in PurePosixPath(dest).parts or not indicizzabile(dest):
            raise CaricamentoError(f"destinazione non valida: {dest!r} (percorso relativo .md, fuori da cartelle nascoste)")
        if dest in contenuti:
            raise CaricamentoError(f"destinazione ripetuta nel piano: {dest}")
        try:
            originale = Path(v.sorgente).expanduser().read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise CaricamentoError(f"sorgente illeggibile: {v.sorgente} ({e})") from None
        contenuti[dest] = componi(originale, v.frontmatter)
        aggiorna[dest] = v.aggiorna
        esiti += controlla_percorso(dest) + controlla_md(dest, contenuti[dest])
    blocchi = bloccanti(esiti)
    if blocchi:
        raise CaricamentoError("\n".join(map(str, blocchi)))
    return contenuti, aggiorna, esiti


def carica_fonti(indice: Indice, piano: list[VocePiano], messaggio: str | None = None, push: bool = True) -> dict:
    root = indice.config.root
    if not piano:
        raise CaricamentoError("piano vuoto")
    contenuti, aggiorna, esiti = _valida(indice, piano)
    if in_staging(root):
        raise CaricamentoError("ci sono già file in staging: committali o toglili (git restore --staged) prima di caricare")
    sporchi = lista_z(git(root, "status", "--porcelain", "-z", "--", *contenuti))
    if sporchi:
        raise CaricamentoError("modifiche locali non committate su: " + ", ".join(s[3:] for s in sporchi))
    up = upstream(root)
    if up:
        git(root, "pull", "--rebase", "--autostash", "--quiet")
    base = git(root, "rev-parse", "HEAD").strip()
    for dest in contenuti:
        esiste = (root / dest).exists()
        if esiste and not aggiorna[dest]:
            raise CaricamentoError(f"{dest} esiste già: usa aggiorna=true oppure un altro nome")
        if aggiorna[dest] and not esiste:
            raise CaricamentoError(f"{dest} non esiste: niente da aggiornare")
    creati = [d for d in contenuti if not (root / d).exists()]
    vettori = _vettori_richiesti(indice.config, contenuti)
    nuovi: list[Path] = []
    try:
        for dest, testo in contenuti.items():
            (root / dest).parent.mkdir(parents=True, exist_ok=True)
            (root / dest).write_text(testo, encoding="utf-8")
        nuovi = indice.sync().vettori_nuovi
        obsoleti = controlla(root, list(contenuti), fai_fetch=False).obsoleti
        if obsoleti:
            raise CaricamentoError("\n".join(o.messaggio() for o in obsoleti))
        git_add(root, [*contenuti, *vettori])
        git(root, "commit", "--no-verify", "--quiet", "-m", messaggio or _messaggio(contenuti))
    except Exception:
        _ripristina(indice, base, contenuti, creati, vettori, nuovi)
        raise
    commit = git(root, "rev-parse", "--short", "HEAD").strip()
    pushato = False
    if push and up:
        try:
            git(root, "push", "--quiet")
        except GitError as e:
            git(root, "reset", "--quiet", "--mixed", base)
            _ripristina(indice, base, contenuti, creati, vettori, nuovi)
            raise CaricamentoError(f"push rifiutato, caricamento annullato: {e}") from None
        pushato = True
    avvisi = [str(e) for e in esiti]
    if not up:
        avvisi.append("branch senza upstream: commit solo locale, nessun push")
    return {"commit": commit, "pushato": pushato, "file": list(contenuti), "avvisi": avvisi}
