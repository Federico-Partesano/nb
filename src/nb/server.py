"""Server MCP: adattatore sottile per Claude Code."""
from __future__ import annotations

import functools
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from nb import caricamento, ricerca, servizi
from nb.config import carica
from nb.embedder import crea
from nb.gitutil import GitError
from nb.indice import Indice

ISTRUZIONI = (
    "Motore di ricerca della knowledge base del team (analisi, documentazione, trascrizioni di call). "
    "Usa `cerca` prima di rispondere e cita sempre `percorso › sezione`; se le fonti non contengono "
    "la risposta dillo. Per caricare file: `proponi_collocazione`, mostra il piano, attendi conferma "
    "esplicita, poi `carica_fonti`."
)


def _json(dati) -> str:
    return json.dumps(dati, ensure_ascii=False, indent=1, default=str)


@contextmanager
def _errore_leggibile() -> Iterator[None]:
    """Gli errori attesi arrivano a Claude con il loro messaggio, non come errore generico."""
    try:
        yield
    except (ValueError, OSError, GitError, caricamento.CaricamentoError) as e:
        raise ToolError(str(e)) from e


def _in_serie(registra, lock):
    def decoratore(funzione):
        @functools.wraps(funzione)
        def avvolta(*args, **kwargs):
            with lock:
                return funzione(*args, **kwargs)
        return registra(avvolta)
    return decoratore


def crea_server(root: Path) -> MCPServer:
    config = carica(root)
    indice = Indice(config, crea(config))
    indice.sync()
    server = MCPServer("nb", instructions=ISTRUZIONI)
    # l'SDK esegue i tool sincroni in thread: una chiamata alla volta sull'indice condiviso

    def tool():
        return _in_serie(server.tool(), indice.lock)


    @tool()
    def cerca(query: str, progetto: str | None = None, tipo: str | None = None,
              da: str | None = None, a: str | None = None, k: int = 8) -> str:
        """Cerca nelle fonti del team (semantica + parole chiave). Filtri facoltativi: progetto,
        tipo (analisi | documentazione | trascrizione | altro), da/a (date AAAA-MM-GG, incluse).
        Ogni risultato inizia con la citazione `percorso › sezione` da riportare nella risposta."""
        indice.sync()
        risultati = ricerca.cerca(indice, query, ricerca.Filtri(progetto, tipo, da, a), k)
        return ricerca.formatta_risultati(risultati) if risultati else "nessun risultato nelle fonti"

    @tool()
    def leggi_fonte(percorso: str, sezione: str | None = None) -> str:
        """Testo completo di una fonte, o di una sola sezione (titolo, anche nel formato `A › B`)."""
        with _errore_leggibile():
            return servizi.leggi(config, percorso, sezione)

    @tool()
    def elenca_fonti(progetto: str | None = None, tipo: str | None = None) -> str:
        """Elenco delle fonti con tipo, progetto, data, partecipanti e numero di chunk."""
        return _json(servizi.elenca(indice, progetto, tipo))

    @tool()
    def stato() -> str:
        """Stato dell'indice, vettori non committati, file modificati sul remoto e avvisi sui frontmatter."""
        with _errore_leggibile():
            return _json(servizi.stato(indice))

    @tool()
    def proponi_collocazione(file: list[str]) -> str:
        """Contesto per decidere dove caricare dei .md locali: documenti simili con la loro cartella,
        probabili duplicati, progetti esistenti e convenzioni. Non scrive nulla."""
        with _errore_leggibile():
            return _json(caricamento.proponi(indice, file))

    @tool()
    def carica_fonti(piano: list[dict], messaggio: str | None = None, push: bool = True) -> str:
        """Scrive i file del piano nel repo, calcola i vettori, fa UN commit e il push.
        Chiamalo SOLO dopo la conferma esplicita dell'utente sul piano.
        Ogni voce: {sorgente, destinazione, frontmatter, aggiorna}. In caso di errore annulla tutto."""
        with _errore_leggibile():
            voci = [caricamento.VocePiano(sorgente=v["sorgente"], destinazione=v["destinazione"],
                                          frontmatter=v.get("frontmatter") or {},
                                          aggiorna=bool(v.get("aggiorna", False))) for v in piano]
            return _json(caricamento.carica_fonti(indice, voci, messaggio, push))

    return server


def serve(root: Path) -> None:
    crea_server(root).run()
