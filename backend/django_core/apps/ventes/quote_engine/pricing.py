"""ROI / savings math — vendored from RedaSolar/devis-simulator (autofill.py).

Pure formulas (Morocco GHI irradiance + ONEE reference pricing). No I/O, no
network, no Django — safe to call on the fly when generating a quote PDF.
"""
from __future__ import annotations


def calculate_savings_roi(puissance_kwc: float, total_sans: float, total_avec: float) -> dict:
    """Auto-compute annual production, savings and ROI from power and option totals.

    Formulas:
      production_annuelle   = kwc x 1240 kWh/kWc/an  (GHI moyen Maroc)
      economie_opt1 (sans)  = production x 60 % autoconso x 1,75 MAD/kWh
      economie_opt2 (avec)  = production x 85 % autoconso x 1,75 MAD/kWh  (batterie)
      roi                   = total_option / economie_annuelle
      monthly               = economie_annuelle x facteur_saisonnier

    Returns a dict directly usable to fill the premium PDF data dict.
    """
    production_annuelle = round(puissance_kwc * 1240)

    # Taux d'autoconsommation x prix kWh ONEE de référence
    economie_opt1 = round(production_annuelle * 0.60 * 1.75)
    economie_opt2 = round(production_annuelle * 0.85 * 1.75)

    # Retour sur investissement (années)
    roi_opt1 = round(total_sans / economie_opt1, 1) if economie_opt1 > 0 else 0.0
    roi_opt2 = round(total_avec / economie_opt2, 1) if economie_opt2 > 0 else 0.0

    # Répartition mensuelle saisonnière (12 facteurs, somme = 1,000)
    _SF = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
           0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
    eco_s_monthly = [round(economie_opt1 * f) for f in _SF]
    eco_a_monthly = [round(economie_opt2 * f) for f in _SF]

    return {
        "prod_kwh":      production_annuelle,
        "eco_s_ann":     economie_opt1,
        "eco_a_ann":     economie_opt2,
        "eco_a_cumul":   economie_opt2,   # même taux utilisé pour la courbe ROI
        "roi_s":         roi_opt1,
        "roi_a":         roi_opt2,
        "eco_s_monthly": eco_s_monthly,
        "eco_a_monthly": eco_a_monthly,
    }
