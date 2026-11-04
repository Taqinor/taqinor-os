# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT15 : (1) production posée par le calepinage (`production_source='calepinage'`, 10 890) non recopiée : prod_kwh =
moteur devis, PDF sans « 10 890 » ; (2) économie SAISIE 16 500 sur deux options : roi_s/roi_a = premier croisement
de cashflow_sans/avec (±0,1), net_gain = fin de courbe, année 1 = −prix de l'option + économie ; PDF résidentiel
imprime ces paybacks (12 factures réelles posées, sans quoi la couche économique est omise — Z2/M1). Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-004", "sha": "c38868a62",
         "attendu": "prod_kwh ≠ 10890 et = témoin ; roi_* = croisement de la courbe de SON option ; PDF imprime roi_s et roi_a",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "authentication.Company"]}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    co = make_company(slug='sonde-amot-ver4-004', nom='SONDE VER4 004')
    adm = get_user_model().objects.create_user(username='sonde-ver4-004', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    L2 = [('Panneau mono 710W', '14', '1200'), ('Onduleur réseau Huawei 10kW', '1', '16000')]
    L4 = L2 + [('Onduleur hybride Deye 10kW', '1', '24000'), ('Batterie Dyness 10kWh', '1', '30000')]

    def croise2(c):  # même interpolation que test_quote_engine_amot15 (_croisement)
        prec = None
        for i, val in enumerate(c):
            if val >= 0:
                depart = prec if prec is not None else val
                span = val - depart
                frac = (0 - depart) / span if span else 0.0
                return i + frac if prec is not None else 0.0
            prec = val
        return None
    out, ok = {}, True
    tem = build_quote_data(make_devis(co, adm, cl, L2, reference='DEV-SONDE-V4-004-T',
                                      etude_params={'scenario': 'Sans batterie'}), clean_pdf_options({}))
    dc = make_devis(co, adm, cl, L2, reference='DEV-SONDE-V4-004-C',
                    etude_params={'scenario': 'Sans batterie', 'production_annuelle': 10890,
                                  'production_source': 'calepinage'})
    d = build_quote_data(dc, clean_pdf_options({}))
    out['calepinage'] = {'prod_kwh': d['prod_kwh'], 'temoin_prod_kwh': tem['prod_kwh'],
                         'etude_production': d['etude'].get('production_annuelle')}
    ok &= d['prod_kwh'] != 10890 and d['prod_kwh'] == tem['prod_kwh']
    rep = api.get(f'/api/django/ventes/devis/{dc.id}/proposal/', HTTP_HOST='localhost')
    body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
    if rep.status_code == 200:
        t = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in fitz.open(stream=body, filetype='pdf')))
        out['calepinage']['pdf_10890'] = '10 890' in t
        ok &= '10 890' not in t
    de = make_devis(co, adm, cl, L4, reference='DEV-SONDE-V4-004-E',
                    etude_params={'scenario': 'Les deux (Sans + Avec)', 'production_annuelle': 12000,
                                  'economies_annuelles': 16500,
                                  'factures_mensuelles_reelles': [1800] * 12})
    e = build_quote_data(de, clean_pdf_options({}))
    r = {'nb_options': e['nb_options'], 'eco_s': e['eco_s_ann'], 'eco_a': e['eco_a_ann'],
         'roi_s': e['roi_s'], 'roi_a': e['roi_a'],
         'crois_s': croise2(e['cashflow_sans']), 'crois_a': croise2(e['cashflow_avec']),
         'net_s': e['net_gain_sans'], 'fin_s': e['cashflow_sans'][-1], 'net_a': e['net_gain_avec'],
         'fin_a': e['cashflow_avec'][-1], 'an1_s': e['cashflow_sans'][0], 'prix_s': float(e['total_sans']),
         'an1_a': e['cashflow_avec'][0], 'prix_a': float(e['total_avec']),
         'savings_method': (e.get('savings_method') or {}).get('model')}
    ok &= abs(r['roi_s'] - r['crois_s']) <= 0.1 and abs(r['roi_a'] - r['crois_a']) <= 0.1
    ok &= r['net_s'] == r['fin_s'] and r['net_a'] == r['fin_a']
    rep = api.get(f'/api/django/ventes/devis/{de.id}/proposal/', HTTP_HOST='localhost')
    body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
    if rep.status_code == 200:
        t = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in fitz.open(stream=body, filetype='pdf')))
        fr = lambda v: f'{v:.1f}'.replace('.', ',')
        r['pdf'] = {'roi_s_imprime': fr(r['roi_s']) in t, 'roi_a_imprime': fr(r['roi_a']) in t,
                    'retours': re.findall(r'[\d]+,\d\s*ans', t)[:6], 'eco_16500': '16 500' in t,
                    'lignes_eco': [l for l in t.split(chr(10)) if re.search(r'(?i)retour|économi|MAD/an|amorti|rentab', l)][:14]}
        ok &= r['pdf']['roi_s_imprime'] and r['pdf']['roi_a_imprime']
    else:
        r['pdf'] = {'http': rep.status_code}
    out['economie_saisie'] = r
    out['repro'] = bool(ok)
    return out
