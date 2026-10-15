# Aperti

Quando chiudi una voce: test che la riproduce → correzione → voce rimossa da qui → riga in `decisioni.md` se è una scelta.

## Piattaforme (mai provate: i test girano solo su macOS)
- **Windows, fine riga CRLF**: `split("\n")` lascia `\r` nel testo → `testo_embed` e hash diversi da quelli di Mac/Linux → il PC Windows ricalcola tutti i vettori in locale e lascia `.bin` non tracciati in `.nb/emb/`. Correzione: normalizzare `\r\n` → `\n` in `fonti.separa_frontmatter`/`analizza`. Il pre-push non è colpito (legge i blob git, già LF).
- **Windows, stderr non UTF-8**: con output catturato da git, Python usa cp1252 e `✋ ⚠ ›` possono sollevare `UnicodeEncodeError` negli hook. Correzione: `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")` all'avvio della CLI.
- **Windows, background**: `start_new_session` in `_indicizza_in_background` è solo POSIX.
- **Test non portabili**: `/etc/hosts`, `chmod`, script `sh` in `test_hooks`/`test_e2e`.
- Prossimo passo proposto: GitHub Actions con matrice ubuntu/windows/macos.

## Minori rimandati dalla revisione finale
- pre-push: push forzato con sha remoto sconosciuto → `GitError` non gestito (traceback).
- `carica_fonti` può scrivere attraverso una cartella symlink committata: manca `resolve().is_relative_to(root)` sulla destinazione.
- Destinazioni duplicate con `./` non riconosciute (normalizzare con `PurePosixPath`).
- Vettori orfani se `indice.sync()` fallisce dentro `carica_fonti` dopo averne scritti.
- `_ripristina` può mascherare l'errore originale se `git restore` fallisce.
- Tool `cerca` ed `elenca_fonti` non sono in `_errore_leggibile`.
- Query vuota o solo spazi → restituisce k risultati arbitrari invece di `[]`.
- post-rewrite dopo `--amend`: `ORIG_HEAD` vecchio, riepilogo fuorviante.
- Primo `pre-commit` offline senza modello in cache → traceback invece di avviso.
- Fence ```` ``` ```` dentro un blocco `~~~` lo chiude (`RE_FENCE` non ricorda il tipo di apertura).

## Prossimi passi
- **Fase 2: UI web** `nb ui` (FastAPI + HTML senza build), chat via `claude -p --output-format stream-json`, citazioni cliccabili, caricamento drag & drop. Spec da scrivere.
- **Idea: strato "LLM wiki"** sopra le fonti (`raw/` + `wiki/` di pagine sintetizzate e mantenute da Claude, ingest che aggiorna le pagine collegate, lint periodico). Il motore attuale ne sarebbe la base; punto critico: conflitti git quando più persone fanno ingest sulla stessa pagina.
