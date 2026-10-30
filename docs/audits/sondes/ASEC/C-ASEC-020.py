SONDE = {"constat": "C-ASEC-020", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : après connexion réelle (/api/django/token/) et un refresh par la route cookie "
                    "/api/django/auth/token/refresh/ (200, NOUVEAU refresh, ancien en liste noire), l'ANCIEN refresh "
                    "rejoué -> 401 par la route cookie et par la route corps /api/django/token/refresh/ ; la route "
                    "corps sur une session de 2 h d'une société session_absolute_hours=1 -> 401 (ou 404 si retirée) "
                    "et UserSession révoquée ; légitime : le NOUVEAU refresh continue de servir (200)"}


def sonde(ctx):
    import uuid
    from datetime import timedelta
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.parametres.models import CompanyProfile
    from authentication.models import Company, UserSession
    from authentication.throttles import LoginRateThrottle
    from core.throttling import CookieRefreshThrottle
    User = get_user_model()
    BON = 'Bon-mdp-123!'
    COOKIE, CORPS = '/api/django/auth/token/refresh/', '/api/django/token/refresh/'
    H = {'HTTP_HOST': 'localhost'}
    s = uuid.uuid4().hex[:6]

    a = Company.objects.create(nom='Sonde ASEC020 a', slug=f'sonde-asec020-{s}-a')
    b = Company.objects.create(nom='Sonde ASEC020 b', slug=f'sonde-asec020-{s}-b')
    CompanyProfile.objects.update_or_create(company=b, defaults={'session_absolute_hours': 1})
    ua = User.objects.create_user(username=f'sonde-asec020-{s}-a', password=BON, company=a)
    ub = User.objects.create_user(username=f'sonde-asec020-{s}-b', password=BON, company=b)

    def login(u):
        api = APIClient()
        r = api.post('/api/django/token/', {'username': u.username, 'password': BON}, format='json', **H)
        return api, r.status_code, (api.cookies['refresh_token'].value if 'refresh_token' in api.cookies else None)

    out = {'throttles': 'LoginRateThrottle et CookieRefreshThrottle neutralisés par mock dans la sonde'}
    patchers = [mock.patch.object(c, 'allow_request', return_value=True)
                for c in (LoginRateThrottle, CookieRefreshThrottle)]
    for p in patchers:
        p.start()
    try:
        api, st, ancien = login(ua)
        r = api.post(COOKIE, **H)
        nouveau = r.cookies['refresh_token'].value if 'refresh_token' in r.cookies else None
        jti_ancien = RefreshToken(ancien, verify=False)['jti'] if ancien else None
        liste_noire = BlacklistedToken.objects.filter(token__jti=jti_ancien).exists() if jti_ancien else False
        voleur = APIClient()
        voleur.cookies['refresh_token'] = ancien
        rejeu_cookie = voleur.post(COOKIE, **H)
        rejeu_corps = APIClient().post(CORPS, {'refresh': ancien}, format='json', **H)
        suite = api.post(COOKIE, **H)
        out['rotation'] = {'login': st, 'refresh_cookie': r.status_code, 'nouveau_different': bool(
            nouveau and nouveau != ancien), 'ancien_en_liste_noire': liste_noire,
            'rejeu_ancien_cookie': rejeu_cookie.status_code, 'rejeu_ancien_corps': rejeu_corps.status_code,
            'cookies_poses_au_rejeu': 'refresh_token' in rejeu_cookie.cookies, 'nouveau_continue': suite.status_code}
        rot_ok = (st == 200 and r.status_code == 200 and nouveau and nouveau != ancien and liste_noire
                  and rejeu_cookie.status_code == 401 and rejeu_corps.status_code in (401, 404)
                  and suite.status_code == 200)
        # Route corps sur une vieille session (société B, durée absolue 1 h)
        _, st_b, ref_b = login(ub)
        session = UserSession.objects.filter(user=ub).latest('pk')
        UserSession.objects.filter(pk=session.pk).update(created_at=timezone.now() - timedelta(hours=2))
        vieille = APIClient().post(CORPS, {'refresh': ref_b}, format='json', **H)
        session.refresh_from_db()
        out['duree_absolue_route_corps'] = {'login': st_b, 'status': vieille.status_code,
                                            'session_revoquee': session.revoked,
                                            'jeton_rendu': isinstance(getattr(vieille, 'data', None), dict)
                                            and 'access' in vieille.data}
        abs_ok = st_b == 200 and (vieille.status_code == 404 or (vieille.status_code == 401 and session.revoked))
    finally:
        for p in patchers:
            p.stop()
    out['verdicts'] = {'rotation_et_rejeu': rot_ok, 'duree_absolue_corps': abs_ok}
    out['repro'] = bool(rot_ok and abs_ok)
    return out
