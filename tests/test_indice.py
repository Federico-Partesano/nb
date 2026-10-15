import os
import sqlite3
import threading

from aiuti import scrivi

from nb.config import carica
from nb.embedder import FakeEmbedder
from nb.indice import Indice

DUE_SEZIONI = "# A\nprimo\n## B\nsecondo\n"


def nuovo(kb, model_id=None):
    c = carica(kb)
    return Indice(c, FakeEmbedder(model_id or c.model_id, c.dim))


def conta(ind, tabella):
    return ind.db.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]


def tocca(p):
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


def test_sync_iniziale(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    rep = ind.sync()
    assert rep.aggiunti == ["generale/a.md"]
    assert conta(ind, "chunk") == 2 and conta(ind, "chunk_fts") == 2
    assert len(rep.vettori_nuovi) == 2
    assert len(list((kb / ".nb" / "emb").glob("*/*.bin"))) == 2


def test_secondo_sync_noop(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    assert not ind.sync().cambiato


def test_mtime_cambiato_contenuto_uguale(kb):
    p = scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    tocca(p)
    assert not ind.sync().cambiato


def test_modifica_riusa_vettori_invariati(kb):
    p = scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    p.write_text("# A\nprimo\n## B\nsecondo cambiato\n")
    tocca(p)
    rep = ind.sync()
    assert rep.modificati == ["generale/a.md"]
    assert len(rep.vettori_nuovi) == 1


def test_spostamento_zero_ricalcoli(kb):
    p = scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    dest = kb / "progetti/x/analisi/a.md"
    dest.parent.mkdir(parents=True)
    p.rename(dest)
    rep = ind.sync()
    assert rep.aggiunti == ["progetti/x/analisi/a.md"]
    assert rep.rimossi == ["generale/a.md"]
    assert rep.vettori_nuovi == []
    assert ind.db.execute("SELECT tipo, progetto FROM file").fetchone() == ("analisi", "x")


def test_rimozione(kb):
    p = scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    p.unlink()
    assert ind.sync().rimossi == ["generale/a.md"]
    assert conta(ind, "chunk") == 0 and conta(ind, "chunk_fts") == 0 and conta(ind, "file") == 0


def test_file_vuoto_indicizzato(kb):
    scrivi(kb, "generale/vuoto.md", "")
    scrivi(kb, "generale/solo-fm.md", "---\ntipo: analisi\n---\n")
    ind = nuovo(kb)
    assert len(ind.sync().aggiunti) == 2
    assert conta(ind, "file") == 2 and conta(ind, "chunk") == 0
    assert ind.matrice().vettori.shape == (0, 384)


def test_db_corrotto_ricostruito(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    ind.close()
    for suffisso in ("-wal", "-shm"):
        (kb / ".nb" / f"index.db{suffisso}").unlink(missing_ok=True)
    (kb / ".nb" / "index.db").write_bytes(b"spazzatura" * 100)
    rep = nuovo(kb).sync()
    assert rep.aggiunti == ["generale/a.md"]
    assert rep.vettori_nuovi == []  # i vettori su disco vengono riusati


def test_cambio_modello_ricostruisce(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    ind.close()
    rep = nuovo(kb, "altro-modello").sync()
    assert rep.aggiunti == ["generale/a.md"]
    assert len(rep.vettori_nuovi) == 2


def test_matrice(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    m = ind.matrice()
    assert m.vettori.shape == (2, 384)
    assert list(m.percorsi) == ["generale/a.md", "generale/a.md"]
    assert len(ind.hash_vivi()) == 2


def test_avvisi(kb):
    scrivi(kb, "generale/a.md", "---\ntipo: boh\n---\nx\n")
    ind = nuovo(kb)
    ind.sync()
    assert "non ammesso" in ind.avvisi()["generale/a.md"][0]


def test_matrice_aggiornata_dopo_sync_di_altro_processo(kb):
    p = scrivi(kb, "generale/a.md", "# A\nalfa\n")
    scrivi(kb, "generale/b.md", "# B\nbeta\n")  # così i nuovi id non riusano i vecchi
    server = nuovo(kb)
    server.sync()
    server.matrice()
    p.write_text("# A\nomega unico\n")
    tocca(p)
    altro = nuovo(kb)
    altro.sync()
    altro.close()
    assert not server.sync().cambiato
    ids = {r[0] for r in server.db.execute("SELECT id FROM chunk")}
    assert set(server.matrice().ids.tolist()) == ids


def test_sync_concorrente_stesso_indice(kb):
    ind = nuovo(kb)
    errori = []

    def lavora(t):
        try:
            for i in range(15):
                scrivi(kb, f"generale/f{t}.md", f"# F\nversione {i} thread {t}\n")
                ind.sync()
        except Exception as e:  # noqa: BLE001
            errori.append(e)

    thread = [threading.Thread(target=lavora, args=(t,)) for t in range(3)]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    assert errori == []
    assert conta(ind, "chunk") == conta(ind, "chunk_fts")


def test_lock_non_tenuto_durante_embedding(kb):
    c = carica(kb)
    scrivi(kb, "generale/vecchio.md", "# V\nvecchio\n")
    ind = nuovo(kb)
    ind.sync()
    (kb / "generale/vecchio.md").unlink()
    scrivi(kb, "generale/nuovo.md", "# N\nnuovo\n")

    class Sonda(FakeEmbedder):
        def embed(self, testi):
            altro = sqlite3.connect(c.index_path, timeout=0.2)
            altro.execute("BEGIN IMMEDIATE")
            altro.rollback()
            altro.close()
            return super().embed(testi)

    ind.embedder = Sonda(c.model_id, c.dim)
    assert ind.sync().aggiunti == ["generale/nuovo.md"]


def test_svuota(kb):
    scrivi(kb, "generale/a.md", DUE_SEZIONI)
    ind = nuovo(kb)
    ind.sync()
    ind.svuota()
    assert conta(ind, "file") == 0 and conta(ind, "chunk") == 0 and conta(ind, "chunk_fts") == 0
    assert ind.sync().aggiunti == ["generale/a.md"]
