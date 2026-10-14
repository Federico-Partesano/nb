from aiuti import scrivi

from nb.config import carica
from nb.embedder import FakeEmbedder
from nb.indice import Indice
from nb.ricerca import Filtri, cerca, formatta_risultati, simili

AUTH = "# Auth\n## SSO\nIl login usa Keycloak come provider SSO aziendale.\n## Password\nReset password via email.\n"


def popola(kb):
    scrivi(kb, "progetti/portale/analisi/auth.md", AUTH)
    scrivi(kb, "progetti/portale/call/2026-10-03-review.md",
           "**Marco** [00:01:00]: decidiamo Keycloak per il single sign on\n**Giulia** [00:02:00]: ok, procedo\n")
    scrivi(kb, "progetti/gestionale/documentazione/fatture.md", "# Fatture\nLe fatture si esportano in XML.\n")
    c = carica(kb)
    ind = Indice(c, FakeEmbedder(c.model_id, c.dim))
    ind.sync()
    return ind


def test_trova_per_parola_chiave(kb):
    r = cerca(popola(kb), "Keycloak")
    assert {x.percorso for x in r[:2]} == {
        "progetti/portale/analisi/auth.md", "progetti/portale/call/2026-10-03-review.md"}


def test_citazione(kb):
    r = cerca(popola(kb), "provider SSO Keycloak")
    assert r[0].citazione == "progetti/portale/analisi/auth.md › Auth › SSO"


def test_filtro_progetto(kb):
    r = cerca(popola(kb), "fatture XML", Filtri(progetto="portale"))
    assert r and all(x.progetto == "portale" for x in r)


def test_filtro_tipo_e_date(kb):
    ind = popola(kb)
    r = cerca(ind, "Keycloak", Filtri(tipo="trascrizione", da="2026-10-01", a="2026-10-31"))
    assert [x.percorso for x in r] == ["progetti/portale/call/2026-10-03-review.md"]
    assert r[0].speaker == ("Marco", "Giulia")
    assert cerca(ind, "Keycloak", Filtri(da="2026-11-01")) == []


def test_query_con_caratteri_speciali(kb):
    ind = popola(kb)
    for q in ['"Keycloak', "C++ -flag: *", "AND OR NOT", "(", "", "NEAR(a b)"]:
        cerca(ind, q)


def test_k(kb):
    assert len(cerca(popola(kb), "il", k=2)) == 2


def test_indice_vuoto(kb):
    c = carica(kb)
    ind = Indice(c, FakeEmbedder(c.model_id, c.dim))
    ind.sync()
    assert cerca(ind, "qualsiasi") == []


def test_formatta(kb):
    testo = formatta_risultati(cerca(popola(kb), "provider SSO Keycloak", k=1))
    assert testo.startswith("[1] progetti/portale/analisi/auth.md › Auth › SSO")
    assert "Keycloak" in testo


def test_simili_trova_duplicato(kb):
    s = simili(popola(kb), "nuovo.md", AUTH)
    assert s[0].percorso == "progetti/portale/analisi/auth.md"
    assert s[0].copertura == 1.0 and s[0].similarita > 0.99


def test_simili_indice_vuoto(kb):
    c = carica(kb)
    ind = Indice(c, FakeEmbedder(c.model_id, c.dim))
    ind.sync()
    assert simili(ind, "x.md", "ciao") == []


def test_cerca_dopo_sync_di_altro_processo(kb):
    ind = popola(kb)
    cerca(ind, "Keycloak")
    p = kb / "progetti/gestionale/documentazione/fatture.md"
    p.write_text("# Fatture\nOra in formato JSON unico\n")
    c = carica(kb)
    altro = Indice(c, FakeEmbedder(c.model_id, c.dim))
    altro.sync()
    altro.close()
    ind.sync()
    r = cerca(ind, "JSON unico")
    assert r[0].percorso == "progetti/gestionale/documentazione/fatture.md"
