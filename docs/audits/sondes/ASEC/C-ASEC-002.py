SONDE = {"constat": "C-ASEC-002", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : PATCH et PUT génériques /users/<id>/ portant password -> 400 "
                    "password_via_reinitialisation (Directeur tiers), Commercial sur lui-même 400/403, mot de passe "
                    "relu inchangé ; POST /users/ sans password -> 400 "
                    "sur password (pas 500), rien créé ; légitime : Directeur -> reinitialiser-mot-de-passe d'un "
                    "Commercial : 'a' -> 400 inchangé, conforme -> 200, sessions de la cible révoquées (/auth/me 401), "
                    "must_change_password vrai, une ligne SettingsAuditLog sans la valeur ; Commercial sur le "
                    "Directeur -> 403"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.parametres.models import SettingsAuditLog
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from authentication.models import Company, UserSession
    from authentication.session_policy import SESSION_CLAIM
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    URL = '/api/django/users/{}/reinitialiser-mot-de-passe/'
    ANCIEN, NOUVEAU = 'Ancien-mdp-123!', 'Nouveau-mdp-456!'

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde ASEC002 {tag}', slug=f'sonde-asec002-{tag}')
        roles = {nom: Role.objects.create(company=co, nom=nom, permissions=list(p), est_systeme=True)
                 for nom, p in (('Directeur', reg.DIRECTEUR_PERMISSIONS), ('Commercial', reg.COMMERCIAL_PERMISSIONS))}
        return co, roles

    def user(co, nom, role):
        return User.objects.create_user(username=f'sonde-asec002-{nom}', password=ANCIEN,
                                        email=f'{nom}@sonde.invalid', company=co, role=role)

    def code(r):
        return r.data.get('code') if isinstance(getattr(r, 'data', None), dict) else None

    def mdp_ok(u, mdp=ANCIEN):
        return User.objects.get(pk=u.pk).check_password(mdp)

    a, ra = societe('a')
    b, rb = societe('b')
    directeur = user(a, 'dir', ra['Directeur'])
    cible = user(a, 'com', ra['Commercial'])
    tiers = user(a, 'com2', ra['Commercial'])
    dir_b = user(b, 'dirb', rb['Directeur'])
    out, gestes = {}, []

    # 1) Mot de passe via PATCH/PUT générique : refusé, rien écrit (Directeur sur Commercial, et Commercial sur soi)
    patch_ok = True
    for acteur, victime in ((directeur, cible), (tiers, tiers)):
        api = APIClient()
        api.force_authenticate(acteur)
        for methode in ('patch', 'put'):
            corps = {'password': NOUVEAU}
            if methode == 'put':
                corps['username'] = victime.username
            r = getattr(api, methode)(f'/api/django/users/{victime.id}/', corps, format='json', **H)
            inchange = mdp_ok(victime)
            gestes.append([acteur.username[14:], victime.username[14:], methode, r.status_code, code(r), inchange])
            if acteur is directeur:  # tiers AYANT le droit users_gerer : la garde password doit répondre
                patch_ok &= r.status_code == 400 and code(r) == 'password_via_reinitialisation' and inchange
            else:  # Commercial sans users_gerer : refusé plus tôt (403 droit) ou 400 password, jamais écrit
                patch_ok &= r.status_code in (400, 403) and inchange
    out['patch_put_password'] = gestes

    # 2) Création sans mot de passe : 400 sur password, jamais 500, rien créé
    api_dir = APIClient()
    api_dir.force_authenticate(directeur)
    r = api_dir.post('/api/django/users/', {'username': 'sonde-asec002-sansmdp'}, format='json', **H)
    cree = User.objects.filter(username='sonde-asec002-sansmdp').exists()
    champs = sorted(r.data) if isinstance(getattr(r, 'data', None), dict) else str(r.content[:200])
    out['creation_sans_mdp'] = [r.status_code, champs, cree]
    creation_ok = r.status_code == 400 and isinstance(r.data, dict) and 'password' in r.data and not cree

    # 3) Rang inférieur : Commercial réinitialise le Directeur -> 403, Directeur inchangé
    api_t = APIClient()
    api_t.force_authenticate(tiers)
    r = api_t.post(URL.format(directeur.id), {'password': NOUVEAU}, format='json', **H)
    out['commercial_sur_directeur'] = [r.status_code, mdp_ok(directeur)]
    rang_ok = r.status_code == 403 and mdp_ok(directeur)
    # Directeur de A sur un compte de B -> 403/404, inchangé
    r = api_dir.post(URL.format(dir_b.id), {'password': NOUVEAU}, format='json', **H)
    out['directeur_a_sur_b'] = [r.status_code, mdp_ok(dir_b)]
    autre_ok = r.status_code in (403, 404) and mdp_ok(dir_b)

    # 4) Parcours légitime : session active de la cible, politique, révocation, rotation, journal
    refresh = RefreshToken.for_user(cible)
    UserSession.objects.create(company=a, user=cible, jti=refresh['jti'])
    access = refresh.access_token
    access[SESSION_CLAIM] = refresh['jti']
    api_cible = APIClient()
    api_cible.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    me_avant = api_cible.get('/api/django/auth/me/', **H).status_code
    faible = api_dir.post(URL.format(cible.id), {'password': 'a'}, format='json', **H)
    faible_champs = sorted(faible.data) if isinstance(getattr(faible, 'data', None), dict) else None
    faible_inchange = mdp_ok(cible)
    leg = api_dir.post(URL.format(cible.id), {'password': NOUVEAU}, format='json', **H)
    relu = User.objects.get(pk=cible.pk)
    sessions_actives = UserSession.objects.filter(user=cible, revoked=False).count()
    me_apres = api_cible.get('/api/django/auth/me/', **H).status_code
    lignes = SettingsAuditLog.objects.filter(company=a, section='utilisateurs',
                                             field=f'user:{cible.username}:mot_de_passe')
    sans_valeur = all(NOUVEAU not in (lg.new_value or '') and NOUVEAU not in (lg.old_value or '') for lg in lignes)
    out['legitime'] = {'me_avant': me_avant, 'mdp_a': [faible.status_code, faible_champs, faible_inchange],
                       'reinit': leg.status_code, 'nouveau_mdp_pose': relu.check_password(NOUVEAU),
                       'must_change_password': relu.must_change_password, 'sessions_actives_cible': sessions_actives,
                       'me_apres': me_apres, 'lignes_journal': lignes.count(),
                       'acteur_journal': [lg.user_id == directeur.id for lg in lignes], 'valeur_absente': sans_valeur}
    leg_ok = (me_avant == 200 and faible.status_code == 400 and 'password' in (faible_champs or []) and faible_inchange
              and leg.status_code == 200 and relu.check_password(NOUVEAU) and relu.must_change_password
              and sessions_actives == 0 and me_apres == 401 and lignes.count() == 1
              and all(out['legitime']['acteur_journal']) and sans_valeur)
    out['verdicts'] = {'patch_put': patch_ok, 'creation': creation_ok, 'rang': rang_ok, 'autre_societe': autre_ok,
                       'legitime': leg_ok}
    out['repro'] = bool(patch_ok and creation_ok and rang_ok and autre_ok and leg_ok)
    return out
