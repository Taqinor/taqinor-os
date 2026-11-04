# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT11 : devis à taux_tva = 0, lignes sans taux propre : totaux_all.ttc = Devis.total_ttc (= HT), ttc_avant suit,
PDF /proposal résidentiel 3 p. + une-page et commercial impriment le TTC du noyau.
Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-003", "sha": "c38868a62",
         "attendu": "taux 0 : totaux_all.ttc == Devis.total_ttc == 19 000 ; PDF imprime 19 000 et pas 22 800",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "authentication.Company"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    co = make_company(slug='sonde-amot-ver4-003', nom='SONDE VER4 003')
    adm = get_user_model().objects.create_user(username='sonde-ver4-003', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    out, ok = {}, True
    for i, mode in enumerate(('residentiel', 'commercial')):
        dv = make_devis(co, adm, cl, [('Panneau mono 550W', '10', '1100'), ('Onduleur réseau Huawei 5kW', '1', '8000')],
                        reference=f'DEV-SONDE-V4-003-{i}')
        Devis.objects.filter(pk=dv.pk).update(taux_tva=Decimal('0'), mode_installation=mode)
        dv.refresh_from_db()
        d = build_quote_data(dv, clean_pdf_options({'pdf_mode': 'full'}))
        r = {'ttc_noyau': float(dv.total_ttc), 'totaux_all_ttc': float(d['totaux_all']['ttc']),
             'tva': float(d['totaux_all']['tva']), 'ttc_avant': float(d['totaux_all']['ttc_avant']),
             'display_total': float(d['display_total'])}
        ok &= abs(r['ttc_noyau'] - r['totaux_all_ttc']) < 0.01 and abs(r['display_total'] - r['ttc_noyau']) < 0.01
        for nom, qs in (('full', ''), ('onepage', '?pdf_mode=onepage')):
            if mode != 'residentiel' and nom == 'onepage':
                continue
            rep = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/{qs}', HTTP_HOST='localhost')
            body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
            if rep.status_code != 200:
                r[nom] = {'http': rep.status_code}; ok = False; continue
            t = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in fitz.open(stream=body, filetype='pdf')))
            r[nom] = {'ttc_19000': '19 000' in t, 'ttc_22800': '22 800' in t,
                      'tva_lignes': re.findall(r'TVA[^\n]{0,30}', t)[:4]}
            ok &= ('19 000' in t) and ('22 800' not in t)
        out[mode] = r
    out['temoin_none'] = 'non jouable : ventes_devis.taux_tva NOT NULL en base (repli None = objets non sauvés seulement)'
    out['repro'] = bool(ok)
    return out
