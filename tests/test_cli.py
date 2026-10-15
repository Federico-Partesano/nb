import numpy as np
from aiuti import commit_e_push, g, scrivi
from typer.testing import CliRunner

from nb.cli import app
from nb.vettori import scrivi as scrivi_vettore

runner = CliRunner()


def test_init_e_search(repo_condiviso, monkeypatch):
    monkeypatch.chdir(repo_condiviso.a)
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["search", "Benvenuto team"])
    assert res.exit_code == 0, res.output
    assert "generale/benvenuto.md › Benvenuto" in res.output


def test_init_fuori_da_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 2 and "git" in res.output


def test_comando_fuori_da_kb(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 2 and "nb init" in res.output


def test_index_e_status(kb, monkeypatch):
    scrivi(kb, "generale/a.md", "# A\nuno\n")
    monkeypatch.chdir(kb)
    res = runner.invoke(app, ["index"])
    assert res.exit_code == 0 and "aggiunti 1" in res.output
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0 and '"file": 1' in res.output


def test_search_nessun_risultato(kb, monkeypatch):
    monkeypatch.chdir(kb)
    res = runner.invoke(app, ["search", "qualcosa"])
    assert res.exit_code == 0 and "nessun risultato" in res.output


def test_check_obsoleto(repo_condiviso, monkeypatch):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "remoto\n", "remoto")
    monkeypatch.chdir(r.a)
    res = runner.invoke(app, ["check", "generale/benvenuto.md"])
    assert res.exit_code == 1 and "modificato sul remoto" in res.output


def test_check_aggiornato(repo_condiviso, monkeypatch):
    monkeypatch.chdir(repo_condiviso.a)
    res = runner.invoke(app, ["check", "generale/benvenuto.md"])
    assert res.exit_code == 0 and "aggiornato" in res.output


def test_sync(repo_condiviso, monkeypatch):
    monkeypatch.chdir(repo_condiviso.a)
    res = runner.invoke(app, ["sync"])
    assert res.exit_code == 0 and '"pushato": true' in res.output


def test_gc_rimuove_orfani(kb, monkeypatch):
    scrivi(kb, "generale/a.md", "# A\nuno\n")
    scrivi_vettore(kb / ".nb" / "emb", "ff" * 32, np.zeros(384, np.float32))
    monkeypatch.chdir(kb)
    res = runner.invoke(app, ["gc"])
    assert res.exit_code == 0 and "rimossi 1" in res.output
    assert not (kb / ".nb" / "emb" / "ff").exists()


def test_reembed(kb, monkeypatch):
    scrivi(kb, "generale/a.md", "# A\nuno\n")
    monkeypatch.chdir(kb)
    runner.invoke(app, ["index"])
    res = runner.invoke(app, ["reembed", "--si"])
    assert res.exit_code == 0 and "1 vettori ricalcolati" in res.output


def test_hook_pre_commit_blocca(repo_condiviso, monkeypatch):
    r = repo_condiviso
    scrivi(r.a, "generale/x.md", "<<<<<<< HEAD\na\n>>>>>>> b\n")
    g(r.a, "add", "-A")
    monkeypatch.chdir(r.a)
    res = runner.invoke(app, ["hook", "pre-commit"])
    assert res.exit_code == 1


def test_hook_sconosciuto(repo_condiviso, monkeypatch):
    monkeypatch.chdir(repo_condiviso.a)
    assert runner.invoke(app, ["hook", "boh"]).exit_code == 2


def test_reembed_con_indice_aperto_altrove(kb, monkeypatch):
    # come con il server MCP attivo: su Windows un file aperto non si può cancellare
    from nb.config import carica
    from nb.embedder import crea
    from nb.indice import Indice

    scrivi(kb, "generale/a.md", "# A\nuno\n")
    c = carica(kb)
    aperto = Indice(c, crea(c))
    aperto.sync()
    monkeypatch.chdir(kb)
    res = runner.invoke(app, ["reembed", "--si"])
    assert res.exit_code == 0, res.output
    assert "1 vettori ricalcolati" in res.output
    aperto.close()
