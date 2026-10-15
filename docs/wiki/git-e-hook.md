# Git e hook: trappole note

Ognuna di queste è costata un bug reale (vedi `decisioni.md`). Se tocchi l'area, aggiungi un test con `repo_condiviso` o in `test_e2e.py` che riproduca il caso con git vero.

## Nomi file
- Sempre output `-z` + `lista_z`: senza, git cita i nomi con accenti/spazi (`"riunione \303\250.md"`).
- `GIT_LITERAL_PATHSPECS=1` è globale in `gitutil`: un pathspec come `*.md` è letterale. Filtra in Python (`indicizzabile`), non con glob git.

## Staging
- `in_staging` filtra `ACMR`: va bene per validare i file nuovi/modificati, **non** per chiedere "lo staging è vuoto?" — per quello `staging_vuoto` (include cancellazioni e rinomine).
- `git show :<p>` = contenuto in staging; `git show <rev>:<p>` = contenuto nella revisione. Gli hook validano lo staging, non il working tree.

## pre-commit
- Normalmente le `git add` fatte dall'hook entrano nel commit.
- `git commit <file>` / `-o` usa un **indice temporaneo** (`GIT_INDEX_FILE` ≠ `<git-dir>/index`) mentre l'indice vero è bloccato da `index.lock`: i vettori aggiunti lì finirebbero nel commit ma non nell'indice vero, e il commit successivo li cancellerebbe. Per questo `_commit_parziale` blocca con istruzioni (`git add … && git commit`) se servono vettori nuovi.
- **Merge in corso** (`<git-dir>/MERGE_HEAD`): la guardia esclude `^MERGE_HEAD`, altrimenti blocca la risoluzione del conflitto proprio sui commit che si stanno integrando.
- Il consiglio all'utente è `git pull --rebase --autostash`: senza `--autostash` il pull fallisce perché il file obsoleto è in staging.
- `--no-verify` salta anche il calcolo dei vettori: il pre-push poi blocca per vettori mancanti → `nb sync` li calcola e committa.

## pre-push
- stdin: `<ref locale> <sha locale> <ref remoto> <sha remoto>`; sha remoto tutto zeri = branch nuovo → file da `git log <locale> --not --remotes`.
- La coerenza controlla l'albero del commit (`git ls-tree`), non il disco.

## Hook installati
- Gli script in `.githooks/` sono una riga: `exec nb hook <nome>`. Se `nb` manca escono 0 con un avviso: non bloccare mai git per un'installazione mancante.
- Gli hook git non viaggiano col clone: `core.hooksPath` lo imposta `nb init` su ogni clone.
- Hook Claude Code (`.claude/settings.json` del knowledge repo): `nb hook claude-pre-edit`, exit 2 = blocca la modifica e il messaggio su stderr arriva a Claude.

## Caricamento e rollback
- Precondizioni prima di scrivere: staging vuoto, destinazioni senza modifiche locali.
- Il rollback non usa mai `reset --hard`: `git reset` (lo staging era vuoto), `git restore --source=<base> --worktree` per i file modificati, cancellazione per quelli creati, rimozione dei soli vettori nuovi del lotto.
- Pull fallito con rebase a metà → `git rebase --abort` (rimette anche l'autostash) + errore chiaro. Remoto irraggiungibile → errore con `push=True`, commit locale con avviso con `push=False`.

## Ambiente dei test
- `repo_condiviso` imposta `core.hooksPath` anche sul bare, perché un `core.hooksPath` globale dell'utente disattiverebbe `hooks/pre-receive` usato per simulare un push rifiutato.
- macOS non ha `timeout`: nei comandi di prova usa Python o `sleep` in pipe.
