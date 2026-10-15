# Indice e concorrenza

Sullo stesso `.nb/index.db` lavorano insieme: il server MCP (più thread: mcp 2.x esegue i tool sincroni in `anyio.to_thread`), il `nb index` in background lanciato dagli hook post-merge, e i comandi CLI. Le regole sotto esistono per questo.

## Regole
- **Un `Indice` = una connessione = un `RLock`** (`indice.lock`). `sync()` e `matrice()` lo prendono; il server avvolge ogni tool con `_in_serie` sullo stesso lock, perché `ricerca` interroga `indice.db` direttamente.
- **Embedding fuori dalla transazione**: `_sync` calcola tutto (chunk, `assicura`) prima di `BEGIN IMMEDIATE`; la scrittura è un blocco breve. Un'operazione lenta dentro la transazione = `database is locked` per l'altro processo dopo 10 s.
- **Ogni file riscritto passa da `_rimuovi` prima di `_inserisci`**, anche se nuovo: un altro processo può averlo inserito nel frattempo.
- **WAL + `timeout=10`** sulla connessione.

## Cache della matrice
- `matrice()` tiene i vettori in memoria (numpy, ricerca esatta: 50k × 384 in pochi ms).
- La cache si invalida con un'**impronta** `(COUNT(*), MAX(id))` letta a ogni chiamata, non con il report del proprio `sync`: se scrive un altro processo, il report locale dice "niente di cambiato" ma l'impronta cambia.
- Funziona solo perché `chunk.id` è `AUTOINCREMENT` (id mai riusati). Senza, cancellare e reinserire gli ultimi chunk ridà gli stessi id e l'impronta non cambia.

## Vettori su disco
- `vettori.scrivi` usa un file temporaneo con nome unico (`mkstemp`) + `os.replace`: più scrittori dello stesso hash scrivono contenuto identico, l'ultimo vince.
- `assicura` legge prima di calcolare: un vettore già presente non viene mai ricalcolato.

## Schema
- `SCHEMA` in `indice.py` (oggi `"2"`) e `model_id` stanno in `meta`. Diversi da quanto atteso, o DB corrotto → file cancellato e ricostruito da `.md` + `.nb/emb/` (i vettori su disco vengono riusati, quindi è veloce).

## Ricerca
- Filtri applicati a entrambe le classifiche: SQL per BM25, insieme di id ammessi per il vettoriale.
- Query FTS costruita solo da token `\w+` tra virgolette uniti con OR: nessun input dell'utente arriva crudo a `MATCH`.
- `simili` assume che i chunk di uno stesso file abbiano id contigui (inseriti in un blocco) e usa `np.maximum.reduceat`; i gruppi duplicati vengono comunque uniti per percorso.
