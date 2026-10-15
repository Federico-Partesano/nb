# nb — guida per agenti

`nb` è il **tool**: indicizza i `.md` di un *knowledge repo* git (un altro repo, dei team) in locale su CPU e li espone a Claude Code via MCP. Questo repo non contiene documenti di team; `src/nb/modelli/` sono i template che `nb init` copia nel knowledge repo.

Spec vincolante: `docs/specs/2026-10-14-nb-design.md`. Codice, messaggi utente, commenti e test sono in italiano: continua così.

## Comandi

```bash
uv sync                    # ambiente (Python 3.12 esatto: onnxruntime)
uv run pytest -q           # suite veloce, senza rete: NB_EMBEDDER=fake è autouse in conftest
uv run pytest -m modello   # modello reale (scarica ~220 MB in ~/.cache/nb)
uv run pytest -m lento     # prestazioni: 50k chunk, ricerca < 200 ms
```

`nb` installato con `uv tool install --editable .` punta a questo checkout: ogni modifica è subito live sul PC.

## Invarianti (rompere uno di questi rompe il team, non solo un test)

- **Hash dei vettori** = `sha256(model_id + "\n" + testo_embed)`, file `.nb/emb/<h[:2]>/<h>.bin` float16. Cambiare `testo_embed` (chunker, titoli, normalizzazione del testo) cambia tutti gli hash: tutti i team ricalcolano e committano vettori nuovi. Trattalo come una migrazione.
- **Il percorso del file non entra mai in `testo_embed`**: spostare/rinominare costa zero ricalcoli.
- **Nessun file condiviso mutabile** generato da `nb` nel knowledge repo: solo file immutabili per hash. Un manifest comune = conflitti garantiti.
- **`.nb/index.db` è una cache** derivata da `.md` + `.nb/emb/`: mai committata, ricostruibile. Cambi allo schema → incrementa `SCHEMA` in `indice.py` (ricostruzione automatica).
- **Le regole di validazione stanno solo in `regole.py`**: hook e caricamento le condividono.
- **CLI e server MCP sono adattatori sottili**: la logica va nel core (`ricerca`, `servizi`, `caricamento`, `hooks`).
- **Mai push o commit nel knowledge repo senza conferma dell'utente**: è scritto nelle docstring dei tool e nella skill `nb-carica`; mantienilo.

## Wiki (leggi la pagina prima di toccare l'area)

- `docs/wiki/architettura.md` — mappa dei moduli e flussi (sync, cerca, commit, push, caricamento). Leggila per orientarti o per aggiungere un modulo.
- `docs/wiki/git-e-hook.md` — trappole git: indice temporaneo, merge in corso, pathspec, `-z`, rollback. Leggila prima di modificare `gitutil`, `guardia`, `hooks`, `coerenza`, `caricamento`.
- `docs/wiki/indice-e-concorrenza.md` — SQLite, lock, processi concorrenti, cache della matrice. Leggila prima di modificare `indice`, `ricerca`, `vettori`, `server`.
- `docs/wiki/decisioni.md` — perché è fatto così (registro append-only). Leggila prima di rimettere in discussione una scelta; aggiungi una voce quando ne prendi una.
- `docs/wiki/aperti.md` — bug noti, limiti di piattaforma, prossimi passi. Aggiornala quando chiudi o scopri un problema.
