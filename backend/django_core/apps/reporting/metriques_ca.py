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

TROIS CHIFFRES D'AFFAIRES, JAMAIS CONFONDUS (copilote vague 2, RPT1) — le
« CA » de l'ERP a trois sens, chacun calculé ICI, par le calcul que son écran
utilise déjà :

* FACTURÉ HT (``ca_ht``) — HT net d'avoirs des factures émises, payées ou en
  retard, à la date d'ÉMISSION ;
* ENCAISSÉ HT (``encaisse_ht``) — part HT des paiements reçus sur ces mêmes
  factures (``ca_encaisse_ht``, le calcul du tableau de bord), à la date
  d'ÉMISSION de la facture ;
* SIGNÉ HT (``ca_signe_ht``) — HT remisé de l'option acceptée des devis
  signés en vigueur, à la date de SIGNATURE (``devis_signes_de_la_fenetre``,
  le calcul du classement commercial).

Un adaptateur reçoit ``user`` : renseigné, il borne les documents à la portée
de son rôle (``borner_portee``, comme le tableau de bord) ; ``None`` = toute
la société (alertes, système).
"""
from decimal import Decimal

#: AANA55 — population du CA facturé / encaissé / en attente : brouillons et
#: annulées exclues (une seule liste, lue par le tableau de bord).
STATUTS_CA = ('emise', 'en_retard', 'payee')

#: Filtres admis → lookup ORM sur ``Facture``.
_FILTRES = {
    'statut': 'statut',
    'statut__in': 'statut__in',
    'type_facture': 'type_facture',
    'type_facture__in': 'type_facture__in',
    'client': 'client_id',
}


def _factures_qs(company, period, filters, user=None):
    """Factures de la société filtrées (liste blanche), bornées à ``period``
    sur ``date_emission`` ; ``user`` renseigné → portée de son rôle."""
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
    if user is not None:
        from apps.reporting.services import borner_portee
        qs = borner_portee(qs, user, 'factures')  # ALEC22
    debut, fin = _bornes(period)
    if debut is not None:
        qs = qs.filter(date_emission__gte=debut)
    if fin is not None:
        qs = qs.filter(date_emission__lte=fin)
    return qs


def _factures(company, period, filters, user=None):
    from apps.facturation.selectors import factures_avec_montant_du
    qs = _factures_qs(company, period, filters, user)
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


def avec_du(factures):
    """APRF13 (C-APRF-025) — ``[(facture, montant_du)]``.

    Un queryset passe par ``facturation.selectors.factures_avec_montant_du``
    (APRF11 : les six relations lues par ``montant_du`` préchargées) et
    ``montant_du`` n'est évalué qu'UNE fois par facture. Une liste déjà
    calculée (paires) est rendue telle quelle.
    """
    if isinstance(factures, list):
        return factures
    from apps.facturation.selectors import factures_avec_montant_du
    return [(f, f.montant_du) for f in factures_avec_montant_du(factures)]


def ht_encaisse(facture):
    """AANA55 — HT réellement encaissé : la part HT des paiements reçus
    (``montant_paye``), jamais ``total_ht`` d'une facture « payée » (un avoir
    qui solde une facture n'encaisse rien)."""
    return _part_ht(facture, facture.montant_paye)


def ca_encaisse_ht(factures):
    """AANA20 / AANA55 — CA encaissé HT (queryset ou paires ``avec_du``) : LE
    calcul du tableau de bord Reporting, lu aussi par l'assistant."""
    return sum((ht_encaisse(f) for f, _du in avec_du(factures)),
               Decimal('0'))


def ttc_net(facture):
    """ASOC73 (D-ASOC-5) — TTC net d'avoirs : ``total_ttc`` − terme ``avoirs``
    de ``decomposition_du`` (même source que ``montant_du`` :
    ``Facture.avoirs_total``), borné à 0. Seul ce terme est lu : calculer les
    six (notes de débit, retenues…) coûtait deux requêtes PAR facture sur une
    population préchargée des seuls avoirs (VNT109, job costing)."""
    net = Decimal(facture.total_ttc or 0) - Decimal(facture.avoirs_total or 0)
    return max(net, Decimal('0'))


def ht_net(facture):
    """ASOC73 — HT net d'avoirs, au prorata HT/TTC (``_part_ht``)."""
    return _part_ht(facture, ttc_net(facture))


def _somme(factures, valeur):
    return sum((valeur(f) for f in factures), Decimal('0'))


def ca_ht(company, user=None, *, period=None, filters=None):
    """Somme des HT nets d'avoirs (ASOC73) de la population — bornée à la
    portée du rôle de ``user`` quand il est fourni (comme signé et encaissé)."""
    return _somme(_factures(company, period, filters, user), ht_net)


def ca_ttc(company, user=None, *, period=None, filters=None):
    """Somme des TTC nets d'avoirs (ASOC73) de la population (même portée)."""
    return _somme(_factures(company, period, filters, user), ttc_net)


def panier_moyen(company, user=None, *, period=None, filters=None):
    """CA TTC ÷ nombre de factures ; ``None`` sur une population vide."""
    factures = _factures(company, period, filters, user)
    if not factures:
        return None
    return _somme(factures, ttc_net) / len(factures)


def ca_facture_ht_periode(company, debut, fin, *, user=None):
    """FACTURÉ HT de ``[debut, fin]`` (date d'émission) : l'adaptateur ``ca_ht``
    sur les statuts du CA, borné à la portée du rôle de ``user``."""
    return _somme(_factures(company, (debut, fin),
                            {'statut__in': list(STATUTS_CA)}, user), ht_net)


def _sans_filtre(nom, filters):
    from apps.semantic.services import MetriqueNonResolvable
    if filters:
        raise MetriqueNonResolvable(
            'Le chiffre « %s » ne prend aucun filtre (reçu : %s).'
            % (nom, ', '.join(sorted(filters))))


def encaisse_ht(company, user=None, *, period=None, filters=None):
    """ENCAISSÉ HT : part HT des paiements reçus sur les factures émises,
    payées ou en retard émises dans ``period`` (date d'émission) — exactement
    ``ca_encaisse_ht`` du tableau de bord Reporting."""
    _sans_filtre('encaissé HT', filters)
    return ca_encaisse_ht(_factures_qs(
        company, period, {'statut__in': list(STATUTS_CA)}, user))


def ca_signe_ht(company, user=None, *, period=None, filters=None):
    """SIGNÉ HT : HT remisé de l'option acceptée des devis signés en vigueur
    dont la signature (``date_acceptation``) tombe dans ``period`` — la
    population et le montant du classement commercial."""
    from apps.reporting.services import (
        borner_portee, devis_signes_de_la_fenetre)
    from apps.ventes.utils.options import option_totaux

    _sans_filtre('signé HT', filters)
    devis = devis_signes_de_la_fenetre({'company': company}, *_bornes(period))
    if user is not None:
        devis = borner_portee(devis, user, 'devis')
    return sum((Decimal(str(option_totaux(d)['ht'])) for d in devis),
               Decimal('0'))


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
    register_adapter('reporting.ca_signe_ht', ca_signe_ht)
    register_adapter('reporting.encaisse_ht', encaisse_ht)
