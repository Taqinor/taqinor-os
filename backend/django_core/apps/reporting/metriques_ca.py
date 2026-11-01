"""AANA77 (D-AANA-6) — adaptateurs sémantiques du CA facturé.

POURQUOI UN ADAPTATEUR ET PAS LE DATASET ``ventes_factures``. Le CA d'une
facture est ``Facture.total_ht`` / ``total_ttc`` : des PROPRIÉTÉS
(``facturation.totaux.TotauxDocumentMixin``), pas des colonnes. Les colonnes
``montant_ht`` / ``montant_ttc`` ne sont remplies que sur les factures
d'échéancier (montants figés) — NULL sur une facture classique, d'où un
``ca_ht`` vide (rejeu AANA74 : 18 factures classiques sur 18). Le total d'une
facture classique sort du noyau canonique (lignes → remise globale arrondie
au centime → palier ARRONDI-100 hérité du devis → ×N villas) : aucune
expression SQL ne le reproduit au centime, et une somme de lignes est
interdite par D-AANA-6. On lit donc la propriété, comme le tableau de bord
(AANA20).

Un adaptateur rend UN SCALAIRE (registre ``apps.semantic.adapters``) :
``period`` borne ``date_emission`` ; ``filters`` = filtres de la définition
puis de l'appelant, sur une liste blanche (un filtre inconnu est refusé, en
français, jamais ignoré).
"""
from decimal import Decimal

#: Filtres admis → lookup ORM sur ``Facture``.
_FILTRES = {
    'statut': 'statut',
    'statut__in': 'statut__in',
    'type_facture': 'type_facture',
    'type_facture__in': 'type_facture__in',
    'client': 'client_id',
}


def _factures(company, period, filters):
    from apps.semantic.services import MetriqueNonResolvable
    from apps.ventes.models import Facture

    criteres = {}
    for cle, valeur in (filters or {}).items():
        if cle not in _FILTRES:
            raise MetriqueNonResolvable(
                'Filtre « %s » non pris en charge pour le CA facturé '
                '(admis : %s).' % (cle, ', '.join(sorted(_FILTRES))))
        criteres[_FILTRES[cle]] = valeur
    qs = Facture.objects.filter(company=company, **criteres)
    if period:
        if isinstance(period, (tuple, list)):
            debut, fin = (list(period) + [None, None])[:2]
        else:
            debut, fin = period.get('debut'), period.get('fin')
        if debut is not None:
            qs = qs.filter(date_emission__gte=debut)
        if fin is not None:
            qs = qs.filter(date_emission__lte=fin)
    return list(qs.prefetch_related('lignes'))


def _somme(factures, attribut):
    return sum((Decimal(getattr(f, attribut) or 0) for f in factures),
               Decimal('0'))


def ca_ht(company, user=None, *, period=None, filters=None):
    """Somme des ``Facture.total_ht`` de la population."""
    return _somme(_factures(company, period, filters), 'total_ht')


def ca_ttc(company, user=None, *, period=None, filters=None):
    """Somme des ``Facture.total_ttc`` de la population."""
    return _somme(_factures(company, period, filters), 'total_ttc')


def panier_moyen(company, user=None, *, period=None, filters=None):
    """CA TTC ÷ nombre de factures ; ``None`` sur une population vide."""
    factures = _factures(company, period, filters)
    if not factures:
        return None
    return _somme(factures, 'total_ttc') / len(factures)


def register_metric_adapters():
    """Enregistre les trois adaptateurs (idempotent) — appelé par ``ready()``."""
    from apps.semantic.adapters import register_adapter
    register_adapter('reporting.ca_ht', ca_ht)
    register_adapter('reporting.ca_ttc', ca_ttc)
    register_adapter('reporting.panier_moyen', panier_moyen)
