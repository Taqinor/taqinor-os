SONDE = {"constat": "C-AMOT-030", "sha": "673ec3f92",
         "attendu": "P2.4 — cartes Éco/Max des devis démo résidentiels 1119 et 1121 (GET /devis/<id>/offres-tailles/) : "
                    "chaque payback_annees publié = croisement du cumul 25 ans de CETTE carte (série du détail de taille, "
                    "même appel compute_cashflow_payback, ± 0,1 an ; clé omise si jamais remboursé), cumul final + prix = "
                    "economies_cumulees_25_ans_mad ; carte Recommandé = roi_s / roi_a du document (PDF)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.taille_detail import CLES_CHARGEABLES, deriver_detail
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)

    def croisement(cumul):
        prec = None
        for i, val in enumerate(cumul):
            if val >= 0:
                if prec is None:
                    return 0.0
                return i + (0 - prec) / (val - prec) if val != prec else float(i)
            prec = val
        return None

    out, ok, cartes = {}, True, 0
    for did in (1119, 1121):
        dv = Devis.objects.get(pk=did, company=admin.company)
        r = api.get(f'/api/django/ventes/devis/{did}/offres-tailles/', **H)
        bloc = (r.data or {}).get('offres_tailles') if r.status_code == 200 else None
        data = build_quote_data(dv, clean_pdf_options({}))
        res = {'http': r.status_code, 'roi_s': data.get('roi_s'), 'roi_a': data.get('roi_a')}
        ok &= r.status_code == 200 and bool(bloc)
        for offre in (bloc or {}).get('offres', []):
            for var in ('sans', 'avec'):
                carte = offre.get(var) or {}
                if not carte:
                    continue
                cle = offre.get('cle')
                ligne = {'payback': carte.get('payback_annees'), 'prix': carte.get('prix_ttc'),
                         'eco': carte.get('economie_annuelle_mad'),
                         'ratio_simple': (round(carte['prix_ttc'] / carte['economie_annuelle_mad'], 2)
                                          if carte.get('prix_ttc') and carte.get('economie_annuelle_mad') else None)}
                if offre.get('est_le_devis'):
                    attendu = data.get('roi_s' if var == 'sans' else 'roi_a')
                    ligne['roi_document'] = attendu
                    ligne['ok'] = (attendu is not None and carte.get('payback_annees') is not None
                                   and abs(float(carte['payback_annees']) - float(attendu)) <= 0.1)
                elif cle in CLES_CHARGEABLES:
                    det = deriver_detail(dv, data, bloc, cle, var) or {}
                    cumul = ((det.get('cashflow') or {}).get('cumulative')) or []
                    cr = croisement(cumul) if cumul else None
                    ligne['croisement_cumul'] = None if cr is None else round(cr, 2)
                    ligne['cumul_final_plus_prix'] = (round(cumul[-1] + float(carte['prix_ttc']), 0)
                                                      if cumul and carte.get('prix_ttc') else None)
                    ligne['eco_25_ans_carte'] = carte.get('economies_cumulees_25_ans_mad')
                    p_ok = ((cr is None and carte.get('payback_annees') is None)
                            or (cr is not None and carte.get('payback_annees') is not None
                                and abs(float(carte['payback_annees']) - cr) <= 0.1))
                    c_ok = (ligne['cumul_final_plus_prix'] is not None and ligne['eco_25_ans_carte'] is not None
                            and abs(ligne['cumul_final_plus_prix'] - float(ligne['eco_25_ans_carte'])) <= 1)
                    ligne['ok'] = bool(cumul) and p_ok and c_ok
                else:
                    continue
                cartes += 1
                ok &= ligne['ok']
                res[f'{cle}_{var}'] = ligne
        out[dv.reference] = res
    out['cartes_controlees'] = cartes
    ok &= cartes >= 6
    out['repro'] = bool(ok)
    return out
