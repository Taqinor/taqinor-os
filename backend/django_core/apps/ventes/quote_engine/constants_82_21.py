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
(``_officiels.MT_GENERAL``) utilisé par l'étude industrielle/commerciale quand le
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
# inchange_depuis}). Aucune valeur n'est recopiée ici.
# (Le miroir JS a disparu avec CIQ228.)
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
# AMOT75 : le dict ``TARIF_MT_ONEE`` (jumeau sans lecteur de production) est
# retiré ; les valeurs se lisent directement dans ``_officiels.MT_GENERAL`` /
# ``_officiels.POSTES_MT`` (seule source).

# Mention affichée avec TOUT chiffre issu du barème MT (jamais un chiffre nu).
MENTION_MT = (
    "Barème ONEE « Tarif Général (MT) », prix TTC tels que publiés sur "
    "one.org.ma (relevé le 03/10/2026 ; la page indique TVA 18 %, taux légal "
    "2026 : 20 %)"
)

#: Fonction de référence des postes (ré-export de la fondation).
poste_horaire = _officiels.poste_horaire


# AMOT47 (C-AMOT-008) — ``tarif_mt_disponible``, ``normaliser_repartition_mt``,
# ``tarif_mt_moyen`` et ``injection_annuelle`` SUPPRIMÉS : aucun lecteur hors
# de leurs propres tests (la revente C&I est chiffrée par ``economie_ci``,
# le barème MT par ``tarif_ci``). Les constantes sourcées ci-dessus restent.
