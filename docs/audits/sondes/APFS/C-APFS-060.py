# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 — sessions support (NTADM22) : (a) un superutilisateur RATTACHÉ à la société A (usage ERP) demande, CONSENT
LUI-MÊME et démarre une session sur un utilisateur de B, sans qu'aucun Administrateur de B ne décide
(`_ActionConsentementView._charger` laisse passer `is_superuser`) ; (b) un agent support NON superutilisateur ouvre une
session (consentie par l'Administrateur de B) sur un compte `is_superuser` de B : le jeton émis
(`AccessToken.for_user(cible)`) porte les pouvoirs plateforme (registre de TOUTES les sociétés).
Témoin : un Administrateur de A (non superuser) qui tente de consentir à la demande visant B → 404.
Vraies routes adminops, comptes rôles système bâtis comme `init_roles`, jeton JWT réel (cookie / Bearer)."""
SONDE = {"constat": "C-APFS-060", "sha": "c9e72d5b20",
         "attendu": "repro si (a) consentir par le superuser de A = 200 avec consentement_par hors de B et demarrer = 200 "
                    "(jeton exploitable dans B) ; (b) demande sur cible superuser = 201 et le jeton émis liste > 1 société",
         "modeles": ["adminops.SessionImpersonation", "authentication.Company", "authentication.CustomUser", "roles.Role"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.adminops.models import SessionImpersonation
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 060 A', slug='sonde-apfs-060-a')
    coB = Company.objects.create(nom='Sonde APFS 060 B', slug='sonde-apfs-060-b')

    def compte(co, nom, suffixe, **extra):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        return U.objects.create_user(username='apfs060-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms), **extra)

    def client(u):
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    def j(r):
        try:
            return r.json()
        except Exception:  # noqa
            return str(getattr(r, 'content', b''))[:160]

    admA = compte(coA, 'Administrateur', 'adm-a')
    admB = compte(coB, 'Administrateur', 'adm-b')
    cibleB = compte(coB, 'Commercial', 'com-b')
    supA = U.objects.create_user(username='apfs060-sup-a', password='x', company=coA,
                                 is_superuser=True, is_staff=True)
    obs = {}

    # (a) superuser de A : demander → consentir lui-même → démarrer
    cs = client(supA)
    r1 = cs.post('/api/django/adminops/impersonation/', {'motif': 'sonde K20a', 'utilisateur_cible': cibleB.id},
                 format='json', **H)
    pk = (j(r1) or {}).get('id') if isinstance(j(r1), dict) else None
    # témoin : Administrateur de A sur la demande visant B
    rt = client(admA).post(f'/api/django/adminops/impersonation/{pk}/consentir/', {}, format='json', **H)
    r2 = cs.post(f'/api/django/adminops/impersonation/{pk}/consentir/', {}, format='json', **H)
    r3 = cs.post(f'/api/django/adminops/impersonation/{pk}/demarrer/', {}, format='json', **H)
    d = SessionImpersonation.objects.filter(pk=pk).first()
    jeton = (j(r3) or {}).get('access') if isinstance(j(r3), dict) else None
    me = None
    if jeton:
        cj = APIClient()
        rm = cj.get('/api/django/auth/me/', HTTP_AUTHORIZATION='Bearer ' + jeton, **H)
        mej = j(rm)
        me = {'http': rm.status_code,
              'username': mej.get('username') if isinstance(mej, dict) else None,
              'company': (mej.get('company') if isinstance(mej, dict) else None)}
    obs['a'] = {'demander_http': r1.status_code, 'temoin_admA_consentir_http': rt.status_code,
                'consentir_par_superuser_A_http': r2.status_code, 'demarrer_http': r3.status_code,
                'demande_company': getattr(d, 'company_id', None), 'coB': coB.id, 'coA': coA.id,
                'consentement_par': getattr(getattr(d, 'consentement_par', None), 'username', None),
                'consentement_par_company': getattr(getattr(d, 'consentement_par', None), 'company_id', None),
                'admins_B_ayant_decide': 0 if (d is None or d.consentement_par_id != admB.id) else 1,
                'jeton_emis': bool(jeton), 'me_avec_jeton': me}

    # (b) support NON superuser → cible superuser de B, consentie par l'Administrateur de B
    supp = U.objects.create_user(username='apfs060-support', password='x', is_taqinor_support=True)
    roleB_adm = Role.objects.get(company=coB, nom='Administrateur')
    superB = U.objects.create_user(username='apfs060-super-b', password='x', company=coB, role=roleB_adm,
                                   role_legacy='admin', is_superuser=True, is_staff=True)
    cp = client(supp)
    b1 = cp.post('/api/django/adminops/impersonation/', {'motif': 'sonde K20b', 'utilisateur_cible': superB.id},
                 format='json', **H)
    pkb = (j(b1) or {}).get('id') if isinstance(j(b1), dict) else None
    b2 = client(admB).post(f'/api/django/adminops/impersonation/{pkb}/consentir/', {}, format='json', **H)
    b3 = cp.post(f'/api/django/adminops/impersonation/{pkb}/demarrer/', {}, format='json', **H)
    jb = (j(b3) or {}).get('access') if isinstance(j(b3), dict) else None
    soc = None
    patchA = None
    if jb:
        cj = APIClient()
        rl = cj.get('/api/django/companies/', HTTP_AUTHORIZATION='Bearer ' + jb, **H)
        lj = j(rl)
        rows = lj.get('results', lj) if isinstance(lj, dict) else lj
        ids = [x.get('id') for x in rows] if isinstance(rows, list) else []
        soc = {'http': rl.status_code, 'nb_societes': len(ids), 'contient_A': coA.id in ids}
        rp = cj.patch(f'/api/django/companies/{coA.id}/', {'tours_actifs': False}, format='json',
                      HTTP_AUTHORIZATION='Bearer ' + jb, **H)
        patchA = rp.status_code
    obs['b'] = {'support_is_superuser': supp.is_superuser, 'demander_cible_superuser_http': b1.status_code,
                'detail_demande': None if b1.status_code < 400 else j(b1),
                'consentir_admB_http': b2.status_code, 'demarrer_http': b3.status_code,
                'jeton_emis': bool(jb), 'companies_avec_jeton': soc, 'patch_company_A_avec_jeton_http': patchA}
    print(obs)
    a, b = obs['a'], obs['b']
    repro_a = (a['temoin_admA_consentir_http'] == 404 and a['consentir_par_superuser_A_http'] == 200
               and a['demarrer_http'] == 200 and a['consentement_par_company'] != coB.id)
    repro_b = (b['demander_cible_superuser_http'] == 201 and b['jeton_emis']
               and bool(soc) and soc['contient_A'])
    obs['repro_a'] = repro_a
    obs['repro_b'] = repro_b
    obs['repro'] = bool(repro_a or repro_b)
    return obs
