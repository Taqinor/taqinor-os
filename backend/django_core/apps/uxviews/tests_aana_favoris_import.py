"""AANA16 (C-AANA-006) — l'import de favoris n'accepte comme
``champ_identifiant`` que les identifiants métier connus
(``_CHAMPS_IDENTIFIANT_CANDIDATS``), jamais une clé ORM libre.

Scénario U3 : un produit de A à ``prix_achat=500``. Avant le correctif,
``champ_identifiant=prix_achat__gte`` avec 400 → importes=1, avec 600 →
importes=0 : un oracle par dichotomie sur le prix d'achat.

Données RÉELLES en base, vrai parseur d'import (aucun mock). Retirer le
contrôle rougit ce test.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from authentication.models import Company

from .models import FavoriUtilisateur

User = get_user_model()

URL = '/api/django/uxviews/favoris/importer/'


def _csv(lignes):
    contenu = '\n'.join(
        ['type,champ_identifiant,identifiant,libelle'] + lignes)
    return SimpleUploadedFile(
        'favoris.csv', contenu.encode('utf-8'), content_type='text/csv')


class TestImportFavorisChamp(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana16-co', defaults={'nom': 'AANA16 Co'})[0]
        self.user = User.objects.create_user(
            username='aana16_u', password='x', company=self.company,
            role_legacy='normal')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='AANA16-P',
            prix_vente=Decimal('900'), prix_achat=Decimal('500'),
            quantite_stock=1)

    def _importer(self, ligne):
        return self.api.post(URL, {'fichier': _csv([ligne])},
                             format='multipart')

    def test_lookup_libre_refuse(self):
        for seuil in ('400', '600'):
            resp = self._importer(
                f'stock.produit,prix_achat__gte,{seuil},X')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['importes'], 0, seuil)
            self.assertEqual(resp.data['non_resolues'], 1, seuil)
        self.assertFalse(
            FavoriUtilisateur.objects.filter(owner=self.user).exists())

    def test_identifiant_metier_toujours_accepte(self):
        resp = self._importer(f'stock.produit,sku,{self.produit.sku},Onduleur')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['importes'], 1)
