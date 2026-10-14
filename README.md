# nb

Knowledge base del team su git, stile NotebookLM ma decentralizzata: le fonti sono `.md` in un repo condiviso, la ricerca gira in locale (CPU), Claude Code risponde citando le fonti tramite MCP.

Design: `docs/specs/2026-10-14-nb-design.md`

## Installazione (ogni PC)

```bash
uv tool install --python 3.12 git+<URL-GITEA>/nb.git
```

Poi, dentro il knowledge repo clonato: `nb init`.

## Comandi

| comando | cosa fa |
|---|---|
| `nb init` | config, hook git, template Claude Code (idempotente) |
| `nb sync` | pull + indice + commit/push dei vettori mancanti |
| `nb search "..."` | ricerca da terminale (`--progetto --tipo --da --a -k`) |
| `nb status` | stato di indice, vettori e remoto |
| `nb check <file>` | il file è stato modificato sul remoto? |
| `nb gc` | rimuove i vettori orfani |
| `nb reembed` | ricalcola tutto dopo un cambio di modello |
| `nb mcp` | server MCP (lo lancia Claude Code da `.mcp.json`) |

## Sviluppo

```bash
uv sync
uv run pytest                 # veloce, senza rete (embedder finto)
uv run pytest -m modello      # scarica e prova il modello reale
uv run pytest -m lento        # prestazioni su 50k chunk
```
