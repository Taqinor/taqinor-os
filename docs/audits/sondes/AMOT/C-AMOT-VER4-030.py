# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT115 (cartes d'option C&I) — jumeau oublié en base « ttc » (TVA déclarée NON récupérable).

`quote_engine/ci/options_cote.py::lignes_avec` imprime toujours l'économie de l'option « avec » en HT
(`_ligne_economie(d, economie, "HT", ...)`, `valeur_chiffree.economie_annuelle_mad` = `total_mad` HT), alors que
`::lignes_sans` imprime l'économie dans la base servie (`<cle>_economie_base`, « TTC » en base ttc) et que
`::_ligne_prix` imprime « Investissement TTC » sur les deux cartes. En base « ttc », la carte « Avec batterie »
garde donc le défaut constaté par C-AMOT-VER-030 (investissement TTC face à une économie HT seule), et les deux
cartes comparent une économie TTC à une économie HT. AMOT115 n'a traité que la base « deux ».
Fonctions pures du moteur (mêmes appels que commercial/cover.py), ni base ni HTTP. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-030", "sha": "c38868a62",
         "attendu": "base ttc, deux options : carte Sans « 118 717 MAD TTC » ; carte Avec « Investissement TTC » + "
                    "« 20 000 MAD HT » sans TTC (24 000 servi) ; base deux : les deux cartes portent la TTC",
         "modeles": ["ventes.Devis"]}


def sonde(ctx):
    import html as _h
    import re
    from apps.ventes.quote_engine.ci import options_cote
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles
    from apps.ventes.quote_engine.residential.theme import fmt

    def txt(h):
        return re.sub(r'\s+', ' ', _h.unescape(re.sub(r'<[^>]+>', ' ', h)).replace('\xa0', ' '))

    def cartes(base):
        synthese = {
            'argent': {'base': base,
                       'economie_annee1': {'total_mad': 98931.16, 'total_mad_ttc': 118717.39},
                       'indicateurs': {'retour_ans': 5.4}},
            'option_batterie': {'totaux': {'ht_net': 700000.0, 'ttc': 840000.0},
                                'valeur_chiffree': {'economie_annuelle_mad': 20000.0, 'retour_simple_ans': 9.1}}}
        ch = chiffres_cles(synthese)
        d = {'langue_sortie': 'fr', 'option_servie': 'sans', 'com_synthese': synthese,
             'com_economies': ch['economie_annuelle_mad'], 'com_economie_base': ch['base_economie'],
             'com_payback': 5.4, 'com_kwc': 100.0, 'puissance_kwc_avec': 100.0,
             'totaux_all': {'ht_net': 533333.0, 'ttc': 640000.0},
             'etude': {'etude_ci': {'option_avec': {'economie_ci': {'economie_annee1': {
                 'total_mad': 20000.0, 'total_mad_ttc': 24000.0}}}}}}
        brut = txt(options_cote.cartes_options(d, 'com', 'c1c', fmt, fmt, 640000.0))
        sans, avec = brut.split('Avec batterie', 1)
        return ch, sans, avec

    ch_ttc, sans_ttc, avec_ttc = cartes('ttc')
    ch_deux, sans_deux, avec_deux = cartes('deux')
    print(f'TTC base_economie={ch_ttc["base_economie"]} economie={ch_ttc["economie_annuelle_mad"]}')
    print(f'TTC SANS: {sans_ttc[:300]}')
    print(f'TTC AVEC: {avec_ttc[:300]}')
    print(f'DEUX AVEC: {avec_deux[:300]}')
    obs = {
        'ttc_sans_eco_ttc': '118 717 MAD TTC' in sans_ttc,
        'ttc_avec_invest_ttc': 'Investissement TTC' in avec_ttc,
        'ttc_avec_eco_ht': '20 000 MAD HT' in avec_ttc,
        'ttc_avec_eco_ttc': '24 000' in avec_ttc,
        'deux_avec_eco_ttc': '24 000 MAD TTC' in avec_deux,
    }
    obs['repro'] = (obs['ttc_sans_eco_ttc'] and obs['ttc_avec_invest_ttc'] and obs['ttc_avec_eco_ht']
                    and not obs['ttc_avec_eco_ttc'])
    return obs
