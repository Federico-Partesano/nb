import pytest

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
