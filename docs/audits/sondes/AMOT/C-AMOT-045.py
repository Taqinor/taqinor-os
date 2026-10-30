SONDE = {"constat": "C-AMOT-045", "sha": "673ec3f92",
         "attendu": "P3.3 — devis INDUSTRIEL démo portant une simulation PÉRIMÉE (etude_params.simulation : champ "
                    "120 kWc, P50 990 000, P90 987 654, posée dans la transaction) : /proposal industriel 4 p. sans "
                    "« 987 654 » (P90 omise) ; la même simulation rendue cohérente (kWc du devis, P50 = production "
                    "imprimée) -> P90 imprimée"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(did):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    def milliers(x):
        return f'{int(round(x)):,}'.replace(',', ' ')

    out, ok, essai = {}, True, None
    for did in (1112, 1044, 1080):
        dv = Devis.objects.filter(pk=did, company=admin.company, mode_installation='industriel').first()
        if dv is None:
            continue
        d = build_quote_data(dv, clean_pdf_options({}))
        ch = chiffres_cles(synthese_ci(dict(d)) or {})
        kwc, prod = ch.get('kwc') or d.get('puissance_kwc'), ch.get('production_kwh_an')
        st, txt, pages = lire(did)
        if st == 200 and kwc and prod and not d.get('regles_calcul_origine'):
            essai = (dv, kwc, prod, pages)
            break
        out[f'ecarte_{did}'] = {'http': st, 'kwc': kwc, 'prod': prod, 'origine': d.get('regles_calcul_origine')}
    if essai is None:
        out['repro'] = False
        return out
    dv, kwc, prod, pages0 = essai
    ep = dict(dv.etude_params or {})
    ep['simulation'] = {'zones': [{'kwc': 120.0}], 'pr': {'p50_kwh': 990000, 'p90_kwh': 987654}}
    Devis.objects.filter(pk=dv.pk).update(etude_params=ep)
    st, txt, pages = lire(dv.id)
    out['devis'] = {'reference': dv.reference, 'kwc': kwc, 'production_imprimee': prod, 'pages_sans_simulation': pages0}
    out['perimee'] = {'http': st, 'pages': pages, 'p90_987654_imprimee': '987 654' in txt,
                      'lignes_p90': [ln for ln in txt.splitlines() if 'P90' in ln][:3]}
    ok &= st == 200 and pages == 4 and '987 654' not in txt
    p90 = round(prod * 0.9)
    ep['simulation'] = {'zones': [{'kwc': float(kwc)}], 'pr': {'p50_kwh': float(prod), 'p90_kwh': p90}}
    Devis.objects.filter(pk=dv.pk).update(etude_params=ep)
    st, txt, pages = lire(dv.id)
    out['coherente'] = {'http': st, 'pages': pages, 'p90_attendue': p90, 'p90_imprimee': milliers(p90) in txt,
                        'lignes_p90': [ln for ln in txt.splitlines() if 'P90' in ln][:3]}
    ok &= st == 200 and pages == 4 and milliers(p90) in txt
    out['repro'] = bool(ok)
    return out
