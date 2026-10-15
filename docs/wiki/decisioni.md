# Decisioni

Registro append-only: la voce più recente in fondo. Formato: **decisione** — perché — costo se sbagliata.

## 2026-10-14 — design (dalla spec)
- **LLM = Claude Code di ciascuno, niente LLM locale** — PC del team solo CPU; l'abbonamento Claude Code c'è già — i chunk rilevanti escono verso Anthropic.
- **Il motore indicizza solo `.md`; conversione PDF/audio a mano, originali fuori dal repo** — scope minimo — un passaggio manuale per il team.
- **Vettori committati, uno per file, nominati per hash del contenuto** — calcolo una volta per tutto il team, zero conflitti di merge, dedup gratis — il repo cresce di ~770 byte per chunk.
- **Il percorso non entra nell'embedding, i titoli sì** — riorganizzare le cartelle non costa ricalcoli — il vettore non "sa" a che progetto appartiene (lo fanno i filtri).
- **Fase 1 = MCP dentro Claude Code; UI web in fase 2; niente TUI** — Claude Code è già una TUI.
- **Hook git condivisi in `.githooks/` + guardia sui file cambiati sul remoto** — richiesta esplicita del team: fermare le modifiche su versioni vecchie prima del commit.

## 2026-10-14 — implementazione
- **Modello `paraphrase-multilingual-MiniLM-L12-v2`** invece di `multilingual-e5-small` — e5-small non è tra i modelli di fastembed; MiniLM sì (verificato) — tronca a 128 token: chunk da ~100 parole.
- **numpy esatto invece di `sqlite-vec`** — una dipendenza nativa in meno; < 200 ms su 50k chunk misurati — oltre ~500k chunk servirà un indice approssimato.
- **Cambio di `model_id` → indice ricostruito, non errore** — dopo un `nb reembed` di un collega il pull deve "funzionare e basta".
- **mcp 2.x (`MCPServer`), vincolo `mcp>=2.3,<3`** — l'API v1 (`FastMCP`) non esiste più in 2.x — un altro cambio di API = riscrivere gli import di `server.py`.
- **Errori attesi → `ToolError`** — in mcp 2.x un'eccezione qualunque arriva a Claude solo come "Error executing tool X", senza motivo.

## 2026-10-15 — correzioni dalla revisione finale
- **Impronta della matrice + `chunk.id AUTOINCREMENT` (schema 2)** — dopo un pull il `nb index` in background rinumerava i chunk e il server cercava id cancellati (crash) — gli indici esistenti si ricostruiscono una volta.
- **Lock su indice e tool MCP; embedding fuori transazione; tmp dei vettori con nome unico** — corruzione FTS e `database is locked` riprodotti con thread/processi concorrenti.
- **`git commit <file>` che richiede vettori nuovi viene bloccato con istruzioni** — l'indice vero è sotto `index.lock`, l'hook non può aggiornarlo — un passo in più per chi usa i commit parziali.
- **La guardia ignora i commit di un merge in corso; suggerisce `--autostash`** — prima bloccava ogni risoluzione di conflitto e suggeriva un comando che falliva.
- **Hook Claude Code blocca (exit 2) invece di avvisare** — con exit 2 Claude riceve il motivo e propone il pull — un passaggio in più se l'utente vuole modificare comunque.
- **`carica_fonti` offline**: errore con `push=True`, commit locale con avviso con `push=False`; rebase a metà annullato — il caricamento non deve mai lasciare il repo in uno stato strano.
