# flake8: noqa  (sonde de contre-visite vérifie AMOT, rejouable par scripts/sonde.py — AMET93)
"""AMOT95 : base « deux » (TVA récupérable non déclarée) ⇒ l'économie de l'année 1 est imprimée HT ET TTC,
et l'investissement TTC n'est plus seul face à une économie HT. CPDF3 (27/10, après AMOT95) a introduit les
cartes « Sans / Avec batterie » de la couverture C&I à deux options (`ci/options_cote.py::cartes_options`) qui
REMPLACENT les tuiles d'argent (`ci/couverture.py::tuiles_argent`, porteuses de « soit N MAD TTC ») : sur ces
cartes, « Investissement TTC » fait face à « Économie annuelle … MAD HT », sans la TTC servie.
Fonctions pures du moteur (mêmes appels que commercial/cover.py et industriel/cover.py), ni base ni HTTP."""
SONDE = {"constat": "C-AMOT-VER-030", "sha": "56d5b623a",
         "attendu": "base deux, deux options : la carte « Sans batterie » imprime Investissement TTC + économie HT "
                    "sans « soit … MAD TTC », alors que la tuile mono-option l'imprime"}


def sonde(ctx):
    import html as _h
    import re
    from apps.ventes.quote_engine.ci import couverture, options_cote
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles
    from apps.ventes.quote_engine.residential.theme import fmt
    synthese = {
        'argent': {'base': 'deux',
                   'economie_annee1': {'total_mad': 98931.16, 'total_mad_ttc': 118717.39},
                   'indicateurs': {'retour_ans': 5.4}},
        'option_batterie': {'totaux': {'ht_net': 700000.0, 'ttc': 840000.0},
                            'valeur_chiffree': {'economie_annuelle_mad': 20000.0, 'retour_simple_ans': 9.1}},
    }
    ch = chiffres_cles(synthese)
    d = {'langue_sortie': 'fr', 'option_servie': 'sans', 'com_synthese': synthese,
         'com_economies': ch['economie_annuelle_mad'], 'com_economie_base': ch['base_economie'],
         'com_payback': 5.4, 'com_kwc': 100.0, 'puissance_kwc_avec': 100.0,
         'totaux_all': {'ht_net': 533333.0, 'ttc': 640000.0}}

    def kpi(val, unit, label, fig):
        return f'{val}{unit} {label}'

    def txt(h):
        return re.sub(r'\s+', ' ', _h.unescape(re.sub(r'<[^>]+>', ' ', h)).replace('\xa0', ' '))

    cartes = txt(options_cote.cartes_options(d, 'com', 'c1c', fmt, fmt, 640000.0))
    d_mono = dict(d, option_servie='avec')
    tuiles = txt(''.join(couverture.tuiles_argent(d_mono, 'com', kpi, fmt)))
    ttc_servie = ch['economie_annuelle_ttc_mad']
    print(f'ttc_servie={ttc_servie} deux_options={options_cote.deux_options(d, "com")}')
    print(f'CARTES: {cartes[:400]}')
    print(f'TUILES_MONO: {tuiles[:300]}')
    carte_ttc_invest = 'Investissement TTC' in cartes
    carte_eco_ht = 'MAD HT' in cartes
    carte_eco_ttc = 'soit' in cartes and '118' in cartes
    tuile_eco_ttc = 'soit' in tuiles and '118' in tuiles
    return {'repro': bool(ttc_servie) and carte_ttc_invest and carte_eco_ht and not carte_eco_ttc and tuile_eco_ttc,
            'carte_invest_ttc': carte_ttc_invest, 'carte_eco_ht': carte_eco_ht,
            'carte_eco_ttc': carte_eco_ttc, 'tuile_mono_eco_ttc': tuile_eco_ttc}
