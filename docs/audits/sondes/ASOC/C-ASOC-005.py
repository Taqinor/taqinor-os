# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 — demande d'approbation ad hoc (XKB2/ZCTR8), écran /approbations.
(R1) l'approbateur clique « Demander un complément » : vraie route
`POST automation/approval-requests/<id>/demande-info/` -> notifications du demandeur (attendu >= 1).
(R2) type SÉQUENTIEL min_approbations=2 : rang 1 approuve par `POST …/approve/` -> notifications aux autres
approbateurs du palier (attendu >= 1) et au demandeur. (T) `notify(demandeur, 'approval_decided')` crée bien
une ligne (le canal fonctionne) ; `'approval_info_requested' in EventType.values`."""
SONDE = {"constat": "C-ASOC-005", "sha": "c514bd8ba",
         "attendu": "repro si R1 : 200, statut info_requested, 0 notification au demandeur ; R2 : 200, pending, "
                    "0 notification à l'approbateur 2 ; T : 1 ligne",
         "modeles": ["notifications.Notification", "automation.ApprovalRequest", "automation.ApprovalDecision"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.test import TestCase, override_settings
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.automation.models import ApprovalRequest, ApprovalRequestType
    from apps.notifications.models import Notification
    from apps.notifications.services import notify
    from apps.notifications.types_evenements import EventType
    U = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    c = Company.objects.create(nom='Sonde ASOC 005', slug='sonde-asoc-005')
    dem = U.objects.create_user(username='sonde-asoc-005-dem', password='x', role_legacy='normal', company=c)
    ap1 = U.objects.create_user(username='sonde-asoc-005-ap1', password='x', role_legacy='admin', company=c)
    ap2 = U.objects.create_user(username='sonde-asoc-005-ap2', password='x', role_legacy='admin', company=c)
    api = APIClient()
    obs = {'type_catalogue': 'approval_info_requested' in EventType.values}

    def compte(u):
        return Notification.objects.filter(company=c, recipient=u).count()

    with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
        with TestCase.captureOnCommitCallbacks(execute=True):
            # R1 — complément demandé
            t1 = ApprovalRequestType.objects.create(company=c, nom='Achat outillage')
            api.force_authenticate(dem)
            rc = api.post('/api/django/automation/approval-requests/', {'request_type': t1.pk, 'payload': {}},
                          format='json', **H)
            obs['R1_creation'] = rc.status_code
            req1 = ApprovalRequest.objects.filter(company=c, request_type=t1).first()
            avant = {u.username: compte(u) for u in (dem, ap1, ap2)}
            obs['R1_apres_soumission'] = avant
            api.force_authenticate(ap1)
            r = api.post(f'/api/django/automation/approval-requests/{req1.pk}/demande-info/',
                         {'motif': 'joindre le devis fournisseur'}, format='json', **H)
            req1.refresh_from_db()
            obs['R1'] = {'http': r.status_code, 'statut': req1.status,
                         'notif_demandeur': compte(dem) - avant['sonde-asoc-005-dem']}
            # R2 — séquentiel, rang 1 approuve
            t2 = ApprovalRequestType.objects.create(
                company=c, nom='Achat séquentiel', min_approbations=2,
                sequence_approbateurs=ApprovalRequestType.SequenceApprobateurs.SEQUENTIEL)
            api.force_authenticate(dem)
            api.post('/api/django/automation/approval-requests/', {'request_type': t2.pk, 'payload': {}},
                     format='json', **H)
            req2 = ApprovalRequest.objects.filter(company=c, request_type=t2).first()
            avant = {u.username: compte(u) for u in (dem, ap1, ap2)}
            api.force_authenticate(ap1)
            r = api.post(f'/api/django/automation/approval-requests/{req2.pk}/approve/', {}, format='json', **H)
            req2.refresh_from_db()
            obs['R2'] = {'http': r.status_code, 'statut': req2.status,
                         'notif_ap2': compte(ap2) - avant['sonde-asoc-005-ap2'],
                         'notif_demandeur': compte(dem) - avant['sonde-asoc-005-dem']}
            # T — le canal fonctionne pour un type catalogué
            n = notify(dem, 'approval_decided', 'Témoin', company=c)
            obs['T'] = {'ligne': n is not None}
    print(obs)
    defaut = (obs['type_catalogue'] is False and obs['R1']['http'] == 200 and obs['R1']['statut'] == 'info_requested'
              and obs['R1']['notif_demandeur'] == 0 and obs['R2']['http'] == 200 and obs['R2']['statut'] == 'pending'
              and obs['R2']['notif_ap2'] == 0)
    obs['repro'] = bool(defaut and obs['T']['ligne'])
    return obs
