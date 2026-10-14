import numpy as np
import pytest

from nb.config import MODELLO_DEFAULT, carica
from nb.embedder import FakeEmbedder, crea
from nb.vettori import assicura, chiave, gc, leggi, percorso_rel, scrivi, tutte

H1, H2 = "ab" * 32, "cd" * 32


def test_chiave():
    assert chiave("m", "a") != chiave("m", "b")
    assert chiave("m", "a") != chiave("n", "a")
    assert len(chiave("m", "a")) == 64


def test_percorso_rel():
    assert percorso_rel(H1) == f".nb/emb/ab/{H1}.bin"


def test_scrivi_leggi_float16(tmp_path):
    v = np.linspace(-1, 1, 384).astype(np.float32)
    p = scrivi(tmp_path, H1, v)
    assert p == tmp_path / "ab" / f"{H1}.bin"
    assert p.stat().st_size == 768
    assert np.allclose(leggi(tmp_path, H1, 384), v, atol=1e-3)


def test_leggi_assente_o_dimensione_sbagliata(tmp_path):
    assert leggi(tmp_path, H1, 384) is None
    scrivi(tmp_path, H2, np.zeros(10, np.float32))
    assert leggi(tmp_path, H2, 384) is None


def test_assicura_calcola_solo_mancanti(tmp_path):
    emb = FakeEmbedder()
    testi = {chiave("fake", t): t for t in ["uno", "due"]}
    vettori, nuovi = assicura(tmp_path, emb, testi)
    assert len(nuovi) == 2 and set(vettori) == set(testi)
    testi[chiave("fake", "tre")] = "tre"
    _, nuovi = assicura(tmp_path, emb, testi)
    assert len(nuovi) == 1


def test_gc(tmp_path):
    scrivi(tmp_path, H1, np.zeros(384, np.float32))
    scrivi(tmp_path, H2, np.zeros(384, np.float32))
    rimossi = gc(tmp_path, {H1})
    assert [p.stem for p in rimossi] == [H2]
    assert tutte(tmp_path) == {H1}
    assert not (tmp_path / "cd").exists()


def test_fake_embedder():
    m = FakeEmbedder().embed(["ciao mondo", "ciao mondo", "tutt'altro discorso"])
    assert m.shape == (3, 384)
    assert np.allclose(np.linalg.norm(m, axis=1), 1)
    assert np.allclose(m[0], m[1])
    assert m[0] @ m[2] < 0.99


def test_crea_usa_fake_con_env(kb):
    e = crea(carica(kb))
    assert isinstance(e, FakeEmbedder) and e.model_id == MODELLO_DEFAULT


@pytest.mark.modello
def test_modello_reale_semantica():
    from nb.embedder import FastEmbedder

    m = FastEmbedder(MODELLO_DEFAULT, 384).embed([
        "Il login avviene tramite single sign-on aziendale",
        "L'autenticazione degli utenti usa SSO",
        "La pizza margherita ha pomodoro e mozzarella",
    ])
    assert m.shape == (3, 384)
    assert m[0] @ m[1] > m[0] @ m[2]
