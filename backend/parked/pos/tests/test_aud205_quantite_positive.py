"""AUD205 — `LigneVenteComptoir.quantite` sans validation (zéro ou négatif).

Rouge avant correctif : `POST /pos/ventes/<id>/lignes/` avec `quantite=-3`
créait la ligne, encaissait un montant NÉGATIF et produisait à la validation
un mouvement de « sortie » de stock au signe inversé — une entrée déguisée en
vente. Vert après : 400, aucune ligne créée, et la base refuse la quantité
non positive quel que soit le chemin d'écriture (CheckConstraint).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.stock.models import Categorie, Produit

User = get_user_model()


class Aud205QuantitePositiveTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud205', defaults={'nom': 'AUD205 Co'})
        self.user = User.objects.create_user(
            username='aud205-caissier', password='x', company=self.co,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble solaire', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=10, categorie=categorie)
        self.vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-AUD205', client=self.client_obj,
            taux_tva=Decimal('20'), created_by=self.user)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self):
        return f'/api/django/pos/ventes/{self.vente.id}/lignes/'

    def test_quantite_negative_refusee(self):
        """ROUGE avant AUD205 : la ligne était créée et encaissait -300 MAD."""
        resp = self.api.post(
            self._url(),
            {'produit': self.produit.id, 'quantite': '-3',
             'prix_unitaire_ttc': '100'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('quantite', resp.data)
        self.assertEqual(self.vente.lignes.count(), 0)

    def test_quantite_zero_refusee(self):
        resp = self.api.post(
            self._url(),
            {'produit': self.produit.id, 'quantite': '0',
             'prix_unitaire_ttc': '100'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.vente.lignes.count(), 0)

    def test_quantite_illisible_refusee(self):
        resp = self.api.post(
            self._url(),
            {'produit': self.produit.id, 'quantite': 'abc',
             'prix_unitaire_ttc': '100'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.vente.lignes.count(), 0)

    def test_quantite_positive_toujours_acceptee(self):
        resp = self.api.post(
            self._url(),
            {'produit': self.produit.id, 'quantite': '3',
             'prix_unitaire_ttc': '100'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        ligne = self.vente.lignes.get()
        self.assertEqual(Decimal(str(ligne.quantite)), Decimal('3'))
        self.assertEqual(ligne.total_ttc, Decimal('300'))

    def test_contrainte_base_refuse_quantite_non_positive(self):
        """Dernier rempart : aucun chemin d'écriture (shell, admin, import)
        ne peut poser une quantité <= 0."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LigneVenteComptoir.objects.create(
                    vente=self.vente, produit=self.produit,
                    designation='Contournement', quantite=Decimal('-3'),
                    prix_unitaire_ttc=Decimal('100'))

    def test_validateur_modele_refuse_quantite_non_positive(self):
        ligne = LigneVenteComptoir(
            vente=self.vente, produit=self.produit, designation='X',
            quantite=Decimal('0'), prix_unitaire_ttc=Decimal('100'))
        with self.assertRaises(DjangoValidationError):
            ligne.full_clean()
