SONDE = {"constat": "C-AMOT-HXH-PAGES", "sha": "673ec3f92",
         "attendu": "P3.5 — chaque mode × format, nombre de pages exact par /proposal : résidentiel 3 / + étude 4 / "
                    "+ annexe calepinage explicite 4 / une-page 1 ; commercial 3 (une-page 1) ; industriel 4 (une-page "
                    "1) ; agricole 3 / + note de calcul 4 (une-page 1). CLAUSE PERSISTANCE : chaque devis re-rendu -> "
                    "texte PDF identique, aucun ShareLink créé par un rendu. CLAUSE CLIENT : le total servi par "
                    "/proposal data (jeton interne) est imprimé dans le PDF"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis, ShareLink
    from apps.ventes.tests._quote_engine_common import make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    User = get_user_model()
    apis = {}
    for nom in ('demo_admin', 'anon_admin'):
        u = User.objects.get(username=nom)
        a = APIClient()
        a.force_authenticate(u)
        apis[u.company_id] = (a, u)

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def rendu(dv, qs=''):
        api = apis[dv.company_id][0]
        r = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, [], b''
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        return 200, [norm(p.get_text()) for p in fitz.open(stream=body, filetype='pdf')], body

    def mad(x):
        return f'{float(x):,.0f}'.replace(',', ' ')

    admin = User.objects.get(username='demo_admin')
    anon = User.objects.get(username='anon_admin')
    co2 = admin.company
    # devis résidentiels de taille courante (<= 10 lignes) : au-delà (~12 lignes communes), la pagination
    # variable documentée (QRES17, gabarit « plus10 ») passe volontairement en 4 pages — observée à part (1121).
    resid = [d for d in Devis.objects.filter(company=co2, mode_installation='residentiel').order_by('-id')
             if 5 <= d.lignes.count() <= 10 and d.statut == 'brouillon' and (d.etude_params or {}).get('dimensionnement')]
    simple = resid[0] if resid else None
    cal = next((d for d in resid if d.roof_layout), None)
    etude = make_devis(co2, admin, make_client(co2), [('Panneau mono 710W', '14', '1200'),
                                                      ('Onduleur réseau Huawei 10kW', '1', '16000')],
                       reference='DEV-SONDE-HXH-ETUDE', etude_params={
                           'scenario': 'Sans batterie', 'production_annuelle': 12000, 'economies_annuelles': 16500})
    Devis.objects.filter(pk=etude.pk).update(mode_installation='residentiel')
    etude.refresh_from_db()
    agri = Devis.objects.filter(company=anon.company, mode_installation='agricole').order_by('-id').first()
    cas = [
        ('residentiel', simple, [('', 3), ('?pdf_mode=onepage', 1)]),
        ('residentiel_etude', etude, [('?include_etude=1', 4), ('', 3)]),
        ('commercial', Devis.objects.get(pk=1116), [('', 3), ('?pdf_mode=onepage', 1)]),
        ('industriel', Devis.objects.get(pk=1112), [('', 4), ('?pdf_mode=onepage', 1)]),
        ('agricole', agri, [('', 3), ('?include_note_calcul=1', 4), ('?pdf_mode=onepage', 1)]),
    ]
    if cal is not None:
        cas.append(('residentiel_calepinage', cal, [('?include_calepinage=1', 4), ('?include_calepinage=0', 3)]))
    out, ok = {}, True
    for nom, dv, formats in cas:
        res = {'reference': dv.reference, 'id': dv.id}
        liens_avant = ShareLink.objects.filter(devis=dv).count()
        premier = None
        for qs, attendu in formats:
            st, pages, body = rendu(dv, qs)
            res[qs or 'defaut'] = {'http': st, 'pages': len(pages), 'attendu': attendu}
            ok &= st == 200 and len(pages) == attendu
            if premier is None and st == 200:
                premier = (qs, pages)
        if premier is not None:
            dv.refresh_from_db()
            st, pages2, _ = rendu(dv, premier[0])
            res['persistance_texte_identique'] = pages2 == premier[1]
            ok &= res['persistance_texte_identique']
        res['sharelink_crees_par_rendus'] = ShareLink.objects.filter(devis=dv).count() - liens_avant
        ok &= res['sharelink_crees_par_rendus'] == 0
        api = apis[dv.company_id][0]
        r = api.post(f'/api/django/ventes/devis/{dv.id}/share-link/', {}, format='json', **H)
        if r.status_code in (200, 201):
            rd = api.get(f"/api/django/ventes/proposal/{r.data.get('token_interne')}/", **H)
            q = (rd.data or {}).get('quote') or {} if rd.status_code == 200 else {}
            tot = q.get('display_total')
            ht = (q.get('totaux_all') or {}).get('ht_net')
            texte = '\n'.join(premier[1]) if premier else ''
            res['client'] = {'http': rd.status_code, 'display_total': tot, 'ht_net': ht,
                             'ttc_imprime': tot is not None and mad(tot) in texte,
                             'ht_imprime': ht is not None and mad(ht) in texte}
            ok &= rd.status_code == 200 and (res['client']['ttc_imprime'] or res['client']['ht_imprime'])
        else:
            res['client'] = {'share_link_http': r.status_code}
            ok = False
        out[nom] = res
    st, pages, _ = rendu(Devis.objects.get(pk=1121))
    out['observation_1121_18_lignes'] = {'http': st, 'pages': len(pages), 'note': 'pagination variable (devis chargé)'}
    out['calepinage_trouve'] = cal is not None
    ok &= cal is not None
    out['repro'] = bool(ok)
    return out
