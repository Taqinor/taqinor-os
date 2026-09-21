"""Sélecteurs (lectures) du module « Veille appels d'offres ».

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin de LIRE des
données de ce module passe par une fonction de CE fichier (jamais en important
``apps.veille_ao.models`` / ``.views`` directement). Les imports restent
paresseux (fonction-locaux) pour éviter les cycles au chargement des apps.
"""
from __future__ import annotations


# ── VAO29 — le carnet des acheteurs à démarcher ──────────────────────────

def acheteurs_cibles(company):
    """Le carnet d'UNE société (jamais tous les locataires)."""
    from .models import AcheteurCible

    return AcheteurCible.objects.filter(company=company)


def relances_dues(company, a_la_date=None):
    """Les relances ÉCHUES, triées par urgence.

    Une relance due doit être visible sans la chercher : elle alimente le
    centre d'échéances, pas une colonne triable qu'il faudrait penser à
    trier. Les relations « sans suite » en sont exclues — relancer quelqu'un
    qui a dit non use la relation au lieu de la construire.
    """
    return acheteurs_cibles(company).relances_dues(a_la_date)


def compte_relances_dues(company, a_la_date=None):
    """Le compteur du badge — une seule requête, jamais une liste chargée."""
    return relances_dues(company, a_la_date).count()


def acheteurs_sans_lead(company):
    """Ceux qui ne sont encore reliés à AUCUN lead CRM.

    Lecture par entier OPAQUE (``lead_id``) : aucun import de
    ``apps.crm.models`` — les deux apps restent découplées.
    """
    return acheteurs_cibles(company).filter(lead_id__isnull=True)


# ── VAO24 — l'état de la veille, pour un autre module qui voudrait le lire ──

def derniere_collecte_reussie(company):
    """Horodatage de la dernière collecte réussie, ou ``None``."""
    from .models import ExecutionCollecte

    execution = ExecutionCollecte.objects.filter(
        company=company).reussies().recentes().first()
    if execution is None:
        return None
    return execution.fin or execution.debut


# ── VAO31 — l'attribution : d'où vient réellement le chiffre d'affaires ────

def attribution(company, depuis=None):
    """« canal → avis → affaires → gagnés », CALCULÉ et jamais saisi.

    L'ISSUE des affaires est lue par le ``selectors.py`` d'``apps.ao``, jamais
    par ses modèles : c'est la frontière inter-apps du dépôt, et c'est ce qui
    garde le contrat import-linter vert.
    """
    from .kpis import attribution as calculer

    return calculer(company, depuis=depuis)
