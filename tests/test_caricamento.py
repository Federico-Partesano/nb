import pytest
from aiuti import commit_e_push, g, scrivi

from nb.caricamento import CaricamentoError, VocePiano, carica_fonti, componi, proponi
from nb.config import carica, scrivi_default
from nb.embedder import crea
from nb.indice import Indice


def indice_di(root):
    c = carica(root)
    return Indice(c, crea(c))


def sorgente(tmp_path, nome, testo):
    p = tmp_path / "in" / nome
    p.parent.mkdir(exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return str(p)


def test_componi_unisce_frontmatter():
    out = componi("---\ntipo: analisi\nprogetto: x\n---\n\ncorpo", {"progetto": "y", "data": None})
    assert out == "---\ntipo: analisi\nprogetto: y\n---\ncorpo\n"
    assert componi("corpo\n", {}) == "corpo\n"


def test_proponi_trova_simili_e_duplicato(repo_condiviso, tmp_path):
    s = sorgente(tmp_path, "x.md", "# Benvenuto\n\nCiao team.\n")
    out = proponi(indice_di(repo_condiviso.a), [s, str(tmp_path / "manca.md")])
    p = out["proposte"][0]
    assert p["simili"][0]["percorso"] == "generale/benvenuto.md"
    assert p["probabile_duplicato"] == "generale/benvenuto.md"
    assert p["titolo"] == "Benvenuto"
    assert "errore" in out["proposte"][1]
    assert "progetti/" in out["convenzioni"]


def test_carica_crea_commit_e_push(repo_condiviso, tmp_path):
    r = repo_condiviso
    s = sorgente(tmp_path, "trascr.md", "**Marco**: decidiamo Keycloak\n")
    piano = [VocePiano(s, "progetti/portale/call/2026-10-14-review-sso.md",
                       {"tipo": "trascrizione", "partecipanti": ["Marco"]})]
    esito = carica_fonti(indice_di(r.a), piano, messaggio="nb: review sso")
    assert esito["pushato"] is True
    g(r.b, "pull", "-q")
    testo = (r.b / "progetti/portale/call/2026-10-14-review-sso.md").read_text()
    assert testo.startswith("---\ntipo: trascrizione\n") and "Keycloak" in testo
    assert any(p.startswith(".nb/emb/") for p in g(r.b, "ls-files").split())
    assert g(r.b, "log", "-1", "--format=%s").strip() == "nb: review sso"


def test_carica_rifiuta_nome_call_sbagliato(repo_condiviso, tmp_path):
    r = repo_condiviso
    s = sorgente(tmp_path, "t.md", "**Marco**: ciao\n")
    with pytest.raises(CaricamentoError, match="AAAA-MM-GG"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "progetti/p/call/Review.md", {})])
    assert not (r.a / "progetti/p/call/Review.md").exists()


def test_carica_rifiuta_destinazione_fuori_repo(repo_condiviso, tmp_path):
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="destinazione non valida"):
        carica_fonti(indice_di(repo_condiviso.a), [VocePiano(s, "../fuori.md", {})])


def test_carica_rifiuta_esistente_senza_aggiorna(repo_condiviso, tmp_path):
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="esiste già"):
        carica_fonti(indice_di(repo_condiviso.a), [VocePiano(s, "generale/benvenuto.md", {})])


def test_carica_aggiorna(repo_condiviso, tmp_path):
    r = repo_condiviso
    s = sorgente(tmp_path, "t.md", "# Benvenuto\n\nVersione 2.\n")
    carica_fonti(indice_di(r.a), [VocePiano(s, "generale/benvenuto.md", {}, aggiorna=True)])
    assert "Versione 2" in (r.a / "generale/benvenuto.md").read_text()


def test_staging_sporco_rifiutato(repo_condiviso, tmp_path):
    r = repo_condiviso
    scrivi(r.a, "generale/altro.md", "x\n")
    g(r.a, "add", "-A")
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="staging"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "generale/nuovo.md", {})])


def test_push_rifiutato_rollback(repo_condiviso, tmp_path):
    r = repo_condiviso
    hook = r.remoto / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    base = g(r.a, "rev-parse", "HEAD").strip()
    s = sorgente(tmp_path, "t.md", "# Nuovo\ncontenuto unico del rollback\n")
    with pytest.raises(CaricamentoError, match="push rifiutato"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "progetti/z/analisi/nuovo.md", {})])
    assert g(r.a, "rev-parse", "HEAD").strip() == base
    assert not (r.a / "progetti").exists()
    assert g(r.a, "diff", "--cached", "--name-only").strip() == ""


def test_senza_upstream_commit_locale(tmp_path):
    root = (tmp_path / "solo").resolve()
    root.mkdir()
    g(root, "init", "-q", "-b", "main")
    g(root, "config", "user.name", "Marco")
    g(root, "config", "user.email", "marco@esempio.it")
    g(root, "config", "commit.gpgsign", "false")
    scrivi_default(root)
    scrivi(root, ".gitignore", ".nb/index.db*\n")
    g(root, "add", "-A")
    g(root, "commit", "-qm", "init")
    s = sorgente(tmp_path, "t.md", "ciao\n")
    esito = carica_fonti(indice_di(root), [VocePiano(s, "generale/a.md", {})])
    assert esito["pushato"] is False
    assert any("upstream" in a for a in esito["avvisi"])


def test_staging_con_cancellazione_rifiutato(repo_condiviso, tmp_path):
    r = repo_condiviso
    g(r.a, "rm", "-q", "generale/benvenuto.md")
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="staging"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "generale/nuovo.md", {})])


def test_remoto_irraggiungibile_senza_push_committa(repo_condiviso, tmp_path):
    r = repo_condiviso
    g(r.a, "remote", "set-url", "origin", str(r.remoto) + "-sparito")
    s = sorgente(tmp_path, "t.md", "ciao offline\n")
    esito = carica_fonti(indice_di(r.a), [VocePiano(s, "generale/offline.md", {})], push=False)
    assert esito["pushato"] is False
    assert any("remoto non raggiungibile" in a for a in esito["avvisi"])
    assert g(r.a, "log", "-1", "--format=%s").strip() == "nb: carica generale/offline.md"


def test_remoto_irraggiungibile_con_push_errore_chiaro(repo_condiviso, tmp_path):
    r = repo_condiviso
    g(r.a, "remote", "set-url", "origin", str(r.remoto) + "-sparito")
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="remoto non raggiungibile"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "generale/offline.md", {})])
    assert not (r.a / "generale/offline.md").exists()


def test_pull_in_conflitto_annulla_rebase(repo_condiviso, tmp_path):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "# Benvenuto\n\nversione B\n", "b")
    scrivi(r.a, "generale/benvenuto.md", "# Benvenuto\n\nversione A\n")
    g(r.a, "commit", "-qam", "a locale")
    s = sorgente(tmp_path, "t.md", "ciao\n")
    with pytest.raises(CaricamentoError, match="commit locali"):
        carica_fonti(indice_di(r.a), [VocePiano(s, "generale/x.md", {})])
    assert not (r.a / ".git/rebase-merge").exists() and not (r.a / ".git/rebase-apply").exists()
    assert g(r.a, "log", "-1", "--format=%s").strip() == "a locale"
