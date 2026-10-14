from dataclasses import dataclass
from pathlib import Path

import pytest
from aiuti import g, scrivi

from nb.config import scrivi_default


@pytest.fixture(autouse=True)
def embedder_finto(monkeypatch):
    monkeypatch.setenv("NB_EMBEDDER", "fake")


@pytest.fixture
def kb(tmp_path):
    root = (tmp_path / "kb").resolve()
    root.mkdir()
    scrivi_default(root)
    return root



@dataclass
class RepoCondiviso:
    remoto: Path
    a: Path
    b: Path


def _configura(clone: Path, nome: str) -> None:
    g(clone, "config", "user.name", nome)
    g(clone, "config", "user.email", f"{nome.lower()}@esempio.it")
    g(clone, "config", "commit.gpgsign", "false")
    g(clone, "config", "core.hooksPath", ".git/hooks-disabilitati")


@pytest.fixture
def repo_condiviso(tmp_path):
    tmp = tmp_path.resolve()
    remoto = tmp / "remoto.git"
    g(tmp, "init", "-q", "--bare", "-b", "main", str(remoto))
    g(remoto, "config", "core.hooksPath", str(remoto / "hooks"))
    a = tmp / "a"
    g(tmp, "clone", "-q", str(remoto), str(a))
    g(a, "symbolic-ref", "HEAD", "refs/heads/main")
    _configura(a, "Marco")
    scrivi_default(a)
    scrivi(a, ".gitignore", ".nb/index.db*\n")
    scrivi(a, "generale/benvenuto.md", "# Benvenuto\n\nCiao team.\n")
    g(a, "add", "-A")
    g(a, "commit", "-qm", "init")
    g(a, "push", "-q", "-u", "origin", "main")
    b = tmp / "b"
    g(tmp, "clone", "-q", str(remoto), str(b))
    _configura(b, "Giulia")
    return RepoCondiviso(remoto, a, b)
