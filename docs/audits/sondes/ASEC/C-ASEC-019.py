SONDE = {"constat": "C-ASEC-019", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : NUM_PROXIES=1, X-Forwarded-For '<forgée>, <visiteur>' -> "
                    "ip_de_requete rend <visiteur> (= get_ident DRF) ; allowlist NetworkPolicy enforce de A "
                    "(10.0.0.0/8) -> 403 malgré <forgée> 10.9.9.9 dans la plage ; connexion /api/django/token/ -> "
                    "UserSession.ip_address = <visiteur> ; dernier saut réellement dans la plage -> 200"}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse
    from django.test import RequestFactory, override_settings
    from rest_framework.test import APIClient
    from rest_framework.throttling import SimpleRateThrottle
    from authentication.models import Company, UserSession
    from authentication.throttles import LoginRateThrottle
    from apps.identity.middleware import NetworkPolicyMiddleware
    from apps.identity.models import IpAllowRule, NetworkPolicy
    from core.throttling import ip_de_requete
    User = get_user_model()
    FORGEE, VISITEUR, NGINX = '10.9.9.9', '203.0.113.19', '172.18.0.5'

    def requete(xff):
        return RequestFactory().get('/api/django/crm/leads/', REMOTE_ADDR=NGINX, HTTP_X_FORWARDED_FOR=xff,
                                    HTTP_HOST='localhost')

    a = Company.objects.create(nom='Sonde ASEC019 a', slug='sonde-asec019-a')
    b = Company.objects.create(nom='Sonde ASEC019 b', slug='sonde-asec019-b')
    ua = User.objects.create_user(username='sonde-asec019-a', password='Bon-mdp-019!', company=a,
                                  email='asec019a@sonde.invalid')
    User.objects.create_user(username='sonde-asec019-b', password='Bon-mdp-019!', company=b,
                             email='asec019b@sonde.invalid')
    out = {}
    with override_settings(NUM_PROXIES=1):
        throttle = SimpleRateThrottle.__new__(SimpleRateThrottle)
        prims = []
        for xff in (f'{FORGEE}, {VISITEUR}', VISITEUR, f'1.1.1.1, {FORGEE}, {VISITEUR}'):
            req = requete(xff)
            with mock.patch('rest_framework.throttling.api_settings') as api:
                api.NUM_PROXIES = 1
                drf = throttle.get_ident(req)
            prims.append([xff, ip_de_requete(req), drf])
        out['primitive'] = prims
        pol = NetworkPolicy.objects.create(company=a, mode=NetworkPolicy.Mode.ENFORCE, applies_to='all')
        IpAllowRule.objects.create(company=a, policy=pol, cidr='10.0.0.0/8')
        mw = NetworkPolicyMiddleware(lambda r: HttpResponse('ok', status=200))
        req = requete(f'{FORGEE}, {VISITEUR}')
        req.user = ua
        req_ok = requete(f'{VISITEUR}, 10.1.2.3')
        req_ok.user = ua
        out['allowlist'] = {'forgee_dans_plage': mw(req).status_code,
                            'dernier_saut_dans_plage': mw(req_ok).status_code}
        pol.delete()  # la connexion ci-dessous ne doit pas être bloquée par l'allowlist
        avant = set(UserSession.objects.filter(user=ua).values_list('pk', flat=True))
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            r = APIClient().post('/api/django/token/', {'username': 'sonde-asec019-a', 'password': 'Bon-mdp-019!'},
                                 format='json', REMOTE_ADDR=NGINX, HTTP_X_FORWARDED_FOR=f'{FORGEE}, {VISITEUR}',
                                 HTTP_HOST='localhost')
        nouvelles = list(UserSession.objects.filter(user=ua).exclude(pk__in=avant).values_list('ip_address', flat=True))
        out['connexion'] = {'http': r.status_code, 'user_session_ip': nouvelles}
    out['repro'] = bool(all(p[1] == VISITEUR == p[2] for p in prims)
                        and out['allowlist'] == {'forgee_dans_plage': 403, 'dernier_saut_dans_plage': 200}
                        and r.status_code == 200 and nouvelles == [VISITEUR])
    return out
