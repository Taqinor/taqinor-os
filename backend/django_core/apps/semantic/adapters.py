"""NTDATA11 — ADAPTATEURS DE MÉTRIQUE : quand le chiffre N'EST PAS une requête.

POURQUOI. Certaines métriques du cœur ne sont PAS un agrégat SQL sur un
dataset. Le DSO et la marge brute du dépôt sont calculés par
``apps.compta.selectors.pilotage_financier`` À PARTIR DU GRAND LIVRE (encours
3421/4411, compte de produits et charges) ; le pipeline pondéré passe
lead-par-lead par ``core.win_probability``. Ces définitions existent DÉJÀ,
elles sont l'autorité du dépôt, et les ré-écrire en SQL produirait un SECOND
chiffre — exactement ce que la couche sémantique existe pour empêcher.

CE QUE C'EST. Un registre en mémoire ``{clé: fonction}`` que les apps
peuplent depuis leur ``apps.py`` ``ready()``, sur le modèle EXACT du registre
de datasets de ``core.data_explorer``. La fonction rend UN SCALAIRE :

    adaptateur(company, user, *, period=None, filters=None) -> valeur | None

``semantic`` n'importe donc AUCUNE app : c'est l'app propriétaire du calcul
qui vient s'enregistrer. Une métrique l'appelle par
``mesure = {"adapter": "compta.dso"}``.

UN ADAPTATEUR NE REND JAMAIS DE SÉRIE. Un scalaire n'a pas de dimensions : le
résolveur refuse un ``group_by`` sur une métrique d'adaptateur, en français,
plutôt que de rendre une série fabriquée.
"""
from __future__ import annotations

# Registre en mémoire : { clé: fonction }.
_ADAPTATEURS: dict[str, object] = {}


class AdaptateurInconnu(Exception):
    """Aucun adaptateur n'est enregistré sous cette clé."""


def register_adapter(cle, fonction):
    """Enregistre un adaptateur scalaire (idempotent : ré-enregistrer écrase).

    Appelé depuis le ``ready()`` de l'app QUI PORTE le calcul — jamais depuis
    ``semantic``, qui n'importe aucune app métier.
    """
    if not cle or not callable(fonction):
        raise ValueError('Adaptateur : clé + fonction appelable requises.')
    _ADAPTATEURS[cle] = fonction


def get_adapter(cle):
    fonction = _ADAPTATEURS.get(cle)
    if fonction is None:
        raise AdaptateurInconnu(
            'Adaptateur de métrique inconnu : « %s » (le module qui le '
            "fournit est peut-être désactivé)." % cle)
    return fonction


def list_adapters():
    """Clés enregistrées, triées (rendu stable)."""
    return sorted(_ADAPTATEURS)
