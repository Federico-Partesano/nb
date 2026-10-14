from aiuti import scrivi

from nb.fonti import analizza, elenca_md, indicizzabile, meta_da_percorso


def test_meta_da_percorso_progetto():
    m = meta_da_percorso("progetti/portale/call/2026-10-03-review-sso.md")
    assert (m.tipo, m.progetto, m.data) == ("trascrizione", "portale", "2026-10-03")


def test_meta_da_percorso_generale():
    m = meta_da_percorso("generale/onboarding.md")
    assert (m.tipo, m.progetto, m.data) == ("altro", None, None)


def test_frontmatter_vince_sul_percorso():
    testo = (
        "---\ntipo: documentazione\nprogetto: gestionale\ndata: 2026-09-01\n"
        "partecipanti: [Marco, Giulia]\n---\n# Auth\ntesto\n"
    )
    f = analizza("progetti/portale/analisi/auth.md", testo)
    assert f.meta.tipo == "documentazione"
    assert f.meta.progetto == "gestionale"
    assert f.meta.data == "2026-09-01"
    assert f.meta.partecipanti == ("Marco", "Giulia")
    assert f.riga_corpo == 7
    assert f.corpo.startswith("# Auth")
    assert f.avvisi == ()


def test_yaml_rotto_usa_percorso_e_avvisa():
    f = analizza("progetti/portale/analisi/auth.md", "---\ntipo: [rotto\n---\ntesto\n")
    assert f.meta.tipo == "analisi"
    assert "YAML non valido" in f.avvisi[0]
    assert f.corpo == "testo\n"


def test_tipo_non_ammesso():
    f = analizza("generale/x.md", "---\ntipo: verbale\n---\nciao\n")
    assert f.meta.tipo == "altro"
    assert "non ammesso" in f.avvisi[0]


def test_frontmatter_non_chiuso():
    f = analizza("generale/x.md", "---\ntipo: analisi\nciao\n")
    assert f.riga_corpo == 1
    assert "mai chiuso" in f.avvisi[0]


def test_file_vuoto():
    f = analizza("generale/vuoto.md", "")
    assert f.corpo == "" and f.meta.tipo == "altro" and f.avvisi == ()


def test_solo_frontmatter():
    f = analizza("generale/x.md", "---\ntipo: analisi\n---\n")
    assert f.corpo == "" and f.meta.tipo == "analisi"


def test_indicizzabile():
    assert indicizzabile("generale/a.md")
    assert indicizzabile("progetti/x/README.md")
    assert not indicizzabile("README.md")
    assert not indicizzabile("CLAUDE.md")
    assert not indicizzabile(".claude/skills/x/SKILL.md")
    assert not indicizzabile("generale/a.pdf")


def test_elenca_md(kb):
    scrivi(kb, "generale/a.md", "a")
    scrivi(kb, "progetti/p/analisi/b.md", "b")
    scrivi(kb, "README.md", "r")
    scrivi(kb, ".claude/skills/x/SKILL.md", "s")
    scrivi(kb, "generale/c.txt", "c")
    assert elenca_md(kb) == ["generale/a.md", "progetti/p/analisi/b.md"]
