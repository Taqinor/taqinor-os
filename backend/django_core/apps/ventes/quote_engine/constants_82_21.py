"""Constantes du décret 82-21 (injection du surplus d'autoproduction) — UN SEUL
module sourcé, que le fondateur peut vérifier ligne à ligne (QXG6).

Décret 2-25-100 (loi 82-21), BO du 9 mars 2026, en vigueur le 9 juin 2026 :
il rend l'injection MT/HT du surplus RÉELLE. Toutes les valeurs de la SECTION
82-21 (celles qui suivent immédiatement) sont ESTIMÉES d'après la recherche
2026-07-16 et portent le flag « à vérifier fondateur » — elles pilotent une
ligne OFF PAR DÉFAUT, activée devis par devis, et ne s'affichent JAMAIS sans la
mention réglementaire ``MENTION_82_21``. (La section QXMT plus bas obéit à la
même règle mais ses valeurs, elles, sont SOURCÉES : voir ``MENTION_MT``.)

Miroir strict de frontend/src/features/ventes/constants82_21 (dans solar.js) —
tout changement ici DOIT être répliqué là-bas (test de parité).

QXMT (18/08/2026) : ce module porte AUSSI le barème MOYENNE TENSION ONEE
(``TARIF_MT_ONEE``) utilisé par l'étude industrielle/commerciale quand le
dossier est raccordé en MT — mêmes règles de sourçage, même miroir solar.js.
"""
from __future__ import annotations

# ── Tarif ANRE de rachat (mars 2026 → févr. 2027), DH/kWh ─────────────────────
# Recherche 2026-07-16 : 0,21 en pointe / 0,18 hors pointe. À VÉRIFIER FONDATEUR.
ANRE_TARIF_POINTE = 0.21        # DH/kWh — à vérifier fondateur
ANRE_TARIF_HORS_POINTE = 0.18   # DH/kWh — à vérifier fondateur

# ── Frais d'accès réseau à DÉDUIRE du tarif (centimes/kWh) ────────────────────
# Recherche 2026-07-16 : ≈ 6,07 + 6,38 c/kWh. À VÉRIFIER FONDATEUR.
FRAIS_RESEAU_C_KWH_1 = 6.07     # c/kWh — à vérifier fondateur
FRAIS_RESEAU_C_KWH_2 = 6.38     # c/kWh — à vérifier fondateur
FRAIS_RESEAU_DH_KWH = (FRAIS_RESEAU_C_KWH_1 + FRAIS_RESEAU_C_KWH_2) / 100.0  # 0,1245 DH/kWh

# ── Plafond d'injection = part MAX de la production injectable ─────────────────
# Recherche 2026-07-16 : 20 % de la production — DÉCRET EN RÉVISION. À vérifier.
PLAFOND_INJECTION_PCT = 20      # % de la production — en révision (à vérifier)

# ── Mention réglementaire OBLIGATOIRE affichée avec TOUTE ligne d'injection ────
MENTION_82_21 = "Tarif ANRE 03/2026-02/2027, plafond en révision"


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
# THT/HT — ambiguë, donc écartée. Le TURD ANRE (5,92 c/kWh, décision
# n°02-25-TURD, BO n°7400 du 01/05/2025) est un tarif d'ACCÈS au réseau payé
# entre opérateurs, PAS un tarif de vente au client final : jamais mélangé ici.
#
# NB nomenclature : « C1 / C2 » n'existe PAS comme option tarifaire MT chez
# l'ONEE (vérifié 18/08/2026 — la MT n'a qu'un « Tarif Général (MT) » ; les
# options nommées TLU/MU/CU/TCU et « Super Pointe » sont réservées à la HT/THT).
# Les seuls C1/C2 de ce module sont FRAIS_RESEAU_C_KWH_1/2, deux composantes de
# frais d'accès du décret 82-21 — aucun rapport avec une classe tarifaire.
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


def net_tarif_dh_kwh(pointe: bool = False) -> float:
    """Tarif NET (rachat ANRE − frais d'accès réseau), DH/kWh, jamais négatif.

    L'injection solaire est DIURNE (heures pleines/creuses, pas la pointe) → on
    valorise par défaut au tarif HORS POINTE net, choix prudent et honnête
    (jamais promettre la pointe sans stockage).
    """
    base = ANRE_TARIF_POINTE if pointe else ANRE_TARIF_HORS_POINTE
    return max(0.0, base - FRAIS_RESEAU_DH_KWH)


def injection_annuelle(production_kwh, autoconsomme_kwh, pointe: bool = False):
    """Surplus injectable (kWh) plafonné à 20 % de la prod + sa valeur NETTE (DH).

    surplus = max(0, production − autoconsommé), borné à ``PLAFOND_INJECTION_PCT``
    de la production ; valeur = surplus × tarif net. Retourne (kwh, dh), tous deux
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
    dh = kwh * net_tarif_dh_kwh(pointe)
    return round(kwh), round(dh)
