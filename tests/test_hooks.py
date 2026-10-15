import json
import os
import sqlite3
import subprocess
import sys
import time

from aiuti import commit_e_push, g, scrivi

from nb.hooks import NOMI, _indicizza_in_background, claude_pre_edit, installa, post_sync, pre_commit, pre_push


def push_args(root):
    locale = g(root, "rev-parse", "HEAD").strip()
    remoto = g(root, "rev-parse", "origin/main").strip()
    return f"refs/heads/main {locale} refs/heads/main {remoto}\n"


def test_installa(repo_condiviso):
    r = repo_condiviso
    installa(r.a)
    for nome in NOMI:
        p = r.a / ".githooks" / nome
        assert os.access(p, os.X_OK)
        assert f"nb hook {nome}" in p.read_text()
    assert g(r.a, "config", "core.hooksPath").strip() == ".githooks"


def test_pre_commit_aggiunge_vettori(repo_condiviso):
    r = repo_condiviso
    scrivi(r.a, "generale/nuovo.md", "# Nuovo\ncontenuto\n")
    g(r.a, "add", "generale/nuovo.md")
    assert pre_commit(r.a) == 0
    staged = g(r.a, "diff", "--cached", "--name-only").split()
    assert any(s.startswith(".nb/emb/") for s in staged)


def test_pre_commit_blocca_conflitto(repo_condiviso, capsys):
    r = repo_condiviso
    scrivi(r.a, "generale/x.md", "<<<<<<< HEAD\na\n=======\nb\n>>>>>>> altro\n")
    g(r.a, "add", "-A")
    assert pre_commit(r.a) == 1
    err = capsys.readouterr().err
    assert "marcatori di conflitto" in err and "--no-verify" in err


def test_pre_commit_blocca_binario(repo_condiviso):
    r = repo_condiviso
    (r.a / "generale").mkdir(exist_ok=True)
    (r.a / "generale/spec.pdf").write_bytes(b"%PDF-1.7")
    g(r.a, "add", "-A")
    assert pre_commit(r.a) == 1


def test_pre_commit_blocca_obsoleto(repo_condiviso, capsys):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "remoto\n", "remoto")
    scrivi(r.a, "generale/benvenuto.md", "locale\n")
    g(r.a, "add", "-A")
    assert pre_commit(r.a) == 1
    assert "modificato sul remoto" in capsys.readouterr().err


def test_pre_push_vettori_mancanti(repo_condiviso, capsys):
    r = repo_condiviso
    scrivi(r.a, "generale/n.md", "# N\ntesto\n")
    g(r.a, "add", "-A")
    g(r.a, "commit", "-qm", "senza vettori")
    assert pre_push(r.a, push_args(r.a)) == 1
    err = capsys.readouterr().err
    assert "vettori mancanti" in err and "generale/n.md" in err


def test_pre_push_ok_con_vettori(repo_condiviso):
    r = repo_condiviso
    scrivi(r.a, "generale/n.md", "# N\ntesto\n")
    g(r.a, "add", "-A")
    assert pre_commit(r.a) == 0
    g(r.a, "commit", "-qm", "con vettori")
    assert pre_push(r.a, push_args(r.a)) == 0


def test_post_sync_riepilogo(repo_condiviso, capsys, monkeypatch):
    r = repo_condiviso
    monkeypatch.setattr("nb.hooks._indicizza_in_background", lambda root: None)
    commit_e_push(r.b, "generale/nuova.md", "x\n", "nuova")
    g(r.a, "pull", "-q")
    assert post_sync(r.a, "post-merge", ["0"]) == 0
    assert "1 nuove" in capsys.readouterr().err


def test_claude_pre_edit_blocca_obsoleto(repo_condiviso, capsys):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "remoto\n", "remoto")
    stdin = json.dumps({"tool_input": {"file_path": str(r.a / "generale/benvenuto.md")}})
    assert claude_pre_edit(r.a, stdin) == 2
    assert "git pull --rebase" in capsys.readouterr().err


def test_claude_pre_edit_ignora_altro(repo_condiviso):
    r = repo_condiviso
    assert claude_pre_edit(r.a, json.dumps({"tool_input": {"file_path": "/etc/hosts"}})) == 0
    assert claude_pre_edit(r.a, "") == 0


def test_pre_commit_risoluzione_merge_non_bloccata(repo_condiviso):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "# Benvenuto\n\nversione B\n", "b")
    scrivi(r.a, "generale/benvenuto.md", "# Benvenuto\n\nversione A\n")
    g(r.a, "commit", "-qam", "a")
    subprocess.run(["git", "pull", "--no-rebase", "-q"], cwd=r.a, capture_output=True)
    assert (r.a / ".git/MERGE_HEAD").exists()
    scrivi(r.a, "generale/benvenuto.md", "# Benvenuto\n\nversione unita\n")
    g(r.a, "add", "-A")
    assert pre_commit(r.a) == 0


def test_messaggio_obsoleto_suggerisce_autostash(repo_condiviso, capsys):
    r = repo_condiviso
    commit_e_push(r.b, "generale/benvenuto.md", "remoto\n", "remoto")
    scrivi(r.a, "generale/benvenuto.md", "locale\n")
    g(r.a, "add", "-A")
    pre_commit(r.a)
    assert "git pull --rebase --autostash" in capsys.readouterr().err


def test_hook_con_stderr_non_utf8(repo_condiviso):
    r = repo_condiviso
    scrivi(r.a, "generale/x.md", "<<<<<<< HEAD\na\n>>>>>>> b\n")
    g(r.a, "add", "-A")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}  # come su Windows quando git cattura l'output
    esito = subprocess.run([sys.executable, "-m", "nb", "hook", "pre-commit"], cwd=r.a, env=env,
                           capture_output=True)
    errore = esito.stderr.decode("utf-8", errors="replace")
    assert esito.returncode == 1, errore
    assert "✋ generale/x.md: marcatori di conflitto" in errore  # simboli leggibili, non \\u270b


def test_cli_con_stdout_non_utf8(kb):
    scrivi(kb, "generale/a.md", "# A\n## B\nKeycloak\n")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    esito = subprocess.run([sys.executable, "-m", "nb", "search", "Keycloak"], cwd=kb, env=env,
                           capture_output=True)
    assert esito.returncode == 0, esito.stderr.decode("utf-8", errors="replace")
    assert "generale/a.md › A › B" in esito.stdout.decode("utf-8")


def test_script_hook_con_fine_riga_lf(repo_condiviso):
    installa(repo_condiviso.a)
    for nome in NOMI:
        assert b"\r" not in (repo_condiviso.a / ".githooks" / nome).read_bytes()


def test_indicizzazione_in_background(kb):
    scrivi(kb, "generale/a.md", "# A\nuno\n")
    _indicizza_in_background(kb)
    db = kb / ".nb" / "index.db"
    for _ in range(100):
        if db.exists():
            try:
                with sqlite3.connect(db) as c:
                    if c.execute("SELECT COUNT(*) FROM chunk").fetchone()[0] == 1:
                        return
            except sqlite3.Error:
                pass
        time.sleep(0.1)
    raise AssertionError("indice non creato dal processo in background")
