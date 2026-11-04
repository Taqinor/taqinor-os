# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""Jumeau ÉCRITURE de C-ACHT-VER4-031 : `reporting/calendar.py::calendar_reschedule`
(`POST /api/django/reporting/calendar/reschedule/`, garde `PeutReplanifierCalendrier` = palier
responsable + un code `reporting` de LECTURE, D-ASEC11) résout sa cible par
`Intervention.objects.filter(**co).get(pk)` / `Installation.objects.filter(**co).get(pk)` —
société seule, sans `scoper_interventions` / `scoper_chantiers`. Un Technicien de portée équipe
(sans superviseur ⇒ soi seul) qui reçoit 404 en GET sur l'intervention d'un autre technicien et
sur un chantier hors portée peut pourtant en DÉPLACER la date par l'Agenda. Témoin : sa propre
intervention (i1). Bonus : un Commercial (portée soi) sur la même cible hors portée."""
SONDE = {"constat": "C-ACHT-VER4-032", "sha": "fcbed3760",
         "modeles": ["installations.Intervention", "installations.Installation",
                     "roles.Role", "authentication.Company", "authentication.User"],
         "attendu": "GET fiche i1=200, i2=404, chantier C2=404 (portée des listes) ; POST reschedule "
                    "i1 → 200 date écrite (témoin) ; i2 → 200 date écrite ; pose C2 → 200 date écrite "
                    "(écriture hors portée) ; sain : 404 et date inchangée pour i2 / C2"}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (
        CANONICAL_SYSTEM_ROLES, COMMERCIAL_PERMISSIONS, TECHNICIEN_PERMISSIONS)

    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACHT VER4-032', slug='sonde-acht-ver4-032')
    rt = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS))
    rc = Role.objects.create(company=co, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS))
    ra = Role.objects.create(company=co, nom='Administrateur',
                             permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
    t1 = U.objects.create_user(username='sonde-v4-032-t1', password='x', company=co, role=rt)
    t2 = U.objects.create_user(username='sonde-v4-032-t2', password='x', company=co, role=rt)
    com = U.objects.create_user(username='sonde-v4-032-com', password='x', company=co, role=rc)
    adm = U.objects.create_user(username='sonde-v4-032-adm', password='x', company=co, role=ra)
    j0 = datetime.date.today() + datetime.timedelta(days=3)
    c1 = Installation.objects.create(company=co, reference='CH-SONDE-V4-032-1', technicien_responsable=t1,
                                     created_by=adm, date_pose_prevue=j0)
    c2 = Installation.objects.create(company=co, reference='CH-SONDE-V4-032-2', technicien_responsable=t2,
                                     created_by=adm, date_pose_prevue=j0)
    i1 = Intervention.objects.create(company=co, installation=c1, type_intervention='pose', technicien=t1,
                                     created_by=adm, date_prevue=j0)
    i2 = Intervention.objects.create(company=co, installation=c2, type_intervention='pose', technicien=t2,
                                     created_by=adm, date_prevue=j0)

    def client(u):
        a = APIClient()
        a.force_authenticate(u)
        return a

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    R = '/api/django/reporting/calendar/reschedule/'
    api = client(t1)
    lecture = {
        'GET_i1': api.get(f'{B}/interventions/{i1.id}/', **H).status_code,
        'GET_i2': api.get(f'{B}/interventions/{i2.id}/', **H).status_code,
        'GET_c2': api.get(f'{B}/chantiers/{c2.id}/', **H).status_code,
    }

    def bouge(a, type_key, obj_id, jours):
        d = j0 + datetime.timedelta(days=jours)
        r = a.post(R, {'type': type_key, 'id': obj_id, 'date': str(d)}, format='json', **H)
        return r.status_code, str(d), (r.data if r.status_code >= 400 else None)

    ecr = {
        'tech_i1_temoin': bouge(api, 'intervention', i1.id, 2),
        'tech_i2_hors_portee': bouge(api, 'intervention', i2.id, 4),
        'tech_pose_c2_hors_portee': bouge(api, 'pose', c2.id, 5),
    }
    i1.refresh_from_db(); i2.refresh_from_db(); c2.refresh_from_db()
    lu_tech = {'i1': str(i1.date_prevue), 'i2': str(i2.date_prevue), 'c2_pose': str(c2.date_pose_prevue)}

    apc = client(com)
    lecture['com_GET_i2'] = apc.get(f'{B}/interventions/{i2.id}/', **H).status_code
    ecr['com_i2_hors_portee'] = bouge(apc, 'intervention', i2.id, 6)
    i2.refresh_from_db()
    lu_com = {'i2': str(i2.date_prevue)}

    print(f"j0={j0} lecture={lecture} ecritures={ecr} relu_apres_tech={lu_tech} relu_apres_com={lu_com}")
    repro = (lecture['GET_i2'] == 404 and lecture['GET_c2'] == 404
             and ecr['tech_i2_hors_portee'][0] == 200 and lu_tech['i2'] == ecr['tech_i2_hors_portee'][1]
             and ecr['tech_pose_c2_hors_portee'][0] == 200
             and lu_tech['c2_pose'] == ecr['tech_pose_c2_hors_portee'][1])
    return {'repro': bool(repro), 'lecture': lecture, 'ecritures': ecr,
            'relu_tech': lu_tech, 'relu_com': lu_com}
