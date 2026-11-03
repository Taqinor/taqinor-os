# flake8: noqa  (sonde de vérification PA1 lane E, rejouable par scripts/sonde.py)
"""E-2 / E-3 / E-6 / E-7 (C-ACVI-161, 162, 165, 166) — visite technique, société démo 1, demo_admin, transaction
annulée. La complétude (photos) est neutralisée en simulant `selectors.visite_terrain_manquants` → [] pour
passer « terminer » par l'API RÉELLE (aucun fichier : MinIO hors d'atteinte de la sonde).
E-2 : notes de PLANIFICATION (« Sonner au portail ») → chatter « Retour terrain » au terminer.
E-3 : côté serveur, local_abrite/local_ventile = false (ce que le front poste pour « jamais répondu ») ne sont
plus « manquants ». E-6 : visite TERMINÉE → PATCH mesures / DELETE photo acceptés, PATCH notes refusé (témoin).
E-7 : PATCH mesures longueur_m = 'NaN' / 'Infinity' → 500 ? ; ENTIER 'Infinity' (valeur_mesure)."""
SONDE = {"constat": "C-ACVI-161+162+165+166", "sha": "352ae5455",
         "attendu": "défauts : note Retour terrain = notes de planification ; false compté répondu ; mesures/photos "
                    "modifiables après terminer ; NaN/Infinity → exception (500)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain",
                     "visites.VisiteMedia", "records.Attachment"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.records.models import Attachment
    from apps.visites import selectors as vsel
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain, VisiteMedia
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
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
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    # ---------- E-2 ----------
    L = Lead.objects.create(company=c, nom='Retour', prenom='SondeE2', telephone='0612349261',
                            email='sonde-acvi-161@example.invalid', ville='Casablanca', owner=ua)
    s, r = appel('post', f'/api/django/crm/leads/{L.id}/visites/planifier/',
                 {'date_prevue': (today + dt.timedelta(days=3)).isoformat(), 'notes': 'Sonner au portail'})
    V = VisiteTerrain.objects.filter(lead=L).order_by('-id').first()
    obs['E2_planifier'] = [s, V.notes if V else None]
    orig = vsel.visite_terrain_manquants
    vsel.visite_terrain_manquants = lambda visite: []
    try:
        n0 = LeadActivity.objects.filter(lead=L).count()
        s, _ = appel('post', f'/api/django/visites/visites/{V.id}/terminer/')
        notes_chatter = list(LeadActivity.objects.filter(lead=L).order_by('id').values_list('user_id', 'body')[n0:])
        obs['E2_terminer'] = {'http': s, 'chatter_nouveau': [(u, b[:160]) for u, b in notes_chatter]}
        try:
            rv = vsel.retour_visite(V)
            obs['E2_retour_visite'] = {k: (str(v)[:80]) for k, v in rv.items()} if isinstance(rv, dict) else str(rv)[:120]
        except Exception as e:
            obs['E2_retour_visite'] = repr(e)[:120]
        e2 = any('Sonner au portail' in b and 'etour' in b for _, b in notes_chatter)

        # ---------- E-6 : visite terminée ----------
        V.refresh_from_db()
        ct = ContentType.objects.get(app_label='crm', model='lead')
        att = Attachment.objects.create(company=c, content_type=ct, object_id=L.id, file_key='sonde/acvi-165.jpg',
                                        filename='mur.jpg', size=10, mime='image/jpeg', uploaded_by=ua)
        m = VisiteMedia.objects.create(company=c, visite=V, attachment=att, slot_code='toiture_vue_generale')
        s_mes, r_mes = appel('patch', f'/api/django/visites/visites/{V.id}/mesures/',
                             {'categorie': 'toiture', 'valeurs': {'longueur_m': 12.5}})
        s_notes, _ = appel('patch', f'/api/django/visites/visites/{V.id}/', {'notes': 'correction après terminer'})
        s_del, _ = appel('delete', f'/api/django/visites/visites/{V.id}/photos/{m.id}/')
        V.refresh_from_db()
        obs['E6'] = {'statut': V.statut, 'patch_mesures': s_mes, 'mesure_stockee': (V.mesures or {}).get('toiture', {}).get('longueur_m'),
                     'patch_notes_temoin': s_notes, 'delete_photo': s_del,
                     'media_restant': VisiteMedia.objects.filter(pk=m.pk).exists()}
        e6 = V.statut == 'terminee' and s_mes == 200 and s_del == 200 and s_notes == 400
    finally:
        vsel.visite_terrain_manquants = orig

    # ---------- E-3 : booléen « non répondu » posté false ----------
    L3 = Lead.objects.create(company=c, nom='Bool', prenom='SondeE3', telephone='0612349262',
                             email='sonde-acvi-162@example.invalid', ville='Rabat', owner=ua)
    V3, err = vs.planifier_visite(L3, ua, today + dt.timedelta(days=2))
    quatre = {'largeur_mur_cm': 120, 'hauteur_mur_cm': 200, 'profondeur_degagement_cm': 80, 'distance_tableau_m': 6}
    s_a, r_a = appel('patch', f'/api/django/visites/visites/{V3.id}/mesures/', {'categorie': 'local_onduleur', 'valeurs': quatre})
    man_a = [str(x) for x in vsel.visite_terrain_manquants(VisiteTerrain.objects.get(pk=V3.pk))]
    s_b, r_b = appel('patch', f'/api/django/visites/visites/{V3.id}/mesures/',
                     {'categorie': 'local_onduleur', 'valeurs': dict(quatre, local_abrite=False, local_ventile=False)})
    man_b = [str(x) for x in vsel.visite_terrain_manquants(VisiteTerrain.objects.get(pk=V3.pk))]
    obs['E3'] = {'patch_4_nombres': s_a, 'manquants_local_apres_4': [x[:90] for x in man_a if "'local_abrite'" in x or "'local_ventile'" in x],
                 'patch_avec_false': s_b, 'manquants_local_apres_false': [x[:90] for x in man_b if "'local_abrite'" in x or "'local_ventile'" in x]}
    e3 = bool(obs['E3']['manquants_local_apres_4']) and not obs['E3']['manquants_local_apres_false']

    # ---------- E-7 : NaN / Infinity ----------
    res = {}
    for brut in ('NaN', 'Infinity', '1e400', '-Infinity'):
        s7, r7 = appel('patch', f'/api/django/visites/visites/{V3.id}/mesures/', {'categorie': 'toiture', 'valeurs': {'longueur_m': brut}})
        res[brut] = [s7, (r7.get('_exc') or r7.get('erreurs') or '') if isinstance(r7, dict) else '']
    try:
        ent = vs.valeur_mesure({'nature': 'entier', 'libelle': 'Âge (ans)'}, 'Infinity')
        res['ENTIER_Infinity_valeur_mesure'] = repr(ent)[:120]
    except Exception as e:
        res['ENTIER_Infinity_valeur_mesure'] = 'EXCEPTION ' + repr(e)[:120]
    obs['E7'] = res
    e7 = any(v[0] >= 500 for k, v in res.items() if isinstance(v, list))
    obs['repro_par_constat'] = {'E2': bool(e2), 'E3_serveur': bool(e3), 'E6': bool(e6), 'E7': bool(e7)}
    return {'repro': bool(e2 and e3 and e6 and e7), 'observe': obs}
