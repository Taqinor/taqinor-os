"""Modèles de l'app `taches` : la répartition par fichier est celle de reference/donnees.md §2."""
from apps.taches.models.projets import ModeleProjet, Projet, RevueProjet, Section  # noqa: F401
from apps.taches.models.taches import (  # noqa: F401
    ElementChecklist,
    Etiquette,
    EtiquetteTache,
    Rappel,
    RegleRecurrence,
    Tache,
    VueEnregistree,
)
