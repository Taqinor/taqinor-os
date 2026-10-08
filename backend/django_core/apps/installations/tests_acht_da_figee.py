"""ACHT12 (C-ACHT-010) — une demande d'achat se FIGE dès sa soumission :
création / modification / suppression de ligne, import CSV et PATCH
d'en-tête refusés (400) hors brouillon ; seul `epinglee` reste libre.

Rejoue CACH-4 : ligne de 90 000 MAD ajoutée à une DA soumise de 100 MAD
(201, `montant_estime` 90 100) ; sur une DA commandée POST 201, PATCH 200,
DELETE 204.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_da_figee"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import DemandeAchat, DemandeAchatLigne

User = get_user_model()
BASE = '/api/django/installations'
MSG = 'repassez-la en brouillon pour la modifier'


class DaFigeeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht12', defaults={'nom': 'Co ACHT12'})
        self.user = User.objects.create_user(
            username='resp-acht12', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self._n = 0

    def _da(self, statut):
        self._n += 1
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-ACHT12-{self._n}',
            objet='Test', created_by=self.user)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Boulonnerie', quantite=Decimal('1'),
            prix_estime=Decimal('100'))
        DemandeAchat.objects.filter(pk=da.pk).update(statut=statut)
        da.refresh_from_db()
        return da

    def _montant(self, da):
        r = self.api.get(f'{BASE}/demandes-achat/{da.id}/')
        return Decimal(str(r.data['montant_estime']))

    def test_ligne_ajoutee_apres_soumission_refusee(self):
        da = self._da(DemandeAchat.Statut.SOUMISE)
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': da.id, 'designation': 'Gros lot',
            'quantite': '1', 'prix_estime': '90000'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Demande soumise : ' + MSG, str(r.data))
        self.assertEqual(da.lignes.count(), 1)
        self.assertEqual(self._montant(da), Decimal('100'))

    def test_patch_entete_approuvee_refuse(self):
        da = self._da(DemandeAchat.Statut.APPROUVEE)
        r = self.api.patch(f'{BASE}/demandes-achat/{da.id}/',
                           {'objet': 'Autre objet'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(MSG, str(r.data))
        da.refresh_from_db()
        self.assertEqual(da.objet, 'Test')

    def test_lignes_commandee_refusees(self):
        da = self._da(DemandeAchat.Statut.COMMANDEE)
        ligne = da.lignes.get()
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': da.id, 'designation': 'X', 'quantite': '1',
            'prix_estime': '1'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.patch(f'{BASE}/demandes-achat-lignes/{ligne.id}/',
                           {'quantite': '50'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.delete(f'{BASE}/demandes-achat-lignes/{ligne.id}/')
        self.assertEqual(r.status_code, 400, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, Decimal('1'))
        self.assertEqual(da.lignes.count(), 1)

    def test_import_csv_soumise_refuse(self):
        da = self._da(DemandeAchat.Statut.SOUMISE)
        fichier = SimpleUploadedFile(
            'lignes.csv', b'designation,quantite,prix_estime\nCable,2,10\n',
            content_type='text/csv')
        r = self.api.post(f'{BASE}/demandes-achat/{da.id}/importer-lignes-csv/',
                          {'fichier': fichier}, format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(da.lignes.count(), 1)

    def test_epinglee_libre(self):
        da = self._da(DemandeAchat.Statut.SOUMISE)
        r = self.api.patch(f'{BASE}/demandes-achat/{da.id}/',
                           {'epinglee': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        self.assertTrue(da.epinglee)

    def test_brouillon_entierement_modifiable(self):
        da = self._da(DemandeAchat.Statut.BROUILLON)
        ligne = da.lignes.get()
        r = self.api.patch(f'{BASE}/demandes-achat/{da.id}/',
                           {'objet': 'Nouvel objet'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.patch(f'{BASE}/demandes-achat-lignes/{ligne.id}/',
                           {'quantite': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': da.id, 'designation': 'X', 'quantite': '1',
            'prix_estime': '1'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.delete(f'{BASE}/demandes-achat-lignes/{ligne.id}/')
        self.assertEqual(r.status_code, 204)
