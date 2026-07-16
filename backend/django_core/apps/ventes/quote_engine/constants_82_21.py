"""Constantes du décret 82-21 (injection du surplus d'autoproduction) — UN SEUL
module sourcé, que le fondateur peut vérifier ligne à ligne (QXG6).

Décret 2-25-100 (loi 82-21), BO du 9 mars 2026, en vigueur le 9 juin 2026 :
il rend l'injection MT/HT du surplus RÉELLE. TOUTES les valeurs ci-dessous sont
ESTIMÉES d'après la recherche 2026-07-16 et portent le flag « à vérifier
fondateur » — elles pilotent une ligne OFF PAR DÉFAUT, activée devis par devis,
et ne s'affichent JAMAIS sans la mention réglementaire ``MENTION_82_21``.

Miroir strict de frontend/src/features/ventes/constants82_21 (dans solar.js) —
tout changement ici DOIT être répliqué là-bas (test de parité).
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
