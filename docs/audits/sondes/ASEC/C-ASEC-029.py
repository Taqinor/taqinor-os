SONDE = {"constat": "C-ASEC-029", "sha": "5908d43bb",
         "attendu": "STATIQUE : settings/prod.py durci (DEBUG=False, HSTS, cookies Secure, SSL redirect derrière "
                    "proxy, CORS restreint) ; la bascule de la PROD sur settings.prod est un geste du fondateur "
                    "(D-ASEC-6), non observable depuis la pile locale"}


def sonde(ctx):
    import os
    import re
    src = open(os.path.join('erp_agentique', 'settings', 'prod.py'), encoding='utf-8').read()
    attendus = {'DEBUG': r'^DEBUG\s*=\s*False', 'HSTS': r'^SECURE_HSTS_SECONDS\s*=\s*[1-9]',
                'SSL redirect': r'^SECURE_SSL_REDIRECT\s*=\s*True',
                'proxy SSL': r"^SECURE_PROXY_SSL_HEADER\s*=\s*\('HTTP_X_FORWARDED_PROTO', 'https'\)",
                'session Secure': r'^SESSION_COOKIE_SECURE\s*=\s*True',
                'CSRF Secure': r'^CSRF_COOKIE_SECURE\s*=\s*True',
                'CORS restreint': r'^CORS_ALLOW_ALL_ORIGINS\s*=\s*False'}
    obs = {k: bool(re.search(p, src, re.M)) for k, p in attendus.items()}
    return ('STATIQUE — settings/prod.py : %s ; pile locale sous DJANGO_SETTINGS_MODULE=%s (attendu en local) ; '
            'réglage réel du serveur NON vérifié ici (lecture prod hors de cette acceptation, geste fondateur).'
            % (obs, os.environ.get('DJANGO_SETTINGS_MODULE')))
