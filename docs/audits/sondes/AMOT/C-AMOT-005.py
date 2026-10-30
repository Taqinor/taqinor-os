SONDE = {"constat": "C-AMOT-005", "sha": "673ec3f92",
         "attendu": "P2.5 — devis deux options signé « sans » puis PDF client téléchargé en variante « avec » "
                    "(GET public /proposal/<jeton>/pdf/?variante=avec) : UNE option, UN total = totaux_avec.ttc = Σ des "
                    "lignes imprimées (jamais le total de l'option signée) ; sans variante, le total signé reste imprimé ; "
                    "mêmes contrôles serveur sur les devis C&I démo signés (1043 commercial, 1044 industriel)"}


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
    anon = APIClient()
    co = admin.company

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(r):
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    def mad(x):
        return f'{float(x):,.0f}'.replace(',', ' ')

    cli = make_client(co)
    devis = make_devis(co, admin, cli, [('Panneau mono 550W', '10', '1100'),
                                        ('Onduleur réseau Huawei 5kW', '1', '8000'),
                                        ('Onduleur hybride Deye 5kW', '1', '15000'),
                                        ('Batterie Dyness 5kWh', '1', '20000')],
                       reference='DEV-SONDE-AMOT005', etude_params=dict(DEUX_OPTIONS))
    Devis.objects.filter(pk=devis.pk).update(mode_installation='residentiel', option_acceptee='sans_batterie',
                                             statut='accepte')
    devis.refresh_from_db()
    out, ok = {}, True
    d_avec = build_quote_data(devis, clean_pdf_options({'variante_option': 'avec'}))
    d_sig = build_quote_data(devis, clean_pdf_options({}))
    t_avec, t_sans = float(d_avec['totaux_avec']['ttc']), float(d_avec['totaux_sans']['ttc'])
    out['serveur'] = {'variante_avec_display_total': float(d_avec['display_total']),
                      'totaux_all_ttc': float(d_avec['totaux_all']['ttc']), 'totaux_avec_ttc': t_avec,
                      'totaux_sans_ttc': t_sans, 'sans_variante_display_total': float(d_sig['display_total']),
                      'deux_options_variante': d_avec.get('deux_options'),
                      'figures_total_affiche': (d_avec.get('figures') or {}).get('total_affiche')}
    ok &= abs(float(d_avec['display_total']) - t_avec) < 0.01
    ok &= abs(float(d_avec['totaux_all']['ttc']) - t_avec) < 0.01
    ok &= abs(float(d_sig['display_total']) - t_sans) < 0.01
    r = api.post(f'/api/django/ventes/devis/{devis.id}/share-link/', {}, format='json', **H)
    out['share_link_http'] = r.status_code
    tok = r.data.get('token') if r.status_code in (200, 201) else None
    if tok:
        st, txt, pages = lire(anon.get(f'/api/django/ventes/proposal/{tok}/pdf/?variante=avec', **H))
        out['pdf_public_variante_avec'] = {'http': st, 'pages': pages, 'total_avec_imprime': mad(t_avec) in txt,
                                           'total_sans_imprime': mad(t_sans) in txt,
                                           'batterie': 'Batterie Dyness 5kWh' in txt,
                                           'onduleur_reseau': 'Onduleur réseau Huawei 5kW' in txt}
        ok &= st == 200 and mad(t_avec) in txt and mad(t_sans) not in txt and 'Batterie Dyness 5kWh' in txt
        st, txt, pages = lire(anon.get(f'/api/django/ventes/proposal/{tok}/pdf/', **H))
        out['pdf_public_sans_variante'] = {'http': st, 'pages': pages, 'total_sans_imprime': mad(t_sans) in txt}
        ok &= st == 200
    else:
        ok = False
    # C&I démo signés : variante « avec » -> display_total = totaux_all = Σ lignes de la variante
    for did in (1043, 1044):
        dv = Devis.objects.filter(pk=did, company=co).first()
        if dv is None:
            out[f'ci_{did}'] = 'absent'
            continue
        try:
            d = build_quote_data(dv, clean_pdf_options({'variante_option': 'avec'}))
            res = {'mode': dv.mode_installation, 'option_acceptee': dv.option_acceptee,
                   'display_total': float(d['display_total']), 'totaux_all_ttc': float(d['totaux_all']['ttc']),
                   'deux_options': d.get('deux_options')}
            res['coherent'] = abs(res['display_total'] - res['totaux_all_ttc']) < 0.01
            ok &= res['coherent']
            st, txt, pages = lire(api.get(f'/api/django/ventes/devis/{did}/proposal/', **H))
            res['proposal_http'], res['pages'] = st, pages
        except Exception as e:  # noqa: BLE001
            res = {'erreur': repr(e)[:200]}
            ok = False
        out[f'ci_{did}'] = res
    out['repro'] = bool(ok)
    return out
