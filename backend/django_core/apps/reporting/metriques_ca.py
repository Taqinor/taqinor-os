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
    debut, fin = _bornes(period)
    if debut is not None:
        qs = qs.filter(date_emission__gte=debut)
    if fin is not None:
        qs = qs.filter(date_emission__lte=fin)
    from apps.facturation.selectors import factures_avec_montant_du
    return list(factures_avec_montant_du(qs))  # lignes + avoirs (ASOC73)


def _bornes(period):
    """``period`` (``(debut, fin)`` ou ``{'debut', 'fin'}``) → (debut, fin)."""
    if not period:
        return None, None
    if isinstance(period, (tuple, list)):
        return tuple((list(period) + [None, None])[:2])
    return period.get('debut'), period.get('fin')


def _part_ht(facture, montant_ttc):
    """AANA55 — part HT d'un montant TTC, au prorata HT/TTC de la facture."""
    total_ttc = Decimal(facture.total_ttc or 0)
    if total_ttc <= 0:
        return Decimal('0')
    montant = min(Decimal(montant_ttc or 0), total_ttc)
    return montant * Decimal(facture.total_ht or 0) / total_ttc


def ttc_net(facture):
    """ASOC73 (D-ASOC-5) — TTC net d'avoirs : ``total_ttc`` − terme ``avoirs``
    de ``decomposition_du`` (même source que ``montant_du``), borné à 0."""
    from apps.facturation.models import decomposition_du
    net = Decimal(facture.total_ttc or 0) - decomposition_du(facture)['avoirs']
    return max(net, Decimal('0'))


def ht_net(facture):
    """ASOC73 — HT net d'avoirs, au prorata HT/TTC (``_part_ht``)."""
    return _part_ht(facture, ttc_net(facture))


def _somme(factures, valeur):
    return sum((valeur(f) for f in factures), Decimal('0'))


def ca_ht(company, user=None, *, period=None, filters=None):
    """Somme des HT nets d'avoirs (ASOC73) de la population."""
    return _somme(_factures(company, period, filters), ht_net)


def ca_ttc(company, user=None, *, period=None, filters=None):
    """Somme des TTC nets d'avoirs (ASOC73) de la population."""
    return _somme(_factures(company, period, filters), ttc_net)


def panier_moyen(company, user=None, *, period=None, filters=None):
    """CA TTC ÷ nombre de factures ; ``None`` sur une population vide."""
    factures = _factures(company, period, filters)
    if not factures:
        return None
    return _somme(factures, ttc_net) / len(factures)


def taux_conversion(company, user=None, *, period=None, filters=None):
    """ASOC72 (D-AANA-1) — LE taux de gain du reporting (gagnés ÷ NON perdus)
    sur la fenêtre de leads du classement ; ``None`` sans lead non perdu."""
    from apps.reporting.services import leads_de_la_fenetre, taux_gain
    from apps.semantic.services import MetriqueNonResolvable
    if filters:
        raise MetriqueNonResolvable(
            'Le taux de conversion ne prend aucun filtre (reçu : %s).'
            % ', '.join(sorted(filters)))
    return taux_gain(leads_de_la_fenetre({'company': company}, *_bornes(period)))


def register_metric_adapters():
    """Enregistre les adaptateurs (idempotent) — appelé par ``ready()``."""
    from apps.semantic.adapters import register_adapter
    register_adapter('reporting.ca_ht', ca_ht)
    register_adapter('reporting.ca_ttc', ca_ttc)
    register_adapter('reporting.panier_moyen', panier_moyen)
    register_adapter('reporting.taux_gain', taux_conversion)
