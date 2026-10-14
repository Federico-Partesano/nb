"""Indice locale (SQLite + FTS5): cache derivata da .md e .nb/emb, mai committata."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from nb.chunker import Chunk, chunk_di
from nb.config import Config
from nb.embedder import Embedder
from nb.fonti import Fonte, elenca_md
from nb.vettori import assicura, chiave

SCHEMA = "2"
DDL = """
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE file(percorso TEXT PRIMARY KEY, mtime_ns INTEGER, sha TEXT, tipo TEXT,
                  progetto TEXT, data TEXT, partecipanti TEXT, avvisi TEXT);
CREATE TABLE chunk(id INTEGER PRIMARY KEY AUTOINCREMENT, percorso TEXT NOT NULL, titoli TEXT, testo TEXT,
                   riga_inizio INTEGER, riga_fine INTEGER, speaker TEXT, hash TEXT, vettore BLOB);
CREATE INDEX chunk_percorso ON chunk(percorso);
CREATE VIRTUAL TABLE chunk_fts USING fts5(testo, titoli, tokenize='unicode61 remove_diacritics 2');
"""


@dataclass
class ReportSync:
    aggiunti: list[str] = field(default_factory=list)
    modificati: list[str] = field(default_factory=list)
    rimossi: list[str] = field(default_factory=list)
    vettori_nuovi: list[Path] = field(default_factory=list)

    @property
    def cambiato(self) -> bool:
        return bool(self.aggiunti or self.modificati or self.rimossi)


@dataclass(frozen=True)
class Matrice:
    ids: np.ndarray
    vettori: np.ndarray
    percorsi: np.ndarray


class Indice:
    def __init__(self, config: Config, embedder: Embedder):
        self.config = config
        self.embedder = embedder
        self.lock = threading.RLock()  # una sola operazione alla volta sulla connessione condivisa
        self.db = self._apri()
        self._matrice: Matrice | None = None
        self._impronta: tuple[int, int] | None = None

    def _connetti(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.config.index_path, timeout=10, check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _apri(self) -> sqlite3.Connection:
        self.config.nb_dir.mkdir(parents=True, exist_ok=True)
        db = None
        try:
            db = self._connetti()
            meta = dict(db.execute("SELECT k, v FROM meta"))
            if meta.get("schema") == SCHEMA and meta.get("model_id") == self.embedder.model_id:
                return db
        except sqlite3.DatabaseError:
            pass
        if db is not None:
            db.close()
        for suffisso in ("", "-wal", "-shm"):
            Path(f"{self.config.index_path}{suffisso}").unlink(missing_ok=True)
        db = self._connetti()
        db.executescript(DDL)
        db.executemany("INSERT INTO meta VALUES (?, ?)", [("schema", SCHEMA), ("model_id", self.embedder.model_id)])
        db.commit()
        return db

    def sync(self) -> ReportSync:
        with self.lock:
            return self._sync()

    def _sync(self) -> ReportSync:
        root = self.config.root
        rep = ReportSync()
        noti = {p: (mt, sha) for p, mt, sha in self.db.execute("SELECT percorso, mtime_ns, sha FROM file")}
        su_disco = elenca_md(root)
        solo_mtime, da_elaborare = [], []
        for p in su_disco:
            mtime = (root / p).stat().st_mtime_ns
            if p in noti and noti[p][0] == mtime:
                continue
            dati = (root / p).read_bytes()
            sha = hashlib.sha256(dati).hexdigest()
            if p in noti and noti[p][1] == sha:
                solo_mtime.append((mtime, p))
                continue
            (rep.modificati if p in noti else rep.aggiunti).append(p)
            da_elaborare.append((p, dati.decode("utf-8", errors="replace"), sha, mtime))
        rep.rimossi = sorted(set(noti) - set(su_disco))
        elaborati, testi = [], {}
        for p, testo, sha, mtime in da_elaborare:
            fonte, chunks = chunk_di(self.config, p, testo)
            hashes = [chiave(self.embedder.model_id, c.testo_embed) for c in chunks]
            testi.update(zip(hashes, (c.testo_embed for c in chunks)))
            elaborati.append((p, sha, mtime, fonte, chunks, hashes))
        # embedding (lento, CPU) prima di toccare il DB: il lock di scrittura dura solo il blocco sotto
        vettori, rep.vettori_nuovi = assicura(self.config.emb_dir, self.embedder, testi)
        if solo_mtime or rep.rimossi or elaborati:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.executemany("UPDATE file SET mtime_ns = ? WHERE percorso = ?", solo_mtime)
                for p in rep.rimossi:
                    self._rimuovi(p)
                for p, sha, mtime, fonte, chunks, hashes in elaborati:
                    self._rimuovi(p)  # anche righe scritte nel frattempo da un altro processo
                    self._inserisci(p, sha, mtime, fonte, chunks, hashes, vettori)
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        return rep

    def _rimuovi(self, p: str) -> None:
        self.db.execute("DELETE FROM chunk_fts WHERE rowid IN (SELECT id FROM chunk WHERE percorso = ?)", (p,))
        self.db.execute("DELETE FROM chunk WHERE percorso = ?", (p,))
        self.db.execute("DELETE FROM file WHERE percorso = ?", (p,))

    def _inserisci(self, p: str, sha: str, mtime: int, fonte: Fonte, chunks: list[Chunk],
                   hashes: list[str], vettori: dict[str, np.ndarray]) -> None:
        m = fonte.meta
        self.db.execute(
            "INSERT INTO file VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (p, mtime, sha, m.tipo, m.progetto, m.data,
             json.dumps(m.partecipanti, ensure_ascii=False), json.dumps(fonte.avvisi, ensure_ascii=False)),
        )
        for c, h in zip(chunks, hashes):
            cur = self.db.execute(
                "INSERT INTO chunk (percorso, titoli, testo, riga_inizio, riga_fine, speaker, hash, vettore) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p, json.dumps(c.titoli, ensure_ascii=False), c.testo, c.riga_inizio, c.riga_fine,
                 json.dumps(c.speaker, ensure_ascii=False), h, vettori[h].astype("<f4").tobytes()),
            )
            self.db.execute("INSERT INTO chunk_fts (rowid, testo, titoli) VALUES (?, ?, ?)",
                            (cur.lastrowid, c.testo, " ".join(c.titoli)))

    def matrice(self) -> Matrice:
        with self.lock:
            # l'impronta cambia anche quando scrive un altro processo (id AUTOINCREMENT, mai riusati)
            impronta = tuple(self.db.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM chunk").fetchone())
            if self._matrice is None or impronta != self._impronta:
                self._matrice = self._carica_matrice()
                self._impronta = impronta
            return self._matrice

    def _carica_matrice(self) -> Matrice:
        righe = self.db.execute("SELECT id, percorso, vettore FROM chunk ORDER BY id").fetchall()
        return Matrice(
            ids=np.array([r[0] for r in righe], dtype=np.int64),
            vettori=np.frombuffer(b"".join(r[2] for r in righe), dtype="<f4").reshape(len(righe), self.embedder.dim),
            percorsi=np.array([r[1] for r in righe], dtype=object),
        )

    def avvisi(self) -> dict[str, list[str]]:
        return {p: json.loads(a) for p, a in
                self.db.execute("SELECT percorso, avvisi FROM file WHERE avvisi != '[]' ORDER BY percorso")}

    def hash_vivi(self) -> set[str]:
        return {h for (h,) in self.db.execute("SELECT DISTINCT hash FROM chunk")}

    def close(self) -> None:
        self.db.close()
