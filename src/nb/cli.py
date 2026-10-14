"""CLI `nb`: adattatore sottile sul core."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import typer

from nb import hooks, servizi
from nb.config import ConfigError, carica, trova_root
from nb.embedder import crea
from nb.gitutil import GitError
from nb.guardia import controlla
from nb.indice import Indice
from nb.iniziale import InitError, inizializza
from nb.ricerca import Filtri, cerca, formatta_risultati
from nb.vettori import gc as gc_vettori

app = typer.Typer(help="nb: knowledge base del team su git, interrogata da Claude Code.",
                  no_args_is_help=True, add_completion=False)


def _esci(messaggio: str, codice: int) -> None:
    typer.echo(messaggio, err=True)
    raise typer.Exit(codice)


def _indice() -> Indice:
    try:
        config = carica(trova_root(Path.cwd()))
    except ConfigError as e:
        _esci(str(e), 2)
    return Indice(config, crea(config))


def _json(dati) -> None:
    typer.echo(json.dumps(dati, ensure_ascii=False, indent=1, default=str))


@app.command()
def init() -> None:
    """Prepara il knowledge repo corrente (config, hook, template per Claude Code)."""
    try:
        for messaggio in inizializza(Path.cwd()):
            typer.echo(messaggio)
    except InitError as e:
        _esci(str(e), 2)


@app.command()
def index(silenzioso: bool = typer.Option(False, "--silenzioso")) -> None:
    """Aggiorna l'indice locale (solo i file cambiati)."""
    rep = _indice().sync()
    if not silenzioso:
        typer.echo(f"aggiunti {len(rep.aggiunti)}, modificati {len(rep.modificati)}, "
                   f"rimossi {len(rep.rimossi)}, vettori calcolati {len(rep.vettori_nuovi)}")


@app.command()
def search(query: str,
           progetto: str | None = typer.Option(None),
           tipo: str | None = typer.Option(None),
           da: str | None = typer.Option(None, help="data minima AAAA-MM-GG"),
           a: str | None = typer.Option(None, help="data massima AAAA-MM-GG"),
           k: int = typer.Option(8, "-k")) -> None:
    """Cerca nelle fonti."""
    indice = _indice()
    indice.sync()
    risultati = cerca(indice, query, Filtri(progetto, tipo, da, a), k)
    typer.echo(formatta_risultati(risultati) if risultati else "nessun risultato")


@app.command()
def status() -> None:
    """Stato di indice, vettori e remoto."""
    _json(servizi.stato(_indice()))


@app.command()
def check(file: Path) -> None:
    """Controlla se un file è stato modificato sul remoto (exit 1 se sì)."""
    root = _indice().config.root
    try:
        rel = file.resolve().relative_to(root).as_posix()
    except ValueError:
        _esci(f"{file} non è dentro il knowledge repo", 2)
    esito = controlla(root, [rel])
    for a in esito.avvisi:
        typer.echo(f"⚠ {a}")
    if esito.obsoleti:
        _esci("\n".join(o.messaggio() for o in esito.obsoleti), 1)
    typer.echo(f"✓ {rel} aggiornato")


@app.command()
def sync() -> None:
    """git pull + indice + commit/push dei vettori mancanti."""
    try:
        _json(servizi.sincronizza(_indice()))
    except GitError as e:
        _esci(str(e), 1)


@app.command()
def gc() -> None:
    """Rimuove i vettori non più usati da nessun .md presente."""
    indice = _indice()
    indice.sync()
    rimossi = gc_vettori(indice.config.emb_dir, indice.hash_vivi())
    typer.echo(f"rimossi {len(rimossi)} vettori orfani" + (" (ricordati di committare .nb/)" if rimossi else ""))


@app.command()
def reembed(si: bool = typer.Option(False, "--si", help="non chiedere conferma")) -> None:
    """Ricalcola tutti i vettori (dopo un cambio di modello in .nb/config.toml)."""
    indice = _indice()
    config = indice.config
    if not si:
        typer.confirm(f"Cancello .nb/emb e ricalcolo tutti i vettori con {config.model_id}. Procedo?", abort=True)
    indice.close()
    shutil.rmtree(config.emb_dir, ignore_errors=True)
    for suffisso in ("", "-wal", "-shm"):
        Path(f"{config.index_path}{suffisso}").unlink(missing_ok=True)
    rep = Indice(config, crea(config)).sync()
    typer.echo(f"{len(rep.vettori_nuovi)} vettori ricalcolati. Ora: git add -A .nb && "
               "git commit -m 'nb: reembed' && git push")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def hook(ctx: typer.Context, nome: str) -> None:
    """Entry point degli hook (usato da .githooks e da Claude Code)."""
    try:
        root = trova_root(Path.cwd())
    except ConfigError:
        raise typer.Exit(0)  # non è un knowledge repo: niente da controllare
    if nome == "pre-commit":
        codice = hooks.pre_commit(root)
    elif nome == "pre-push":
        codice = hooks.pre_push(root, sys.stdin.read())
    elif nome in ("post-merge", "post-checkout", "post-rewrite"):
        codice = hooks.post_sync(root, nome, list(ctx.args))
    elif nome == "claude-pre-edit":
        codice = hooks.claude_pre_edit(root, sys.stdin.read())
    else:
        typer.echo(f"hook sconosciuto: {nome}", err=True)
        codice = 2
    raise typer.Exit(codice)


@app.command()
def mcp() -> None:
    """Avvia il server MCP su stdio (lanciato da Claude Code via .mcp.json)."""
    from nb.server import serve

    try:
        serve(trova_root(Path.cwd()))
    except ConfigError as e:
        _esci(str(e), 2)
