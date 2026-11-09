# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT16 (clause client) : panneaux variantés 550 W « sans » / 710 W « avec », sans structure ni pose : les cartes
d'option du PDF résidentiel /proposal impriment « 10 panneaux 550 W » et « 10 panneaux 710 W », jamais
« Structures + installation complète » ; avec structure + pose, la puce revient. Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-005", "sha": "c38868a62",
         "attendu": "sans_bullets[0]='10 panneaux 550 W', avec_bullets[0]='10 panneaux 710 W', aucune puce Structures ; "
                    "PDF idem ; témoin structure+pose : puce présente",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "authentication.Company"]}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    co = make_company(slug='sonde-amot-ver4-005', nom='SONDE VER4 005')
    adm = get_user_model().objects.create_user(username='sonde-ver4-005', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    PUCE = 'Structures + installation complète'
    out, ok = {}, True
    for nom, extra in (('nu', []), ('structure_pose', [('Structure acier', '10', '300'),
                                                       ('Installation et mise en service', '1', '4000')])):
        dv = make_devis(co, adm, cl, [('Panneau mono 550W', '10', '1000'), ('Panneau mono 710W', '10', '1300'),
                                      ('Onduleur réseau Huawei 5kW', '1', '8000'), ('Onduleur hybride Deye 5kW', '1', '15000'),
                                      ('Batterie Dyness 5kWh', '1', '20000')] + extra,
                        reference=f'DEV-SONDE-V4-005-{nom}',
                        etude_params={'scenario': 'Les deux (Sans + Avec)', 'factures_mensuelles_reelles': [1500] * 12})
        dv.lignes.filter(designation='Panneau mono 550W').update(variante='sans')
        dv.lignes.filter(designation='Panneau mono 710W').update(variante='avec')
        d = build_quote_data(dv, clean_pdf_options({}))
        r = {'sans_bullets': d['sans_bullets'], 'avec_bullets': d['avec_bullets']}
        rep = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/', HTTP_HOST='localhost')
        body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
        if rep.status_code == 200:
            pages = [re.sub(r'[   ]', ' ', p.get_text()) for p in fitz.open(stream=body, filetype='pdf')]
            p1 = pages[0]
            r['pdf_p1'] = {'550': '10 panneaux 550 W' in p1, '710': '10 panneaux 710 W' in p1,
                           'puce_structures': PUCE in '\n'.join(pages)}
        else:
            r['pdf_p1'] = {'http': rep.status_code}
        if nom == 'nu':
            ok &= (d['sans_bullets'][:1] == ['10 panneaux 550 W'] and d['avec_bullets'][:1] == ['10 panneaux 710 W']
                   and PUCE not in d['sans_bullets'] + d['avec_bullets']
                   and r['pdf_p1'].get('550') and r['pdf_p1'].get('710') and not r['pdf_p1'].get('puce_structures'))
        else:
            ok &= PUCE in d['sans_bullets'] and PUCE in d['avec_bullets']
        out[nom] = r
    out['repro'] = bool(ok)
    return out
