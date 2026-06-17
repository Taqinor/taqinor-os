"""A3 — l'option retenue à l'acceptation (« Sans batterie » / « Avec batterie »)
est AUTORITATIVE en aval.

La facture (échéancier) et le chantier (nomenclature/BOM) n'utilisent QUE les
lignes de l'option acceptée :

  * « Sans batterie » → exclut les batteries et les onduleurs hybrides ;
  * « Avec batterie » → exclut les onduleurs réseau/injection.

Le découpage réutilise EXACTEMENT les mêmes prédicats que le moteur de devis
(``quote_engine.builder``) pour rester identique au PDF. On ne filtre que pour
un VRAI devis à deux options (réseau ET hybride+batterie) ; un devis à option
unique, un pompage ou une liste libre garde TOUTES ses lignes — comportement
historique strictement inchangé.

Les totaux sont calculés par la MÊME formule que ``Devis.total_ht/total_tva``
(somme des lignes, TVA par ligne), donc au centime près et cohérents avec les
factures existantes ; on ne réimplémente aucun calcul d'argent à la main.
"""
from __future__ import annotations

from decimal import Decimal

# Prédicats de classification — partagés avec le moteur de devis. Purs (chaînes).
from apps.ventes.quote_engine.builder import (
    _is_battery, _is_hybrid_inverter, _is_reseau_inverter,
)

SANS_BATTERIE = 'sans_batterie'
AVEC_BATTERIE = 'avec_batterie'


def _blob(ligne) -> str:
    """Désignation + nom du produit lié — le moteur classe sur les deux pour
    qu'une désignation éditée à la main ne casse pas le découpage."""
    produit = getattr(ligne, 'produit', None)
    nom = getattr(produit, 'nom', '') or ''
    desig = getattr(ligne, 'designation', '') or ''
    return f"{desig} {nom}"


def filter_lines_for_option(lignes, option):
    """Filtre PUR d'une liste de lignes selon l'option (testable sans Django).

    Miroir exact du split de ``build_quote_data`` : « sans » = ni batterie ni
    onduleur hybride ; « avec » = pas d'onduleur réseau. Toute autre valeur
    (vide / inconnue) renvoie toutes les lignes.
    """
    if option == SANS_BATTERIE:
        return [li for li in lignes
                if not _is_battery(_blob(li))
                and not _is_hybrid_inverter(_blob(li))]
    if option == AVEC_BATTERIE:
        return [li for li in lignes if not _is_reseau_inverter(_blob(li))]
    return list(lignes)


def has_two_options(devis) -> bool:
    """True si le devis comporte deux VRAIES options (réseau ET hybride+batterie)
    — seul cas où l'option retenue change réellement le périmètre facturé."""
    try:
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        return data.get('nb_options', 1) == 2
    except Exception:  # noqa: BLE001 — l'aval ne doit jamais casser sur le PDF
        return False


def option_lines(devis, option=None):
    """Lignes RÉELLES du devis pour l'option retenue (nomenclature du chantier).

    Ne filtre que pour un vrai devis à deux options ; sinon renvoie toutes les
    lignes (option unique, pompage, liste libre → périmètre complet inchangé).
    """
    if option is None:
        option = getattr(devis, 'option_acceptee', '') or ''
    lignes = list(devis.lignes.select_related('produit').all())
    if not option or not has_two_options(devis):
        return lignes
    return filter_lines_for_option(lignes, option)


def option_totaux(devis, option=None) -> dict:
    """Totaux HT / TVA / TTC (Decimals, centime) pour l'option retenue.

    Calculés par la même formule que ``Devis.total_ht/total_tva`` mais sur le
    sous-ensemble de lignes de l'option. Sans vraie deuxième option, renvoie les
    totaux complets du devis → identiques au comportement historique au centime.
    """
    if option is None:
        option = getattr(devis, 'option_acceptee', '') or ''
    if not option or not has_two_options(devis):
        ht = Decimal(str(devis.total_ht))
        tva = Decimal(str(devis.total_tva))
        return {'ht': ht, 'tva': tva, 'ttc': ht + tva}
    lignes = filter_lines_for_option(
        list(devis.lignes.select_related('produit').all()), option)
    ht = sum((Decimal(str(li.total_ht)) for li in lignes), Decimal('0'))
    tva = sum(
        (Decimal(str(li.total_ht)) * (Decimal(str(li.taux_tva_effectif))
                                      / Decimal('100'))
         for li in lignes),
        Decimal('0'))
    return {'ht': ht, 'tva': tva, 'ttc': ht + tva}
