import pytest

from nb.config import MODELLO_DEFAULT, ConfigError, carica, scrivi_default, trova_root


def test_default(kb):
    c = carica(kb)
    assert c.root == kb
    assert c.model_id == MODELLO_DEFAULT
    assert (c.dim, c.max_parole, c.overlap, c.max_file_mb) == (384, 100, 20, 5.0)
    assert c.emb_dir == kb / ".nb" / "emb"
    assert c.index_path == kb / ".nb" / "index.db"


def test_scrivi_default_non_sovrascrive(kb):
    (kb / ".nb" / "config.toml").write_text("[chunk]\nmax_parole = 50\noverlap = 5\n")
    assert scrivi_default(kb) is False
    assert carica(kb).max_parole == 50


def test_trova_root_da_sottocartella(kb):
    sotto = kb / "progetti" / "x"
    sotto.mkdir(parents=True)
    assert trova_root(sotto) == kb


def test_trova_root_assente(tmp_path):
    with pytest.raises(ConfigError, match="nb init"):
        trova_root(tmp_path)


def test_overlap_troppo_grande(kb):
    (kb / ".nb" / "config.toml").write_text("[chunk]\nmax_parole = 10\noverlap = 10\n")
    with pytest.raises(ConfigError, match="overlap"):
        carica(kb)


def test_toml_rotto(kb):
    (kb / ".nb" / "config.toml").write_text("[chunk\n")
    with pytest.raises(ConfigError, match="non valido"):
        carica(kb)
