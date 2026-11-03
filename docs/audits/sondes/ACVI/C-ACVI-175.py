# flake8: noqa  (constat C-ACVI-175 : copie rejouable de la sonde groupée C-ACVI-169, sa clé dans `observe`)
"""E-10 / E-11 / E-16 / E-15 / E-14 (C-ACVI-169, 170, 175, 174, 173) — aval de la revue, société démo 1, acteur
demo_admin, lead au responsable demo_resp, visite assignée à demo_tech, transaction annulée. Complétude simulée
(`selectors.visite_terrain_manquants` → []) pour passer terminer/valider par l'API réelle.
E-10 : C&I validée (puissance constatée 36 kVA recopiée) → renvoyer → colonnes et visite_effectuee restent ;
re-terminer → 2e note « terminée », 2e notification au responsable, débrief re-posé si le 1er est clos.
E-11 : correction humaine (PATCH lead 30 kVA) puis re-valider → la mesure écrase (36).
E-16 : lead avec V1 terminée + V2 planifiée → absent de chaine_commerciale.visites_a_venir (témoin présent).
E-15 : V1 validée + nouvelle visite brouillon → visite_feu_vert None, releve_pour_calepinage garde V1.
E-14 : POST /visites/visites/ sans date sur un lead NEW → note signée + first_contacted_at posé (témoin avec date)."""
SONDE = {"constat": "C-ACVI-169+170+175+174+173", "sha": "352ae5455",
         "attendu": "défauts : colonnes gardées au renvoi + doubles notes/notifs ; correction humaine écrasée ; "
                    "visite à venir masquée ; feu vert perdu ; premier contact posé par une note de visite",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain",
                     "notifications.Notification"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_selectors import chaine_commerciale
    from apps.notifications.models import Notification
    from apps.visites import selectors as vsel
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    resp = U.objects.get(username='demo_resp')
    tech = U.objects.get(username='demo_tech')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    today = timezone.localdate()
    obs = {}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth in ('get', 'delete'):
                    r = getattr(api, meth)(url, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace') if r.content else ''
            try:
                return r.status_code, json.loads(txt) if txt else {}
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    def ouvertes(L):
        return list(RelanceEtape.objects.filter(lead=L, statut='a_faire').values_list('id', 'libelle'))

    orig = vsel.visite_terrain_manquants
    vsel.visite_terrain_manquants = lambda visite: []
    try:
        # ---------- E-10 / E-11 ----------
        L = Lead.objects.create(company=c, nom='CI', prenom='SondeE10', telephone='0612349369',
                                email='sonde-acvi-169@example.invalid', ville='Tanger', owner=resp,
                                type_installation='commercial')
        V, err = vs.planifier_visite(L, ua, today + dt.timedelta(days=1), commercial=tech)
        s_m, r_m = appel('patch', f'/api/django/visites/visites/{V.id}/mesures/',
                         {'categorie': 'comptage', 'valeurs': {'puissance_souscrite_kva_constatee': 36}})
        s_t1, _ = appel('post', f'/api/django/visites/visites/{V.id}/terminer/')
        notes_t1 = LeadActivity.objects.filter(lead=L, body__icontains='terminée').count()
        notif_t1 = Notification.objects.filter(recipient=resp).count()
        ouv_t1 = ouvertes(L)
        s_v1, _ = appel('post', f'/api/django/visites/visites/{V.id}/valider/')
        L.refresh_from_db()
        apres_v1 = {'kva': str(L.compteur_puissance_kva), 'source': L.puissance_souscrite_source,
                    'visite_effectuee': L.visite_effectuee}
        # 1er débrief / suite clos par le commercial
        RelanceEtape.objects.filter(lead=L, statut='a_faire').update(statut='fait', traite_le=timezone.now(), traite_par=ua)
        s_r, r_r = appel('post', f'/api/django/visites/visites/{V.id}/renvoyer/', {'motif': 'Refaire le comptage', 'photos': [], 'mesures': []})
        L.refresh_from_db()
        V.refresh_from_db()
        apres_renvoi = {'http': s_r, 'statut': V.statut, 'kva': str(L.compteur_puissance_kva),
                        'source': L.puissance_souscrite_source, 'visite_effectuee': L.visite_effectuee}
        s_p, r_p = appel('patch', f'/api/django/crm/leads/{L.id}/', {'compteur_puissance_kva': '30'})
        L.refresh_from_db()
        apres_humain = {'http': s_p, 'kva': str(L.compteur_puissance_kva), 'source': L.puissance_souscrite_source,
                        'err': r_p if s_p >= 400 else ''}
        n_notif0 = Notification.objects.filter(recipient=resp).count()
        s_t2, _ = appel('post', f'/api/django/visites/visites/{V.id}/terminer/')
        notes_t2 = LeadActivity.objects.filter(lead=L, body__icontains='terminée').count()
        notif_t2 = Notification.objects.filter(recipient=resp).count()
        ouv_t2 = ouvertes(L)
        s_v2, _ = appel('post', f'/api/django/visites/visites/{V.id}/valider/')
        L.refresh_from_db()
        obs['E10_E11'] = {
            'mesure': s_m, 'terminer1': s_t1, 'notes_terminee_apres_t1': notes_t1, 'ouvertes_apres_t1': ouv_t1,
            'valider1': s_v1, 'apres_valider1': apres_v1, 'renvoyer': apres_renvoi, 'patch_humain': apres_humain,
            'terminer2': s_t2, 'notes_terminee_apres_t2': notes_t2,
            'notifs_resp_t1_t2': [notif_t1, n_notif0, notif_t2],
            'notifs_resp_types_recents': list(Notification.objects.filter(recipient=resp).order_by('-id').values_list('event_type', flat=True)[:4]),
            'ouvertes_apres_t2': ouv_t2, 'valider2': s_v2,
            'apres_valider2': {'kva': str(L.compteur_puissance_kva), 'source': L.puissance_souscrite_source}}
        e10 = (apres_renvoi['kva'] == apres_v1['kva'] and apres_renvoi['visite_effectuee'] is True
               and notes_t2 > notes_t1 and len(ouv_t2) >= 1)
        e11 = apres_humain['kva'].startswith('30') and str(L.compteur_puissance_kva).startswith('36')

        # ---------- E-16 ----------
        L16 = Lead.objects.create(company=c, nom='AVenir', prenom='SondeE16', telephone='0612349375',
                                  email='sonde-acvi-175@example.invalid', ville='Rabat', owner=ua)
        V16a, _ = vs.planifier_visite(L16, ua, today, commercial=tech)
        appel('post', f'/api/django/visites/visites/{V16a.id}/terminer/')
        V16b, _ = vs.planifier_visite(L16, ua, today + dt.timedelta(days=4), commercial=tech)
        L16.refresh_from_db()
        T16 = Lead.objects.create(company=c, nom='AVenirTemoin', prenom='SondeE16', telephone='0612349376',
                                  email='sonde-acvi-175t@example.invalid', ville='Rabat', owner=ua)
        vs.planifier_visite(T16, ua, today + dt.timedelta(days=4), commercial=tech)
        T16.refresh_from_db()
        cc = chaine_commerciale(ua, c, limite=500)
        va = json.dumps(cc.get('visites_a_venir'), default=str)
        obs['E16'] = {'L16': {'visite_effectuee': L16.visite_effectuee, 'visite_prevue_le': str(L16.visite_prevue_le),
                              'V2_statut': VisiteTerrain.objects.get(pk=V16b.pk).statut},
                      'L16_dans_visites_a_venir': f'"id": {L16.id},' in va or f'"lead_id": {L16.id}' in va or f'"id": {L16.id}}}' in va,
                      'temoin_dans_visites_a_venir': f'"id": {T16.id},' in va or f'"lead_id": {T16.id}' in va or f'"id": {T16.id}}}' in va,
                      'cles_visites_a_venir': sorted((cc.get('visites_a_venir') or {}).keys()) if isinstance(cc.get('visites_a_venir'), dict) else type(cc.get('visites_a_venir')).__name__}
        e16 = obs['E16']['temoin_dans_visites_a_venir'] and not obs['E16']['L16_dans_visites_a_venir']

        # ---------- E-15 ----------
        L15 = Lead.objects.create(company=c, nom='FeuVert', prenom='SondeE15', telephone='0612349374',
                                  email='sonde-acvi-174@example.invalid', ville='Fès', owner=ua)
        V15, _ = vs.planifier_visite(L15, ua, today, commercial=tech)
        appel('post', f'/api/django/visites/visites/{V15.id}/terminer/')
        s_v15, _ = appel('post', f'/api/django/visites/visites/{V15.id}/valider/')
        fv_avant = vsel.visite_feu_vert(c.id, L15.id)
        s_a, _ = appel('post', '/api/django/visites/visites/', {'lead': L15.id})
        s_b, _ = appel('post', '/api/django/visites/visites/', {'lead': L15.id})
        fv_apres = vsel.visite_feu_vert(c.id, L15.id)
        try:
            rel = vsel.releve_pour_calepinage(L15)
            rel_id = rel.get('visite_id') if isinstance(rel, dict) else rel
        except Exception as e:
            rel_id = 'exc ' + repr(e)[:80]
        obs['E15'] = {'valider': s_v15, 'feu_vert_avant': (fv_avant or {}).get('visite_id'), 'posts_sans_date': [s_a, s_b],
                      'nb_visites': VisiteTerrain.objects.filter(lead=L15).count(),
                      'statuts': list(VisiteTerrain.objects.filter(lead=L15).order_by('id').values_list('statut', flat=True)),
                      'feu_vert_apres': fv_apres, 'releve_calepinage_visite_id': rel_id, 'V1': V15.id}
        e15 = fv_avant and fv_apres is None and rel_id == V15.id and obs['E15']['nb_visites'] == 3
    finally:
        vsel.visite_terrain_manquants = orig

    # ---------- E-14 ----------
    L14 = Lead.objects.create(company=c, nom='PremierContact', prenom='SondeE14', telephone='0612349373',
                              email='sonde-acvi-173@example.invalid', ville='Agadir', owner=ua)
    T14 = Lead.objects.create(company=c, nom='PremierContactTemoin', prenom='SondeE14', telephone='0612349377',
                              email='sonde-acvi-173t@example.invalid', ville='Agadir', owner=ua)
    s1, _ = appel('post', '/api/django/visites/visites/', {'lead': L14.id})
    s2, _ = appel('post', '/api/django/visites/visites/', {'lead': T14.id, 'date_prevue': (today + dt.timedelta(days=2)).isoformat()})
    L14.refresh_from_db()
    T14.refresh_from_db()
    obs['E14'] = {'sans_date': {'http': s1, 'stage': L14.stage, 'first_contacted_at_pose': L14.first_contacted_at is not None,
                                'notes': list(LeadActivity.objects.filter(lead=L14).values_list('user_id', 'kind', 'body'))[:3]},
                  'temoin_avec_date': {'http': s2, 'first_contacted_at_pose': T14.first_contacted_at is not None,
                                       'notes': [(u, k, b[:70]) for u, k, b in LeadActivity.objects.filter(lead=T14).values_list('user_id', 'kind', 'body')][:3]}}
    e14 = L14.first_contacted_at is not None and T14.first_contacted_at is None
    obs['repro_par_constat'] = {'E10': bool(e10), 'E11': bool(e11), 'E16': bool(e16), 'E15': bool(e15), 'E14': bool(e14)}
    return {'repro': bool(e10 and e11 and e16 and e15 and e14), 'observe': obs}
