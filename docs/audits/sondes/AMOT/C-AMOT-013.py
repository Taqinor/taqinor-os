SONDE = {"constat": "C-AMOT-013", "sha": "673ec3f92",
         "attendu": "P2.3 — devis deux options à étude SAISIE (economies_annuelles 16 500, production_annuelle 12 000, "
                    "société démo) : roi_s / roi_a = premier croisement de cashflow_sans / cashflow_avec (± 0,1 an), "
                    "net_gain_* = fin de courbe, année 1 = −prix de l'option + économie ; le PDF résidentiel (+ étude) "
                    "imprime ces paybacks ; une production « calepinage » n'est pas recopiée (prod_kwh = moteur)"}


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

    def croisement(cumul):
        prec = None
        for i, val in enumerate(cumul):
            if val >= 0:
                if prec is None:
                    return 0.0
                return i + (0 - prec) / (val - prec) if val != prec else float(i)
            prec = val
        return None

    lignes = [('Panneau mono 710W', '14', '1200'), ('Onduleur réseau Huawei 10kW', '1', '16000'),
              ('Onduleur hybride Deye 10kW', '1', '24000'), ('Batterie Dyness 10kWh', '1', '30000')]
    cli = make_client(co)
    devis = make_devis(co, admin, cli, lignes, reference="DEV-SONDE-AMOT013", etude_params={
        'scenario': 'Les deux (Sans + Avec)', 'production_annuelle': 12000, 'economies_annuelles': 16500})
    Devis.objects.filter(pk=devis.pk).update(mode_installation='residentiel')
    devis.refresh_from_db()
    out, ok = {}, True
    d = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
    for opt, cle in (('sans', 'roi_s'), ('avec', 'roi_a')):
        cumul = d.get(f'cashflow_{opt}') or []
        cr = croisement(cumul)
        an1 = cumul[0] if cumul else None
        attendu_an1 = -float(d[f'total_{opt}']) + 16500
        res = {'roi': d.get(cle), 'croisement_courbe': None if cr is None else round(cr, 2),
               'net_gain': d.get(f'net_gain_{opt}'), 'fin_courbe': cumul[-1] if cumul else None,
               'annee1': an1, 'annee1_attendue': attendu_an1}
        res['ok'] = (cr is not None and d.get(cle) is not None and abs(float(d[cle]) - cr) <= 0.1
                     and d.get(f'net_gain_{opt}') == cumul[-1] and abs(an1 - attendu_an1) <= 1)
        out[opt] = res
        ok &= res['ok']
    out['eco_ann'] = [d.get('eco_s_ann'), d.get('eco_a_ann')]
    ok &= d.get('eco_s_ann') == 16500 and d.get('eco_a_ann') == 16500
    for nom, qs in (('residentiel_3p', ''), ('residentiel_etude', '?include_etude=1')):
        st, txt, pages = lire(devis.id, qs)
        roi_txt = {o: f"{float(d[c]):.1f}".replace('.', ',') for o, c in (('sans', 'roi_s'), ('avec', 'roi_a'))}
        res = {'http': st, 'pages': pages,
               'payback_sans_imprime': roi_txt['sans'] in txt, 'payback_avec_imprime': roi_txt['avec'] in txt,
               'eco_16500_imprimee': '16 500' in txt,
               'lignes_retour': [ln for ln in txt.splitlines() if 'ans' in ln and (roi_txt['sans'] in ln or
                                                                                  roi_txt['avec'] in ln)][:4]}
        res['retour_en_autre_valeur'] = [ln for ln in txt.splitlines() if 'Retour en' in ln
                                         and roi_txt['sans'] not in ln and roi_txt['avec'] not in ln]
        out[nom] = res
        # le 3 pages résidentiel n'imprime AUCUN payback (méthode seulement) : on y exige l'absence de
        # contradiction ; la page étude (4 p.) imprime les deux paybacks de la courbe.
        ok &= st == 200 and not res['retour_en_autre_valeur']
        if nom == 'residentiel_etude':
            ok &= pages == 4 and res['payback_sans_imprime'] and res['payback_avec_imprime']
    # production calepinage non recopiée
    t = make_devis(co, admin, cli, lignes[:2], reference='DEV-SONDE-AMOT013-T',
                   etude_params={'scenario': 'Sans batterie'})
    c = make_devis(co, admin, cli, lignes[:2], reference='DEV-SONDE-AMOT013-C', etude_params={
        'scenario': 'Sans batterie', 'production_annuelle': 10890, 'production_source': 'calepinage'})
    dt = build_quote_data(t, clean_pdf_options({'pdf_mode': 'full'}))
    dc = build_quote_data(c, clean_pdf_options({'pdf_mode': 'full'}))
    out['calepinage'] = {'prod_temoin': dt.get('prod_kwh'), 'prod_calepinage_devis': dc.get('prod_kwh')}
    ok &= dc.get('prod_kwh') != 10890 and dc.get('prod_kwh') == dt.get('prod_kwh')
    out['repro'] = bool(ok)
    return out
