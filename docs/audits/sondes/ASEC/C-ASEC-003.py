SONDE = {"constat": "C-ASEC-003", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : POST /api/django/token/ réel (APIClient sans force_authenticate) -> chaque "
                    "mauvais mot de passe 401 et failed_login_count +1 (1, 2), verrou (locked_until) au 3e = seuil "
                    "société 3 (compteur remis à 0 au verrou), "
                    "puis bon mot de passe -> même 401 que faux ; inconnu vs faux -> 401 au corps identique ; 3 OTP "
                    "faux après bon mot de passe -> verrou ; même code TOTP deux fois -> 200 puis 401 "
                    "otp_deja_utilise ; succès remet le compteur à 0"}


def sonde(ctx):
    import uuid
    from unittest import mock
    import pyotp
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.parametres.models import CompanyProfile
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    User = get_user_model()
    URL = '/api/django/token/'
    BON = 'Bon-mdp-123!'
    s = uuid.uuid4().hex[:6]  # le plancher (compte, IP) vit dans le cache Redis : jamais deux runs sur le même nom
    n = [0]

    def ip():  # IP différente à chaque requête (comme les tests) : le plancher IP ne se mêle pas au seuil société
        n[0] += 1
        return f'198.51.100.{n[0] % 250 + 1}'

    def post(**corps):
        return APIClient().post(URL, corps, format='json', REMOTE_ADDR=ip(), HTTP_HOST='localhost')

    def corps(r):
        c = dict(r.data) if isinstance(getattr(r, 'data', None), dict) else {'brut': str(r.content[:200])}
        if isinstance(c.get('error'), dict):
            c['error'] = {k: v for k, v in c['error'].items() if k != 'request_id'}
        return c

    def societe(tag, seuil):
        co = Company.objects.create(nom=f'Sonde ASEC003 {tag}', slug=f'sonde-asec003-{s}-{tag}')
        CompanyProfile.objects.update_or_create(company=co, defaults={'lockout_max_attempts': seuil,
                                                                      'lockout_duration_minutes': 15})
        return co

    def user(co, nom):
        return User.objects.create_user(username=f'sonde-asec003-{s}-{nom}', password=BON, company=co)

    def relu(u):
        return User.objects.get(pk=u.pk)

    a, b = societe('a', 3), societe('b', 0)
    u3, u3otp, uotp, u0 = user(a, 'u3'), user(a, 'otpfaux'), user(b, 'otp'), user(b, 'u0')
    for u in (u3otp, uotp):
        u.totp_secret = pyotp.random_base32()
        u.totp_enabled = True
        u.save()
    out = {'throttle': 'LoginRateThrottle (scope login, 5/min par IP) neutralisé par mock dans la sonde ; '
                       'REMOTE_ADDR varié par requête'}
    patcher = mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True)
    patcher.start()
    try:
        # 1) Mauvais mots de passe : compteur +1 à chaque échec, verrou au 3e (le compteur repart à 0 quand
        #    le verrou est posé : password_policy.register_failed_login, conception)
        compteurs, statuts = [], []
        for _ in range(3):
            r = post(username=u3.username, password='faux')
            statuts.append(r.status_code)
            compteurs.append(relu(u3).failed_login_count)
        verrou = relu(u3).locked_until is not None
        faux_inconnu = post(username=f'sonde-asec003-{s}-inconnu', password='faux')
        bon_verrouille = post(username=u3.username, password=BON)
        out['seuil_societe'] = {'statuts': statuts, 'compteurs': compteurs, 'locked_until_pose': verrou,
                                'bon_mdp_verrouille': bon_verrouille.status_code,
                                'cookie_access_emis': 'access_token' in bon_verrouille.cookies,
                                'meme_corps_que_inconnu': corps(bon_verrouille) == corps(faux_inconnu)}
        seuil_ok = (statuts == [401] * 3 and compteurs == [1, 2, 0] and verrou
                    and bon_verrouille.status_code == 401 and corps(bon_verrouille) == corps(faux_inconnu)
                    and 'access_token' not in bon_verrouille.cookies)
        # 2) Inconnu vs mauvais mot de passe d'un compte existant (non verrouillé) : identiques
        faux_connu = post(username=u0.username, password='faux')
        faux_inc2 = post(username=f'sonde-asec003-{s}-inconnu2', password='faux')
        out['inconnu_vs_faux'] = [faux_connu.status_code, faux_inc2.status_code, corps(faux_connu),
                                  corps(faux_connu) == corps(faux_inc2)]
        enum_ok = faux_connu.status_code == faux_inc2.status_code == 401 and corps(faux_connu) == corps(faux_inc2)
        # 3) OTP faux après bon mot de passe : compté, verrou au seuil
        otp_statuts = [post(username=u3otp.username, password=BON, otp='000000').status_code for _ in range(3)]
        out['otp_faux'] = {'statuts': otp_statuts, 'compteur': relu(u3otp).failed_login_count,
                           'locked_until_pose': relu(u3otp).locked_until is not None}
        otp_faux_ok = otp_statuts == [401] * 3 and relu(u3otp).locked_until is not None
        # 4) Rejeu TOTP : même code deux fois
        code = pyotp.TOTP(uotp.totp_secret).now()
        premier = post(username=uotp.username, password=BON, otp=code)
        pas = relu(uotp).totp_dernier_pas
        second = post(username=uotp.username, password=BON, otp=code)
        out['rejeu_totp'] = {'premier': premier.status_code, 'totp_dernier_pas_relu': pas is not None,
                             'second': second.status_code, 'code_second': corps(second).get('code'),
                             'cookie_second': 'access_token' in second.cookies}
        rejeu_ok = (premier.status_code == 200 and pas is not None and second.status_code == 401
                    and corps(second).get('code') in ('otp_deja_utilise', 'otp_deja_utilisateur')
                    and 'access_token' not in second.cookies)
        # 5) Succès remet à zéro (société à 0, compte u0 : 1 échec plus haut + 1 ici)
        post(username=u0.username, password='faux')
        avant_succes = relu(u0).failed_login_count
        ok = post(username=u0.username, password=BON)
        out['succes_remet_a_zero'] = [avant_succes, ok.status_code, relu(u0).failed_login_count]
        reset_ok = avant_succes == 2 and ok.status_code == 200 and relu(u0).failed_login_count == 0
    finally:
        patcher.stop()
    out['verdicts'] = {'seuil': seuil_ok, 'enumeration': enum_ok, 'otp_faux': otp_faux_ok, 'rejeu': rejeu_ok,
                       'reset': reset_ok}
    out['repro'] = bool(seuil_ok and enum_ok and otp_faux_ok and rejeu_ok and reset_ok)
    return out
