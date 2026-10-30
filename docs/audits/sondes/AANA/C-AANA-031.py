"""Sonde AANA50 : rejoue C-AANA-031 (audit analyse du 05/10) : CSV produits `X,S1,abc` / `Y,S2,-5` / `Z,S3,10,2.7` ->
skipped=[], prix 'abc' avalé en 0, -5 accepté, quantité 2.7 tronquée à 2."""
SONDE = {
    'constat': 'C-AANA-031',
    'sha': '5908d43bb',
    'attendu': "défaut absent : lignes 1-2 ignorées avec raison, ligne 3 refusée (quantité non entière), aucun produit S1/S2/S3 créé",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.stock.models import Produit
    co = Company.objects.create(nom='Sonde 031', slug='sonde-aana-031')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aana-031', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    f = SimpleUploadedFile('p.csv', 'Nom,SKU,Prix,Quantite\nX,S1,abc,\nY,S2,-5,\nZ,S3,10,2.7\n'.encode(), content_type='text/csv')
    r = api.post('/api/django/imports/commit/', {'file': f, 'target': 'products'}, format='multipart', HTTP_HOST='localhost')
    sk = {s['ligne']: s['raison'] for s in (r.data.get('skipped') or [])} if r.status_code == 200 else {}
    crees = [(p[0], str(p[1]), p[2]) for p in Produit.objects.filter(company=co, sku__in=['S1', 'S2', 'S3']).values_list('sku', 'prix_vente', 'quantite_stock')]
    print('commit=%s skipped=%s produits_crees=%s' % (r.status_code, sk, crees))
    return {'repro': r.status_code == 200 and sorted(sk) == [1, 2, 3] and not crees, 'skipped': sk, 'crees': crees}
