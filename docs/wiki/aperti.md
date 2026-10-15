# Aperti

Quando chiudi una voce: test che la riproduce → correzione → voce rimossa da qui → riga in `decisioni.md` se è una scelta.

## Piattaforme
- CI (`.github/workflows/test.yml`): suite completa su ubuntu, windows e macos; test del modello reale su ubuntu e windows. Una piattaforma rossa in CI è un bug aperto: annotalo qui finché non è chiuso.

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
