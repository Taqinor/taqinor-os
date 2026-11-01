# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT39 : la synthèse C&I (`quote_engine/ci/synthese.py::_bloc_baseline_source`) parcourt les feuilles de
consommation dans un ordre différent de celui du moteur (`domain/etude_ci.py::_consommation`) : kWh annuel déclaré
(retenu par le moteur) + relevé de 12 factures → la couverture imprime « 12 factures » à côté de la consommation
du moteur. Fonctions pures, ni base ni HTTP."""
SONDE = {"constat": "C-AMOT-VER-004", "sha": "d57c36964",
         "attendu": "kwh_annuel + releve_kwh 12 mois : moteur retient kwh_annuel, synthèse étiquette la source « factures »"}


def sonde(ctx):
    from apps.ventes.domain import etude_ci as moteur
    from apps.ventes.quote_engine.ci.synthese import synthese_ci
    res = moteur._Resolution()
    res.poser('kwh_annuel', 300000, {'origine': 'devis', 'detail': 'client', 'date': None})
    res.poser('releve_kwh', [{'mois': '2026-%02d' % m, 'kwh': 20000} for m in range(1, 13)],
              {'origine': 'lead', 'detail': 'facture', 'date': '2026-09-10'})
    _conso, retenue = moteur._consommation(res, {}, [], [])
    data = {'mode_installation': 'industriel', 'langue_sortie': 'fr', 'puissance_kwc': 50.0, 'nb_panneaux': 90,
            'etude': {'etude_ci': {'entrees_resolues': res.entrees_resolues(),
                                   'sous_reserve_visite': {'valeur': False}, 'profil_charge': {'methode': 'declare'},
                                   'bilan': {'production_kwh': 79482, 'taux_autoconso': 0.81, 'taux_couverture': 0.276}}},
            'payment_terms': {'acompte': 50, 'materiel': 40, 'solde': 10}, 'sans_ok': True, 'avec_ok': False}
    base = synthese_ci(data).get('baseline') or {}
    print(f'moteur retient={retenue} synthese source={base.get("source")} estimation={base.get("estimation")}')
    return {'repro': retenue == 'kwh_annuel' and base.get('source') == 'factures',
            'retenue': retenue, 'source': base.get('source')}
