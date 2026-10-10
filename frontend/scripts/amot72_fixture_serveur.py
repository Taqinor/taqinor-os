"""AMOT72 — produit la fixture SERVEUR (pricing.calculate_savings_roi corrigé
par AMOT58, rendement_une_fois=True) pour le cas VB : 6 kWc, eco_avec 7 200,
total avec 90 000, taux d'autoconsommation 0,45 / 0,75.
Lancer depuis backend/django_core :
    python ../../frontend/scripts/amot72_fixture_serveur.py ../../frontend/src/features/ventes/golden/amot72_payback_serveur.json
"""
import json
import sys

sys.path.insert(0, '.')
from apps.ventes.quote_engine import pricing  # noqa: E402

ECO_SANS, ECO_AVEC = 5400.0, 7200.0
mois = [{'economie_sans_mad': ECO_SANS / 12, 'economie_avec_mad': ECO_AVEC / 12,
         'facture_avant_mad': 900.0} for _ in range(12)]
bloc = {
    'kwc': 6.0,
    'annuel': {'production_kwh': 9000.0, 'consommation_kwh': 8000.0,
               'economie_sans_mad': ECO_SANS, 'economie_avec_mad': ECO_AVEC,
               'taux_autoconso_sans': 0.45, 'taux_autoconso_avec': 0.75},
    'mois': mois,
    'rendement_batterie': 0.9,
}
entree = {'puissance_kwc': 6.0, 'total_sans': 60000.0, 'total_avec': 90000.0,
          'battery_kwh': 10.0, 'stockage_present': True, 'etude_horaire': bloc}
res = pricing.calculate_savings_roi(
    entree['puissance_kwc'], entree['total_sans'], entree['total_avec'],
    battery_kwh=entree['battery_kwh'], stockage_present=True,
    etude_horaire=bloc, rendement_une_fois=True)
cles = {k: v for k, v in res.items() if isinstance(v, (int, float, str, bool, type(None)))}
sortie = {
    '_': 'AMOT72 — produit par le SERVEUR corrigé (AMOT58, rendement_une_fois=True) via '
         'frontend/scripts/amot72_fixture_serveur.py ; jamais recopié à la main.',
    'entree': entree,
    'serveur': cles,
}
open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps(sortie, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({k: v for k, v in cles.items() if 'payback' in k or 'gain' in k or 'cumul' in k or 'economie' in k},
                 ensure_ascii=False, indent=1))
