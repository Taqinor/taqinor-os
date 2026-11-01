# flake8: noqa  (sonde de contre-visite vérifie ASEC, rejouable par scripts/sonde.py — AMET93)
"""ASEC2 : la garde de rang (`role_plus_large`) ne vit qu'à l'ATTRIBUTION d'un rôle (`/users/`). Un Commercial
responsable (porte `users_gerer`, pas `paie_gerer` / `parametres_modifier` / `compta_valider`) crée un rôle étroit,
l'attribue à un Commercial, puis l'ÉLARGIT par `PATCH /roles/<id>/` (`apps/roles/views.py::RoleViewSet.perform_update`
ne refuse que les codes élevés et son PROPRE rôle) et réinitialise le mot de passe du compte : il opère un compte qui
porte des droits plus larges que les siens. Vraies routes, transaction annulée."""
SONDE = {"constat": "C-ASEC-VER-002", "sha": "ba577e26a",
         "attendu": "PATCH /roles/R/ ajoutant des codes que l'acteur n'a pas, sur un rôle porté par un compte qu'il gère : accepté (200), puis réinitialisation du mot de passe de ce compte 200"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS
    User = get_user_model()
    co = Company.objects.create(nom='Sonde ASEC VER-002', slug='sonde-asec-ver-002')
    r_cresp = Role.objects.create(company=co, nom='Commercial responsable', permissions=list(COMMERCIAL_RESP_PERMISSIONS),
                                  est_systeme=True)
    r_com = Role.objects.create(company=co, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
    cresp = User.objects.create_user(username='sonde-asec-ver002-cresp', password='Sonde-Ver002-a!x', company=co,
                                     role=r_cresp)
    com = User.objects.create_user(username='sonde-asec-ver002-com', password='Sonde-Ver002-b!x', company=co, role=r_com)
    api = APIClient()
    api.force_authenticate(cresp)
    base = [c for c in COMMERCIAL_RESP_PERMISSIONS if c.startswith('crm_')][:1]
    extra = [c for c in ('paie_gerer', 'parametres_modifier', 'compta_valider') if c not in COMMERCIAL_RESP_PERMISSIONS]
    r1 = api.post('/api/django/roles/', {'nom': 'Sonde etroit', 'permissions': base}, format='json', HTTP_HOST='localhost')
    rid = (r1.data or {}).get('id') if hasattr(r1, 'data') else None
    r2 = api.patch(f'/api/django/users/{com.id}/', {'role': rid}, format='json', HTTP_HOST='localhost')
    r3 = api.patch(f'/api/django/roles/{rid}/', {'permissions': base + extra}, format='json', HTTP_HOST='localhost')
    r4 = api.post(f'/api/django/users/{com.id}/reinitialiser-mot-de-passe/', {'password': 'Qz7#wLp2!vR9-mK4@tH6'},
                  format='json', HTTP_HOST='localhost')
    com.refresh_from_db()
    porte = sorted(set(com.role.permissions or []) - set(COMMERCIAL_RESP_PERMISSIONS)) if com.role_id else []
    print(f'create={r1.status_code} assign={r2.status_code} elargir={r3.status_code} '
          f'{getattr(r3, "data", "") if r3.status_code >= 400 else ""} reinit={r4.status_code} {getattr(r4, "data", "") if r4.status_code >= 400 else ""} codes_hors_acteur={porte}')
    return {'repro': r3.status_code == 200 and r4.status_code == 200 and bool(porte),
            'create': r1.status_code, 'assign': r2.status_code, 'elargir': r3.status_code,
            'reinit': r4.status_code, 'codes_hors_acteur': porte}
