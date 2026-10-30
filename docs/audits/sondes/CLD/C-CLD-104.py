SONDE = {"constat": "C-CLD-104", "sha": "5908d43bb",
         "attendu": "P-CLD-4 (CLD13) — usine 90 000 kWh/mois : harnais R3 (test_ciq122, catalogue figé) rejoué "
                    "sur le code de la pile ⇒ groupe 335 → 405 amorti (retenue ≈ 400-405 kWc posés, jamais 335) ; "
                    "devis automatique de la même usine MT sur la pile : règle des 10 ans recalculée sur les "
                    "paliers servis (aucun groupe au-delà ne se rembourse en 10 ans, fenêtre ≥ 4 paliers), kWc "
                    "posé = aperçu = étude = PDF, DC/AC ≤ 1,35"}


# ---- outillage commun (copié dans chaque sonde CLD/CEC : une sonde est autonome) ----
H = {'HTTP_HOST': 'localhost'}
_TEL = [0]


def _client():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    api = APIClient()
    # Société démo 2 (catalogue C&I aux 71 articles tarifés ; prix d'essai, jamais un fait).
    api.force_authenticate(get_user_model().objects.get(username='demo_admin'))
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


def sonde(ctx):
    api = _client()
    ok, faits = {}, {}
    from apps.ventes.tests import test_ciq122_cas_reference as h
    r3 = h._etudier(mode='industriel', tension='mt', tarif={'contrat': 'mt_general'},
                    consommation={'kwh_mensuels': [90000] * 12},
                    rythme={'jours_ouverts': [True] * 6 + [False], 'equipes': '2x8', 'debut_equipe_h': 6})
    t3 = r3['taille']
    faits['R3'] = {'retenue': t3['retenue_kwc'], 'nb_panneaux': t3['nb_panneaux'], 'raison': t3.get('raison_arret'),
                   'paliers_330_410': [(p['kwc'], p['ratio_marginal_annees'], p['admis']) for p in t3['paliers']
                                       if 330 <= p['kwc'] <= 410]}
    ok['R3_405'] = 400 <= t3['retenue_kwc'] <= 406 and abs(t3['retenue_kwc'] - t3['nb_panneaux'] * 0.71) < 0.006
    o = _devis_auto(api, 'CLD104 usine 90000', type_installation='industriel', tension_raccordement='mt',
                    conso_mensuelle_kwh='90000', jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=6,
                    regime_equipes='2x8')
    ok['devis_auto_201'] = o['auto_statut'] == 201
    if not ok['devis_auto_201']:
        return {'repro': False, 'ok': ok, 'faits': faits, 'refus': o}
    t, pv = o['eci']['taille'], o['preview']['taille']
    tcc = o['ep'].get('taille_creation_ci') or {}
    faits['pile'] = {'retenue': t['retenue_kwc'], 'creation': tcc.get('raison_arret'),
                     'paliers': [(p['kwc'], p['ratio_marginal_annees'], p['admis'], p.get('borne'))
                                 for p in pv['paliers']]}
    ok['regle_10_ans_pile'] = _regle_10_ans(pv['paliers'])
    syn = o['prop'].get('synthese_ci') or {}
    kw_ac = (syn.get('installation') or {}).get('kw_ac_total')
    faits['kw_ac'] = kw_ac
    ok['meme_kwc_pdf'] = (pv['retenue_kwc'] == t['retenue_kwc'] == o['auto']['kwc']
                          and _dans_pdf(o['pdf'], r'Centrale solaire %s kWc' % _kwc_pdf(t['retenue_kwc'])))
    ok['ratio_dc_ac'] = bool(kw_ac) and t['retenue_kwc'] / kw_ac <= 1.35
    ok['oracle7_prix_achat'] = o['oracle7']
    return {'repro': all(ok.values()), 'ok': ok, 'faits': faits, 'devis': o['auto']['reference']}
