"""Écritures/orchestration du répertoire ``Tiers`` (ARC17).

Point d'entrée WRITE que les autres apps consommeront (ARC18/19) sans importer
``tiers.models`` : ``tiers`` reste une couche fondation. ``company`` est
TOUJOURS un argument explicite posé par l'appelant côté serveur — jamais lue
d'un corps de requête ici.
"""
from .models import Tiers


def creer_tiers(*, company, nom, **champs):
    """Crée un ``Tiers`` pour une société donnée.

    ``company`` et ``nom`` sont obligatoires ; les autres champs
    (coordonnées, identifiants légaux, rôles, type) sont optionnels et
    passés tels quels au modèle.
    """
    return Tiers.objects.create(company=company, nom=nom, **champs)
