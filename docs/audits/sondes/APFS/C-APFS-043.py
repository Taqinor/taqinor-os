# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K08 — demandes d'approbation : le CRUD générique du `ModelViewSet` (`IsAnyRole`) reste servi à côté des gestes
nommés. Le Commercial soumet une demande (type à champ requis `taux`), le Directeur l'approuve (vraies routes) :
  témoin ASEC30 : `PATCH {payload}` d'une demande approuvée → refusé (400/409) ;
  défaut 1 : `DELETE approval-requests/<id>/` par le demandeur d'une demande APPROUVÉE → 204, demande ET décisions
  effacées (cascade) ;
  défaut 2 : `PATCH {payload: {}}` d'une demande EN ATTENTE → 200 sans `validate_payload` (champ requis vidé) —
  ce que `resoumettre` refuse."""
SONDE = {"constat": "C-APFS-043", "sha": "57d3fd371d",
         "attendu": "repro si PATCH payload après approbation = 400/409 (témoin) ET DELETE après approbation = 204 "
                    "avec ligne et décisions disparues ; PATCH {} en attente = 200 champ requis vide",
         "modeles": ["automation.ApprovalRequest", "automation.ApprovalDecision", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.automation.models import ApprovalRequestType, ApprovalRequest, ApprovalDecision
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde APFS 043', slug='sonde-apfs-043')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s043-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(u)))
        return u, c

    _, cd = compte('Directeur')
    com, cc = compte('Commercial')
    typ = ApprovalRequestType.objects.create(company=co, nom='Remise exceptionnelle', palier_approbateur='admin',
                                             champs_requis=['taux'])
    base = '/api/django/automation/approval-requests/'
    obs = {}
    s = cc.post(base, {'request_type': typ.id, 'payload': {'taux': 5}}, format='json', **H)
    obs['soumettre_http'] = s.status_code
    rid = s.data['id']
    ap = cd.post(f'{base}{rid}/approve/', {'note': 'ok 5 %'}, format='json', **H)
    obs['approuver_http'] = ap.status_code
    obs['statut_apres_approbation'] = ApprovalRequest.objects.get(pk=rid).status
    p = cc.patch(f'{base}{rid}/', {'payload': {'taux': 25}}, format='json', **H)
    obs['temoin_patch_apres_decision_http'] = p.status_code
    obs['payload_apres_patch'] = ApprovalRequest.objects.get(pk=rid).payload
    nb_dec = ApprovalDecision.objects.filter(request_id=rid).count()
    d = cc.delete(f'{base}{rid}/', **H)
    obs['delete_apres_decision_http'] = d.status_code
    obs['ligne_existe'] = ApprovalRequest.objects.filter(pk=rid).exists()
    obs['decisions_avant_apres'] = [nb_dec, ApprovalDecision.objects.filter(request_id=rid).count()]
    # demande en attente : PATCH contournant validate_payload ; témoin resoumettre
    s2 = cc.post(base, {'request_type': typ.id, 'payload': {'taux': 5}}, format='json', **H)
    r2 = s2.data['id']
    p2 = cc.patch(f'{base}{r2}/', {'payload': {}}, format='json', **H)
    obs['patch_en_attente_http'] = p2.status_code
    obs['payload_en_attente'] = ApprovalRequest.objects.get(pk=r2).payload
    obs['erreurs_validate_payload'] = typ.validate_payload(ApprovalRequest.objects.get(pk=r2).payload)
    print(obs)
    temoin_ok = obs['approuver_http'] == 200 and obs['statut_apres_approbation'] == 'approved' and \
        obs['temoin_patch_apres_decision_http'] in (400, 409) and obs['payload_apres_patch'] == {'taux': 5}
    defaut = obs['delete_apres_decision_http'] == 204 and not obs['ligne_existe']
    obs['temoin_ok'] = temoin_ok
    obs['defaut_patch_en_attente'] = obs['patch_en_attente_http'] == 200 and bool(obs['erreurs_validate_payload'])
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
