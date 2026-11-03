# flake8: noqa  (seconde lentille L2 de C-ACVI-101, rejouable par scripts/sonde.py)
"""C-ACVI-101 L2 — autres chemins que les sondes 101/160 (rôle Commercial terrain, société démo 1,
transaction annulée). (a) PATCH `commercial` sur la visite brouillon du collègue T2 par T1 (porte d'édition) ;
(b) POST /visites/visites/ {lead, date_prevue} SANS `commercial` : la visite de T2 est-elle déplacée, et T1
reçoit-il un panneau client d'une visite qu'il ne peut pas relire ? (c) POST SANS date (date_requise=False)
sur un lead sans visite : panneau client servi sans rendez-vous ; (d) POST avec `commercial: T2` : T1 pose un
rendez-vous dans l'agenda d'un collègue sur un lead qu'il ne lit pas."""
SONDE = {"constat": "C-ACVI-101-L2", "sha": "352ae5455",
         "attendu": "(a) 404 attendu (queryset borné) ; (b)(c)(d) défaut si 201 + client_panel avec téléphone, "
                    "visite de T2 déplacée",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_TERRAIN_PERMISSIONS
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    role = Role.objects.create(company=c, nom='Commercial terrain sonde 101L2',
                               permissions=list(COMMERCIAL_TERRAIN_PERMISSIONS))
    t1 = U.objects.create_user(username='sonde-acvi-101l2-t1', password='x', company=c, role=role)
    t2 = U.objects.create_user(username='sonde-acvi-101l2-t2', password='x', company=c, role=role)
    A1, A2 = APIClient(), APIClient()
    A1.force_authenticate(t1)
    A2.force_authenticate(t2)

    def appel(cl, meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = cl.get(url, HTTP_HOST='localhost')
                else:
                    r = getattr(cl, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def panel(r):
        cp = r.get('client_panel') if isinstance(r, dict) else None
        return {'telephone': bool(isinstance(cp, dict) and cp.get('telephone')),
                'adresse': bool(isinstance(cp, dict) and cp.get('adresse')),
                'devis': len(r.get('devis') or []) if isinstance(r, dict) else None,
                'id': r.get('id') if isinstance(r, dict) else None}

    today = timezone.localdate()
    mk = lambda n: Lead.objects.create(company=c, nom='Sonde101L2', prenom=n, telephone='06123401%02d' % len(n),
                                       adresse='7 rue %s' % n, ville='Rabat', owner=ua)
    L, L2, L3 = mk('un'), mk('deux'), mk('trois')
    V = VisiteTerrain.objects.create(company=c, lead=L, commercial=t2, statut='brouillon',
                                     date_prevue=today + dt.timedelta(days=5), mesures={}, qualification={})
    obs = {'temoin_T1_GET_lead': appel(A1, 'get', f'/api/django/crm/leads/{L.id}/')[0],
           'temoin_T1_GET_visite_T2': appel(A1, 'get', f'/api/django/visites/visites/{V.id}/')[0]}
    # (a) PATCH commercial sur la visite du collègue
    s, r = appel(A1, 'patch', f'/api/django/visites/visites/{V.id}/', {'commercial': t1.id})
    V.refresh_from_db()
    obs['a_PATCH_commercial_visite_T2'] = {'http': s, 'commercial_apres': V.commercial.username}
    # (b) POST sans commercial sur le lead de la visite de T2
    s, r = appel(A1, 'post', '/api/django/visites/visites/',
                 {'lead': L.id, 'date_prevue': (today + dt.timedelta(days=11)).isoformat()})
    V.refresh_from_db()
    obs['b_POST_sans_commercial'] = {'http': s, 'panel': panel(r),
                                     'visite_T2_apres': {'date': str(V.date_prevue), 'commercial': V.commercial.username},
                                     'meme_visite': panel(r)['id'] == V.id,
                                     'T1_relit_la_visite': appel(A1, 'get', f'/api/django/visites/visites/{V.id}/')[0]}
    # (c) POST sans date sur un lead sans visite
    s, r = appel(A1, 'post', '/api/django/visites/visites/', {'lead': L2.id})
    obs['c_POST_sans_date'] = {'http': s, 'panel': panel(r)}
    # (d) POST qui assigne la visite à T2
    s, r = appel(A1, 'post', '/api/django/visites/visites/',
                 {'lead': L3.id, 'date_prevue': (today + dt.timedelta(days=4)).isoformat(), 'commercial': t2.id})
    v3 = VisiteTerrain.objects.filter(lead=L3).first()
    obs['d_POST_assigne_T2'] = {'http': s, 'panel': panel(r),
                                'visite_commercial': v3.commercial.username if v3 and v3.commercial else None}
    obs['defauts'] = {
        'a_patch_hors_queryset': obs['a_PATCH_commercial_visite_T2']['http'] not in (403, 404),
        'b_deplace_visite_collegue_et_panel': obs['b_POST_sans_commercial']['http'] == 201
        and obs['b_POST_sans_commercial']['panel']['telephone'] and V.date_prevue == today + dt.timedelta(days=11),
        'c_panel_sans_rdv': obs['c_POST_sans_date']['http'] == 201 and obs['c_POST_sans_date']['panel']['telephone'],
        'd_rdv_pose_chez_collegue': obs['d_POST_assigne_T2']['http'] == 201 and obs['d_POST_assigne_T2']['visite_commercial'] == t2.username,
    }
    repro = obs['temoin_T1_GET_lead'] in (403, 404) and (obs['defauts']['b_deplace_visite_collegue_et_panel']
                                                         or obs['defauts']['c_panel_sans_rdv'])
    return {'repro': bool(repro), 'observe': obs}
