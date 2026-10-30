SONDE = {"constat": "C-AMOT-001", "sha": "673ec3f92",
         "attendu": "P2.4 — devis mono-option « onduleur réseau + batterie » (société démo, demo_admin) : la batterie et "
                    "son prix figurent au tableau, total imprimé = Devis.total_ttc du noyau sur le PDF résidentiel "
                    "full ET une-page ET dans /proposal data (jeton interne) ; scénario stocké « Avec batterie » conservé ; "
                    "avertissement interne « batterie sans onduleur hybride » ; prix d'achat absent ; re-rendu identique "
                    "hors horodatage ; aucun ShareLink créé par un rendu"}


def sonde(ctx):
    import re
    import fitz
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import ShareLink
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)
    co = admin.company

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def rendu(did, qs=''):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0, b''
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count, body

    def textes(body):
        return [p.get_text() for p in fitz.open(stream=body, filetype='pdf')]

    cli = make_client(co)
    devis = make_devis(co, admin, cli, [('Panneau mono 550W', '10', '1100'),
                                        ('Onduleur réseau Huawei 5kW', '1', '8000'),
                                        ('Batterie Dyness 5kWh', '1', '20000')],
                       reference='DEV-SONDE-AMOT001', etude_params={'scenario': 'Avec batterie'})
    for lg in devis.lignes.all():
        lg.produit.prix_achat = Decimal('7313.17')
        lg.produit.save(update_fields=['prix_achat'])
    devis.mode_installation = 'residentiel'
    devis.save(update_fields=['mode_installation'])
    devis.refresh_from_db()
    ttc = float(devis.total_ttc)
    ttc_txt = f'{ttc:,.0f}'.replace(',', ' ')
    out = {'devis': devis.reference, 'total_ttc_noyau': ttc}
    ok = True
    for mode in ('full', 'onepage'):
        d = build_quote_data(devis, clean_pdf_options({'pdf_mode': mode}))
        des = [it['designation'] for it in d['all_items']]
        warn = any('batterie sans onduleur hybride' in a for a in d.get('avertissements_internes', []))
        out[f'serveur_{mode}'] = {'batterie_dans_all_items': 'Batterie Dyness 5kWh' in des,
                                  'display_total': float(d['display_total']), 'scenario': d.get('scenario'),
                                  'avertissement': warn}
        ok &= ('Batterie Dyness 5kWh' in des and abs(float(d['display_total']) - ttc) < 0.01
               and d.get('scenario') == 'Avec batterie' and warn)
    liens_avant = ShareLink.objects.filter(devis=devis).count()
    corps = {}
    for nom, qs in (('full', ''), ('onepage', '?pdf_mode=onepage')):
        st, txt, pages, body = rendu(devis.id, qs)
        corps[nom] = body
        has_bat = 'Batterie Dyness 5kWh' in txt
        has_ttc = ttc_txt in txt
        achat = '7 313,17' in txt or '7313' in txt
        out[f'pdf_{nom}'] = {'http': st, 'pages': pages, 'batterie': has_bat, 'total_ttc_imprime': has_ttc,
                             'prix_achat_visible': achat, 'sans_batterie_titre': 'Sans batterie' in txt}
        ok &= st == 200 and has_bat and has_ttc and not achat
        ok &= pages == (3 if nom == 'full' else 1)
    # CLAUSE PERSISTANCE : rouvrir et re-rendre -> texte identique ; aucun ShareLink par un rendu
    devis.refresh_from_db()
    st2, txt2, _, body2 = rendu(devis.id, '')
    identique = textes(body2) == textes(corps['full'])
    out['re_rendu_texte_identique'] = identique
    out['re_rendu_octets_identiques'] = body2 == corps['full']
    out['sharelink_crees_par_rendu'] = ShareLink.objects.filter(devis=devis).count() - liens_avant
    ok &= identique and out['sharelink_crees_par_rendu'] == 0
    # CLAUSE CLIENT : /proposal data (jeton interne d'aperçu) = PDF
    r = api.post(f'/api/django/ventes/devis/{devis.id}/share-link/', {}, format='json', **H)
    out['share_link_http'] = r.status_code
    if r.status_code in (200, 201):
        tok = r.data.get('token_interne')
        rd = api.get(f'/api/django/ventes/proposal/{tok}/', **H)
        q = (rd.data or {}).get('quote', {}) if rd.status_code == 200 else {}
        des = [it.get('designation') for it in q.get('all_items', [])]
        brut = str(rd.data)
        out['data'] = {'http': rd.status_code, 'display_total': q.get('display_total'),
                       'batterie': 'Batterie Dyness 5kWh' in des,
                       'cle_prix_achat': 'prix_achat' in brut, 'valeur_prix_achat': '7313.17' in brut}
        ok &= (rd.status_code == 200 and q.get('display_total') is not None
               and abs(float(q['display_total']) - ttc) < 0.01 and 'Batterie Dyness 5kWh' in des
               and 'prix_achat' not in brut and '7313.17' not in brut)
    else:
        ok = False
    out['repro'] = bool(ok)
    return out
