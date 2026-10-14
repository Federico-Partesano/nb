"""Operazioni di alto livello condivise da CLI e server MCP."""
from __future__ import annotations

import json

from nb.chunker import RE_FENCE, RE_TITOLO
from nb.coerenza import mancanti_a, md_tracciati
from nb.config import Config
from nb.fonti import indicizzabile
from nb.gitutil import fetch, git, git_add, in_repo, lista_z, remoti_cambiati, upstream
from nb.indice import Indice
from nb.vettori import assicura, percorso_rel


def stato(indice: Indice) -> dict:
    rep = indice.sync()
    root = indice.config.root
    db = indice.db
    risultato = {
        "file": db.execute("SELECT COUNT(*) FROM file").fetchone()[0],
        "chunk": db.execute("SELECT COUNT(*) FROM chunk").fetchone()[0],
        "modello": indice.config.model_id,
        "appena_sincronizzati": {"aggiunti": rep.aggiunti, "modificati": rep.modificati, "rimossi": rep.rimossi},
        "upstream": None,
        "vettori_non_committati": 0,
        "modificati_sul_remoto": [],
        "avvisi": indice.avvisi(),
    }
    if in_repo(root):
        risultato["vettori_non_committati"] = len(lista_z(
            git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", ".nb/emb")))
        risultato["upstream"] = upstream(root)
        if risultato["upstream"]:
            errore = fetch(root)
            if errore:
                risultato["avvisi"]["(git)"] = [f"fetch non riuscito: {errore}"]
            risultato["modificati_sul_remoto"] = remoti_cambiati(root)
    return risultato


def elenca(indice: Indice, progetto: str | None = None, tipo: str | None = None) -> list[dict]:
    indice.sync()
    cond, par = [], []
    if progetto:
        cond.append("f.progetto = ?")
        par.append(progetto)
    if tipo:
        cond.append("f.tipo = ?")
        par.append(tipo)
    sql = ("SELECT f.percorso, f.tipo, f.progetto, f.data, f.partecipanti, COUNT(c.id) "
           "FROM file f LEFT JOIN chunk c ON c.percorso = f.percorso"
           + (" WHERE " + " AND ".join(cond) if cond else "")
           + " GROUP BY f.percorso ORDER BY f.percorso")
    return [{"percorso": p, "tipo": t, "progetto": pr, "data": d, "partecipanti": json.loads(pa), "chunk": n}
            for p, t, pr, d, pa, n in indice.db.execute(sql, par)]


def leggi(config: Config, percorso: str, sezione: str | None = None) -> str:
    root = config.root
    p = (root / percorso).resolve()
    if not p.is_relative_to(root) or not indicizzabile(percorso) or not p.is_file():
        raise ValueError(f"fonte non trovata: {percorso}")
    testo = p.read_text(encoding="utf-8", errors="replace")
    if not sezione:
        return testo
    cercato = sezione.split("›")[-1].strip().lower()
    righe = testo.split("\n")
    inizio, livello, titoli, in_codice = None, 0, [], False
    for i, riga in enumerate(righe):
        if RE_FENCE.match(riga):
            in_codice = not in_codice
            continue
        m = None if in_codice else RE_TITOLO.match(riga)
        if not m:
            continue
        titoli.append(m.group(2))
        if inizio is None and m.group(2).strip().lower() == cercato:
            inizio, livello = i, len(m.group(1))
        elif inizio is not None and len(m.group(1)) <= livello:
            return "\n".join(righe[inizio:i]).rstrip() + "\n"
    if inizio is None:
        raise ValueError(f"sezione '{sezione}' non trovata in {percorso}. Sezioni: {', '.join(titoli)}")
    return "\n".join(righe[inizio:]).rstrip() + "\n"


def sincronizza(indice: Indice) -> dict:
    """git pull + indice + commit/push dei vettori mancanti per i .md già committati."""
    config = indice.config
    root = config.root
    up = upstream(root)
    if up:
        git(root, "pull", "--rebase", "--autostash", "--quiet")
    rep = indice.sync()
    mancanti = mancanti_a(config, "HEAD", md_tracciati(root))
    pushato = False
    if mancanti:
        assicura(config.emb_dir, indice.embedder, {h: t for h, (_, t) in mancanti.items()})
        git_add(root, [percorso_rel(h) for h in mancanti])
        git(root, "commit", "--no-verify", "--quiet", "-m", f"nb: {len(mancanti)} vettori mancanti",
            "--only", "--", ".nb/emb")
        if up:
            git(root, "push", "--quiet")
            pushato = True
    return {"aggiunti": rep.aggiunti, "modificati": rep.modificati, "rimossi": rep.rimossi,
            "vettori_committati": len(mancanti), "pushato": pushato}
