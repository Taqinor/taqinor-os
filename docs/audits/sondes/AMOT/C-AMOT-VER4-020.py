# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT72 (miroir écran `paybackMoteurHoraire`) × décision fondateur 08/10 (« devis envoyés : nouveaux rendus
seulement »).

Le serveur ne déduit le rendement batterie qu'UNE fois en modèle horaire SEULEMENT aux règles corrigées :
`quote_engine/etude_chiffrage.py::chiffrer_etude` passe `rendement_une_fois=_corrige` (calcul_corrige(devis)) à
`pricing.calculate_savings_roi` — un devis aux règles d'origine (`Devis.regles_calcul = 1`) garde la part batterie
du cashflow. Le miroir écran `frontend/src/features/ventes/calc/roi.js::paybackMoteurHoraire` pose
`batteryShare: 0` SANS condition et `pages/ventes/generator/hooks/useApercuEtude.js` ne lui passe aucun
`reglesCalcul` (lecture de code, ce dépôt) : il vaut le serveur `rendement_une_fois=True` (parité prouvée par la
fixture `golden/amot72_payback_serveur.json`). La sonde chiffre le cas VB d'AMOT72 côté serveur aux deux niveaux :
s'ils diffèrent, l'écran du générateur d'un devis d'origine contredit le PDF que ce devis imprime. Fonction pure,
aucune écriture. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-020", "sha": "c38868a62",
         "attendu": "cas VB (6 kWc, éco avec 7 200, total 90 000, rendement 0,9) : roi_a serveur règles d'origine (rendement_une_fois=False) ≠ roi_a règles corrigées (= écran AMOT72) ; gain net différent",
         "modeles": ["ventes.Devis"]}


def sonde(ctx):
    from apps.ventes.quote_engine import pricing
    eco_sans, eco_avec = 5400.0, 7200.0
    bloc = {
        'kwc': 6.0,
        'annuel': {'production_kwh': 9000.0, 'consommation_kwh': 8000.0,
                   'economie_sans_mad': eco_sans, 'economie_avec_mad': eco_avec,
                   'taux_autoconso_sans': 0.45, 'taux_autoconso_avec': 0.75},
        'mois': [{'economie_sans_mad': eco_sans / 12, 'economie_avec_mad': eco_avec / 12,
                  'facture_avant_mad': 900.0} for _ in range(12)],
        'rendement_batterie': 0.9,
    }
    obs = {}
    for nom, une_fois in (('corrige_ecran', True), ('origine_pdf', False)):
        r = pricing.calculate_savings_roi(6.0, 60000.0, 90000.0, battery_kwh=10.0, stockage_present=True,
                                          etude_horaire=bloc, rendement_une_fois=une_fois)
        obs[nom] = {k: r.get(k) for k in ('roi_a', 'roi_a_jamais', 'net_gain_avec', 'roi_s', 'net_gain_sans')}
    print(obs)
    a, b = obs['corrige_ecran'], obs['origine_pdf']
    repro = (a['roi_a'] != b['roi_a'] or a['net_gain_avec'] != b['net_gain_avec'])
    return {'repro': bool(repro), **obs}
