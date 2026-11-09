# flake8: noqa  (sonde d'audit vérifie ASEC 04/11, rejouable par scripts/sonde.py — AMET93)
"""Jumeau d'ASEC30 : `apps/automation/serializers.py::ApprovalRequestSerializer.validate` ne fige `payload` /
`request_type` qu'une fois la demande DÉCIDÉE. Une demande EN ATTENTE à double approbation (ZCTR7,
`min_approbations=2`) déjà approuvée une fois reste PATCHable par son demandeur ; le PATCH ne purge pas les
décisions (contrairement à `services.resoumettre`, qui les efface « sinon un ancien approve compterait encore »).
Le 2e approbateur valide alors un contenu que le 1er n'a jamais vu. Chaîne API réelle. Transaction annulée."""
SONDE = {"constat": "C-ASEC-VER4-020", "sha": "8fb8ba32b",
         "attendu": "approve(resp1) 200 → PATCH payload montant 100→100000 par le demandeur 200 → approve(resp2) 200 : demande APPROUVÉE à 100000 avec l'approbation de resp1 donnée sur 100 ; attendu sain : PATCH refusé (ou décisions purgées) dès la 1re décision",
         "modeles": ["authentication.Company", "automation.ApprovalRequest", "automation.ApprovalDecision",
                     "automation.ApprovalRequestType"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.automation.models import ApprovalRequest, ApprovalRequestType
    User = get_user_model()
    co = Company.objects.create(nom='Sonde ASEC-VER4-020', slug='sonde-asec-ver4-020')
    dem = User.objects.create_user(username='sonde-v4020-dem', password='x', role_legacy='normal', company=co)
    r1 = User.objects.create_user(username='sonde-v4020-r1', password='x', role_legacy='responsable', company=co)
    r2 = User.objects.create_user(username='sonde-v4020-r2', password='x', role_legacy='responsable', company=co)
    t = ApprovalRequestType.objects.create(company=co, nom='Achat double contrôle', min_approbations=2)
    req = ApprovalRequest.objects.create(company=co, request_type=t, demandeur=dem, payload={'montant': 100})
    B = '/api/django/automation/approval-requests'
    etapes = {}

    def api(u):
        c = APIClient()
        c.force_authenticate(u)
        return c

    r = api(r1).post(f'{B}/{req.pk}/approve/', {'note': 'ok pour 100'}, format='json', HTTP_HOST='localhost')
    etapes['approve_r1'] = r.status_code
    req.refresh_from_db()
    etapes['statut_apres_r1'] = req.status
    r = api(dem).patch(f'{B}/{req.pk}/', {'payload': {'montant': 100000}}, format='json', HTTP_HOST='localhost')
    etapes['patch_demandeur'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    req.refresh_from_db()
    etapes['decisions_apres_patch'] = req.decisions.count()
    r = api(r2).post(f'{B}/{req.pk}/approve/', {'note': 'ok'}, format='json', HTTP_HOST='localhost')
    etapes['approve_r2'] = r.status_code
    req.refresh_from_db()
    obs = {'statut_final': req.status, 'payload_final': req.payload,
           'decisions': list(req.decisions.values_list('decided_by__username', 'decision'))}
    print(f'etapes={etapes} obs={obs}')
    repro = (req.status == ApprovalRequest.Status.APPROVED and req.payload.get('montant') == 100000
             and etapes['patch_demandeur'][0] == 200)
    return {'repro': repro, 'etapes': etapes, **obs}
