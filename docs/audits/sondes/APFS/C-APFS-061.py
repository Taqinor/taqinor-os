# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 — deux doctrines « superuser » : `core/mixins.py::company_qs` borne un superuser RATTACHÉ à une société à
celle-ci (usage ERP), mais `authentication/views.py::CompanyViewSet` (+ `EstSaPropreSocieteOuOperateurPlateforme`)
le traite en opérateur plateforme : liste de TOUTES les sociétés, PATCH de la société B. Témoins : un `is_staff`
non superuser de A → 403 sur B ; le même superuser de A ne voit que A sur une vue `TenantMixin` (leads de B absents).
Complément service : `apps/ged/selectors.py::acl_effective` (superuser de A sur un dossier GED de B)."""
SONDE = {"constat": "C-APFS-061", "sha": "c9e72d5b20",
         "attendu": "repro si superuser de A : PATCH companies/<B>/ = 200 (B modifiée) et liste > 1 société, alors que "
                    "le staff de A reçoit 403 et que les leads du superuser de A ne montrent pas ceux de B",
         "modeles": ["authentication.Company", "authentication.CustomUser", "crm.Lead", "roles.Role"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.crm.models import Lead
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 061 A', slug='sonde-apfs-061-a')
    coB = Company.objects.create(nom='Sonde APFS 061 B', slug='sonde-apfs-061-b')
    perms = list(R['Administrateur'])
    roleA = Role.objects.create(company=coA, nom='Administrateur', permissions=perms, est_systeme=True)

    def client(u):
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    def j(r):
        try:
            return r.json()
        except Exception:  # noqa
            return None

    supA = U.objects.create_user(username='apfs061-sup-a', password='x', company=coA, role=roleA,
                                 role_legacy='admin', is_superuser=True, is_staff=True)
    staffA = U.objects.create_user(username='apfs061-staff-a', password='x', company=coA, role=roleA,
                                   role_legacy=tier_for_role_fields('Administrateur', True, perms), is_staff=True)
    Lead.objects.create(company=coA, nom='Lead A 061')
    lb = Lead.objects.create(company=coB, nom='Lead B 061')
    cs, ct = client(supA), client(staffA)
    rl = cs.get('/api/django/companies/', **H)
    lj = j(rl)
    rows = lj.get('results', lj) if isinstance(lj, dict) else (lj or [])
    ids = [x.get('id') for x in rows] if isinstance(rows, list) else []
    rp = cs.patch(f'/api/django/companies/{coB.id}/', {'nom': 'B renommée par le superuser de A'}, format='json', **H)
    rpa = cs.patch(f'/api/django/companies/{coB.id}/', {'actif': False}, format='json', **H)
    coB.refresh_from_db()
    rt = ct.patch(f'/api/django/companies/{coB.id}/', {'nom': 'tentative staff'}, format='json', **H)
    rlead = cs.get('/api/django/crm/leads/?page_size=200', **H)
    lr = j(rlead)
    lrows = lr.get('results', lr) if isinstance(lr, dict) else (lr or [])
    lead_ids = [x.get('id') for x in lrows] if isinstance(lrows, list) else []
    ged = None
    try:
        from apps.ged.models import Folder
        from apps.ged.selectors import acl_effective
        fb = Folder.objects.create(company=coB, nom='Dossier B 061')
        ged = {'acl_superuser_A_sur_dossier_B': acl_effective(fb, supA),
               'acl_staff_A_sur_dossier_B': acl_effective(fb, staffA)}
    except Exception as exc:  # noqa
        ged = f'non joué : {exc!r}'[:160]
    obs = {'liste_http': rl.status_code, 'nb_societes_listees': len(ids), 'liste_contient_B': coB.id in ids,
           'patch_nom_B_http': rp.status_code, 'patch_actif_B_http': rpa.status_code,
           'B_nom_apres': coB.nom, 'B_actif_apres': coB.actif, 'B_statut_apres': coB.statut,
           'temoin_staff_A_patch_B_http': rt.status_code,
           'leads_superuser_A_http': rlead.status_code, 'voit_lead_B': lb.id in lead_ids, 'nb_leads': len(lead_ids),
           'ged': ged}
    print(obs)
    obs['repro'] = bool(rp.status_code == 200 and coB.nom.startswith('B renommée') and rt.status_code == 403
                        and not obs['voit_lead_B'] and obs['liste_contient_B'])
    return obs
