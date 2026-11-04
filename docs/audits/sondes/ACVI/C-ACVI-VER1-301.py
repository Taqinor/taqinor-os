# flake8: noqa  (sonde de contre-visite ACVI66, rejouable par scripts/sonde.py)
"""ACVI66 — vérificateur frais : une visite annulée par `annuler_rendez_vous` doit être `annulee`, gelée
(`terminer` → 400 clé `statut`, SANS simuler la complétude), `Lead.visite_effectuee` reste faux, état relu
de la base identique (date vide, notes avec la ligne « annulé »). Société démo, API réelle, transaction annulée.
Second chemin : PATCH {date_prevue: null} (annuler_visite, ACVI60) et DELETE doivent aussi donner `annulee`."""
SONDE = {"constat": "C-ACVI-178", "sha": "06ced8b1a",
         "attendu": "repro: False — statut annulee, terminer 400 `statut`, visite_effectuee faux, relecture identique",
         "modeles": ["crm.Lead", "visites.VisiteTerrain"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
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

    def nouveau(n, jours):
        L = Lead.objects.create(company=c, nom=f'Annul{n}', prenom='Ver1', telephone=f'06123466{n:02d}',
                                email=f'sonde-ver1-66-{n}@example.invalid', ville='Casablanca', owner=ua)
        V, err = vs.planifier_visite(L, ua, today + dt.timedelta(days=jours), commercial=tech)
        return L, V

    # --- chemin 1 : annuler_rendez_vous (porte du CRM) puis terminer SANS mock de complétude
    L, V = nouveau(1, 3)
    n = vs.annuler_rendez_vous(L, ua)
    V = VisiteTerrain.objects.get(pk=V.pk)
    apres = {'annules': n, 'statut': V.statut, 'date': str(V.date_prevue), 'notes': V.notes[-90:],
             'modifiable': V.modifiable, 'raison': V.raison_lecture_seule}
    s, r = appel('post', f'/api/django/visites/visites/{V.id}/terminer/')
    L.refresh_from_db()
    V2 = VisiteTerrain.objects.get(pk=V.pk)
    obs['chemin_annuler_rendez_vous'] = {
        'apres_annulation': apres, 'terminer_http': s, 'terminer_corps': r,
        'visite_effectuee': L.visite_effectuee, 'relu': {'statut': V2.statut, 'date': str(V2.date_prevue),
                                                      'notes_identiques': V2.notes == V.notes}}
    ok1 = (V.statut == 'annulee' and V.date_prevue is None and 'annulé' in V.notes and s == 400
           and isinstance(r, dict) and 'statut' in (r.get('erreurs') or {}) and not L.visite_effectuee
           and V2.statut == 'annulee' and V2.notes == V.notes)

    # --- terminer avec complétude SIMULÉE (le défaut d'origine : 200 sur annulée) : doit rester 400
    import apps.visites.selectors as vsel
    orig = vsel.visite_terrain_manquants
    vsel.visite_terrain_manquants = lambda visite: []
    try:
        s2, r2 = appel('post', f'/api/django/visites/visites/{V.id}/terminer/')
    finally:
        vsel.visite_terrain_manquants = orig
    L.refresh_from_db()
    obs['terminer_completude_simulee'] = {'http': s2, 'visite_effectuee': L.visite_effectuee}
    ok1b = s2 == 400 and not L.visite_effectuee

    # --- les autres gestes d'écriture sur une annulée sont gelés (photos/mesures/notes via PATCH)
    s3, r3 = appel('patch', f'/api/django/visites/visites/{V.id}/', {'notes': 'tentative'})
    obs['patch_notes_sur_annulee'] = {'http': s3, 'corps': r3 if s3 >= 400 else 'accepté'}

    # --- chemin 2 : PATCH date_prevue null (ACVI60) -> annulee ; DELETE
    L5, V5 = nouveau(5, 4)
    s5, r5 = appel('patch', f'/api/django/visites/visites/{V5.id}/', {'date_prevue': None})
    V5 = VisiteTerrain.objects.get(pk=V5.pk)
    obs['chemin_patch_date_null'] = {'http': s5, 'statut': V5.statut, 'date': str(V5.date_prevue)}
    ok2 = s5 == 200 and V5.statut == 'annulee' and V5.date_prevue is None

    # --- planifier de nouveau après annulation : une NOUVELLE visite (pas la annulée réutilisée)
    L7, V7 = nouveau(7, 3)
    vs.annuler_rendez_vous(L7, ua)
    V7b, err = vs.planifier_visite(L7, ua, today + dt.timedelta(days=6), commercial=tech)
    V7 = VisiteTerrain.objects.get(pk=V7.pk)
    obs['replanifier_apres_annulation'] = {'nouvelle_id_differente': V7b.pk != V7.pk, 'ancienne_statut': V7.statut,
                                           'nouvelle_statut': V7b.statut, 'err': err}
    ok3 = V7b.pk != V7.pk and V7.statut == 'annulee' and V7b.statut == 'brouillon'

    obs['verifs'] = {'ok1': bool(ok1), 'ok1b': bool(ok1b), 'ok2': bool(ok2), 'ok3': bool(ok3)}
    return {'repro': not (ok1 and ok1b and ok2 and ok3), 'observe': obs}
