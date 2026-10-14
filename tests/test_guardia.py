from aiuti import commit_e_push, g, scrivi

from nb.gitutil import in_staging
from nb.guardia import controlla


def test_file_modificato_sul_remoto(repo_condiviso):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "# Benvenuto\n\nAggiornato.\n", "aggiornato benvenuto")
    scrivi(r.a, "generale/benvenuto.md", "# Benvenuto\n\nModifica locale.\n")
    g(r.a, "add", "-A")
    esito = controlla(r.a, ["generale/benvenuto.md"])
    assert [o.percorso for o in esito.obsoleti] == ["generale/benvenuto.md"]
    c = esito.obsoleti[0].commit[0]
    assert (c.autore, c.messaggio) == ("Giulia", "aggiornato benvenuto")
    assert "git pull --rebase" in esito.obsoleti[0].messaggio()


def test_file_diverso_passa(repo_condiviso):
    r = repo_condiviso
    commit_e_push(r.b, "generale/altro.md", "altro\n", "altro")
    scrivi(r.a, "generale/benvenuto.md", "locale\n")
    assert controlla(r.a, ["generale/benvenuto.md"]).obsoleti == []


def test_nome_con_accenti_e_spazi(repo_condiviso):
    r = repo_condiviso
    nome = "generale/riunione è qui.md"
    commit_e_push(r.a, nome, "uno\n", "uno")
    g(r.b, "pull", "-q")
    commit_e_push(r.b, nome, "due\n", "due")
    assert [o.percorso for o in controlla(r.a, [nome]).obsoleti] == [nome]


def test_in_staging_con_accenti(repo_condiviso):
    r = repo_condiviso
    scrivi(r.a, "generale/è.md", "x\n")
    g(r.a, "add", "-A")
    assert in_staging(r.a) == ["generale/è.md"]


def test_senza_upstream(tmp_path):
    g(tmp_path, "init", "-q")
    esito = controlla(tmp_path, ["x.md"])
    assert esito.obsoleti == [] and "upstream" in esito.avvisi[0]


def test_fetch_fallito_avvisa(repo_condiviso):
    r = repo_condiviso
    g(r.a, "remote", "set-url", "origin", str(r.remoto) + "-sparito")
    esito = controlla(r.a, ["generale/benvenuto.md"])
    assert esito.obsoleti == []
    assert "fetch non riuscito" in esito.avvisi[0]
