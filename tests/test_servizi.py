import pytest
from aiuti import g, scrivi

from nb.config import carica
from nb.embedder import crea
from nb.indice import Indice
from nb.servizi import elenca, leggi, sincronizza, stato


def indice_di(root):
    c = carica(root)
    return Indice(c, crea(c))


def test_leggi_intero_e_sezione(kb):
    scrivi(kb, "generale/a.md", "# A\nuno\n## B\ndue\n# C\ntre\n")
    c = carica(kb)
    assert leggi(c, "generale/a.md").startswith("# A")
    sezione = leggi(c, "generale/a.md", "A › B")
    assert "due" in sezione and "tre" not in sezione
    assert "tre" not in leggi(c, "generale/a.md", "A")


def test_leggi_errori(kb):
    scrivi(kb, "generale/a.md", "# A\nuno\n")
    c = carica(kb)
    with pytest.raises(ValueError, match="fonte non trovata"):
        leggi(c, "../fuori.md")
    with pytest.raises(ValueError, match="fonte non trovata"):
        leggi(c, "generale/manca.md")
    with pytest.raises(ValueError, match="Sezioni: A"):
        leggi(c, "generale/a.md", "Zeta")


def test_elenca_con_filtri(kb):
    scrivi(kb, "progetti/p/analisi/a.md", "# A\nuno\n")
    scrivi(kb, "progetti/q/call/2026-10-01-x.md", "Marco: ciao\n")
    ind = indice_di(kb)
    assert [f["percorso"] for f in elenca(ind)] == ["progetti/p/analisi/a.md", "progetti/q/call/2026-10-01-x.md"]
    assert [f["percorso"] for f in elenca(ind, tipo="trascrizione")] == ["progetti/q/call/2026-10-01-x.md"]
    assert elenca(ind, progetto="p")[0]["chunk"] == 1


def test_stato_fuori_da_git(kb):
    scrivi(kb, "generale/a.md", "---\ntipo: boh\n---\nx\n")
    s = stato(indice_di(kb))
    assert s["file"] == 1 and s["upstream"] is None
    assert "generale/a.md" in s["avvisi"]


def test_stato_vede_modifiche_remote(repo_condiviso):
    r = repo_condiviso
    scrivi(r.b, "generale/nuova.md", "x\n")
    g(r.b, "add", "-A")
    g(r.b, "commit", "-qm", "nuova")
    g(r.b, "push", "-q")
    s = stato(indice_di(r.a))
    assert s["modificati_sul_remoto"] == ["generale/nuova.md"]


def test_sincronizza_committa_vettori_mancanti(repo_condiviso):
    r = repo_condiviso
    esito = sincronizza(indice_di(r.a))
    assert esito["vettori_committati"] > 0 and esito["pushato"] is True
    g(r.b, "pull", "-q")
    assert any(p.startswith(".nb/emb/") for p in g(r.b, "ls-files").split())
    assert sincronizza(indice_di(r.a))["vettori_committati"] == 0
