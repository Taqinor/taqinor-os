"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-012 (audit analyse du 05/10, §6) : la révocation d'une clé environnement='test' répondait 404.
"""
SONDE = {
    'constat': 'C-AANA-012',
    'sha': '5908d43bb',
    'attendu': "défaut absent : POST keys/<id>/revoke/ sur une clé de bac à sable répond 200 et la clé est refusée ensuite",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.publicapi.models import ApiKey
    from apps.publicapi.portees import SCOPE_READ_LEADS
    co = Company.objects.create(nom='Sonde 012', slug='sonde-aana-012')
    adm = get_user_model().objects.create_user(username='sonde-aana-012', password='x', company=co,
                                               role_legacy='admin')
    s = APIClient()
    s.force_authenticate(adm)
    c = s.post('/api/django/publicapi/keys/', {'label': 'test', 'scopes': [SCOPE_READ_LEADS],
                                               'environnement': 'test'}, format='json', HTTP_HOST='localhost')
    cid, brute = c.data['id'], c.data['key']
    ka = APIClient()
    ka.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
    avant = ka.get('/api/public/v1/leads/', HTTP_HOST='localhost').status_code
    rev = s.post('/api/django/publicapi/keys/%s/revoke/' % cid, HTTP_HOST='localhost')
    apres = ka.get('/api/public/v1/leads/', HTTP_HOST='localhost').status_code
    actif = ApiKey.objects.get(pk=cid).enabled
    print('creation=%s avant=%s revoke=%s apres=%s enabled=%s' % (c.status_code, avant, rev.status_code, apres, actif))
    return {'repro': rev.status_code == 200 and not actif and apres in (401, 403),
            'revoke': rev.status_code, 'apres': apres}
