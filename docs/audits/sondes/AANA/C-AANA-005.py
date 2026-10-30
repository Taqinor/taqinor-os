"""Sonde AANA50 : rejoue C-AANA-005 (audit analyse du 05/10, U2) : un utilisateur de A épinglait un client de B
(`POST /uxviews/favoris/` -> 201, libelle = nom du client de B)."""
SONDE = {
    'constat': 'C-AANA-005',
    'sha': '5908d43bb',
    'attendu': "défaut absent : épingler le client de B est refusé (4xx), aucune ligne FavoriUtilisateur, le nom de B ne fuit pas",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.uxviews.models import FavoriUtilisateur
    a = Company.objects.create(nom='Sonde 005 A', slug='sonde-aana-005-a')
    b = Company.objects.create(nom='Sonde 005 B', slug='sonde-aana-005-b')
    u = get_user_model().objects.create_user(username='sonde-aana-005', password='x', company=a, role_legacy='normal')
    cb = Client.objects.create(company=b, nom='Secret Client B 005')
    api = APIClient()
    api.force_authenticate(u)
    r = api.post('/api/django/uxviews/favoris/', {'modele': 'crm.client', 'object_id': cb.pk}, format='json', HTTP_HOST='localhost')
    ligne = FavoriUtilisateur.objects.filter(owner=u, object_id=cb.pk).exists()
    fuite = 'Secret Client B 005' in str(getattr(r, 'data', ''))
    print('POST favoris client de B -> %s ligne_creee=%s nom_de_B_fuite=%s' % (r.status_code, ligne, fuite))
    return {'repro': r.status_code in (400, 403, 404) and not ligne and not fuite, 'statut': r.status_code, 'ligne': ligne, 'fuite': fuite}
