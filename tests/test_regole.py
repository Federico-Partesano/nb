from nb.regole import bloccanti, controlla_file, controlla_md, controlla_percorso


def livelli(esiti):
    return [e.livello for e in esiti]


def test_struttura_ok():
    assert controlla_percorso("progetti/portale/analisi/auth-sso.md") == []
    assert controlla_percorso("generale/onboarding.md") == []


def test_fuori_struttura_avvisa():
    assert livelli(controlla_percorso("varie/appunti.md")) == ["avviso"]


def test_call_nome_sbagliato_blocca():
    assert bloccanti(controlla_percorso("progetti/portale/call/Review SSO.md"))


def test_call_nome_giusto():
    assert controlla_percorso("progetti/portale/call/2026-10-03-review-sso.md") == []


def test_nome_non_slug_avvisa():
    assert livelli(controlla_percorso("generale/Note Varie.md")) == ["avviso"]


def test_esenti():
    assert controlla_percorso("README.md") == []
    assert controlla_file(".claude/settings.json", b"{}", 5) == []
    assert controlla_file(".githooks/pre-commit", b"#!/bin/sh", 5) == []


def test_md_frontmatter_rotto_blocca():
    assert bloccanti(controlla_md("generale/a.md", "---\ntipo: [x\n---\nciao\n"))


def test_md_tipo_non_ammesso_blocca():
    assert bloccanti(controlla_md("generale/a.md", "---\ntipo: verbale\n---\nciao\n"))


def test_marcatori_conflitto_bloccano():
    testo = "ciao\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> origin/main\n"
    esiti = bloccanti(controlla_md("generale/a.md", testo))
    assert esiti and "marcatori di conflitto" in esiti[0].messaggio


def test_separatore_markdown_non_e_conflitto():
    assert controlla_md("generale/a.md", "Titolo\n=======\n\ntesto\n") == []


def test_segreto_certo_blocca():
    assert bloccanti(controlla_md("generale/a.md", "chiave: AKIAABCDEFGHIJKLMNOP\n"))


def test_segreto_probabile_avvisa():
    assert livelli(controlla_md("generale/a.md", "la password: Estate2026! per il db\n")) == ["avviso"]


def test_binario_blocca():
    assert bloccanti(controlla_file("generale/spec.pdf", b"%PDF", 5))


def test_file_troppo_grande_blocca():
    assert bloccanti(controlla_file("generale/a.md", b"a" * (2 * 1024 * 1024), 1))


def test_vettori_esenti():
    assert controlla_file(".nb/emb/ab/abc.bin", b"\0" * 768, 5) == []


def test_non_md_avvisa():
    assert livelli(controlla_file("generale/note.txt", b"ciao", 5)) == ["avviso"]


def test_str_esito():
    e = controlla_percorso("varie/a.md")[0]
    assert str(e).startswith("⚠ varie/a.md:")
