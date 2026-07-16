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


def disponible_credit(client):
    """NTCRD5 — disponible de crédit d'un client.

    ``montant_limite - encours_client`` ; ``None`` (illimité) si aucune
    ``LimiteCredit`` active n'est définie pour ce client — comportement
    historique inchangé (aucun hold possible sans limite). Renvoie
    ``{'limite': Decimal|None, 'encours': Decimal, 'disponible': Decimal|None,
    'pct_utilise': float|None, 'depasse': bool}``."""
    from .models import LimiteCredit

    encours = encours_client(client)
    limite_obj = LimiteCredit.objects.filter(
        client=client, actif=True).first()
    montant_limite = limite_obj.montant_limite if limite_obj else None

    if montant_limite is None:
        return {
            'limite': None, 'encours': encours, 'disponible': None,
            'pct_utilise': None, 'depasse': False,
        }

    disponible = montant_limite - encours
    pct_utilise = (
        float(encours / montant_limite) if montant_limite > 0 else 0.0)
    return {
        'limite': montant_limite, 'encours': encours,
        'disponible': disponible, 'pct_utilise': pct_utilise,
        'depasse': disponible < 0,
    }
