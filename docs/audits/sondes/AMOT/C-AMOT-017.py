SONDE = {"constat": "C-AMOT-017", "sha": "673ec3f92",
         "attendu": "P3.6 — échéancier 50/50 typé (acompte 50 / solde 50) : payment_terms = {acompte 50, materiel 0, "
                    "solde 50} (somme 100) ; cases du « Devis final » (montants_tranches) = 50/50 ; PDF résidentiel 3 p. "
                    "devis_final et une-page devis_final : « 50% » imprimé, aucune « réception du matériel » ni « 60% » ; "
                    "page publique (/proposal data, conditions) = mêmes puces que le PDF, sans créneau matériel"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)
    co = admin.company

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(did, qs):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    devis = make_devis(co, admin, make_client(co), [('Panneau mono 550W', '10', '1100'),
                                                   ('Onduleur réseau Huawei 5kW', '1', '8000')],
                       reference='DEV-SONDE-AMOT017')
    Devis.objects.filter(pk=devis.pk).update(mode_installation='residentiel', echeancier=[
        {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 50},
        {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 50}])
    devis.refresh_from_db()
    out, ok = {}, True
    data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full', 'devis_final': True}))
    cases = (data.get('montants_tranches') or {}).get('sans') or {}
    out['payment_terms'] = data.get('payment_terms')
    out['cases'] = {k: cases.get(k) for k in ('deux_cases', 'pct_a', 'pct_b', 'pct_c') if k in cases}
    ok &= data.get('payment_terms') == {'acompte': 50, 'materiel': 0, 'solde': 50}
    ok &= bool(cases.get('deux_cases'))
    for nom, qs in (('residentiel_final', '?devis_final=1'), ('onepage_final', '?pdf_mode=onepage&devis_final=1')):
        st, txt, pages = lire(devis.id, qs)
        lignes = [ln for ln in txt.splitlines() if '%' in ln and ('commande' in ln.lower() or 'marche' in ln.lower()
                                                                    or 'acompte' in ln.lower() or 'solde' in ln.lower()
                                                                    or 'matériel' in ln.lower())]
        out[nom] = {'http': st, 'pages': pages, 'cinquante': '50%' in txt or '50 %' in txt,
                    'reception_materiel': 'réception du matériel' in txt, 'soixante': '60%' in txt or '60 %' in txt,
                    'lignes_paiement': lignes[:6]}
        ok &= st == 200 and ('50%' in txt or '50 %' in txt) and 'réception du matériel' not in txt
        ok &= not ('60%' in txt or '60 %' in txt)
    r = api.post(f'/api/django/ventes/devis/{devis.id}/share-link/', {}, format='json', **H)
    if r.status_code in (200, 201):
        rd = api.get(f"/api/django/ventes/proposal/{r.data.get('token_interne')}/", **H)
        cond = (rd.data or {}).get('conditions') if rd.status_code == 200 else None
        out['page_publique'] = {'http': rd.status_code, 'conditions': cond}
        brut = norm(' '.join(cond or []))
        ok &= (rd.status_code == 200 and bool(cond) and 'réception du matériel' not in brut
               and ('50%' in brut or '50 %' in brut))
    else:
        out['share_link_http'] = r.status_code
        ok = False
    out['repro'] = bool(ok)
    return out
