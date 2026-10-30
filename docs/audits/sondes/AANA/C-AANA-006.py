"""Sonde AANA50 : rejoue C-AANA-006 (audit analyse du 05/10, U3) : l'import de favoris acceptait `champ_identifiant=prix_achat__gte`,
un oracle par dichotomie sur Produit.prix_achat (400 -> importes=1, 600 -> importes=0)."""
SONDE = {
    'constat': 'C-AANA-006',
    'sha': '5908d43bb',
    'attendu': "défaut absent : champ_identifiant=prix_achat__gte refusé pour les deux seuils (importes 0, non_resolues 1), aucun favori créé",
}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit
    from apps.uxviews.models import FavoriUtilisateur
    co = Company.objects.create(nom='Sonde 006', slug='sonde-aana-006')
    u = get_user_model().objects.create_user(username='sonde-aana-006', password='x', company=co, role_legacy='normal')
    Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-006', prix_vente=Decimal('900'), prix_achat=Decimal('500'), quantite_stock=1)
    api = APIClient()
    api.force_authenticate(u)
    res = {}
    for seuil in ('400', '600'):
        contenu = 'type,champ_identifiant,identifiant,libelle\nstock.produit,prix_achat__gte,%s,X' % seuil
        f = SimpleUploadedFile('f.csv', contenu.encode(), content_type='text/csv')
        r = api.post('/api/django/uxviews/favoris/importer/', {'fichier': f}, format='multipart', HTTP_HOST='localhost')
        res[seuil] = (r.status_code, r.data.get('importes') if r.status_code == 200 else None, r.data.get('non_resolues') if r.status_code == 200 else None)
    crees = FavoriUtilisateur.objects.filter(owner=u).count()
    print('seuil->(HTTP, importes, non_resolues)=%s favoris_crees=%s' % (res, crees))
    return {'repro': all(v == (200, 0, 1) for v in res.values()) and crees == 0, 'resultats': res, 'favoris': crees}
