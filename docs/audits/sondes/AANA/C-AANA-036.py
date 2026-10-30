"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-036 (audit analyse du 05/10, §6) : code mort / résidus parqués (partie exécutable en processus).
"""
SONDE = {
    'constat': 'C-AANA-036',
    'sha': '5908d43bb',
    'attendu': "défaut absent : scope juridique:read absent de portees, routes reporting/p2p/kpi et envois-rapports non servies ; FastAPI /kb/redaction, /projets/generer-plan, /chat/transcribe vérifiés hors sonde",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.urls import Resolver404, resolve
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.publicapi import portees
    codes = [c for c, _ in portees.SCOPE_CHOICES]
    scope_ok = 'juridique:read' not in codes and 'juridique:read' not in portees.ALL_SCOPES \
        and not hasattr(portees, 'SCOPE_READ_JURIDIQUE')
    co = Company.objects.create(nom='Sonde 036', slug='sonde-aana-036')
    adm = get_user_model().objects.create_user(username='sonde-aana-036', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(adm)
    routes = {}
    for ch in ('/api/django/reporting/p2p/kpi/', '/api/django/reporting/envois-rapports/'):
        try:
            resolu = resolve(ch).view_name
        except Resolver404:
            resolu = None
        routes[ch] = {'resolve': resolu, 'GET': api.get(ch, HTTP_HOST='localhost').status_code}
    routes_ok = all(v['resolve'] is None and v['GET'] == 404 for v in routes.values())
    print('juridique:read absent=%s routes=%s | FastAPI /kb/redaction, /projets/generer-plan, /chat/transcribe : vérifié hors sonde'
          % (scope_ok, routes))
    return {'repro': scope_ok and routes_ok, 'scope_juridique_absent': scope_ok, 'routes': routes,
            'hors_sonde': ['/kb/redaction', '/projets/generer-plan', '/chat/transcribe']}
