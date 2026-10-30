SONDE = {"constat": "C-AMOT-043", "sha": "673ec3f92",
         "attendu": "P3.1 — devis deux options ancré sur 12 factures, recommended_option = « Sans batterie » : "
                    "data.recommended = Sans ; PDF résidentiel 3 p. : la pastille « Recommandé » est sur l'option 1 "
                    "(avant « OPTION 2 »), « Pourquoi nous la recommandons : l'investissement… », pas « vos soirées et les "
                    "coupures », la mini-pastille page 3 suit la case « Sans batterie » ; témoin « Avec » : pastille après "
                    "« OPTION 2 »"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import DEUX_OPTIONS, make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)
    co = admin.company

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def pages_txt(did, qs=''):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, []
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        return 200, [norm(p.get_text()) for p in fitz.open(stream=body, filetype='pdf')]

    cli = make_client(co)
    lignes = [('Panneau mono 550W', '10', '1100'), ('Onduleur réseau Huawei 5kW', '1', '8000'),
              ('Onduleur hybride Deye 5kW', '1', '15000'), ('Batterie Dyness 5kWh', '1', '20000')]
    out, ok = {}, True
    for reco in ('Sans batterie', 'Avec batterie'):
        etude = dict(DEUX_OPTIONS, factures_mensuelles_reelles=[1800] * 12, distributeur='onee',
                     ville='casablanca', recommended_option=reco)
        dv = make_devis(co, admin, cli, lignes, reference=f'DEV-SONDE-AMOT043-{reco[:4]}', etude_params=etude)
        Devis.objects.filter(pk=dv.pk).update(mode_installation='residentiel')
        d = build_quote_data(dv, clean_pdf_options({'pdf_mode': 'full'}))
        st, pg = pages_txt(dv.id)
        p1 = pg[0] if pg else ''
        tout = '\n'.join(pg)
        i_reco = p1.find('Recommandé')
        i_opt2 = p1.find('O P T I O N 2')
        p3 = pg[-1] if pg else ''
        i_sans = p3.find('Sans batterie —')
        i_avec = p3.find('Avec batterie —')
        i_mini = p3.find('recommandé', min(x for x in (i_sans, i_avec) if x >= 0) if max(i_sans, i_avec) >= 0 else 0)
        res = {'recommended_serveur': d.get('recommended'), 'http': st, 'pages': len(pg),
               'pastille_avant_option2': 0 <= i_reco < i_opt2, 'nb_pastilles_p1': p1.count('Recommandé'),
               'pourquoi': [ln for ln in tout.splitlines() if 'Pourquoi nous la recommandons' in ln][:1],
               'soirees_coupures': 'vos soirées et les coupures' in tout,
               'mini_p3_apres_sans_avant_avec': (i_sans >= 0 and i_avec >= 0 and i_sans < i_mini < i_avec)}
        out[reco] = res
        if reco == 'Sans batterie':
            ok &= (d.get('recommended') == 'Sans batterie' and st == 200 and res['pastille_avant_option2']
                   and res['nb_pastilles_p1'] == 1 and not res['soirees_coupures']
                   and any("l'investissement" in x or 'l’investissement' in x for x in res['pourquoi'])
                   and res['mini_p3_apres_sans_avant_avec'])
        else:
            ok &= st == 200 and i_reco > i_opt2 >= 0
    out['repro'] = bool(ok)
    return out
