# flake8: noqa
"""Founder-editable economic constants for the AGRICOLE quote economics.

EVERY rate here is a DEFAULT, flagged « à confirmer » — none is a hardcoded
client-facing claim. The renderer reads an override from the company Paramètres
when present (see ``economics.load_constants``) and falls back to these. The
sources are the 2026 research base (AMEE national solar-pumping programme +
Moroccan butane/diesel market); keep them tunable because fuel prices and the
butane subsidy move.

Sources (2026-06):
  · Coût/m³ pompé : Solaire 0,44 · Butane 0,76 · Diesel 1,67 MAD/m³
    (programme national pompage solaire, ministère / AMEE).
  · Bonbonne butane 12 kg : 50 MAD subventionnée → ~128 MAD coût réel
    (subvention ~78 MAD/bonbonne, en cours de décompensation).
  · Gasoil ~13,5 MAD/L (volatile, à relever en direct).
  · Subvention FDA pompage solaire : 30 % (depuis 19/02/2024), versée a
    posteriori ; plafond ~30 000 MAD à confirmer auprès de la DPA/ORMVA.
"""

# Coût de l'eau pompée par source d'énergie (MAD / m³) — chiffres officiels.
COST_PER_M3 = {
    "solaire": 0.44,   # à confirmer
    "butane": 0.76,    # à confirmer (subventionné aujourd'hui)
    "diesel": 1.67,    # à confirmer
}

# Décompensation : multiplicateur coût butane réel / subventionné (≈ 128/50).
BUTANE_DECOMP_MULTIPLIER = 2.5      # à confirmer (suit le marché GPL mondial)
BUTANE_12KG_SUBVENTIONNE = 50       # MAD, mi-2026
BUTANE_12KG_REEL = 128              # MAD, ≈ non subventionné
BUTANE_SUBVENTION_PAR_BONBONNE = 78  # MAD pris en charge par l'État

# Bilan bottom-up (utilisé pour le CO₂ et l'estimation bonbonnes/an).
BUTANE_KG_PER_H_PER_CV = 0.25       # kg/h par CV — à confirmer
BUTANE_KWH_PER_KG = 12.7            # constante physique
BUTANE_KG_CO2_PER_KG = 3.0         # ~2,98 kg CO₂ / kg GPL
DIESEL_L_PER_H_PER_CV = 0.20        # L/h par CV — à confirmer
DIESEL_MAD_PER_L = 13.5             # à confirmer (relever en direct)
DIESEL_KG_CO2_PER_L = 2.68          # constante (gasoil)

# Volume annuel pompé estimé depuis le besoin de pointe (cf. agronomy.js).
PUMPING_DAYS_PER_YEAR = 300         # à confirmer
PEAK_TO_AVG = 0.62                  # jour de pointe → moyenne annuelle, à confirmer

# Production PV : rendement spécifique (kWh / kWc / an) — défaut Maroc prudent.
SPECIFIC_YIELD_KWH_KWC = 1650       # à confirmer (≈ 1600-1900 selon région)

# Subvention FDA pompage solaire.
FDA_SUBSIDY_PCT = 30                # %
FDA_SUBSIDY_CAP = 30000            # MAD — plafond à confirmer (DPA/ORMVA)

# Répartition mensuelle (12) — irrigation (besoin estival fort) & production PV.
# Poids normalisés (somme ≈ 1). À confirmer / affiner par région.
WATER_MONTHLY_WEIGHTS = [0.030, 0.040, 0.060, 0.085, 0.110, 0.130,
                         0.140, 0.130, 0.100, 0.075, 0.055, 0.045]
PROD_MONTHLY_WEIGHTS = [0.061, 0.069, 0.090, 0.097, 0.106, 0.107,
                        0.110, 0.103, 0.090, 0.077, 0.049, 0.041]

# Carburant de référence par défaut (le plus répandu en agriculture marocaine).
DEFAULT_CURRENT_FUEL = "butane"     # "butane" | "diesel" | "none"
