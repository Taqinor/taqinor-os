"""CE2E6 (AMOT64 a) — le productible SAISI par la société atteint le moteur horaire.

« Toute valeur saisie respectée » : ``CompanyProfile.productible_kwh_kwc``
pilotait déjà le chemin non horaire (``pricing.calculate_savings_roi``,
production = kWc × productible × ``PRODUCTION_DERATE``), mais le moteur horaire
chiffrait toujours sur la série PVGIS de la ville. La série mensuelle PVGIS est
donc mise à l'ÉCHELLE de la valeur saisie (même forme mois par mois, total =
valeur société) AVANT le calcul des jours types : la production ET les
économies qui en dérivent bougent ensemble — aucune seconde source, aucune
production réécrite après coup.

Niveau de règles 3 (``regles_au_moins(devis, REGLES_CORRIGEES_2710)``) : un
devis rendu aux règles d'avant garde la production que le client a reçue.
Sans valeur société (vide) : ``None``, série PVGIS inchangée à l'octet.
"""
from __future__ import annotations

import logging

from apps.ventes.domain.regles_calcul import (
    REGLES_CORRIGEES_2710, regles_au_moins)
from apps.ventes.horaire.base import _num

logger = logging.getLogger("apps.ventes.etude_horaire")


def productible_societe(company, devis=None):
    """Productible annuel saisi par la société (kWh/kWc/an), ou ``None``.

    ``None`` : pas de société, devis aux règles d'avant le niveau 3, champ vide
    ou illisible. ``devis=None`` (aperçu de création, lead) suit les règles
    courantes. Même lecture que le chiffrage (``parametres.selectors.tariff_for``).
    """
    if company is None or not regles_au_moins(devis, REGLES_CORRIGEES_2710):
        return None
    try:
        from apps.parametres.selectors import tariff_for
        valeur = _num(tariff_for(company).get("productible_kwh_kwc"))
    except Exception:  # noqa: BLE001 — une étude ne casse jamais sur un réglage (D-ENF22-BLE001)
        logger.warning("productible société illisible — série PVGIS gardée",
                       exc_info=True)
        return None
    return valeur if valeur > 0 else None


def productible_du_devis(devis):
    """:func:`productible_societe` pour la société de CE devis."""
    return productible_societe(getattr(devis, "company", None), devis)


def mettre_a_l_echelle(mensuel, productible_kwh_kwc):
    """``(productibles, source)`` de ``productible_mensuel`` ramenés au total saisi.

    La forme mensuelle PVGIS est gardée ; seul le total annuel devient la
    valeur société. Valeur absente/≤ 0 ou série vide ⇒ ``mensuel`` tel quel.
    """
    cible = _num(productible_kwh_kwc)
    if not mensuel or cible <= 0:
        return mensuel
    productibles, source = mensuel
    total = sum(_num(v) for v in productibles)
    if total <= 0:
        return mensuel
    facteur = cible / total
    return ([_num(v) * facteur for v in productibles],
            "productible_societe:%g;forme:%s" % (cible, source))
