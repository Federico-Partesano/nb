import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from aiuti import g, scrivi

from nb.hooks import installa


@pytest.fixture
def nb_nel_path(monkeypatch):
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    assert shutil.which("nb"), "comando nb non trovato nel venv: esegui `uv sync`"


def test_commit_reale_aggiunge_vettori(repo_condiviso, nb_nel_path):
    r = repo_condiviso
    installa(r.a)
    scrivi(r.a, "generale/e2e.md", "# E2E\ncontenuto di prova\n")
    g(r.a, "add", "-A")
    g(r.a, "commit", "-qm", "e2e")
    nel_commit = g(r.a, "show", "--name-only", "--format=", "HEAD").split()
    assert "generale/e2e.md" in nel_commit
    assert any(f.startswith(".nb/emb/") for f in nel_commit)


def test_commit_reale_bloccato(repo_condiviso, nb_nel_path):
    r = repo_condiviso
    installa(r.a)
    scrivi(r.a, "generale/rotto.md", "<<<<<<< HEAD\nx\n>>>>>>> y\n")
    g(r.a, "add", "-A")
    esito = subprocess.run(["git", "commit", "-qm", "rotto"], cwd=r.a, capture_output=True, text=True)
    assert esito.returncode != 0
    assert "marcatori di conflitto" in esito.stderr


def test_push_reale_bloccato_senza_vettori(repo_condiviso, nb_nel_path):
    r = repo_condiviso
    installa(r.a)
    scrivi(r.a, "generale/n.md", "# N\ntesto\n")
    g(r.a, "add", "-A")
    g(r.a, "commit", "-q", "--no-verify", "-m", "senza vettori")
    esito = subprocess.run(["git", "push", "-q"], cwd=r.a, capture_output=True, text=True)
    assert esito.returncode != 0
    assert "vettori mancanti" in esito.stderr


def test_commit_parziale_bloccato_con_istruzioni(repo_condiviso, nb_nel_path):
    r = repo_condiviso
    installa(r.a)
    scrivi(r.a, "generale/benvenuto.md", "# Benvenuto\n\ntesto nuovo\n")
    esito = subprocess.run(["git", "commit", "-m", "parziale", "generale/benvenuto.md"],
                           cwd=r.a, capture_output=True, text=True)
    assert esito.returncode != 0
    assert "git add generale/benvenuto.md" in esito.stderr
    assert ".nb/emb" not in g(r.a, "status", "--porcelain")
