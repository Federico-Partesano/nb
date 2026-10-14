"""Configurazione del knowledge repo (.nb/config.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

NB_DIR = ".nb"
MODELLO_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TIPI = ("analisi", "documentazione", "trascrizione", "altro")
CARTELLA_TIPO = {"analisi": "analisi", "documentazione": "documentazione", "call": "trascrizione"}

CONFIG_DEFAULT = f"""\
[embedding]
model_id = "{MODELLO_DEFAULT}"
dim = 384

[chunk]
max_parole = 100
overlap = 20

[regole]
max_file_mb = 5
"""


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    root: Path
    model_id: str = MODELLO_DEFAULT
    dim: int = 384
    max_parole: int = 100
    overlap: int = 20
    max_file_mb: float = 5.0

    @property
    def nb_dir(self) -> Path:
        return self.root / NB_DIR

    @property
    def emb_dir(self) -> Path:
        return self.nb_dir / "emb"

    @property
    def index_path(self) -> Path:
        return self.nb_dir / "index.db"


def file_config(root: Path) -> Path:
    return root / NB_DIR / "config.toml"


def trova_root(inizio: Path) -> Path:
    inizio = inizio.resolve()
    for p in (inizio, *inizio.parents):
        if file_config(p).is_file():
            return p
    raise ConfigError("nessun knowledge repo nb qui (manca .nb/config.toml): esegui `nb init`")


def carica(root: Path) -> Config:
    try:
        dati = tomllib.loads(file_config(root).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"manca {file_config(root)}: esegui `nb init`") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f".nb/config.toml non valido: {e}") from None
    emb, chunk, regole = dati.get("embedding", {}), dati.get("chunk", {}), dati.get("regole", {})
    config = Config(
        root=root.resolve(),
        model_id=str(emb.get("model_id", MODELLO_DEFAULT)),
        dim=int(emb.get("dim", 384)),
        max_parole=int(chunk.get("max_parole", 100)),
        overlap=int(chunk.get("overlap", 20)),
        max_file_mb=float(regole.get("max_file_mb", 5)),
    )
    if config.overlap >= config.max_parole:
        raise ConfigError("chunk.overlap deve essere minore di chunk.max_parole")
    return config


def scrivi_default(root: Path) -> bool:
    """Scrive la config di default se manca. True se l'ha scritta."""
    f = file_config(root)
    if f.exists():
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(CONFIG_DEFAULT, encoding="utf-8")
    return True
