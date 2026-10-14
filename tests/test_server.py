import asyncio
import json

import pytest
from aiuti import g, scrivi

from nb.server import crea_server


def chiama(server, nome, argomenti):
    risultato = asyncio.run(server.call_tool(nome, argomenti))
    testo = "\n".join(getattr(c, "text", "") for c in risultato.content)
    if risultato.is_error:
        raise RuntimeError(testo)
    return testo


def test_tool_esposti(kb):
    nomi = {t.name for t in asyncio.run(crea_server(kb).list_tools())}
    assert nomi == {"cerca", "leggi_fonte", "elenca_fonti", "stato", "proponi_collocazione", "carica_fonti"}


def test_cerca(kb):
    scrivi(kb, "generale/a.md", "# A\nIl provider è Keycloak\n")
    s = crea_server(kb)
    assert "generale/a.md › A" in chiama(s, "cerca", {"query": "Keycloak"})
    scrivi(kb, "generale/b.md", "# B\nNuovo file dopo l'avvio: Grafana\n")
    assert "generale/b.md › B" in chiama(s, "cerca", {"query": "Grafana"})  # auto-sync


def test_cerca_vuoto(kb):
    assert "nessun risultato" in chiama(crea_server(kb), "cerca", {"query": "x"})


def test_leggi_fonte(kb):
    scrivi(kb, "generale/a.md", "# A\nuno\n## B\ndue\n# C\ntre\n")
    out = chiama(crea_server(kb), "leggi_fonte", {"percorso": "generale/a.md", "sezione": "A › B"})
    assert "due" in out and "tre" not in out


def test_leggi_fonte_fuori_repo(kb):
    with pytest.raises(Exception, match="fonte non trovata"):
        chiama(crea_server(kb), "leggi_fonte", {"percorso": "../segreti.md"})


def test_elenca_e_stato(kb):
    scrivi(kb, "progetti/p/analisi/a.md", "# A\nuno\n")
    s = crea_server(kb)
    assert json.loads(chiama(s, "elenca_fonti", {"progetto": "p"}))[0]["percorso"] == "progetti/p/analisi/a.md"
    assert json.loads(chiama(s, "stato", {}))["file"] == 1


def test_proponi_e_carica(repo_condiviso, tmp_path):
    r = repo_condiviso
    sorgente = tmp_path / "nota.md"
    sorgente.write_text("# Nota\nDecisione: usiamo Keycloak.\n")
    s = crea_server(r.a)
    proposta = json.loads(chiama(s, "proponi_collocazione", {"file": [str(sorgente)]}))
    assert proposta["proposte"][0]["titolo"] == "Nota"
    piano = [{"sorgente": str(sorgente), "destinazione": "generale/nota.md", "frontmatter": {"tipo": "altro"}}]
    esito = json.loads(chiama(s, "carica_fonti", {"piano": piano}))
    assert esito["pushato"] is True
    g(r.b, "pull", "-q")
    assert (r.b / "generale/nota.md").exists()
