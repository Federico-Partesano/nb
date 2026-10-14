# Knowledge base del team: regole per Claude

Questo repo è la knowledge base del team. Il server MCP `nb` è il motore di ricerca.

## Rispondere alle domande
- Per ogni domanda sui contenuti usa `cerca`; aggiungi i filtri `progetto`, `tipo`, `da`/`a` quando la domanda li implica.
- Usa `leggi_fonte` quando serve il contesto completo di un documento o di una sezione.
- Cita sempre le fonti nel formato `percorso › sezione`. Per le trascrizioni indica la data della call e chi ha parlato.
- Se l'informazione non è nelle fonti rispondi "non presente nelle fonti". Non inventare e non completare con conoscenze generali senza dirlo.

## Caricare o modificare
- Per aggiungere fonti segui la skill `nb-carica`. Mai committare o pushare senza conferma esplicita dell'utente.
- Se un hook segnala che un file è stato modificato sul remoto, proponi `git pull --rebase` prima di toccarlo.
