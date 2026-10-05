"""Constantes 82-21 (loi n° 82-21 ; décret n° 2.25.100 ; décision ANRE n° 04/26)
— UN SEUL module sourcé, que le fondateur peut vérifier ligne à ligne (QXG6,
D-CIQ-4, CIQ201).

Loi n° 82-21 relative à l'autoproduction d'énergie électrique (BO 7400) ;
décret n° 2.25.100 (BO 7489 du 09/03/2026, en vigueur le 09/06/2026) ;
décision ANRE n° 04/26 (tarif de l'excédent, 01/03/2026 → 28/02/2027).

Le RÉGIME (déclaration / accord / autorisation) n'est PAS calculé ici : les
seuils et ``regime_8221_suggere`` sont des RÉ-EXPORTS du noyau
``core.reglementaire.regime_8221`` (CIQ612, seule source).

QXMT (18/08/2026) : ce module porte AUSSI le barème MOYENNE TENSION ONEE
(``TARIF_MT_ONEE``) utilisé par l'étude industrielle/commerciale quand le
dossier est raccordé en MT.
"""
from __future__ import annotations

import datetime as _dt

# Régime 82-21 : RÉ-EXPORTS du noyau (identité, jamais une copie — CIQ612).
from core.reglementaire.regime_8221 import (  # noqa: F401  (ré-exports)
    SEUIL_AUTORISATION_KW,
    SEUIL_DECLARATION_KW,
    regime_8221_suggere,
)

# ── Tarif de l'excédent injecté (décision ANRE n° 04/26), DH/kWh HT ─────────
# Source : décision ANRE n° 04/26, art. 6-7 — prix hors impôts, taxes et TSS,
# applicables à l'excédent injecté en MT/HT/THT SEULEMENT (aucune revente BT).
# Art. 10 : le tarif est ARRÊTÉ à la signature de la convention, puis révisé
# sur le tarif général moyen hors taxes.
ANRE_TARIF_HORS_POINTE = 0.18   # DH/kWh HT — décision ANRE 04/26, art. 6-7
ANRE_TARIF_POINTE = 0.21        # DH/kWh HT — décision ANRE 04/26, art. 6-7
ANRE_TARIF_SOURCE = (
    "décision ANRE n° 04/26, art. 6-7 (hors impôts, taxes, TSS), "
    "MT/HT/THT seulement")
# Période de validité (décision ANRE n° 04/26, art. 4).
ANRE_PERIODE = (_dt.date(2026, 3, 1), _dt.date(2027, 2, 28))

# ── Plafond légal d'injection : part MAX de la production annuelle ─────────
# Source : loi 82-21 art. 12 (BO 7400) ; décision ANRE n° 04/26 art. 7.
PLAFOND_INJECTION_PCT = 20
PLAFOND_INJECTION_SOURCE = "loi 82-21 art. 12 (BO 7400) ; ANRE 04/26 art. 7"

# ── Tarifs d'accès / services système : DOCUMENTAIRES, jamais soustraits ────
# La décision ANRE 02/25 (BO 7400, art. 8) exonère de TURD/TURT
# l'autoproducteur consommant sur le MÊME site : aucun net n'est calculé.
# TSS : une éventuelle TSS sur l'énergie injectée n'est pas déduite —
# modalités MT non arrêtées (ANRE 02/25 §4).
TSS_C_KWH = 6.81    # c/kWh — décision ANRE 02/26 ; documentaire, jamais soustrait
# Transit HORS site — jamais appliqués sur site (documentaires, datés).
TURD_C_KWH = 6.07   # c/kWh — décision ANRE 03/26, depuis le 01/03/2026
TURT_C_KWH = 6.85   # c/kWh — décision ANRE 02/26, au 01/03/2026

# ── Mentions UNIQUES (aucune autre copie côté Python) ─────────────────────
MENTION_82_21 = (
    "Tarif d'excédent ANRE (décision 04/26) : 18 cDH/kWh hors pointe, "
    "21 cDH/kWh pointe, HT hors TSS ; plafond légal 20 % de la production "
    "annuelle (loi 82-21, art. 12) ; tarif arrêté à la signature de la "
    "convention puis indexé sur le tarif général moyen"
)
MENTION_ART13 = (
    "Contribution aux services système et de distribution prévue par l'art. 13 "
    "de la loi 82-21 : non encore fixée par l'ANRE, non incluse"
)
MENTION_BT = (
    "Revente du surplus non ouverte en basse tension à ce jour — ANRE "
    "décision 04/26 ; installation dimensionnée pour l'autoconsommation"
)


def tarif_excedent_en_vigueur(date_signature_prevue=None):
    """Tarif d'excédent applicable à une convention signée à cette date.

    Retour : ``(tarif, motif)``. ``tarif`` = ``{'hors_pointe', 'pointe',
    'source', 'periode'}`` tant que la date tombe dans ``ANRE_PERIODE`` (ou est
    inconnue : décision en vigueur), ``motif`` None. Après le 28/02/2027 sans
    nouvelle décision saisie (ou avant le 01/03/2026) : ``(None, motif)`` —
    JAMAIS extrapolé.
    """
    debut, fin = ANRE_PERIODE
    d = date_signature_prevue
    if isinstance(d, str):
        try:
            d = _dt.date.fromisoformat(d[:10])
        except ValueError:
            d = None
    if isinstance(d, _dt.datetime):
        d = d.date()
    if d is not None and d > fin:
        return None, (
            "Tarif d'excédent après le 28/02/2027 non publié : aucune "
            "décision ANRE postérieure à la 04/26 n'est saisie")
    if d is not None and d < debut:
        return None, "Date antérieure à la décision ANRE 04/26 (01/03/2026)"
    return {
        'hors_pointe': ANRE_TARIF_HORS_POINTE,
        'pointe': ANRE_TARIF_POINTE,
        'source': ANRE_TARIF_SOURCE,
        'periode': (debut.isoformat(), fin.isoformat()),
    }, None


# ══ QXMT — Tarifs MOYENNE TENSION ONEE (raccordement MT, dossiers > 50 kW) ═══
# Miroir STRICT de ``TARIF_MT_ONEE`` dans frontend/src/features/ventes/solar.js
# (test de parité plus bas dans tests/test_qx50_injection_82_21.py).
#
# RÈGLE FONDATEUR — ZÉRO CHIFFRE INVENTÉ (PLAN2 QXG6). Une valeur n'apparaît
# ici QUE si une source OFFICIELLE ou de premier rang la publie, source et date
# citées sur la ligne. Toute valeur non sourcée reste ``None`` : l'étude OMET le
# calcul correspondant plutôt que d'afficher un chiffre douteux. Jamais de
# placeholder chiffré, jamais de reprise d'une estimation « ordre de grandeur »
# (le site porte un blend indicatif 1,15 DH/kWh dans apps/web/src/lib/
# estimatorPro.ts — explicitement une hypothèse, donc inutilisable ici).
#
# SOURCE des trois prix + de la prime (relevée ET vérifiée le 18/08/2026) :
#   ONEE — Branche Électricité, page officielle « Tarif Général (MT) »
#   https://www.one.org.ma/fr/pages/interne.asp?esp=1&id1=14&id2=114&t2=1
#   La page précise : « Les tarifs sont exprimés en dirhams TVA comprise
#   (TVA est de 18 %) ». Elle n'affiche NI date d'entrée en vigueur NI numéro
#   d'arrêté — d'où la mention de consultation portée par MENTION_MT.
# NON RETENU volontairement : la page ONEE « Grands Comptes » sans tag de
# tension (494,09 DH/kVA ; 1,3645 / 0,9736 / 0,7131) est citée ailleurs comme
# « MT » mais ne porte aucun libellé de tension et vit dans l'arborescence
# THT/HT — ambiguë, donc écartée. Le TURD ANRE (6,07 c/kWh depuis le
# 01/03/2026, décision ANRE 03/26 — ``TURD_C_KWH``) est un tarif d'ACCÈS au
# réseau, transit HORS site, PAS un tarif de vente au client final : jamais
# mélangé ici.
#
# NB nomenclature : « C1 / C2 » n'existe PAS comme option tarifaire MT chez
# l'ONEE (vérifié 18/08/2026 — la MT n'a qu'un « Tarif Général (MT) » ; les
# options nommées TLU/MU/CU/TCU et « Super Pointe » sont réservées à la HT/THT).
TARIF_MT_ONEE = {
    # Redevance de consommation par poste horaire, DH/kWh TVA (18 %) comprise.
    # ONEE « Tarif Général (MT) », one.org.ma, consulté le 18/08/2026.
    "POINTE": 1.4157,
    "PLEINES": 1.0101,
    "CREUSES": 0.7398,
    # Prime fixe / redevance de puissance, DH par kVA souscrit et par an.
    # Même source, même date. DÉLIBÉRÉMENT NON déduite des économies : le
    # solaire ne réduit pas la puissance souscrite.
    "PRIME_PUISSANCE_DH_KVA_AN": 512.62,
    "TVA_INCLUSE_PCT": 18,
    # Durées officielles des plages horaires (heures/jour). La page MT ne les
    # publie QUE dans un diagramme image (non extractible) — plages MT à
    # fournir par le fondateur (source officielle introuvable au 18/08/2026).
    # ``None`` = AUCUNE répartition par défaut n'est inventée. (Les seules
    # plages publiées en clair sur one.org.ma appartiennent au tarif Optionnel
    # « Super Pointe » THT/HT, explicitement PAS à la MT.)
    "PLAGES_H": None,
}

# Mention affichée avec TOUT chiffre issu du barème MT (jamais un chiffre nu).
MENTION_MT = (
    "Barème ONEE « Tarif Général (MT) », TVA 18 % comprise — "
    "one.org.ma, consulté le 18/08/2026 (la page ne publie pas de date "
    "d'entrée en vigueur)"
)


def tarif_mt_disponible() -> bool:
    """Le barème MT est-il exploitable (les 3 postes horaires sourcés > 0) ?"""
    return all(
        isinstance(TARIF_MT_ONEE.get(k), (int, float)) and TARIF_MT_ONEE[k] > 0
        for k in ("POINTE", "PLEINES", "CREUSES")
    )


def normaliser_repartition_mt(repartition):
    """Répartition horaire client (%) → parts normalisées à 100 %, ou ``None``.

    ``None`` quand rien d'exploitable n'est fourni : les plages MT officielles
    n'étant pas publiées, AUCUNE répartition par défaut n'est inventée. Les
    valeurs non numériques ou négatives comptent pour 0. Défensif : jamais
    d'exception.
    """
    def part(value):
        try:
            n = float(value)
        except (TypeError, ValueError):
            return 0.0
        return n if n > 0 else 0.0

    src = repartition or {}
    pointe = part(src.get("pointe"))
    pleines = part(src.get("pleines"))
    creuses = part(src.get("creuses"))
    somme = pointe + pleines + creuses
    if somme <= 0:
        return None
    return {
        "pointe": round(pointe / somme * 100, 1),
        "pleines": round(pleines / somme * 100, 1),
        "creuses": round(creuses / somme * 100, 1),
    }


def tarif_mt_moyen(repartition):
    """Prix moyen pondéré (DH/kWh TTC) du barème MT, ou ``None``.

    ``None`` — jamais un nombre de repli — si le barème n'est pas sourcé ou si
    la répartition est absente : c'est ce ``None`` qui fait OMETTRE le calcul
    d'économies plutôt que d'inventer un tarif.
    """
    if not tarif_mt_disponible():
        return None
    parts = normaliser_repartition_mt(repartition)
    if not parts:
        return None
    moyen = (
        parts["pointe"] * TARIF_MT_ONEE["POINTE"]
        + parts["pleines"] * TARIF_MT_ONEE["PLEINES"]
        + parts["creuses"] * TARIF_MT_ONEE["CREUSES"]
    ) / 100.0
    return moyen if moyen > 0 else None


def injection_annuelle(production_kwh, autoconsomme_kwh, pointe: bool = False):
    """Surplus injectable (kWh) plafonné à 20 % de la prod + sa valeur BRUTE HT (DH).

    surplus = max(0, production − autoconsommé), borné à ``PLAFOND_INJECTION_PCT``
    (loi 82-21 art. 12) ; valeur = surplus × tarif ANRE 04/26 BRUT HT (hors
    pointe par défaut : l'injection solaire est diurne). AUCUNE déduction
    TURD/TURT/TSS (ANRE 02/25 art. 8). MT/HT/THT seulement — en BT l'appelant
    ne valorise aucune revente (``MENTION_BT``). Retourne (kwh, dh), tous deux
    ≥ 0 et arrondis. Défensif : jamais d'exception.
    """
    try:
        prod = max(0.0, float(production_kwh or 0))
        auto = max(0.0, float(autoconsomme_kwh or 0))
    except (TypeError, ValueError):
        return 0, 0
    surplus = max(0.0, prod - auto)
    plafond = prod * PLAFOND_INJECTION_PCT / 100.0
    kwh = min(surplus, plafond)
    tarif = ANRE_TARIF_POINTE if pointe else ANRE_TARIF_HORS_POINTE
    dh = kwh * tarif
    return round(kwh), round(dh)
