"""Hook git e Claude Code. Ogni funzione restituisce l'exit code."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from nb.coerenza import emb_tracciati, mancanti_a, richiesti_a
from nb.config import carica
from nb.embedder import crea
from nb.fonti import indicizzabile
from nb.gitutil import GitError, git, git_add, git_bytes, git_dir, in_staging, lista_z
from nb.guardia import EsitoGuardia, controlla
from nb.regole import bloccanti, controlla_file
from nb.vettori import assicura, percorso_rel

NOMI = ("pre-commit", "pre-push", "post-merge", "post-checkout", "post-rewrite")
ZERO = "0" * 40
SCRIPT = """#!/bin/sh
# generato da `nb init`: non modificare a mano
command -v nb >/dev/null 2>&1 || {{ echo "nb non installato: hook {nome} saltato (vedi README)" >&2; exit 0; }}
exec nb hook {nome} "$@"
"""


def _err(*righe: str) -> None:
    for r in righe:
        print(r, file=sys.stderr)


def installa(root: Path) -> None:
    cartella = root / ".githooks"
    cartella.mkdir(exist_ok=True)
    for nome in NOMI:
        p = cartella / nome
        p.write_text(SCRIPT.format(nome=nome), encoding="utf-8", newline="\n")  # sh su Windows: niente CRLF
        p.chmod(0o755)
    git(root, "config", "core.hooksPath", ".githooks")


def _stampa_guardia(esito: EsitoGuardia) -> None:
    _err(*(f"⚠ {a}" for a in esito.avvisi))
    _err(*(o.messaggio() for o in esito.obsoleti))


def pre_commit(root: Path) -> int:
    config = carica(root)
    staged = in_staging(root)
    esiti = []
    for p in staged:
        esiti += controlla_file(p, git_bytes(root, "show", f":{p}"), config.max_file_mb)
    da_guardare = [p for p in staged if not p.startswith(".nb/")]
    guardia = controlla(root, da_guardare) if da_guardare else EsitoGuardia()
    _err(*(str(e) for e in esiti))
    _stampa_guardia(guardia)
    if bloccanti(esiti) or guardia.obsoleti:
        _err("commit bloccato da nb (solo in emergenza: git commit --no-verify)")
        return 1
    richiesti = richiesti_a(config, "", [p for p in staged if indicizzabile(p)])
    if richiesti and _commit_parziale(root):
        # `git commit <file>` usa un indice temporaneo: i vettori aggiunti qui non finirebbero
        # nell'indice vero e il commit successivo li cancellerebbe
        tracciati = emb_tracciati(root, "HEAD")
        senza = sorted({p for h, (p, _) in richiesti.items() if percorso_rel(h) not in tracciati})
        if senza:
            _err("✋ commit parziale (git commit <file>): nb non può aggiungere i vettori nuovi.",
                 f"   Fai: git add {shlex.join(senza)} && git commit")
            return 1
        return 0
    if richiesti:
        assicura(config.emb_dir, crea(config), {h: t for h, (_, t) in richiesti.items()})
        git_add(root, [percorso_rel(h) for h in richiesti])
    return 0


def _commit_parziale(root: Path) -> bool:
    indice = os.environ.get("GIT_INDEX_FILE")
    return bool(indice) and (root / indice).resolve() != (git_dir(root) / "index").resolve()


def _file_da_pushare(root: Path, locale: str, remoto: str) -> list[str]:
    if remoto == ZERO:
        return lista_z(git(root, "log", "--name-only", "-z", "--format=", locale, "--not", "--remotes"))
    return lista_z(git(root, "diff", "--name-only", "-z", "--diff-filter=ACMR", remoto, locale))


def pre_push(root: Path, stdin: str) -> int:
    config = carica(root)
    toccati: set[str] = set()
    senza_vettori: set[str] = set()
    for riga in stdin.splitlines():
        parti = riga.split()
        if len(parti) != 4 or parti[1] == ZERO:
            continue  # riga malformata o cancellazione di branch
        _, locale, _, remoto = parti
        file = [p for p in _file_da_pushare(root, locale, remoto) if not p.startswith(".nb/")]
        toccati.update(file)
        senza_vettori.update(p for p, _ in mancanti_a(config, locale, file).values())
    guardia = controlla(root, sorted(toccati)) if toccati else EsitoGuardia()
    _stampa_guardia(guardia)
    for p in sorted(senza_vettori):
        _err(f"✋ vettori mancanti per {p}: esegui `nb sync` (o ricommitta con gli hook attivi)")
    if guardia.obsoleti or senza_vettori:
        _err("push bloccato da nb")
        return 1
    return 0


def _riepilogo(uscita: str) -> str:
    voci = lista_z(uscita)
    conteggi = {"A": 0, "M": 0, "D": 0, "R": 0}
    i = 0
    while i < len(voci):
        stato = voci[i][0]
        passo = 3 if stato in "RC" else 2
        percorso = voci[i + passo - 1] if i + passo - 1 < len(voci) else ""
        if indicizzabile(percorso):
            conteggi[stato if stato in conteggi else "M"] += 1
        i += passo
    if not any(conteggi.values()):
        return ""
    return (f"nb: fonti {conteggi['A']} nuove, {conteggi['M']} modificate, {conteggi['D']} rimosse, "
            f"{conteggi['R']} spostate — indice in aggiornamento")


def _indicizza_in_background(root: Path) -> None:
    if os.name == "nt":
        staccato = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        staccato = {"start_new_session": True}
    subprocess.Popen([sys.executable, "-m", "nb", "index", "--silenzioso"], cwd=root,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **staccato)


def post_sync(root: Path, nome: str, args: list[str]) -> int:
    if nome == "post-checkout" and (len(args) < 3 or args[2] != "1"):
        return 0  # checkout di singoli file, non di branch
    prima = args[0] if nome == "post-checkout" else "ORIG_HEAD"
    try:
        riepilogo = _riepilogo(git(root, "diff", "--name-status", "-z", prima, "HEAD"))
    except GitError:
        riepilogo = ""
    if riepilogo:
        _err(riepilogo)
    _indicizza_in_background(root)
    return 0


def claude_pre_edit(root: Path, stdin: str) -> int:
    try:
        file_path = json.loads(stdin or "{}").get("tool_input", {}).get("file_path")
    except json.JSONDecodeError:
        return 0
    if not file_path:
        return 0
    try:
        rel = Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return 0
    if not indicizzabile(rel):
        return 0
    esito = controlla(root, [rel])
    if esito.obsoleti:
        _err(esito.obsoleti[0].messaggio(),
             "Prima di modificarlo aggiorna il repo con `git pull --rebase` (chiedi conferma all'utente).")
        return 2
    return 0
