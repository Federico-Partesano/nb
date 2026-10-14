from nb.chunker import chunk_di, spezza
from nb.config import carica
from nb.fonti import analizza


def doc(testo, percorso="generale/doc.md"):
    return analizza(percorso, testo)


def call(testo):
    return analizza("progetti/p/call/2026-10-03-call.md", testo)


def test_titoli_annidati():
    f = doc("# Spec auth\nintro\n## Login\nlogin testo\n### SSO\nsso testo\n## Logout\nlogout testo\n")
    cs = spezza(f, 100, 20)
    assert [c.titoli for c in cs] == [
        ("Spec auth",), ("Spec auth", "Login"), ("Spec auth", "Login", "SSO"), ("Spec auth", "Logout"),
    ]
    assert cs[2].testo == "sso testo"
    assert cs[2].testo_embed == "Spec auth › Login › SSO\nsso testo"
    assert (cs[2].riga_inizio, cs[2].riga_fine) == (6, 6)


def test_senza_titoli_testo_embed_uguale():
    c = spezza(doc("solo testo\n"), 100, 20)[0]
    assert c.titoli == () and c.testo_embed == "solo testo"


def test_titolo_dentro_codice_ignorato():
    cs = spezza(doc("# A\n```bash\n# commento\n```\ntesto\n"), 100, 20)
    assert len(cs) == 1
    assert cs[0].titoli == ("A",)
    assert "# commento" in cs[0].testo


def test_sezioni_vuote_saltate():
    assert [c.titoli for c in spezza(doc("# A\n\n# B\ntesto\n"), 100, 20)] == [("B",)]


def test_numeri_riga_con_frontmatter():
    c = spezza(doc("---\ntipo: analisi\n---\n# A\nriga\n"), 100, 20)[0]
    assert c.riga_inizio == 5


def test_sezione_lunga_spezzata_con_overlap():
    paragrafi = [f"paragrafo{i} " + "parola " * 29 for i in range(10)]  # 30 parole ciascuno
    cs = spezza(doc("# Lungo\n" + "\n\n".join(paragrafi) + "\n"), 100, 35)
    assert len(cs) > 1
    assert all(len(c.testo.split()) <= 100 + 35 for c in cs)
    assert "paragrafo2 " in cs[0].testo and "paragrafo2 " in cs[1].testo  # overlap
    assert all(c.titoli == ("Lungo",) for c in cs)


def test_trascrizione_non_spezza_battute():
    righe = [f"**{'Marco' if i % 2 == 0 else 'Giulia'}** [00:{i:02d}:00]: " + "bla " * 20 for i in range(12)]
    cs = spezza(call("\n".join(righe) + "\n"), 100, 20)
    assert len(cs) > 1
    for c in cs:
        assert c.testo.startswith("**")
        assert set(c.speaker) == {"Marco", "Giulia"}


def test_speaker_formati():
    testo = "Marco Rossi: ciao\n**Giulia:** ok\nLuca [00:01:02]: si\ncontinua Luca\n"
    c = spezza(call(testo), 100, 20)[0]
    assert c.speaker == ("Marco Rossi", "Giulia", "Luca")


def test_battuta_lunghissima_spezzata():
    testo = "**Marco**: inizio\n" + "\n".join("riga " * 30 for _ in range(10)) + "\n"
    cs = spezza(call(testo), 100, 20)
    assert len(cs) > 1


def test_file_vuoto():
    assert spezza(doc(""), 100, 20) == []


def test_chunk_di(kb):
    fonte, cs = chunk_di(carica(kb), "generale/a.md", "# A\nciao\n")
    assert fonte.percorso == "generale/a.md"
    assert cs[0].percorso == "generale/a.md" and cs[0].testo == "ciao"
