# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K26 — multi-société (XPLT19) : après `POST auth/switch-company/` vers B, `CookieJWTAuthentication` remplace
`user.company` par B mais garde `user.role` = le rôle de la société d'ATTACHE A. Un compte Administrateur de A,
membre de B sans AUCUN rôle attribué dans B, y agit en Administrateur (liste et gestion des comptes de B,
écritures), et l'Administrateur de B ne le voit pas dans sa liste `users/` (filtre sur la société d'attache).
Témoin : un Commercial de A membre de B reste Commercial dans B (users/ → 403). Jeton JWT réel, switch réel."""
SONDE = {"constat": "C-APFS-064", "sha": "c9e72d5b20",
         "attendu": "repro si, après switch vers B, l'Administrateur de A liste les comptes de B (200) et crée un lead "
                    "de B, alors que l'Administrateur de B ne le voit pas dans users/",
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
    coA = Company.objects.create(nom='Sonde APFS 064 A', slug='sonde-apfs-064-a')
    coB = Company.objects.create(nom='Sonde APFS 064 B', slug='sonde-apfs-064-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        return U.objects.create_user(username='apfs064-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms))

    def client(u):
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    def j(r):
        try:
            return r.json()
        except Exception:  # noqa
            return None

    def ids_users(r):
        d = j(r)
        rows = d.get('results', d) if isinstance(d, dict) else (d or [])
        return [x.get('id') for x in rows] if isinstance(rows, list) else []

    admA = compte(coA, 'Administrateur', 'adm-a')
    comA = compte(coA, 'Commercial', 'com-a')
    admB = compte(coB, 'Administrateur', 'adm-b')
    comB = compte(coB, 'Commercial', 'com-b')
    admA.societes_autorisees.add(coA, coB)
    comA.societes_autorisees.add(coA, coB)

    def basculer(u):
        c = client(u)
        r = c.post('/api/django/auth/switch-company/', {'company_id': coB.id}, format='json', **H)
        acc = r.cookies.get('access_token')
        if acc is not None:
            c.cookies['access_token'] = acc.value
        return c, r.status_code

    ca, sa = basculer(admA)
    ru = ca.get('/api/django/users/?page_size=200', **H)
    vus = ids_users(ru)
    rl = ca.post('/api/django/crm/leads/', {'nom': 'Lead créé dans B par admin de A 064'}, format='json', **H)
    lead_id = (j(rl) or {}).get('id') if isinstance(j(rl), dict) else None
    lead = Lead.objects.filter(pk=lead_id).first()
    rB = client(admB).get('/api/django/users/?page_size=200', **H)
    vus_par_B = ids_users(rB)
    cc, sc = basculer(comA)
    rcu = cc.get('/api/django/users/?page_size=200', **H)
    obs = {'admA_role_company': admA.role.company_id, 'coA': coA.id, 'coB': coB.id,
           'admA_role_dans_B': Role.objects.filter(company=coB, pk=admA.role_id).exists(),
           'switch_admA_http': sa, 'users_dans_B_par_admA_http': ru.status_code,
           'admA_voit_comptes_B': comB.id in vus and admB.id in vus,
           'lead_cree_par_admA_http': rl.status_code, 'lead_company': getattr(lead, 'company_id', None),
           'users_par_admB_http': rB.status_code, 'admB_voit_admA': admA.id in vus_par_B,
           'temoin_switch_comA_http': sc, 'temoin_users_par_comA_dans_B_http': rcu.status_code}
    print(obs)
    obs['repro'] = bool(sa == 200 and ru.status_code == 200 and obs['admA_voit_comptes_B']
                        and not obs['admA_role_dans_B'] and not obs['admB_voit_admA'])
    return obs
