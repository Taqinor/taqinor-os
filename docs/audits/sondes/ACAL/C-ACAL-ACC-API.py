SONDE = {"constat": "C-ACAL-ACC-API", "sha": "665a4ce53",
         "attendu": "ACAL351 (parties API seulement, société démo 2, transaction annulée) : S-A aller-retour — "
                    "l'`exemple` de roof_layout_v2.schema.json semé par POST layout/, relu, renvoyé à l'identique : "
                    "réponse « inchangé », document / layout_hash / empreinte / resultat et nombre de versions "
                    "identiques clé par clé ; S-B jeton If-Match périmé -> 409 document_modifie sans écriture, sans "
                    "jeton -> 428 ; DELETE -> 405 ; S-G id d'une autre société et id absent -> même statut et même "
                    "message ; depuis-lead rejoué deux fois -> un seul calepinage ; P6.2 restaurer v1 -> document v1 ; "
                    "S-E simuler -> resultat, puis Enregistrer sans geste ne périme pas la simulation ; S-H export-csv "
                    "horaire en text/csv et note-calcul.pdf servis.",
         "modeles": ["calepinage.Calepinage", "crm.Lead", "ventes.Devis"]}

H = {'HTTP_HOST': 'localhost'}
C = '/api/django/calepinage/calepinages/'


def _api(user):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user)
    return api


def _j(r):
    try:
        return r.json()
    except Exception:
        return None


def _post(api, url, data=None, jeton=None):
    kw = dict(H)
    if jeton is not None:
        kw['HTTP_IF_MATCH'] = '"%s"' % jeton
    return api.post(url, data if data is not None else {}, format='json', **kw)


def sonde(ctx):
    import copy
    import json
    from django.contrib.auth import get_user_model
    from apps.calepinage.models import Calepinage
    U = get_user_model()
    u = U.objects.get(username='demo_admin')
    co = u.company
    api = _api(u)
    ok, mes = {}, {}
    exemple = json.load(open('apps/calepinage/contract_samples/roof_layout_v2.schema.json', encoding='utf-8'))['exemple']

    def lead(tag):
        r = api.post('/api/django/crm/leads/', {'nom': 'QA-ACAL-ACC %s' % tag, 'ville': 'Casablanca',
                                                 'telephone': '0661%06d' % (abs(hash(tag)) % 1000000),
                                                 'type_installation': 'residentiel', 'facture_hiver': '800',
                                                 'raccordement': 'triphase'}, format='json', **H)
        assert r.status_code == 201, (r.status_code, str(_j(r))[:300])
        return r.json()['id']

    # ---------------- S-A : aller-retour octet-identique ----------------
    lid = lead('S-A')
    r = api.post(C, {'lead': lid, 'titre': 'QA-ACAL-ACC S-A'}, format='json', **H)
    assert r.status_code == 201, (r.status_code, str(_j(r))[:300])
    cid = r.json()['id']
    api.get('%s%s/design-context/' % (C, cid), **H)
    l0 = api.get('%s%s/layout/' % (C, cid), **H).json()
    w = _post(api, '%s%s/layout/' % (C, cid), {'roof_layout': copy.deepcopy(exemple)}, l0.get('empreinte_document') or '')
    mes['S-A_semis'] = '%s %s' % (w.status_code, str(_j(w))[:160])
    l1 = api.get('%s%s/layout/' % (C, cid), **H).json()
    d1 = api.get('%s%s/' % (C, cid), **H).json()
    v1 = api.get('%s%s/versions/' % (C, cid), **H)
    nv1 = len(v1.json() if isinstance(v1.json(), list) else v1.json().get('results', []))
    w2 = _post(api, '%s%s/layout/' % (C, cid), {'roof_layout': copy.deepcopy(l1['roof_layout'])}, l1['empreinte_document'])
    l2 = api.get('%s%s/layout/' % (C, cid), **H).json()
    d2 = api.get('%s%s/' % (C, cid), **H).json()
    v2 = api.get('%s%s/versions/' % (C, cid), **H)
    nv2 = len(v2.json() if isinstance(v2.json(), list) else v2.json().get('results', []))
    cles_perdues = sorted(set(exemple) - set(l1['roof_layout'] or {}))
    diff = sorted(k for k in set(l1['roof_layout']) | set(l2['roof_layout'])
                  if l1['roof_layout'].get(k) != l2['roof_layout'].get(k))
    mes['S-A'] = {'semis_statut': w.status_code, 'renvoi_statut': w2.status_code, 'renvoi': str(_j(w2))[:200],
                  'cles_exemple_absentes_apres_semis': cles_perdues, 'diff_cles_apres_renvoi': diff,
                  'layout_hash': [l1.get('layout_hash'), l2.get('layout_hash')], 'versions': [nv1, nv2]}
    ok['S-A_semis_200'] = w.status_code == 200
    ok['S-A_renvoi_inchange'] = w2.status_code == 200 and bool((_j(w2) or {}).get('inchange'))
    ok['S-A_document_identique'] = not diff and l1['empreinte_document'] == l2['empreinte_document']
    ok['S-A_hash_identique'] = l1.get('layout_hash') == l2.get('layout_hash')
    ok['S-A_resultat_identique'] = d1.get('resultat') == d2.get('resultat')
    ok['S-A_aucune_version_creee'] = nv1 == nv2

    # ---------------- S-B : jeton périmé / absent ----------------
    modif = copy.deepcopy(l2['roof_layout'])
    modif['panelWatt'] = (modif.get('panelWatt') or 500) + 5
    r409 = _post(api, '%s%s/layout/' % (C, cid), {'roof_layout': modif}, 'jeton-perime-acal')
    r428 = api.post('%s%s/layout/' % (C, cid), {'roof_layout': modif}, format='json', **H)
    l3 = api.get('%s%s/layout/' % (C, cid), **H).json()
    mes['S-B'] = {'perime': [r409.status_code, str(_j(r409))[:160]], 'sans_jeton': [r428.status_code, str(_j(r428))[:120]]}
    ok['S-B_409_document_modifie'] = r409.status_code == 409 and (_j(r409) or {}).get('code') == 'document_modifie'
    ok['S-B_428_sans_jeton'] = r428.status_code == 428
    ok['S-B_rien_ecrit'] = l3['empreinte_document'] == l2['empreinte_document']
    # Écriture par SECTION (ACAL22) : jeton périmé -> 409 nommé sans écriture ; jeton courant -> écrite.
    horizon8 = [{'azimut': a, 'hauteur': 2} for a in range(0, 360, 45)]
    s409 = api.post('%s%s/layout/section/' % (C, cid), {'cle': 'horizonProfile', 'valeur': horizon8,
                                                         'base_empreinte': 'jeton-perime-acal'}, format='json', **H)
    l3b = api.get('%s%s/layout/' % (C, cid), **H).json()
    s200 = api.post('%s%s/layout/section/' % (C, cid), {'cle': 'horizonProfile', 'valeur': horizon8,
                                                         'base_empreinte': l3b['empreinte_document']}, format='json', **H)
    l3c = api.get('%s%s/layout/' % (C, cid), **H).json()
    mes['S-B_section'] = {'perime': [s409.status_code, str(_j(s409))[:140]], 'courant': [s200.status_code,
                                                                                       str(_j(s200))[:140]]}
    ok['S-B_section_409_sans_ecriture'] = (s409.status_code == 409 and (_j(s409) or {}).get('code') == 'document_modifie'
                                           and l3b['empreinte_document'] == l3['empreinte_document'])
    ok['S-B_section_ecrite_jeton_courant'] = (s200.status_code == 200
                                              and l3c['empreinte_document'] != l3b['empreinte_document'])
    l3 = l3c

    # ---------------- P6.2 : version v2 puis restauration de v1 ----------------
    w3 = _post(api, '%s%s/layout/' % (C, cid), {'roof_layout': modif}, l3['empreinte_document'])
    vs = api.get('%s%s/versions/' % (C, cid), **H).json()
    vs = vs if isinstance(vs, list) else vs.get('results', [])
    mes['P6.2_versions'] = [(v.get('id'), v.get('numero') or v.get('version'), v.get('libelle') or v.get('label'))
                            for v in vs][:6]
    restaure = None
    if len(vs) >= 2:
        v_ancienne = sorted(vs, key=lambda v: v.get('id'))[0]
        rr = _post(api, '%s%s/versions/%s/restaurer/' % (C, cid, v_ancienne['id']), {})
        l4 = api.get('%s%s/layout/' % (C, cid), **H).json()
        restaure = rr.status_code
        ok['P6.2_restauration_tient'] = rr.status_code in (200, 201) and (l4['roof_layout'] or {}).get(
            'panelWatt') == l2['roof_layout'].get('panelWatt')
        vs2 = api.get('%s%s/versions/' % (C, cid), **H).json()
        vs2 = vs2 if isinstance(vs2, list) else vs2.get('results', [])
        mes['P6.2_apres_restauration'] = [(v.get('id'), v.get('libelle') or v.get('label') or v.get('motif'))
                                          for v in vs2][:6]
    mes['P6.2'] = 'écriture v2 %s, restaurer %s' % (w3.status_code, restaure)

    # ---------------- DELETE -> 405 ----------------
    rd = api.delete('%s%s/' % (C, cid), **H)
    mes['DELETE'] = rd.status_code
    ok['DELETE_405'] = rd.status_code == 405

    # ---------------- S-G : autre société vs absent ----------------
    autre = Calepinage.objects.exclude(company=co).order_by('id').first()
    if autre:
        ra = api.get('%s%s/' % (C, autre.id), **H)
        rb = api.get('%s%s/' % (C, 999999999), **H)
        def sans_rid(j):  # request_id = identifiant de traçage propre à chaque requête, hors message
            j = copy.deepcopy(j or {})
            (j.get('error') or {}).pop('request_id', None)
            return j
        mes['S-G'] = {'autre_societe': [ra.status_code, _j(ra)], 'absent': [rb.status_code, _j(rb)]}
        ok['S-G_meme_reponse'] = ra.status_code == rb.status_code == 404 and sans_rid(_j(ra)) == sans_rid(_j(rb))
    else:
        mes['S-G'] = 'non jouable : aucun calepinage hors société 2'

    # ---------------- depuis-lead rejoué -> un seul calepinage ----------------
    lid2 = lead('depuis-lead')
    p1 = _post(api, C + 'depuis-lead/', {'lead': lid2})
    p2 = _post(api, C + 'depuis-lead/', {'lead': lid2})
    n_lead = Calepinage.objects.filter(company=co, lead_id=lid2).count()
    mes['depuis_lead'] = {'1er': [p1.status_code, (_j(p1) or {}).get('id')], '2e': [p2.status_code, (_j(p2) or {}).get('id')],
                          'calepinages_du_lead': n_lead}
    ok['depuis_lead_un_seul'] = p1.status_code in (200, 201) and p2.status_code in (200, 201) and n_lead == 1

    # ---------------- S-E : simuler, puis Enregistrer sans geste ne périme pas ----------------
    l5 = api.get('%s%s/layout/' % (C, cid), **H).json()
    rs = _post(api, '%s%s/simuler/' % (C, cid), {})
    # La simulation part en tâche de fond (202 + job) ; Celery est coupé par la sonde : le CORPS de la
    # tâche est exécuté ici, dans la transaction annulée (HTTP sortant bloqué : météo de repli seulement).
    tache = None
    jid = (_j(rs) or {}).get('job_id')
    if rs.status_code == 202 and jid:
        from apps.calepinage.tasks import simuler_calepinage
        try:
            simuler_calepinage.run(job_id=jid, company_id=co.id, calepinage_id=cid)
            tache = 'exécutée'
        except Exception as e:
            tache = 'échec : %s' % str(e)[:200]
        from django.apps import apps as _apps
        etat = None
        for m in _apps.get_models():
            if {'progress_pct', 'kind'} <= {f.name for f in m._meta.fields}:
                o = m.objects.filter(pk=jid).values().first()
                etat = {k: (str(v)[:200] if v is not None else None) for k, v in (o or {}).items()
                        if k in ('statut', 'status', 'message_erreur', 'error', 'progress_pct')}
                break
        mes['S-E_job'] = [tache, etat]
    res1 = api.get('%s%s/resultat/' % (C, cid), **H)
    r_same = _post(api, '%s%s/layout/' % (C, cid), {'roof_layout': copy.deepcopy(l5['roof_layout'])},
                   l5['empreinte_document'])
    res2 = api.get('%s%s/resultat/' % (C, cid), **H)
    j1, j2 = _j(res1) or {}, _j(res2) or {}

    def fraicheur(j):
        return {k: j.get(k) for k in ('perime', 'est_perime', 'statut', 'fraicheur', 'a_jour', 'empreinte_simulation')
                if k in j}
    # Simulation réellement faite = la série horaire et le résultat moteur existent (export-csv et
    # note de calcul servis), jamais la seule présence de clés (toujours servies, à null).
    simule = api.get('%s%s/export-csv/' % (C, cid), **H).status_code == 200
    mes['S-E_resultat_simulation'] = str(j1.get('simulation'))[:200]
    mes['S-E'] = {'simuler': [rs.status_code, str(_j(rs))[:160]], 'resultat': res1.status_code,
                  'cles_resultat': sorted(j1)[:25], 'simulation_presente': simule,
                  'fraicheur_avant': fraicheur(j1), 'fraicheur_apres_enregistrer_sans_geste': fraicheur(j2),
                  'renvoi': r_same.status_code}
    ok['S-E_simuler_accepte'] = rs.status_code in (200, 201, 202) and res1.status_code == 200
    if simule:
        ok['S-E_enregistrer_sans_geste_ne_perime_pas'] = r_same.status_code == 200 and j1 == j2

    # ---------------- S-H : export-csv horaire, note de calcul ----------------
    csv = api.get('%s%s/export-csv/' % (C, cid), **H)
    note = api.get('%s%s/note-calcul.pdf/' % (C, cid), **H)
    mes['S-H'] = {'export_csv': [csv.status_code, csv.get('Content-Type'), str(_j(csv))[:200] if csv.status_code != 200 else ''],
                  'note_calcul': [note.status_code, note.get('Content-Type'), str(_j(note))[:200] if note.status_code != 200 else '']}
    if simule:
        ok['S-H_export_csv'] = csv.status_code == 200 and 'csv' in (csv.get('Content-Type') or '')
        ok['S-H_note_calcul_200'] = note.status_code == 200
    return {'repro': all(ok.values()), 'ko': sorted(k for k, v in ok.items() if not v),
            'ok': sorted(k for k, v in ok.items() if v), 'mesures': mes}
