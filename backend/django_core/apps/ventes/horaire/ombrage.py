"""D-RES-2710-1 — l'ombrage SERVI par le calepinage dans le moteur horaire.

Décision fondateur (27/10/2026) : quand un calepinage existe pour le devis, la
production du moteur horaire résidentiel (``etude_horaire.jours_types_annee``,
les courbes de la proposition, la production par option) retire la perte
d'ombrage SERVIE par ce calepinage — la même lecture que l'étude bancable
(``etude._ombrage_du_calepinage``, CALX197/ACAL144). Sans calepinage, sans
simulation, ou simulation périmée : aucun ombrage (comportement d'avant,
octet-identique). ``lead.ombrage`` n'est JAMAIS lu (QJR107/D7 : pas de
coefficient sourcé).

Le moteur CONSOMME la perte du calepinage, il ne la remplace pas par la
production du calepinage (D-ACAL-6). La perte retenue est ``global`` de
``ombrage_servi`` : la perte d'ombrage de la cascade du SITE (somme des pans,
rapportée à l'énergie d'entrée — donc déjà pondérée par l'énergie de chaque
pan), en pour cent.

Niveau de règles 3 (``regles_au_moins(devis, REGLES_CORRIGEES_2710)``) : un
devis envoyé avant la correction garde la production que le client a reçue.
"""
from __future__ import annotations

import logging

from apps.ventes.domain.regles_calcul import (
    REGLES_CORRIGEES_2710, regles_au_moins)

logger = logging.getLogger("apps.ventes.etude_horaire")

#: Provenance publiée dans le bloc horaire (``ombrage.source``).
SOURCE_OMBRAGE_CALEPINAGE = 'calepinage'


def perte_ombrage_du_devis(devis):
    """Perte d'ombrage (%) servie par le calepinage du devis, ou ``None``.

    ``None`` : pas de devis enregistré, devis aux règles d'avant le niveau 3,
    pas de calepinage lisible, simulation absente ou périmée, valeur hors
    ``[0, 100[``. Ne lève jamais (un bloc horaire ne casse pas sur une lecture
    cross-app).
    """
    if devis is None or not getattr(devis, 'pk', None):
        return None
    if not regles_au_moins(devis, REGLES_CORRIGEES_2710):
        return None
    try:
        from apps.calepinage.selectors import ombrage_servi
        servi = ombrage_servi(devis.pk, getattr(devis, 'company', None))
    except Exception:  # noqa: BLE001 — lecture cross-app, jamais bloquante (D-ENF22-BLE001)
        logger.warning('ombrage du calepinage illisible (devis %s)',
                       getattr(devis, 'pk', None), exc_info=True)
        return None
    if not servi or servi.get('perime'):
        return None
    try:
        perte = float(servi.get('global'))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= perte < 100.0:
        return None
    return perte


def facteur_ombrage(perte_pct):
    """Facteur multiplicatif de production : ``1 − perte/100`` (1,0 sans perte)."""
    if perte_pct is None:
        return 1.0
    try:
        perte = float(perte_pct)
    except (TypeError, ValueError):
        return 1.0
    if not 0.0 <= perte < 100.0:
        return 1.0
    return 1.0 - perte / 100.0


def bloc_ombrage(perte_pct):
    """Bloc publié avec le résultat horaire (``None`` sans perte appliquée)."""
    if perte_pct is None:
        return None
    return {'perte_pct': round(float(perte_pct), 2),
            'source': SOURCE_OMBRAGE_CALEPINAGE}


def facteur_production_saison(devis):
    """Facteur de ``courbes_journalieres.production_par_saison`` pour ce devis.

    C-RHOR-004 — la production PAR SAISON servie à la page client
    (``courbes_journalieres.production`` et ``production_par_option`` :
    « Production ≈ X kWh/jour », pic en kW) était le productible PVGIS
    (``loss=14``) × kWc, SANS le complément ``PRODUCTION_DERATE`` que le
    moteur horaire, le PDF et la production annuelle par option appliquent :
    la courbe annonçait ≈ 7,5 % de production de plus que le devis. Niveau 3 :
    ``PRODUCTION_DERATE`` × ombrage du calepinage ; avant : 1,0 (chiffre
    d'origine, le client relit ce qu'il a reçu).
    """
    if not regles_au_moins(devis, REGLES_CORRIGEES_2710):
        return 1.0
    from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
    return PRODUCTION_DERATE * facteur_ombrage(perte_ombrage_du_devis(devis))
