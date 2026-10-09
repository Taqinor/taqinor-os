"""ENF14 — chargeur du fichier unique des exceptions PERMANENTES signées.

``scripts/exceptions_permanentes.yml`` liste les SEULES exceptions approuvées
nommément par le fondateur (règle du 09/10/2026, docs/claude-memory/
enforce-all-checks.md). Toute autre allowlist/base de dette est de la dette à
ramener à zéro. Format : sous-ensemble strict de YAML (pas de dépendance PyYAML
dans les gardes) :

    categorie:
      raison: une ligne
      entrees:
        - "valeur"        # une entrée par ligne, entre guillemets doubles
        # les lignes de commentaire sont permises partout

Usage : ``charger("tenant_exempt_models")`` -> ``set[str]`` des entrées.
"""
from __future__ import annotations

from pathlib import Path

FICHIER = Path(__file__).resolve().parent / "exceptions_permanentes.yml"


def _parser(texte: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    courant = None
    for brut in texte.splitlines():
        if not brut.strip() or brut.lstrip().startswith("#"):
            continue
        indent = len(brut) - len(brut.lstrip())
        ligne = brut.strip()
        if indent == 0 and ligne.endswith(":"):
            courant = out.setdefault(ligne[:-1], {"raison": "", "entrees": []})
        elif courant is None:
            continue
        elif ligne.startswith("- "):
            val = ligne[2:].strip()
            if len(val) >= 2 and val[0] == val[-1] == '"':
                val = val[1:-1]
            courant["entrees"].append(val)
        elif ligne.startswith("raison:") or ligne.startswith("critere:"):
            courant["raison"] = ligne.split(":", 1)[1].strip()
    return out


def categories(chemin: Path | None = None) -> dict[str, dict]:
    p = Path(chemin) if chemin else FICHIER
    if not p.is_file():
        return {}
    return _parser(p.read_text(encoding="utf-8"))


def charger(categorie: str, chemin: Path | None = None) -> set[str]:
    """Entrées permanentes d'une catégorie (ensemble vide si absente)."""
    return set(categories(chemin).get(categorie, {}).get("entrees", []))
