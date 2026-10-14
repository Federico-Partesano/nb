# Knowledge base del team

Analisi, documentazione e trascrizioni delle call in markdown, interrogabili da Claude Code tramite `nb`.

## Primo avvio (una volta per PC)

1. Installa nb: `uv tool install --python 3.12 git+<URL-GITEA>/nb.git`
2. Clona questo repo ed entra nella cartella: `nb init` (attiva gli hook git).
3. Apri Claude Code qui dentro e approva il server MCP `nb` quando te lo chiede.
4. La prima ricerca scarica il modello di embedding (~220 MB, una volta sola).

## Struttura

```
progetti/<progetto>/analisi/          analisi, studi, proposte
progetti/<progetto>/documentazione/   documentazione di progetto e applicativi
progetti/<progetto>/call/             trascrizioni: AAAA-MM-GG-titolo.md
generale/                             tutto ciò che è trasversale
```

## Convenzioni

- Nel repo vanno **solo `.md`**. PDF, audio e video restano fuori: si convertono prima in markdown.
- Nomi file: `minuscolo-con-trattini.md`; le trascrizioni `AAAA-MM-GG-titolo.md`.
- Frontmatter facoltativo (se manca, progetto e tipo si ricavano dalla cartella):

```yaml
---
tipo: trascrizione        # analisi | documentazione | trascrizione | altro
progetto: portale-clienti
data: 2026-10-14
partecipanti: [Marco, Giulia]
---
```

## Uso quotidiano

- Domande: chiedi a Claude Code, che cerca nelle fonti e cita `percorso › sezione`.
- Caricare file: in Claude Code `/nb-carica <file.md> ...`. Claude propone cartella, nome e frontmatter e aspetta il tuo ok.
- `nb sync` aggiorna (pull + indice + vettori mancanti). `nb status` mostra lo stato. `nb search "..."` cerca da terminale.

## Regole git

Gli hook bloccano: file modificati sul remoto mentre li cambiavi, marcatori di conflitto, binari, file oltre 5 MB, segreti evidenti. `git commit --no-verify` solo in emergenza.
Su Gitea il branch `main` è protetto: niente force push, niente cancellazione.
