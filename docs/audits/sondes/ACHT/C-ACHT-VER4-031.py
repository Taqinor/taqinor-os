# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT50 : `interventions/calendrier/` et `chantiers/gantt/` partent de `get_queryset()`
(portée Feature F) : un Technicien n'y voit que sa portée. Jumeau non borné : l'Agenda
(`reporting/calendar.py::calendar_events`, `GET /api/django/reporting/calendar/`, IsAnyRole)
lit `Intervention.objects.filter(**co)` et `Installation.objects.filter(**co)` sans
`scoper_interventions` / `scoper_chantiers` : le technicien t1 y voit l'intervention de t2 et
la pose d'un chantier hors portée (référence, technicien, lien). Témoin : le calendrier
d'installations du même t1 = {i1}."""
SONDE = {"constat": "C-ACHT-VER4-031", "sha": "fcbed3760",
         "modeles": ["installations.Intervention", "installations.Installation",
                     "roles.Role", "authentication.Company", "authentication.User"],
         "attendu": "témoin installations/calendrier t1 = {i1} ; agenda reporting t1 contient i1 ET i2 "
                    "et la pose du chantier hors portée"}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS

    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACHT VER4-031', slug='sonde-acht-ver4-031')
    rt = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS))
    ra = Role.objects.create(company=co, nom='Administrateur',
                             permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
    t1 = U.objects.create_user(username='sonde-v4-031-t1', password='x', company=co, role=rt)
    t2 = U.objects.create_user(username='sonde-v4-031-t2', password='x', company=co, role=rt)
    adm = U.objects.create_user(username='sonde-v4-031-adm', password='x', company=co, role=ra)
    jour = datetime.date.today() + datetime.timedelta(days=2)
    ch = Installation.objects.create(company=co, reference='CH-SONDE-V4-031', technicien_responsable=adm,
                                     created_by=adm, date_pose_prevue=jour)
    i1 = Intervention.objects.create(company=co, installation=ch, type_intervention='pose', technicien=t1,
                                     date_prevue=jour)
    i2 = Intervention.objects.create(company=co, installation=ch, type_intervention='pose', technicien=t2,
                                     date_prevue=jour)
    api = APIClient()
    api.force_authenticate(t1)
    f, t = str(jour - datetime.timedelta(days=1)), str(jour + datetime.timedelta(days=1))
    r_t = api.get('/api/django/installations/interventions/calendrier/', {'date_from': f, 'date_to': t},
                  HTTP_HOST='localhost')
    temoin = sorted(iv['id'] for g in (r_t.json() if r_t.status_code == 200 else [])
                    for iv in g['interventions'])
    r = api.get('/api/django/reporting/calendar/', {'from': f, 'to': t, 'types': 'intervention,pose'},
                HTTP_HOST='localhost')
    evs = r.json() if r.status_code == 200 else {}
    evs = evs.get('events', evs) if isinstance(evs, dict) else evs
    vus = sorted((e.get('type'), e.get('obj_id')) for e in (evs or []))
    print(f"témoin installations/calendrier http={r_t.status_code} ids={temoin} (i1={i1.id}, i2={i2.id}) ; "
          f"agenda reporting http={r.status_code} {vus} (chantier={ch.id})")
    repro = (temoin == [i1.id] and r.status_code == 200
             and ('intervention', i2.id) in vus and ('pose', ch.id) in vus)
    return {'repro': bool(repro), 'temoin': temoin, 'agenda': vus, 'http_agenda': r.status_code}
