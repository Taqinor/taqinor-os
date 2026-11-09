# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT8 (clause client) : devis mono-option « onduleur réseau + batterie » (sans hybride), rendu réel /proposal
(résidentiel 3 p. et une-page) + build_quote_data des trois marchés : batterie au tableau, total imprimé = noyau,
scénario « Avec batterie », avertissement interne ; témoin réseau seul inchangé. Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-001", "sha": "c38868a62",
         "attendu": "batterie présente et display_total = Devis.total_ttc (résidentiel/commercial/industriel), PDF full "
                    "et une-page impriment « Batterie Dyness 5kWh » et le TTC du noyau ; re-rendu identique",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "authentication.Company"]}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    co = make_company(slug='sonde-amot-ver4-001', nom='SONDE VER4 001')
    adm = get_user_model().objects.create_user(username='sonde-ver4-001', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    out, ok = {}, True
    for i, mode in enumerate(('residentiel', 'commercial', 'industriel')):
        dv = make_devis(co, adm, cl, [('Panneau mono 550W', '10', '1100'), ('Onduleur réseau Huawei 5kW', '1', '8000'),
                                      ('Batterie Dyness 5kWh', '1', '20000')],
                        reference=f'DEV-SONDE-V4-001-{i}', etude_params={'scenario': 'Avec batterie'})
        Devis.objects.filter(pk=dv.pk).update(mode_installation=mode)
        dv.refresh_from_db()
        d = build_quote_data(dv, clean_pdf_options({'pdf_mode': 'full'}))
        des = [it['designation'] for it in d['all_items']]
        r = {'ttc_noyau': float(dv.total_ttc), 'display_total': float(d['display_total']),
             'totaux_all_ttc': float(d['totaux_all']['ttc']), 'batterie': 'Batterie Dyness 5kWh' in des,
             'scenario': d.get('scenario'),
             'avert': any('batterie sans onduleur hybride' in a for a in d.get('avertissements_internes', []))}
        ok &= r['batterie'] and abs(r['display_total'] - r['ttc_noyau']) < 0.01 and r['avert']
        out[mode] = r
        if mode == 'residentiel':
            ttc_txt = f"{float(dv.total_ttc):,.0f}".replace(',', ' ')
            textes = {}
            for nom, qs in (('full', ''), ('onepage', '?pdf_mode=onepage')):
                rep = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/{qs}', HTTP_HOST='localhost')
                body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
                if rep.status_code != 200:
                    out[f'pdf_{nom}'] = {'http': rep.status_code}; ok = False; continue
                doc = fitz.open(stream=body, filetype='pdf')
                t = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in doc))
                textes[nom] = t
                out[f'pdf_{nom}'] = {'pages': doc.page_count, 'batterie': 'Batterie Dyness 5kWh' in t,
                                     'ttc_imprime': ttc_txt in t, 'titre_sans': 'Sans batterie' in t}
                ok &= 'Batterie Dyness 5kWh' in t and ttc_txt in t
            rep2 = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/', HTTP_HOST='localhost')
            body2 = b''.join(rep2.streaming_content) if getattr(rep2, 'streaming', False) else rep2.content
            t2 = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in fitz.open(stream=body2, filetype='pdf')))
            out['re_rendu_texte_identique'] = t2 == textes.get('full')
    temoin = make_devis(co, adm, cl, [('Panneau mono 550W', '10', '1100'), ('Onduleur réseau Huawei 5kW', '1', '8000')],
                        reference='DEV-SONDE-V4-001-T')
    dt = build_quote_data(temoin, clean_pdf_options({'pdf_mode': 'full'}))
    out['temoin_reseau'] = {'scenario': dt.get('scenario'), 'display_total': float(dt['display_total']),
                            'ttc_noyau': float(temoin.total_ttc)}
    out['repro'] = bool(ok)
    return out
