"""Recharge VE nocturne et plancher de batterie (SPL258, déplacé de ``etude_horaire.py``).

CAD170 / QJR612 : la couche véhicule entièrement nocturne, ses kWh/jour, le
besoin de stockage qu'elle ajoute (servi par une taille d'offre RÉELLEMENT
vendue) et le plancher appliqué au choix du stockage. Une feuille qui ne lit
que ``horaire/base._num`` et, en import local, ``courbes_journalieres``.
Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_eh_ve.json``.
"""
from __future__ import annotations

import logging

from apps.ventes.horaire.base import _num

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.etude_horaire")


# ════════════════════════════════════════════════════════════════════════════
# CAD170 — LA RECHARGE NOCTURNE SE COUVRE PAR LE STOCKAGE, PAS PAR UN CONSEIL
# ════════════════════════════════════════════════════════════════════════════
#
# LE CAS MAJORITAIRE. La fenêtre de recharge par défaut est 21h-6h : la voiture
# se charge quand le champ ne produit plus. L'audit du 21/09/2026 a mesuré
# l'effet sur l'autoconsommation — NUL, même avec une batterie de 10 kWh
# (reproduit deux fois par ses relecteurs).
#
# LA DÉCISION FONDATEUR (21/09/2026). On ne conseille PAS « rechargez de
# jour » comme argument principal : on DIMENSIONNE la batterie pour couvrir la
# recharge nocturne. Le conseil de décaler la recharge est ÉCARTÉ — le gain
# chiffré qui le soutenait était gonflé par l'absence de borne que CAD165 (4)
# a corrigée.
#
# LES DEUX BORNES, et pourquoi elles ne sont pas négociables :
#   · l'énergie ajoutée est celle que le moteur PLACE déjà (``kwh_jour`` de la
#     couche véhicule, dérivée des km déclarés et de la conversion ADEME) —
#     aucune consommation de recharge n'est inventée ici ;
#   · le besoin est ensuite servi par une TAILLE D'OFFRE RÉELLEMENT VENDUE :
#     jamais une batterie sur mesure, jamais au-delà du catalogue. Sans
#     catalogue, aucune taille n'est proposée — l'omission est nommée.


def _couche_ve_nocturne(equipements):
    """La couche véhicule quand sa recharge est ENTIÈREMENT nocturne, sinon None.

    « Nocturne » n'est pas un horaire choisi ici : c'est la fenêtre
    heures-creuses que le module de courbes documente déjà
    (``courbes_journalieres.VE_CRENEAUX['nuit']``). Une recharge déclarée de
    jour ou de soirée n'entre donc pas dans ce calcul."""
    couche = (equipements or {}).get('ve') or {}
    heures = couche.get('heures') or []
    if not heures:
        return None
    try:
        from ..courbes_journalieres import VE_CRENEAUX
        nuit = set(VE_CRENEAUX['nuit'])
    except Exception:  # noqa: BLE001 — sans fenêtre de référence, on s'abstient
        return None
    return couche if set(heures) <= nuit else None


def recharge_ve_nocturne_kwh_jour(equipements) -> float:
    """kWh/jour de recharge NOCTURNE à couvrir, ou ``0.0``.

    Pas de couche véhicule, ou recharge déclarée hors de la nuit ⇒ ``0.0`` :
    il n'y a alors rien à ajouter au stockage."""
    couche = _couche_ve_nocturne(equipements)
    if couche is None:
        return 0.0
    return max(0.0, _num(couche.get('kwh_jour')))


def besoin_stockage_avec_recharge_ve(besoin_kwh, equipements,
                                     tailles_offre_kwh) -> dict:
    """CAD170 — le besoin de stockage AUGMENTÉ de la recharge nocturne.

    ``besoin_kwh``       le besoin de stockage établi par ailleurs (kWh) ;
    ``equipements``      les couches de ``composer_equipements`` ;
    ``tailles_offre_kwh`` les capacités RÉELLEMENT VENDUES (catalogue).

    Renvoie ``{besoin_base_kwh, recharge_ve_kwh, besoin_total_kwh,
    taille_retenue_kwh, plafonne, motif}``.

    La taille retenue est la PLUS PETITE taille d'offre qui couvre le besoin
    total ; si aucune ne le couvre, c'est la PLUS GRANDE, et ``plafonne`` vaut
    True avec son motif — jamais une capacité hors catalogue, jamais une
    batterie sur mesure. Sans catalogue, ``taille_retenue_kwh`` vaut ``None``
    et le motif nomme ce qui manque (aucune taille inventée)."""
    base = max(0.0, _num(besoin_kwh))
    recharge = recharge_ve_nocturne_kwh_jour(equipements)
    total = base + recharge
    tailles = sorted({round(max(0.0, _num(t)), 3)
                      for t in (tailles_offre_kwh or []) if _num(t) > 0})
    sortie = {
        'besoin_base_kwh': round(base, 2),
        'recharge_ve_kwh': round(recharge, 2),
        'besoin_total_kwh': round(total, 2),
        'taille_retenue_kwh': None,
        'plafonne': False,
        'motif': '',
    }
    if not tailles:
        sortie['motif'] = (
            "aucune taille d'offre connue : le besoin est chiffré, la "
            "capacité à vendre reste à choisir dans le catalogue — jamais "
            "une batterie sur mesure.")
        return sortie
    couvrantes = [t for t in tailles if t >= total]
    if couvrantes:
        sortie['taille_retenue_kwh'] = couvrantes[0]
        return sortie
    sortie['taille_retenue_kwh'] = tailles[-1]
    sortie['plafonne'] = True
    sortie['motif'] = (
        f"besoin de {round(total, 2)} kWh plafonné à la plus grande taille "
        f"vendue ({tailles[-1]} kWh) : au-delà du catalogue, on ne compose "
        "pas une batterie sur mesure.")
    return sortie


# ── QJR612 — LE PLANCHER RÉELLEMENT APPLIQUÉ AU CHOIX DU STOCKAGE ────────────
#
# DÉCISION FONDATEUR (30/09/2026, verbatim) : « add more panels so battery is
# always charged. and btw this is a rule that exists already for batteries in
# general in my ERP ». Le plancher ci-dessous RELÈVE la batterie retenue ; la
# règle « batteries toujours pleines » (``se_remplit_tous_les_jours``, déjà
# appliquée par ``dimensionnement.balayer_tailles``) fait alors monter le champ
# jusqu'à ce que cette batterie se remplisse chaque jour — jamais une banque
# qui dort.


def equipements_sans_recharge_ve_nocturne(equipements):
    """Les couches du lead SANS la couche véhicule NOCTURNE — la base du
    plancher, pour ne jamais compter deux fois la recharge.

    Une recharge de jour ou de soirée n'est pas la couche nocturne : les
    couches sont alors rendues telles quelles. ``None`` reste ``None``."""
    if equipements is None:
        return None
    if _couche_ve_nocturne(equipements) is None:
        return equipements
    return {cle: couche for cle, couche in equipements.items() if cle != 've'}


def plancher_batterie_recharge_ve(besoin_base_kwh, equipements,
                                  tailles_offre_kwh):
    """Le PLANCHER de stockage imposé par la recharge VE nocturne, ou ``None``.

    ``None`` quand aucune recharge nocturne n'est déclarée : rien ne change
    alors, à l'octet près. Sinon, la sortie de
    :func:`besoin_stockage_avec_recharge_ve` — ``besoin_base_kwh`` doit être le
    besoin du même lead SANS la couche VE nocturne
    (:func:`equipements_sans_recharge_ve_nocturne`), ``tailles_offre_kwh`` les
    capacités RÉELLEMENT composées (jamais inventées)."""
    if recharge_ve_nocturne_kwh_jour(equipements) <= 0:
        return None
    return besoin_stockage_avec_recharge_ve(
        besoin_base_kwh, equipements, tailles_offre_kwh)
