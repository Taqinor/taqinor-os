"""Fournisseur d'effacement 09-08 de l'app `taches` (reference/donnees.md §5 ; regles.md « Effacement 09-08 »).

Seconde porte de l'effacement (la première : le récepteur `lead_erased` de `receivers.py`) :
`register_dsr_provider('taches', export=None, erase=effacer_sujet)`, posé par `TachesConfig.ready()`.
`taches` ne détient aucune donnée du sujet à exporter (`export=None`). L'ordre d'effacement par
défaut (0) passe AVANT `crm` (100) : la clé de résolution (e-mail, téléphone) existe encore.
"""
from core import dsr as registre_dsr

PROVIDER_NAME = 'taches'


def effacer_sujet(company, subject_identifier):
    """Résout le sujet en leads et clients par la porte de `crm` (`cibles_du_sujet`, même résolution
    qu'`erase_crm`) puis efface ce que `taches` en garde → nombre de lignes touchées."""
    from apps.crm.selectors import cibles_du_sujet
    from apps.taches.services.donnees import effacer_cibles

    cibles = cibles_du_sujet(company, subject_identifier)
    return effacer_cibles(company.pk, leads=cibles['leads'], clients=cibles['clients'])


def register():
    """Enregistre le fournisseur (idempotent). Appelé par `TachesConfig.ready()`."""
    registre_dsr.register_dsr_provider(PROVIDER_NAME, export=None, erase=effacer_sujet)
