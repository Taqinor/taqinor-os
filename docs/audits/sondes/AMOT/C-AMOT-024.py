SONDE = {"constat": "C-AMOT-024", "sha": "673ec3f92",
         "attendu": "P2.3 — devis démo à bloc HORAIRE avec option batterie : le rendement batterie n'est déduit qu'une "
                    "fois -> cashflow_avec[0] + total_avec = eco_a_ann (± 1 MAD), roi_a = croisement de la courbe "
                    "(± 0,1 an) ; l'économie annuelle avec batterie imprimée par le PDF (+ étude) = eco_a_ann"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(did, qs):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    def croisement(cumul):
        prec = None
        for i, val in enumerate(cumul):
            if val >= 0:
                if prec is None:
                    return 0.0
                return i + (0 - prec) / (val - prec) if val != prec else float(i)
            prec = val
        return None

    def mad(x):
        return f'{float(x):,.0f}'.replace(',', ' ')

    out, ok, rejoues = {}, True, 0
    cands = Devis.objects.filter(company=admin.company, mode_installation='residentiel',
                                 etude_params__has_key='etude_horaire').order_by('-id')[:25]
    for dv in cands:
        try:
            d = build_quote_data(dv, clean_pdf_options({'pdf_mode': 'full'}))
        except Exception as e:  # noqa: BLE001
            out[dv.reference] = {'erreur': repr(e)[:160]}
            continue
        cumul = d.get('cashflow_avec') or []
        if not cumul or not d.get('eco_a_ann') or not d.get('total_avec'):
            continue
        cr = croisement(cumul)
        an1 = cumul[0] + float(d['total_avec'])
        res = {'id': dv.id, 'nb_options': d.get('nb_options'), 'savings_method': d.get('savings_method'),
               'eco_a_ann': d.get('eco_a_ann'), 'flux_an1': round(an1, 2), 'roi_a': d.get('roi_a'),
               'croisement': None if cr is None else round(cr, 2)}
        res['ok'] = abs(an1 - float(d['eco_a_ann'])) <= 1 and (
            (cr is None and d.get('roi_a') in (None, 0)) or (cr is not None and d.get('roi_a') is not None
                                                              and abs(float(d['roi_a']) - cr) <= 0.1))
        ok &= res['ok']
        if rejoues < 2:
            st, txt, pages = lire(dv.id, '?include_etude=1')
            res['pdf_etude'] = {'http': st, 'pages': pages, 'eco_a_imprimee': mad(d['eco_a_ann']) in txt}
            ok &= st == 200 and mad(d['eco_a_ann']) in txt
        rejoues += 1
        out[dv.reference] = res
        if rejoues >= 4:
            break
    out['devis_rejoues'] = rejoues
    ok &= rejoues >= 1
    out['repro'] = bool(ok)
    return out
