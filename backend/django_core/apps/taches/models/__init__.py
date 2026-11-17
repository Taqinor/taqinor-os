"""Modèles de l'app `taches` : la répartition par fichier est celle de reference/donnees.md §2.

Importe chaque sous-module (enregistrement des 21 modèles) sans ré-exporter un seul nom : un
appelant importe depuis le module propriétaire (`from apps.taches.models.taches import Tache`).
"""
from apps.taches.models import (  # noqa: F401
    agenda,
    erp,
    gestes,
    journee,
    presence,
    projets,
    rythme,
    taches,
)
