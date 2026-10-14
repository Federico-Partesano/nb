"""Guardia: un file che stai per committare/modificare è stato cambiato sul remoto?"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from nb.gitutil import Commit, commit_che_toccano, fetch, upstream


@dataclass(frozen=True)
class Obsoleto:
    percorso: str
    commit: tuple[Commit, ...]

    def messaggio(self) -> str:
        righe = [f"✋ {self.percorso} è stato modificato sul remoto"]
        righe += [f'   {c.hash} — {c.autore}, {c.quando}: "{c.messaggio}"' for c in self.commit]
        righe.append("   Fai: git pull --rebase   poi riprova")
        return "\n".join(righe)


@dataclass
class EsitoGuardia:
    obsoleti: list[Obsoleto] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)


def controlla(root: Path, percorsi: list[str], fai_fetch: bool = True, timeout: float = 3.0) -> EsitoGuardia:
    esito = EsitoGuardia()
    if upstream(root) is None:
        esito.avvisi.append("branch senza upstream: controllo delle modifiche remote saltato")
        return esito
    if fai_fetch:
        errore = fetch(root, timeout)
        if errore:
            esito.avvisi.append(f"fetch non riuscito ({errore}): controllo sull'ultimo stato noto del remoto")
    for p in percorsi:
        commit = commit_che_toccano(root, "HEAD..@{u}", p)
        if commit:
            esito.obsoleti.append(Obsoleto(p, tuple(commit)))
    return esito
