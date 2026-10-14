---
name: nb-carica
description: Carica uno o più file .md nella knowledge base del team scegliendo cartella, nome e frontmatter. Usare quando l'utente chiede di caricare, aggiungere o archiviare documenti, analisi o trascrizioni nel repo.
---

# Caricare fonti nella knowledge base

1. Chiama `proponi_collocazione` con i percorsi dei file.
2. Per ogni file decidi:
   - **progetto e cartella**: preferisci quella dei documenti più simili; `call/` per le trascrizioni, `analisi/` per studi e proposte, `documentazione/` per la documentazione di progetti e applicativi, `generale/` per i contenuti trasversali;
   - **duplicato** (`probabile_duplicato` valorizzato): proponi di aggiornare quel file (`aggiorna: true`) invece di crearne uno nuovo;
   - **nome**: `minuscolo-con-trattini.md`; trascrizioni `AAAA-MM-GG-titolo.md` con la data della call;
   - **frontmatter**: deducilo dal contenuto (`tipo`, `progetto`, `data`, `partecipanti` per le call).
3. Mostra il piano in una tabella `| file | destinazione | frontmatter | nota |` e **attendi la conferma**.
4. Un progetto o una cartella nuovi vanno segnalati e confermati a parte, in modo esplicito.
5. Dopo il sì chiama `carica_fonti` con il piano (`sorgente`, `destinazione`, `frontmatter`, `aggiorna`).
6. Riporta commit, push e avvisi. In caso di errore spiega la causa: non riprovare alla cieca.
