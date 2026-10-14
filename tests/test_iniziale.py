import json

import pytest
from aiuti import g, scrivi

from nb.iniziale import InitError, inizializza


def test_init_crea_tutto(repo_condiviso):
    r = repo_condiviso
    messaggi = inizializza(r.a / "generale")  # funziona anche da una sottocartella
    for f in ("README.md", "CLAUDE.md", ".claude/skills/nb-carica/SKILL.md", ".claude/settings.json", ".mcp.json"):
        assert (r.a / f).is_file(), f
    assert json.loads((r.a / ".mcp.json").read_text())["mcpServers"]["nb"]["args"] == ["mcp"]
    assert "claude-pre-edit" in (r.a / ".claude/settings.json").read_text()
    assert ".nb/index.db*" in (r.a / ".gitignore").read_text()
    assert g(r.a, "config", "core.hooksPath").strip() == ".githooks"
    assert any("git push" in m for m in messaggi)


def test_init_idempotente_non_sovrascrive(repo_condiviso):
    r = repo_condiviso
    scrivi(r.a, "README.md", "il nostro readme\n")
    inizializza(r.a)
    inizializza(r.a)
    assert (r.a / "README.md").read_text() == "il nostro readme\n"
    assert (r.a / ".gitignore").read_text().count(".nb/index.db*") == 1


def test_init_fuori_da_git(tmp_path):
    with pytest.raises(InitError, match="git"):
        inizializza(tmp_path)
