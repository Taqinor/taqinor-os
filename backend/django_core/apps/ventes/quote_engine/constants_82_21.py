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

# Grille ONEE officielle : module PUR de fondation (CIQ202, une seule source).
from apps.parametres import tarifs_officiels as _officiels

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


def _aujourdhui_casablanca():
    """AMOT28 — la date du jour à Casablanca (fuseau du marché)."""
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.now(ZoneInfo("Africa/Casablanca")).date()
    except Exception:  # noqa: BLE001 — base tz absente : date UTC
        return _dt.datetime.now(_dt.timezone.utc).date()


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
    if d is None:
        # AMOT28 (C-AMOT-029) — sans date de signature prévue, la date du
        # JOUR (Africa/Casablanca) fait foi : après le 28/02/2027 la garde
        # d'expiration s'arme d'elle-même, jamais un tarif extrapolé.
        d = _aujourdhui_casablanca()
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


# ══ QXMT — Tarifs MOYENNE TENSION ONEE (raccordement MT) ═══════════════════
# CIQ202 : UNE seule source — ``apps/parametres/tarifs_officiels.py`` (module
# PUR de fondation, chaque valeur avec {source_url, page_audience, releve_le,
# inchange_depuis}). Ce dict LIT ce module : aucune valeur recopiée ici.
# Miroir JS : ``TARIF_MT_ONEE`` de frontend/src/features/ventes/solar.js
# (parité testée dans tests/test_qx50_injection_82_21.py ; le miroir disparaît
# avec CIQ228).
#
# RÈGLE FONDATEUR — ZÉRO CHIFFRE INVENTÉ (PLAN2 QXG6, D-CIQ-4). Les prix sont
# TTC TELS QUE PUBLIÉS : la page ONEE garde un libellé « TVA 18 % » périmé
# (taux légal de l'électricité 2026 : 20 %, ``TVA_PAR_MILLESIME`` de
# bareme.py) — aucun TTC n'est re-multiplié ; le HT se dérive (÷ 1,20) dans
# ``ventes/tarif_ci.py`` et porte « estimation ».
# NON RETENU : la grille « Grands Comptes » (494,09 DH/kVA ; 1,3645 / 0,9736 /
# 0,7131) — branche THT/HT, pas une grille MT. Le TURD (6,07 c/kWh depuis le
# 01/03/2026, décision ANRE 03/26 — ``TURD_C_KWH``) est un tarif d'ACCÈS au
# réseau, transit HORS site, jamais un tarif de vente.
#
# NB nomenclature : « C1 / C2 » n'existe PAS comme option tarifaire MT chez
# l'ONEE — la MT n'a qu'un « Tarif Général (MT) » ; les options TLU/MU/CU/TCU
# et « Super Pointe » sont réservées à la HT/THT.
TARIF_MT_ONEE = {
    # Redevance de consommation par poste horaire, DH/kWh TTC publié.
    "POINTE": _officiels.MT_GENERAL['pointe']['valeur'],
    "PLEINES": _officiels.MT_GENERAL['pleines']['valeur'],
    "CREUSES": _officiels.MT_GENERAL['creuses']['valeur'],
    # Prime fixe, DH par kVA souscrit et par an. DÉLIBÉRÉMENT NON déduite des
    # économies : le solaire ne réduit pas la puissance souscrite.
    "PRIME_PUISSANCE_DH_KVA_AN":
        _officiels.MT_GENERAL['prime_fixe_kva_an']['valeur'],
    # Plages horaires PUBLIÉES (heure GMT, intervalles [de_h, a_h)) : schéma
    # one.org.ma/images/horr.jpg, page bi-horaire ; décision ANRE 04/26 art. 7.
    "PLAGES_H": _officiels.POSTES_MT,
}

# Mention affichée avec TOUT chiffre issu du barème MT (jamais un chiffre nu).
MENTION_MT = (
    "Barème ONEE « Tarif Général (MT) », prix TTC tels que publiés sur "
    "one.org.ma (relevé le 03/10/2026 ; la page indique TVA 18 %, taux légal "
    "2026 : 20 %)"
)

#: Fonction de référence des postes (ré-export de la fondation).
poste_horaire = _officiels.poste_horaire


def tarif_mt_disponible() -> bool:
    """Le barème MT est-il exploitable (les 3 postes horaires sourcés > 0) ?"""
    return all(
        isinstance(TARIF_MT_ONEE.get(k), (int, float)) and TARIF_MT_ONEE[k] > 0
        for k in ("POINTE", "PLEINES", "CREUSES")
    )


def normaliser_repartition_mt(repartition):
    """Répartition horaire client (%) → parts normalisées à 100 %, ou ``None``.

    ``None`` quand rien d'exploitable n'est fourni : les plages MT publiées
    sont des HEURES, pas la répartition de la consommation du client — AUCUNE
    répartition de consommation par défaut n'est inventée. Les
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
