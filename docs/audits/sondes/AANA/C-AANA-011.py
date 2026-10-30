"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-011 (audit analyse du 05/10, §6) : ?owner=<u2> exposait la vue PERSONNELLE d'un collaborateur.
"""
SONDE = {
    'constat': 'C-AANA-011',
    'sha': '5908d43bb',
    'attendu': "défaut absent : GET saved-views/?owner=<u2> avec une clé read:vues ne renvoie pas la vue personnelle de u2",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.uxviews.models import SavedView
    from apps.publicapi.models import ApiKey
    from apps.publicapi.portees import SCOPE_READ_VUES
    co = Company.objects.create(nom='Sonde 011', slug='sonde-aana-011')
    u2 = get_user_model().objects.create_user(username='sonde-aana-011-u2', password='x', company=co)
    SavedView.objects.create(company=co, owner=u2, ecran='crm.leads', nom='Perso U2',
                             visibilite=SavedView.Visibilite.PERSONNELLE)
    SavedView.objects.create(company=co, owner=u2, ecran='crm.leads', nom='Equipe U2',
                             visibilite=SavedView.Visibilite.EQUIPE)
    _c, brute = ApiKey.issue(company=co, label='vues', scopes=[SCOPE_READ_VUES])
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
    r = api.get('/api/public/v1/saved-views/', {'owner': u2.id}, HTTP_HOST='localhost')
    data = r.data
    lignes = data['results'] if isinstance(data, dict) and 'results' in data else data
    noms = sorted(l['nom'] for l in lignes)
    print('statut=%s noms=%s' % (r.status_code, noms))
    return {'repro': r.status_code == 200 and 'Perso U2' not in noms, 'noms': noms}
