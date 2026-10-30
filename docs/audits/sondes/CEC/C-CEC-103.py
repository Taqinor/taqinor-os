SONDE = {"constat": "C-CEC-103", "sha": "5908d43bb",
         "attendu": "CEC6 — devis automatique usine MT (60 000 kWh/mois, lun-sam 2×8 dès 6 h, Tarif Général) : "
                    "option « sans » : économie an 1 PDF = economie_ci = bannière = /proposition = Σ kWh évités "
                    "par poste horaire × tarif (à la main), retour PDF = mode_kpis /proposition = bannière = flux "
                    "servi interpolé = flux reconstruit à la main ; option « avec batterie » présente, économie et "
                    "retour servis, imprimés, égaux au recalcul"}


# ---- outillage commun (copié dans chaque sonde CLD/CEC : une sonde est autonome) ----
H = {'HTTP_HOST': 'localhost'}
_TEL = [0]


def _client():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    api = APIClient()
    # Société démo 2 (catalogue C&I aux 71 articles tarifés ; prix d'essai, jamais un fait).
    u = get_user_model().objects.get(username='demo_admin')
    api.force_authenticate(u)
    # Rejeu 30/10 (règle marginale des 10 ans, afae583c4d/e1353d4278) : le catalogue démo porte des câbles « au mètre »
    # à des prix fictifs (1 500 / 900 MAD/m) qui empêchent tout module de batterie de se rembourser — prix d'essai
    # réalistes, DANS la transaction annulée, pour que l'option « avec batterie » existe et que CEC6 se vérifie.
    from apps.stock.models import Produit
    for p in Produit.objects.filter(company_id=u.company_id, nom__startswith='Câble'):
        if 'mètre' in p.nom:
            p.prix_vente = 15 if 'solaire' in p.nom else 40
            p.save(update_fields=['prix_vente'])
    return api


def _lead(api, nom, **champs):
    _TEL[0] += 1
    corps = {'nom': 'Sonde %s' % nom, 'ville': 'Casablanca',
             'telephone': '06619%05d' % (hash(nom) % 90000 + _TEL[0]), 'raccordement': 'triphase'}
    corps.update(champs)
    r = api.post('/api/django/crm/leads/', corps, format='json', **H)
    if r.status_code != 201:
        raise AssertionError('lead %s : %s %s' % (nom, r.status_code, str(r.data)[:400]))
    return r.data['id']


def _pdf_texte(api, did):
    r = api.get('/api/django/ventes/devis/%s/proposal/' % did, **H)
    corps = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
    if r.status_code != 200:
        return r.status_code, 0, ''
    import fitz
    doc = fitz.open(stream=corps, filetype='pdf')
    return 200, doc.page_count, '\n'.join(p.get_text() for p in doc).replace(' ', ' ').replace('\xa0', ' ')


def _devis_auto(api, nom, preview=True, **champs):
    """Lead (profil déclaré) -> POST /ventes/devis/auto/ (bouton « Devis automatique ») ->
    devis relu, aperçu du générateur (etude-ci/preview), economie-ci, PDF /proposal (texte
    PyMuPDF) et charge /proposition (jeton d'aperçu interne du share-link)."""
    lid = _lead(api, nom, **champs)
    r = api.post('/api/django/ventes/devis/auto/', {'lead': lid}, format='json', **H)
    if r.status_code >= 300:
        return {'lead': lid, 'auto_statut': r.status_code, 'auto_refus': str(r.data)[:500]}
    auto = {k: v for k, v in r.data.items() if k != 'alertes'}
    did = auto['id']
    d = api.get('/api/django/ventes/devis/%s/' % did, **H).data
    ep = d.get('etude_params') or {}
    out = {'lead': lid, 'auto_statut': r.status_code, 'auto': auto, 'devis': did, 'ep': ep,
           'eci': ep.get('etude_ci') or {},
           'alertes_codes': sorted({a.get('code') for a in r.data.get('alertes') or []}),
           'lignes': [(li.get('designation'), float(li.get('quantite') or 0)) for li in d.get('lignes') or []]}
    if preview:
        pv = api.post('/api/django/ventes/etude-ci/preview/', {'lead': lid}, format='json', **H)
        out['preview'] = pv.data if pv.status_code == 200 else {'statut': pv.status_code}
    e = api.get('/api/django/ventes/devis/%s/economie-ci/' % did, **H)
    out['eco'] = e.data if e.status_code == 200 else {'statut_http': e.status_code}
    out['pdf_statut'], out['pdf_pages'], out['pdf'] = _pdf_texte(api, did)
    s = api.post('/api/django/ventes/devis/%s/share-link/' % did, {}, format='json', **H)
    pr = api.get('/api/django/ventes/proposal/%s/' % s.data.get('token_interne'), **H)
    out['prop'] = pr.data if pr.status_code == 200 else {'statut_http': pr.status_code}
    # Oracle 7 (qa-explorer) : ni prix d'achat ni marge dans le PDF client ni dans la charge /proposition.
    import json as _j
    import re as _re
    out['oracle7'] = (_re.search(r"(?i)prix d.achat|prix_achat|co[uû]t d.achat|\bmarge\b", out['pdf']) is None
                      and 'prix_achat' not in _j.dumps(out['prop'], default=str))
    return out


def _fr(x, dec=0):
    """Nombre au format du PDF : « 40 876 », « 7,7 », « 25,56 »."""
    s = ('{:,.%df}' % dec).format(x).replace(',', ' ').replace('.', ',')
    return s


def _kwc_pdf(kwc):
    """Motif du kWc imprimé (« 25,56 », « 85,2 » ou « 85,20 »)."""
    t = _fr(kwc, 2)
    return t[:-1] + '0?' if t.endswith('0') else t


def _dans_pdf(texte, motif):
    import re
    return re.search(motif, texte) is not None


def _retour_flux(flux):
    """Retour au dixième recalculé à la main : année où le cumul passe à zéro, interpolée."""
    cumul = 0.0
    for f in flux:
        prec = cumul
        cumul += f['flux_mad']
        if f['annee'] and cumul >= 0:
            return round(f['annee'] - 1 + (-prec) / f['flux_mad'], 1)
    return None


def _regle_10_ans(paliers, horizon=10):
    """Règle des 10 ans recalculée à la main sur les paliers servis : les paliers admis forment un
    préfixe ; aucun groupe de paliers au-delà du dernier admis ne se rembourse (Σ coût ÷ Σ économie)
    dans l'horizon ; la fenêtre regardée compte au moins 4 paliers au-delà (CLD8) sauf borne."""
    admis = [p['admis'] for p in paliers]
    k = admis.index(False) if False in admis else len(admis)
    if any(admis[k:]):
        return False
    autre_borne = any(p.get('borne') not in (None, 'horizon_marginal') for p in paliers[k:])
    cout = eco = 0.0
    for p in paliers[k:]:
        if p.get('borne') not in (None, 'horizon_marginal'):
            break
        cout += p['cout_ht']
        eco += p['economie_annuelle']
        if eco > 0 and cout / eco <= horizon:
            return False
    return len(paliers) - k >= 4 or autre_borne or len(paliers) == k


def _flux_main(invest_ht, eco1, remplacements, deg=0.005, horizon=25):
    """Flux 25 ans reconstruit À LA MAIN : économie an n = éco an 1 × (1 − 0,5 %)^(n−1)
    (médiane NREL du moteur), moins les remplacements à leur année."""
    flux = [{'annee': 0, 'flux_mad': -invest_ht}]
    for n in range(1, horizon + 1):
        f = eco1 * (1 - deg) ** (n - 1) - sum(m for a, m in remplacements if a == n)
        flux.append({'annee': n, 'flux_mad': f})
    return flux


def _cec(api, nom, **champs):
    """CEC6 — économie et retour, option « sans » ET option « avec batterie » : PDF /proposal, bloc
    economie_ci (GET economie-ci), bannière du devis auto, charge /proposition (mode_kpis, synthèse) et
    recalcul À LA MAIN (Σ kWh évités × tarif du poste ; flux 25 ans reconstruit, dégradation 0,5 %/an
    et remplacements servis ; retour interpolé au dixième)."""
    o = _devis_auto(api, nom, **champs)
    if o['auto_statut'] != 201:
        return {'sans': {'ok': {'devis_auto_201': False}, 'refus': o.get('auto_refus')}, 'avec': None}
    eco, prop, pdf = o['eco'], o['prop'], o['pdf']
    syn = prop.get('synthese_ci') or {}
    kp = prop.get('mode_kpis') or {}
    q = prop.get('quote') or {}
    ok, f = {}, {}
    e1 = eco['economie_annee1']
    main_eco = sum(p['kwh_evites'] * p['tarif_kwh'] for p in e1['par_poste'])
    kwh_ev = sum(p['kwh_evites'] for p in e1['par_poste'])
    b = o['eci']['bilan']
    f['economie'] = {'economie_ci': e1['total_mad'], 'main': round(main_eco, 2), 'kwh_evites': kwh_ev,
                     'autoconso_bilan': b['autoconso_kwh'], 'banniere': o['auto'].get('economie_an_1_ht'),
                     'mode_kpis': kp.get('economies_annuelles'),
                     'synthese': ((syn.get('argent') or {}).get('economie_annee1') or {}).get('total_mad'),
                     'par_poste': [(p['poste'], p['kwh_evites'], p['tarif_kwh'], p['mad']) for p in e1['par_poste']]}
    ok['eco_main'] = abs(main_eco - e1['total_mad']) <= max(1.0, 0.001 * e1['total_mad'])
    ok['kwh_evites_bilan'] = abs(kwh_ev - b['autoconso_kwh']) <= 1
    ok['eco_partout'] = (o['auto'].get('economie_an_1_ht') == e1['total_mad'] == kp.get('economies_annuelles')
                         == f['economie']['synthese'])
    # Mise en page à deux options (« Économie annuelle ») OU mono-option (« Économies estimées / an (HT) »,
    # « Économie de l'année 1 (HT) ») — rejeu 30/10 : même chiffre, libellé selon la mise en page.
    ok['eco_pdf'] = (_dans_pdf(pdf, r'conomie annuelle\s*\n%s MAD HT' % _fr(e1['total_mad']))
                     or _dans_pdf(pdf, r'%s MAD\s*\n[ÉE]conomie' % _fr(e1['total_mad'])))
    flux = eco['flux_ht']['flux']
    invest = -flux[0]['flux_mad']
    remp = [(r['annee'], r['montant_ht_mad']) for r in eco.get('remplacements') or []]
    main_flux = _flux_main(invest, e1['total_mad'], remp)
    r_main, r_serv = _retour_flux(main_flux), _retour_flux(flux)
    m = (__import__('re').search(r'Retour sur investissement\s*\n([\d,]+) ans', pdf)
         or __import__('re').search(r'([\d,]+) ans\s*\n(?:Retour estimé|Délai de retour)', pdf))
    r_pdf = float(m.group(1).replace(',', '.')) if m else None
    f['retour'] = {'pdf': r_pdf, 'mode_kpis_proposition': kp.get('payback'), 'banniere': o['auto'].get('retour_ans'),
                   'flux_servi_interpole': r_serv, 'main': r_main, 'simple_invest_sur_eco': round(invest / e1['total_mad'], 2),
                   'indicateurs_retour_ans_entier': eco['indicateurs'].get('retour_ans'),
                   'invest_ht': invest, 'ht_net_devis': (q.get('totaux_sans') or {}).get('ht_net'),
                   'remplacements': remp}
    ok['invest_ht_devis'] = abs(invest - ((q.get('totaux_sans') or {}).get('ht_net') or 0)) <= 0.05
    ok['flux_main'] = all(abs(a['flux_mad'] - c['flux_mad']) <= 0.02 * abs(c['flux_mad']) + 1
                          for a, c in zip(main_flux, flux))
    ok['retour_partout'] = r_pdf is not None and r_pdf == kp.get('payback') == o['auto'].get('retour_ans') == r_serv
    ok['oracle7_prix_achat'] = o['oracle7']
    ok['retour_main'] = r_main is not None and r_pdf is not None and abs(r_main - r_pdf) <= 0.1
    sans = {'ok': ok, 'faits': f, 'devis': o['auto']['reference'], 'scenario': o['ep'].get('scenario')}
    # ---- option « avec batterie » ----
    av = (o['eci'].get('option_avec') or {})
    if not av:
        return {'sans': sans, 'avec': {'ok': {'option_avec_presente': False}, 'scenario': o['ep'].get('scenario'),
                                       'lignes': o['lignes']}}
    ok2, f2 = {}, {}
    eav = (av.get('economie_ci') or {}).get('economie_annee1') or {}
    main_av = sum(p['kwh_evites'] * p['tarif_kwh'] for p in eav.get('par_poste') or [])
    ob = (syn.get('option_batterie') or {})
    vc = ob.get('valeur_chiffree') or {}
    tav = (q.get('totaux_avec') or {})
    pva = (o['preview'].get('option_avec') or {})
    f2['economie'] = {'etude': av.get('economie_annuelle_mad'), 'economie_ci': eav.get('total_mad'),
                      'main': round(main_av, 2), 'proposition': vc.get('economie_annuelle_mad'),
                      'apercu': pva.get('economie_annuelle_mad')}
    ok2['eco_main'] = bool(eav) and abs(main_av - eav['total_mad']) <= max(1.0, 0.001 * eav['total_mad'])
    ok2['eco_partout'] = av.get('economie_annuelle_mad') == eav.get('total_mad') == vc.get('economie_annuelle_mad')
    ok2['eco_pdf'] = len(__import__('re').findall(r'conomie annuelle\s*\n%s MAD HT' % _fr(av.get('economie_annuelle_mad') or 0), pdf)) >= 1
    ok2['invest_pdf'] = _dans_pdf(pdf, r'Investissement TTC\s*\n%s,00 MAD' % _fr(tav.get('ttc') or 0))
    fx = pva.get('economie_flux') or {}
    remp_av = [(r['annee'], r['montant_ht_mad']) for r in fx.get('remplacements') or []]
    flux_av = (fx.get('flux_ht') or {}).get('flux') or []
    r_av_main = _retour_flux(_flux_main(tav.get('ht_net') or 0, eav.get('total_mad') or 0, remp_av)) if remp_av or flux_av else None
    m2 = __import__('re').search(r'Avec batterie[\s\S]{0,300}?Retour sur investissement\s*\n([\d,]+) ans', pdf)
    f2['retour'] = {'apercu_generateur': pva.get('retour_simple_ans'), 'etude_du_devis': av.get('retour_simple_ans'),
                    'proposition': vc.get('retour_simple_ans'), 'pdf': m2.group(1) if m2 else None,
                    'main_sur_invest_du_devis': r_av_main, 'invest_ht_devis': tav.get('ht_net'),
                    'invest_ht_apercu': pva.get('cout_vente_ht'), 'remplacements_apercu': remp_av,
                    'flux_etude_du_devis': av.get('economie_flux') is not None}
    ok2['retour_servi_devis'] = av.get('retour_simple_ans') is not None
    ok2['retour_pdf_proposition'] = m2 is not None and vc.get('retour_simple_ans') is not None
    ok2['retour_main'] = (r_av_main is not None and av.get('retour_simple_ans') is not None
                          and abs(r_av_main - av['retour_simple_ans']) <= 0.1)
    return {'sans': sans, 'avec': {'ok': ok2, 'faits': f2}}


def _verdict(r):
    s_ok = all(r['sans']['ok'].values())
    a_ok = r['avec'] is not None and all(r['avec']['ok'].values())
    return {'repro': s_ok and a_ok, 'sans_pass': s_ok, 'avec_pass': a_ok, **r}


def sonde(ctx):
    return _verdict(_cec(_client(), 'CEC103 usine MT', type_installation='industriel', tension_raccordement='mt',
                         conso_mensuelle_kwh='60000', jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=6,
                         regime_equipes='2x8'))
