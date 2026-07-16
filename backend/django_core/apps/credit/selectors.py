"""apps.credit.selectors — lectures pures (jamais d'écriture ici).

Toute lecture cross-app passe par le ``selectors.py`` PUBLIC déjà exposé de
l'app cible (jamais un import direct de ``apps.ventes.models``/
``apps.crm.models`` ni une modification du ``selectors.py`` d'une autre app —
frontière inter-app CLAUDE.md). Quand aucun sélecteur existant ne couvre
exactement un besoin, on compose avec ceux qui existent plutôt que d'en
ajouter un nouveau côté ventes.
"""
from decimal import Decimal


def encours_client(client):
    """NTCRD4 — encours documentaire réel d'un client : Σ factures ouvertes
    (hors ``ANNULEE``/``PAYEE``), via le sélecteur EXISTANT
    ``apps.ventes.selectors.encours_clients_par_tiers`` (YLEDG13, déjà exposé
    cross-app — jamais un nouvel import/édition de ``ventes.selectors``).

    LIMITE CONNUE (périmètre de ce lane) : ne compte QUE les factures
    ouvertes — les BC ``LIVRE`` sans facture liée ne sont pas inclus, faute
    d'un sélecteur ventes existant les exposant sans modifier
    ``apps.ventes.selectors`` (hors périmètre déclaré de cette app). Un
    sélecteur ventes dédié (``encours_ouvert``) pourrait fermer cet écart
    dans une lane ventes future."""
    from apps.ventes.selectors import encours_clients_par_tiers

    entries = encours_clients_par_tiers(client.company)
    for entry in entries:
        if entry['tiers_id'] == client.id:
            return entry['encours']
    return Decimal('0')
