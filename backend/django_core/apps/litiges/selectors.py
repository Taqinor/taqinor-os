"""Sélecteurs (lecture seule) du module ``apps.litiges``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""


def relances_suspendues_pour_facture(facture_id: int, company) -> bool:
    """Retourne True si au moins un litige ouvert bloque les relances pour
    cette facture.

    LITIGE3 — utilisé par ``ventes.scheduled.relance_reminders`` (via import
    local) pour court-circuiter l'envoi sur les factures en litige financier
    bloquant.

    Critères :
    - source_type == 'facture'
    - source_id == facture_id
    - company == company (isolation multi-tenant)
    - statut pas terminal (pas 'resolue' ni 'rejetee')
    - bloque_relances == True

    Args:
        facture_id: PK de la Facture à vérifier.
        company: instance ``authentication.Company`` de la société.

    Returns:
        True si un litige bloquant est actif, False sinon.
    """
    from .models import Reclamation

    STATUTS_OUVERTS = (
        Reclamation.Statut.OUVERTE,
        Reclamation.Statut.EN_TRAITEMENT,
    )
    return Reclamation.objects.filter(
        company=company,
        source_type='facture',
        source_id=facture_id,
        statut__in=STATUTS_OUVERTS,
        bloque_relances=True,
    ).exists()
