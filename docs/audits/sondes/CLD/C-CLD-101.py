SONDE = {"constat": "C-CLD-101", "sha": "5908d43bb",
         "attendu": "P-CLD-1 (CLD13) — boulangerie 6 000 kWh/mois 7/7 6-22 h sans talon : devis automatique C&I "
                    "créé ; talon = F (rapport BDEW G5 ≈ 0,705, statut estimation) ; taux d'autoconso = "
                    "autoconsommé ÷ production ; taille au kWc posé (panneaux entiers × 710 Wc) = dernier palier "
                    "admis de la règle des 10 ans ; PDF /proposal = même kWc, production et autoconso ; harnais R3 "
                    "(test_ciq122) rejoué sur le code de la pile : 30,53 kWc, 48 824 kWh, autoconso 0,654 ; même "
                    "taille saisie 30,53 sur la pile : même production"}


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
    o = _devis_auto(api, 'CLD101 boulangerie', type_installation='commercial',
                    categorie_commerciale='boulangerie', conso_mensuelle_kwh='6000',
                    jours_ouverture=[1, 2, 3, 4, 5, 6, 7], heure_debut=6, heure_fin=22,
                    contrat_electricite='bt_patente', tension_raccordement='bt')
    ok['devis_auto_201'] = o['auto_statut'] == 201
    if not ok['devis_auto_201']:
        return {'repro': False, 'refus': o}
    eci, b = o['eci'], o['eci']['bilan']
    talon = eci['profil_charge']['talon']
    faits['talon'] = talon
    rapport = (talon.get('valeur') or {}).get('rapport_nuit_jour')
    ok['talon_F'] = (talon.get('statut') == 'estimation' and 'G5' in str(talon.get('source'))
                     and rapport is not None and abs(rapport - 0.705) <= 0.005)
    # Le rapport publié est bien celui de la courbe : creux ÷ niveau des heures ouvertes du jour ouvré.
    jt = [j for j in eci['profil_charge']['jours_types'] if j['type_jour'] == 'ouvre']
    ok['talon_dans_la_courbe'] = all(abs(min(j['charge_kwh']) / max(j['charge_kwh']) - rapport) < 0.002 for j in jt)
    conso = sum(j['nb_jours'] * sum(j['charge_kwh']) for j in eci['profil_charge']['jours_types'])
    faits['conso_courbe_kwh'] = round(conso)
    ok['energie_conservee'] = abs(conso - 72000) <= 72
    taux = b['autoconso_kwh'] / b['production_kwh']
    faits['bilan'] = {k: b[k] for k in ('production_kwh', 'autoconso_kwh', 'surplus_kwh', 'taux_autoconso',
                                         'taux_couverture')}
    ok['autoconso_definition'] = abs(taux - b['taux_autoconso']) <= 0.001 and \
        abs(b['autoconso_kwh'] / 72000 - b['taux_couverture']) <= 0.001
    t = eci['taille']
    tcc = o['ep'].get('taille_creation_ci') or {}
    pv = o['preview']['taille']
    admis = [p for p in pv['paliers'] if p['admis']]
    faits['taille'] = {'retenue': t['retenue_kwc'], 'nb_panneaux': t['nb_panneaux'],
                       'creation': tcc.get('raison_arret'), 'paliers': [(p['kwc'], p['ratio_marginal_annees'],
                                                                         p['admis']) for p in pv['paliers']]}
    import math
    ok['taille_posee'] = (abs(t['retenue_kwc'] - t['nb_panneaux'] * 0.71) < 0.006
                          and t['nb_panneaux'] == math.ceil(admis[-1]['kwc'] / 0.71 - 1e-9)
                          and tcc.get('raison_arret') == 'horizon_marginal'
                          and _regle_10_ans(pv['paliers']))
    pdf = o['pdf']
    ok['pdf_coherent'] = (o['pdf_statut'] == 200 and o['pdf_pages'] == 3
                          and _dans_pdf(pdf, r'Centrale solaire %s kWc' % _kwc_pdf(t['retenue_kwc']))
                          and _dans_pdf(pdf, r'%s kWh/an' % _fr(b['production_kwh']))
                          and _dans_pdf(pdf, r'%d %%\s*\nAutoconsommation' % round(b['taux_autoconso'] * 100)))
    # Même taille SAISIE que R3 (30,53 kWc) sur la pile : production au prorata du productible.
    pv2 = api.post('/api/django/ventes/etude-ci/preview/', {'lead': o['lead'], 'taille_explicite_kwc': 30.53},
                   format='json', **H).data
    faits['pile_30_53'] = {k: pv2['bilan'][k] for k in ('production_kwh', 'taux_autoconso')}
    ok['pile_30_53_production_R3'] = abs(pv2['bilan']['production_kwh'] - 48824) <= 49
    # Harnais R3 (test_ciq122 : catalogue et PVGIS figés) rejoué sur le code de la pile.
    from apps.ventes.tests import test_ciq122_cas_reference as h
    r3 = h._etudier(rythme={'categorie_commerciale': 'boulangerie', 'jours_ouverts': [True] * 7,
                            'plages': {'ouvre': [[6, 22]]}})
    faits['R3'] = {'retenue': r3['taille']['retenue_kwc'], 'production': r3['bilan']['production_kwh'],
                   'autoconso': r3['bilan']['taux_autoconso'],
                   'talon': (r3['profil_charge']['talon'].get('valeur') or {}).get('rapport_nuit_jour')}
    ok['R3_rejoue'] = (r3['taille']['retenue_kwc'] == 30.53 and abs(r3['bilan']['production_kwh'] - 48824) <= 49
                       and abs(r3['bilan']['taux_autoconso'] - 0.654) <= 0.005)
    ok['oracle7_prix_achat'] = o['oracle7']
    return {'repro': all(ok.values()), 'ok': ok, 'faits': faits, 'devis': o['auto']['reference']}
