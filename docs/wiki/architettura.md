# Architettura

## Moduli (`src/nb/`)

Dipendenze solo verso l'alto della tabella: un modulo usa quelli sopra di lui.

| Modulo | Responsabilità |
|---|---|
| `config` | `.nb/config.toml` → `Config` (modello, dimensioni chunk, limiti). `trova_root` risale fino a `.nb/config.toml`. |
| `fonti` | quali `.md` sono indicizzabili (`indicizzabile`), frontmatter + metadati dal percorso (`analizza`). Il frontmatter vince sul percorso. |
| `regole` | validazione condivisa (struttura, nomi call, frontmatter, conflitti, binari, segreti) → `Esito` blocco/avviso. |
| `chunker` | `Fonte` → `Chunk`: per titoli `#`–`###` (documenti) o per battute (trascrizioni, `meta.tipo == "trascrizione"`). `testo_embed` = titoli + testo. |
| `embedder` | `FastEmbedder` (fastembed, lazy) o `FakeEmbedder` (hash di parole, per i test) via `crea(config)`. |
| `vettori` | file per hash in `.nb/emb/`: `chiave`, `assicura` (calcola solo i mancanti), `gc`. |
| `indice` | SQLite locale: `file`, `chunk` (vettore BLOB), `chunk_fts` (FTS5). `sync()` incrementale; `matrice()` numpy in memoria. |
| `ricerca` | `cerca` ibrida (vettoriale + BM25, fusione RRF k=60, filtri), `simili` (per il caricamento), `formatta_risultati`. |
| `gitutil` | subprocess git con `GIT_LITERAL_PATHSPECS=1`, `GIT_TERMINAL_PROMPT=0`; liste `-z`. |
| `guardia` | file in staging già cambiati sul remoto (`git log HEAD..@{u} -- <file>`). |
| `coerenza` | quali vettori servono a una revisione e quali mancano (`mancanti_a`). Non serve il modello: solo chunking + hash. |
| `hooks` | `pre_commit`, `pre_push`, `post_sync`, `claude_pre_edit`, `installa`. Ritornano exit code. |
| `caricamento` | `proponi` (contesto per Claude) e `carica_fonti` (scrivi → vettori → un commit → push, con rollback). |
| `servizi` | operazioni condivise CLI/MCP: `stato`, `elenca`, `leggi`, `sincronizza`. |
| `iniziale` | `nb init`: config, `.gitignore`, hook, template da `modelli/` (mai sovrascritti). |
| `cli` / `server` | adattatori Typer / MCP (`MCPServer` di mcp 2.x). |

## Flussi

**Sync dell'indice** (`Indice.sync`, chiamato prima di ogni `cerca` MCP e da `nb index`): elenca i `.md` → salta se mtime uguale → se sha uguale aggiorna solo mtime → altrimenti chunk → hash → `assicura` (embedding dei soli mancanti) → **poi** una transazione breve che riscrive le righe dei file cambiati.

**Domanda**: Claude → tool `cerca` → `sync` → top-50 vettoriali + top-50 BM25 (stessi filtri) → RRF → testo con citazione `percorso › titoli` → eventuale `leggi_fonte`.

**Commit** (`pre-commit`): regole sui file in staging (contenuto letto da `git show :p`) → guardia → se tutto ok calcola i vettori dei `.md` in staging e li aggiunge al commit.

**Push** (`pre-push`): per ogni ref, file del range → guardia + coerenza (ogni `.md` pushato ha i suoi vettori nell'albero del commit).

**Dopo pull/checkout/rebase**: riepilogo su stderr + `python -m nb index --silenzioso` in background.

**Caricamento** (tool `proponi_collocazione` → piano mostrato all'utente → conferma → `carica_fonti`): valida → staging vuoto e destinazioni pulite → `pull --rebase --autostash` → scrive → sync → guardia → `git add` solo lotto + vettori → commit `--no-verify` → push; ogni errore ripristina solo i file del lotto.

## Dove vive lo stato

| Stato | Dove | Condiviso? |
|---|---|---|
| fonti | `.md` nel knowledge repo | sì (git) |
| vettori | `.nb/emb/` | sì (git, immutabili) |
| config | `.nb/config.toml` | sì (git) |
| indice | `.nb/index.db` (+ `-wal`, `-shm`) | no, cache locale |
| modello | `~/.cache/nb/fastembed` | no |
| hook | `.githooks/` + `core.hooksPath` | script sì, attivazione per clone (`nb init`) |

## Test

`tests/conftest.py`: `kb` (cartella con config, senza git) e `repo_condiviso` (bare `main` + cloni `a` = Marco e `b` = Giulia, hook disabilitati). `tests/aiuti.py`: `scrivi`, `g` (git per i test), `commit_e_push`. `test_e2e.py` usa `git commit`/`git push` veri con gli hook installati e richiede `nb` nel venv.
