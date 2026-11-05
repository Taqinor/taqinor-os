# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT19 (Then « le texte cite exactement les tranches des cases ») : le builder réécrit `payment_terms` depuis
`montants_tranches[_branche_imprimee]` où `_branche_imprimee` = « avec » dès que `deux_options` ; les CASES du
« Devis final » (residential/trust.py, generate_devis_premium.py) choisissent leur branche par scénario puis
`recommended` (« sans » si l'option recommandée est « Sans batterie »). Avec un échéancier dont une tranche est en
DIRHAMS (`tranches_echeancier_en_montant`), les % diffèrent d'une branche à l'autre : texte et cases divergent-ils ?
Moteur réel, transaction annulée.

Réalignée le 05/11/2026 sur AMOT122 (D-AMOT-VER4-1) : les cases du Devis final lisent désormais
`data['branche_echeancier']` quand le builder la sert (niveau ≥ 12 : `option_effective`), la règle
scénario → `recommended` n'étant plus que le repli d'hier. La sonde recalcule donc la branche des cases
EXACTEMENT comme `residential/trust.py::_bloc_paiement` et le Devis final de `generate_devis_premium.py`
(et non plus avec l'ancienne règle seule, qui la faisait répondre `repro` à tort)."""
SONDE = {"constat": "C-AMOT-VER4-007", "sha": "c38868a62",
         "attendu": "devis deux options, option recommandée « Sans batterie », acompte 10 000 MAD : le % d'acompte "
                    "imprimé dans le texte (puces CGV, page publique, résidentiel) = le % de la case Acompte du Devis "
                    "final ; REPRO = ils diffèrent",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "authentication.Company"]}


def sonde(ctx):
    import html as _h
    import re
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.quote_engine.clauses_cgv import cgv_bullets_remplies
    from apps.ventes.quote_engine.residential import render as res_render
    from apps.ventes.quote_engine.residential import renderer as res_renderer
    from apps.ventes.public.payload_conditions import _conditions_publiques
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis, make_user

    def txt(h):
        return _h.unescape(re.sub(r'<[^>]+>', ' ', h or '')).replace('\xa0', ' ')

    co = make_company(slug='sonde-amot-ver4-007', nom='SONDE VER4 007')
    us = make_user(co)
    dv = make_devis(co, us, make_client(co), [
        ('Panneau mono 550W', '10', '1100'),
        ('Onduleur réseau Huawei 5kW', '1', '8000'),
        ('Onduleur hybride Deye 5kW', '1', '15000'),
        ('Batterie Dyness 5kWh', '1', '20000'),
    ], reference='DEV-SONDE-VER4-007',
        etude_params={'scenario': 'Les deux (Sans + Avec)', 'recommended_option': 'Sans batterie'})
    Devis.objects.filter(pk=dv.pk).update(mode_installation='residentiel', echeancier=[
        {'libelle': 'Acompte', 'type': 'montant', 'pct_or_montant': 10000},
        {'libelle': 'Solde', 'pct_or_montant': 50}])
    dv.refresh_from_db()
    data = build_quote_data(dv, clean_pdf_options({'pdf_mode': 'full', 'devis_final': True}))
    scen, reco = data.get('scenario'), data.get('recommended')
    branche_hier = ('sans' if scen == 'Sans batterie' else 'avec' if scen == 'Avec batterie'
                    else 'sans' if reco == 'Sans batterie' else 'avec')
    # AMOT122 — la branche SERVIE par le builder prime (trust._bloc_paiement, Devis final legacy).
    servie = data.get('branche_echeancier')
    branche_cases = servie if servie in ('sans', 'avec') else branche_hier
    mt = data.get('montants_tranches') or {}
    cases = mt.get(branche_cases) or {}
    termes = data.get('payment_terms')
    res_html = res_render.build_html(res_renderer._augment(dict(data)))
    res = txt(res_html)
    from apps.ventes.quote_engine import generate_devis_premium as legacy
    leg_html = legacy.render_html_for(dict(data))
    cgv = [txt(p) for p in cgv_bullets_remplies(data)]
    pub = [txt(str(p)) for p in (_conditions_publiques(data, dv) or [])]
    m_res_cases = re.findall(r'class="p3-pay-p">([^<]+)<', res_html)
    out = {
        'nb_options': data.get('nb_options'), 'scenario': scen, 'recommended': reco,
        'branche_cases': branche_cases, 'branche_echeancier_servie': servie, 'branche_regle_hier': branche_hier,
        'cases_sans': {k: mt.get('sans', {}).get(k) for k in ('pct_a', 'acompte', 'pct_s2', 'deux_cases', 'total')},
        'cases_avec': {k: mt.get('avec', {}).get(k) for k in ('pct_a', 'acompte', 'pct_s2', 'deux_cases', 'total')},
        'payment_terms_texte': termes,
        'cgv_acompte': [p for p in cgv if 'compte' in p][:2],
        'publique_acompte': [p for p in pub if 'compte' in p][:2],
        'residentiel_case_acompte_pct': m_res_cases[:2],
        'legacy_texte_acompte': re.findall(r'compte[^<]{0,40}?[\d.,]+\s*(?:%|&#37;)', leg_html)[:4],
        'residentiel_ligne_acompte': re.findall(r'Acompte à la commande : [\d.,]+%', res)[:2],
    }
    repro = str((termes or {}).get('acompte')) != str(cases.get('pct_a'))
    out['repro'] = repro
    return out
