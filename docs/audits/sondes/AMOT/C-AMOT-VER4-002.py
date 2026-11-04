# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT10 : devis deux options SIGNÉ « sans » (option_acceptee), téléchargement de la variante « avec » :
display_total = totaux_all = totaux_avec (3 marchés) ; PDF rendu par generate_premium_devis_pdf(variante_option='avec') — l'appel de public_views.proposal_pdf, seul chemin qui transmet la variante — imprime le TTC « avec »,
jamais celui de l'option signée ; sans variante, le total signé reste (QJR401). Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-002", "sha": "c38868a62",
         "attendu": "variante avec : display_total == totaux_avec.ttc == totaux_all.ttc sur résidentiel/commercial/"
                    "industriel ; PDF imprime le TTC avec et pas le TTC sans ; sans variante : display_total = TTC sans",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "authentication.Company"]}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    from apps.ventes.utils.options import SANS_BATTERIE
    co = make_company(slug='sonde-amot-ver4-002', nom='SONDE VER4 002')
    adm = get_user_model().objects.create_user(username='sonde-ver4-002', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    out, ok = {}, True
    for i, mode in enumerate(('residentiel', 'commercial', 'industriel')):
        dv = make_devis(co, adm, cl, [('Panneau mono 550W', '10', '1100'), ('Onduleur réseau Huawei 5kW', '1', '8000'),
                                      ('Onduleur hybride Deye 5kW', '1', '15000'), ('Batterie Dyness 5kWh', '1', '20000')],
                        reference=f'DEV-SONDE-V4-002-{i}', etude_params={'scenario': 'Les deux (Sans + Avec)'})
        Devis.objects.filter(pk=dv.pk).update(mode_installation=mode, option_acceptee=SANS_BATTERIE)
        dv.refresh_from_db()
        d = build_quote_data(dv, clean_pdf_options({'variante_option': 'avec'}))
        d0 = build_quote_data(dv, clean_pdf_options({}))
        r = {'display_total': float(d['display_total']), 'totaux_all': float(d['totaux_all']['ttc']),
             'totaux_avec': float(d['totaux_avec']['ttc']), 'totaux_sans': float(d['totaux_sans']['ttc']),
             'sans_variante_display': float(d0['display_total']), 'nb_options': d.get('nb_options')}
        ok &= abs(r['display_total'] - r['totaux_avec']) < 0.01 and abs(r['totaux_all'] - r['totaux_avec']) < 0.01
        ok &= abs(r['sans_variante_display'] - r['totaux_sans']) < 0.01
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        from apps.ventes.utils.pdf import download_pdf
        # Même appel que public_views.proposal_pdf (variante whitelistée par clean_pdf_options)
        body = download_pdf(generate_premium_devis_pdf(dv.id, clean_pdf_options({'variante_option': 'avec'}),
                                                       persist=False))
        if body:
            t = re.sub(r'[   ]', ' ', '\n'.join(p.get_text() for p in fitz.open(stream=body, filetype='pdf')))
            f = lambda v: f"{v:,.0f}".replace(',', ' ')
            r['pdf'] = {'ttc_avec_imprime': f(r['totaux_avec']) in t, 'ttc_sans_imprime': f(r['totaux_sans']) in t,
                        'investissement': re.findall(r'Investissement[^\n]*\n?[^\n]*', t)[:2]}
            ok &= r['pdf']['ttc_avec_imprime']
            pages = [re.sub(r'[   ]', ' ', p.get_text()) for p in fitz.open(stream=body, filetype='pdf')]
            ctxs = []
            for n, pg in enumerate(pages):
                for m in re.finditer(re.escape(f(r['totaux_sans'])), pg):
                    ctxs.append(f'p{n + 1}: ' + pg[max(0, m.start() - 200):m.end() + 80].replace('\n', ' | '))
            r['pdf']['contexte_ttc_sans'] = ctxs[:3]
            r['pdf']['pages'] = len(pages)
        else:
            r['pdf'] = {'vide': True}; ok = False
        out[mode] = r
    out['repro'] = bool(ok)
    return out
