# flake8: noqa  (sonde de contre-visite vérifie ASEC du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASEC2/ASEC3 : la garde de rang `authentication/role_tiers.py::peut_gerer` ne refuse que `rang(cible) > rang(acteur)` ;
entre deux comptes du MÊME palier « responsable » elle laisse tout passer, sans comparer leurs codes. Un Technicien
responsable (porte `users_gerer`, PAS `ventes_voir` / `encaisser` / `crm_*`) réinitialise le mot de passe d'un Commercial
responsable par `POST /users/<id>/reinitialiser-mot-de-passe/`, se connecte avec par `/api/django/token/` et lit les
factures, qu'il ne lit pas sous son propre compte. Vraies routes, vraie connexion. Transaction annulée."""
SONDE = {"constat": "C-ASEC-VER4-001", "sha": "8fb8ba32b",
         "attendu": "reinit (Technicien resp -> Commercial resp) 200 ; token avec le nouveau mot de passe 200 ; GET facturation/factures/ : 403 sous le propre compte, 200 sous le compte repris ; attendu sain : 403 rang_cible (codes de la cible hors de ceux de l'acteur)",
         "modeles": ["authentication.Company", "authentication.CustomUser", "roles.Role", "authentication.UserSession"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_RESP_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS
    User = get_user_model()
    co = Company.objects.create(nom='Sonde ASEC VER4-001', slug='sonde-asec-ver4-001')
    r_cr = Role.objects.create(company=co, nom='Commercial responsable', permissions=list(COMMERCIAL_RESP_PERMISSIONS),
                               est_systeme=True)
    r_tr = Role.objects.create(company=co, nom='Technicien responsable', permissions=list(TECHNICIEN_RESP_PERMISSIONS),
                               est_systeme=True)
    cr = User.objects.create_user(username='sonde-asec-v4-001-cr', password='Ancien-Cr-9!xq', company=co, role=r_cr,
                                  email='cr-v4001@example.invalid')
    tr = User.objects.create_user(username='sonde-asec-v4-001-tr', password='Ancien-Tr-9!xq', company=co, role=r_tr,
                                  email='tr-v4001@example.invalid')
    codes_gagnes = sorted(set(COMMERCIAL_RESP_PERMISSIONS) - set(TECHNICIEN_RESP_PERMISSIONS))
    H = {'HTTP_HOST': 'localhost'}
    api = APIClient()
    api.force_authenticate(tr)
    propre = api.get('/api/django/facturation/factures/', **H).status_code
    nouveau = 'Qz7#wLp2!vR9-mK4@tH6'
    r = api.post(f'/api/django/users/{cr.id}/reinitialiser-mot-de-passe/', {'password': nouveau}, format='json', **H)
    reinit = (r.status_code, getattr(r, 'data', None) if r.status_code >= 400 else None)
    cr.refresh_from_db()
    hash_change = cr.check_password(nouveau)
    pris = APIClient()
    t = pris.post('/api/django/token/', {'username': cr.username, 'password': nouveau}, format='json',
                  REMOTE_ADDR='10.9.9.41', **H)
    token = (t.status_code, getattr(t, 'data', None) if t.status_code >= 400 else None)
    repris = pris.get('/api/django/facturation/factures/', **H).status_code if t.status_code == 200 else None
    obs = {'factures_propre_compte': propre, 'reinit': reinit, 'hash_change': hash_change, 'token': token,
           'factures_compte_repris': repris, 'must_change_password': cr.must_change_password,
           'nb_codes_gagnes': len(codes_gagnes),
           'codes_gagnes_extrait': [c for c in codes_gagnes if c in ('encaisser', 'ventes_voir', 'ventes_valider',
                                                                     'crm_voir', 'crm_export', 'client_pii_voir')]}
    print(obs)
    repro = reinit[0] == 200 and hash_change and token[0] == 200 and repris == 200 and propre == 403
    return {'repro': repro, **obs}
