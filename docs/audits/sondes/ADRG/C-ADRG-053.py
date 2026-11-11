# flake8: noqa  (sonde d'audit PF4 « droits de la grille », groupe ADRG — rejouable par scripts/sonde.py, AMET93)
"""C-ADRG-053 — le palier CRM (rôle SYSTÈME « Commercial », sans aucun droit d'administration) re-pointe un compte
du portail client vers un AUTRE client par `PATCH /api/django/portail/comptes-portail/<id>/ {client: B}`
(`apps/portail/views.py::ComptePortailClientViewSet`, `IsResponsableOrAdmin` + `permission_module='crm'` ;
`ComptePortailClientSerializer` : `client` inscriptible, contrôle même société seulement). Le jeton de A reste ;
`public_views.py::portail_mon_releve` (`_resoudre_compte_par_token` → `compte.client`) sert alors le relevé de B
(`ventes.selectors.releve_client_portail` → bloc `client` : id, nom, e-mail, téléphone, adresse de B).
Second cas (observé, hors `repro`) : PATCH `{actif: true}` d'un compte révoqué → `services.reactiver_acces_client`,
geste que le code se décrit « action ADMIN explicite ». Rôle semé exactement comme `init_roles` (get_or_create nom +
permissions du registre vivant + `SYSTEM_ROLE_PERIMETRES`). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADRG-053", "sha": "29787bc59",
         "attendu": "Commercial (sans roles_gerer) : relevé témoin par le jeton de A = client A (200) ; PATCH "
                    "{client: B} 200 ; même jeton → relevé du client B (REPRO). Attendu sain : PATCH 403 (geste "
                    "d'administrateur) et le jeton de A sert toujours A. Second cas : PATCH {actif: true} d'un "
                    "compte révoqué par le Commercial → 200 et accès par jeton rouvert (attendu sain : 403)",
         "modeles": ["authentication.Company", "authentication.CustomUser", "roles.Role", "crm.Client",
                     "portail.ComptePortailClient"]}


def sonde(ctx):
    import secrets
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.portail.models import ComptePortailClient
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES

    co = Company.objects.create(nom='Sonde ADRG 053', slug='sonde-adrg-053')
    U = get_user_model()
    # Rôle système RÉEL « Commercial », semé comme init_roles.Command.handle (get_or_create + périmètre canonique).
    perms = dict(CANONICAL_SYSTEM_ROLES)['Commercial']
    role, _cree = Role.objects.get_or_create(
        company=co, nom='Commercial', defaults={'permissions': list(perms), 'est_systeme': True})
    if role.perimetre != SYSTEM_ROLE_PERIMETRES.get('Commercial'):
        role.perimetre = SYSTEM_ROLE_PERIMETRES.get('Commercial')
        role.save(update_fields=['perimetre'])
    u = U.objects.create_user(username='sonde-adrg-053-com', password='x', company=co, role=role,
                              role_legacy='normal')
    u.refresh_from_db()

    def client(lettre):
        return Client.objects.create(company=co, nom=f'ClientSonde{lettre}', prenom='ADRG053',
                                     email=f'adrg053-{lettre.lower()}@example.invalid')

    ca, cb, cc = client('A'), client('B'), client('C')
    jeton_a = 'adrg053-a-' + secrets.token_urlsafe(16)
    compte_a = ComptePortailClient.objects.create(company=co, client=ca, token_acces=jeton_a, actif=True)

    api = APIClient()
    api.force_authenticate(u)
    H = {'format': 'json', 'HTTP_HOST': 'localhost'}
    pub = APIClient()  # le portail public : AUCUNE authentification, le jeton seul

    def releve(jeton):
        r = pub.get(f'/api/django/public/portail/{jeton}/mon-releve/', HTTP_HOST='localhost')
        data = getattr(r, 'data', None)
        cli = (data or {}).get('client') if isinstance(data, dict) else None
        return r.status_code, (cli or {}).get('id'), (cli or {}).get('nom'), (cli or {}).get('email')

    codes = sorted(role.permissions or [])
    obs = {
        'role': (role.nom, role.est_systeme, role.perimetre),
        'menu_tier': u.menu_tier, 'is_admin_role': u.is_admin_role,
        'role_porte_un_droit_admin': sorted(set(codes) & {'roles_gerer', 'users_gerer', 'users_voir',
                                                         'modules_gerer', 'parametres_modifier'}),
        'codes_crm_du_role': [c for c in codes if c.startswith('crm_')],
        'ids': {'A': ca.id, 'B': cb.id, 'C': cc.id, 'compte_A': compte_a.id},
    }

    # (1) Témoin : le jeton de A sert le relevé de A.
    obs['etape1_releve_avant'] = releve(jeton_a)
    # (2) Le Commercial re-pointe le compte de A vers B.
    r2 = api.patch(f'/api/django/portail/comptes-portail/{compte_a.id}/', {'client': cb.id}, **H)
    obs['etape2_patch_client'] = (r2.status_code, getattr(r2, 'data', None) if r2.status_code >= 400 else None)
    compte_a.refresh_from_db()
    obs['etape2_compte_relu'] = {'client_id': compte_a.client_id, 'meme_jeton': compte_a.token_acces == jeton_a,
                                 'actif': compte_a.actif}
    # (3) Le MÊME jeton, sans login.
    obs['etape3_releve_apres'] = releve(jeton_a)
    s1, id1 = obs['etape1_releve_avant'][0], obs['etape1_releve_avant'][1]
    s3, id3, nom3 = obs['etape3_releve_apres'][0], obs['etape3_releve_apres'][1], obs['etape3_releve_apres'][2]
    obs['client_servi_avant_apres'] = (id1, id3)
    repro = bool(s1 == 200 and id1 == ca.id
                 and r2.status_code in (200, 202) and compte_a.client_id == cb.id
                 and s3 == 200 and id3 == cb.id and nom3 and 'ClientSondeB' in nom3)

    # ── Second cas (observé seulement) : réouverture d'un accès révoqué par le Commercial ──
    jeton_c = 'adrg053-c-' + secrets.token_urlsafe(16)
    compte_c = ComptePortailClient.objects.create(company=co, client=cc, token_acces=jeton_c, actif=False)
    obs['cas2_releve_revoque'] = releve(jeton_c)
    r5 = api.patch(f'/api/django/portail/comptes-portail/{compte_c.id}/', {'actif': True}, **H)
    compte_c.refresh_from_db()
    obs['cas2_patch_actif'] = (r5.status_code, getattr(r5, 'data', None) if r5.status_code >= 400 else None)
    obs['cas2_actif_relu'] = compte_c.actif
    obs['cas2_releve_apres'] = releve(jeton_c)
    obs['cas2_acces_rouvert'] = bool(obs['cas2_releve_revoque'][0] == 404 and r5.status_code == 200
                                     and compte_c.actif and obs['cas2_releve_apres'][0] == 200)

    print(f'obs={obs}')
    return {'repro': repro, **obs}
