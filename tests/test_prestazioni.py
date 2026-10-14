import time

import pytest
from aiuti import scrivi

from nb.config import carica
from nb.embedder import FakeEmbedder
from nb.indice import Indice
from nb.ricerca import Filtri, cerca


@pytest.mark.lento
def test_ricerca_50k_chunk_sotto_200ms(kb):
    for i in range(1000):
        sezioni = "\n".join(
            f"## Sezione {j}\nDocumento {i} sezione {j} tratta argomento{(i * 50 + j) % 997} e modulo{j}.\n"
            for j in range(50))
        scrivi(kb, f"progetti/p{i % 20}/analisi/doc-{i}.md", f"# Doc {i}\n{sezioni}")
    c = carica(kb)
    indice = Indice(c, FakeEmbedder(c.model_id, c.dim))
    indice.sync()
    assert indice.db.execute("SELECT COUNT(*) FROM chunk").fetchone()[0] == 50_000
    cerca(indice, "riscaldamento")  # carica la matrice in memoria
    inizio = time.perf_counter()
    for q in ("argomento42 modulo7", "sezione documento", "argomento500"):
        cerca(indice, q)
        cerca(indice, q, Filtri(progetto="p3"))
    assert (time.perf_counter() - inizio) / 6 < 0.2
