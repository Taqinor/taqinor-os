"""ACHT11 (C-ACHT-009/012) — bornes de saisie des lignes de DA (quantité > 0
et finie, prix >= 0) y compris à l'import CSV ; `generer-bcf` transmet le
chantier de la DA au BCF et rend 400 sur une quantité non entière.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_da_lignes"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, Installation)
from apps.stock.models import Fournisseur, Produit
from apps.crm.models import Client

User = get_user_model()
BASE = '/api/django/installations'


class DaLignesTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht11', defaults={'nom': 'Co ACHT11'})
        self.user = User.objects.create_user(
            username='resp-acht11', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ACHT11', sku='PAN-ACHT11',
            prix_vente=Decimal('100'), quantite_stock=10)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ACHT11')
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht11@example.invalid')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CHT-ACHT11', client=client)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-ACHT11-1', objet='Test',
            created_by=self.user, chantier=self.chantier,
            fournisseur_suggere=self.fournisseur)

    def _post_ligne(self, **kw):
        corps = {'demande': self.da.id, 'designation': 'X',
                 'quantite': '1', 'prix_estime': '1'}
        corps.update(kw)
        return self.api.post(f'{BASE}/demandes-achat-lignes/', corps,
                             format='json')

    def test_quantite_negative_refusee(self):
        for q in ('0', '-3'):
            r = self._post_ligne(quantite=q)
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn('quantite', r.data)
        self.assertEqual(self.da.lignes.count(), 0)

    def test_prix_negatif_refuse(self):
        r = self._post_ligne(prix_estime='-5')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('prix_estime', r.data)
        self.assertEqual(self.da.lignes.count(), 0)

    def test_csv_nan_infinity_rapportes(self):
        csv = (b'designation,quantite,prix_estime\n'
               b'x,NaN,1\ny,Infinity,1\nz,1,-7\nok,2,10\n')
        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/importer-lignes-csv/',
            {'fichier': SimpleUploadedFile('l.csv', csv)},
            format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['importees'], 1)
        self.assertEqual(len(r.data['erreurs']), 3)
        self.assertEqual(self.da.lignes.count(), 1)
        self.da.refresh_from_db()
        self.assertEqual(self.da.montant_estime, Decimal('20'))

    def _approuver(self):
        DemandeAchat.objects.filter(pk=self.da.pk).update(
            statut=DemandeAchat.Statut.APPROUVEE)

    def test_bcf_porte_chantier(self):
        DemandeAchatLigne.objects.create(
            demande=self.da, produit=self.produit, quantite=Decimal('2'),
            prix_estime=Decimal('10'))
        self._approuver()
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/generer-bcf/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.da.refresh_from_db()
        self.assertEqual(self.da.bon_commande.chantier_origine_id,
                         self.chantier.id)

    def test_decimal_refuse_au_bcf(self):
        DemandeAchatLigne.objects.create(
            demande=self.da, produit=self.produit, quantite=Decimal('2.5'),
            prix_estime=Decimal('10'))
        self._approuver()
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/generer-bcf/',
                          {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.APPROUVEE)
