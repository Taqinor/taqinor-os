# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K45 : « mot de passe à changer » n'est appliqué côté serveur QUE par les gardes portail (AUD139
`roles.permissions.exiger_mot_de_passe_change`). Deux comptes INTERNES (rôle système Commercial, CANONICAL_SYSTEM_ROLES) :
(E) mot de passe EXPIRÉ (FG22 : `password_expiry_days`=30, `password_changed_at` il y a 60 j) → la vraie connexion
/api/django/token/ arme `must_change_password` ; (R) mot de passe RÉINITIALISÉ par un Directeur via la vraie route
`users/<id>/reinitialiser-mot-de-passe/` (ASEC3) → drapeau posé, mot de passe connu du gérant. Puis l'API interne
(GET crm/leads/, POST crm/leads/) sans changer le mot de passe. Témoin : /auth/me/ annonce bien le drapeau."""
SONDE = {"constat": "C-APFS-002", "sha": "c9e72d5b2",
         "attendu": "repro si E et R : login 200, must_change_password=True (lu par /auth/me/), puis GET crm/leads/ = 200 "
                    "et POST crm/leads/ = 201 sans changement de mot de passe (attendu : 403 code mot_de_passe_a_changer)",
         "modeles": ["authentication.CustomUser", "crm.Lead", "parametres.CompanyProfile"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from authentication.throttles import LoginRateThrottle
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde APFS002', slug='sonde-apfs002')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    prof.password_expiry_days = 30
    prof.save()

    def compte(nom_role, username, mdp):
        perms = list(R[nom_role])
        role, _ = Role.objects.get_or_create(company=co, nom=nom_role,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username=username, password=mdp, company=co, role=role,
                                  email=f'{username}@sonde.invalid',
                                  role_legacy=tier_for_role_fields(nom_role, True, perms))
        return u

    MDP = 'Sonde-APFS002-Ok!7'
    directeur = compte('Directeur', 'sonde_apfs002_dir', MDP)
    e = compte('Commercial', 'sonde_apfs002_exp', MDP)
    U.objects.filter(pk=e.pk).update(password_changed_at=timezone.now() - timezone.timedelta(days=60),
                                     must_change_password=False)
    r_ = compte('Commercial', 'sonde_apfs002_rei', MDP)
    apid = APIClient()
    apid.force_authenticate(directeur)
    NOUVEAU = 'Reinit-APFS002-Zq!4'
    rr = apid.post(f'/api/django/users/{r_.id}/reinitialiser-mot-de-passe/', {'password': NOUVEAU}, format='json', **H)
    out = {'reinit_par_directeur': {'http': rr.status_code, 'detail': None if rr.status_code < 400 else str(rr.content[:200])}}

    def parcours(username, mdp, tag):
        api = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            lg = api.post('/api/django/token/', {'username': username, 'password': mdp}, format='json', **H)
        me = api.get('/api/django/auth/me/', **H)
        flag_me = (me.json() or {}).get('must_change_password') if me.status_code == 200 else None
        g = api.get('/api/django/crm/leads/', **H)
        p = api.post('/api/django/crm/leads/', {'nom': f'Lead {tag} APFS002', 'telephone': '0611223344'}, format='json', **H)
        flag = U.objects.get(username=username).must_change_password
        return {'login': lg.status_code, 'me': me.status_code, 'me_must_change_password': flag_me,
                'flag_en_base': flag, 'GET_crm_leads': g.status_code,
                'POST_crm_leads': p.status_code,
                'POST_detail': None if p.status_code < 400 else str(p.content[:160])}

    out['E_expire'] = parcours(e.username, MDP, 'E')
    out['R_reinit'] = parcours(r_.username, NOUVEAU, 'R') if rr.status_code == 200 else 'reinit refusée'

    def defaut(x):
        return (isinstance(x, dict) and x['login'] == 200 and x['flag_en_base'] is True and x['me_must_change_password'] is True
                and x['GET_crm_leads'] == 200)
    out['E_defaut'] = defaut(out['E_expire'])
    out['R_defaut'] = defaut(out['R_reinit'])
    out['repro'] = bool(out['E_defaut'] and out['R_defaut'])
    print(out)
    return out
