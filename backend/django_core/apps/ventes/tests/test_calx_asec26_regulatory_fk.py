"""ASEC26 (C-ASEC-005 site d) — la FK ``chantier`` du dossier réglementaire
(et de sa sœur la régularisation 8221) est BORNÉE à la société de
l'utilisateur, en création comme en mise à jour.

Un chantier (``installations.Installation``) d'une autre société, ou un id
inexistant, donne 400 sur ``chantier`` sans rien créer ni modifier, et sans
renvoyer aucun libellé de l'autre société ; un chantier de la société passe.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.ventes.models import Devis, RegulatoryDossier, Regularisation8221
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ventes/dossiers-reglementaires/'
URL_REGUL = '/api/django/ventes/regularisations-8221/'


def _client(company, suffixe):
    return Client.objects.create(
        company=company, nom='Bennani', prenom='Sara',
        email=f'asec26_{suffixe}@example.com', telephone='+212600000000')


class RegulatoryFkSocieteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.co_a = Company.objects.create(nom='Co A', slug='asec26-a')
        cls.co_b = Company.objects.create(nom='Co B', slug='asec26-b')
        cls.user_a = User.objects.create_user(
            username='asec26_a', password='x', role_legacy='responsable',
            company=cls.co_a)
        cls.client_a = _client(cls.co_a, 'a')
        cls.client_b = _client(cls.co_b, 'b')
        cls.devis_a = Devis.objects.create(
            company=cls.co_a, reference='DEV-ASEC26-A', client=cls.client_a,
            statut='brouillon', created_by=cls.user_a)
        cls.chantier_a = Installation.objects.create(
            company=cls.co_a, reference='CH-ASEC26-A', client=cls.client_a)
        cls.chantier_b = Installation.objects.create(
            company=cls.co_b, reference='CH-ASEC26-B-SECRET',
            client=cls.client_b)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user_a)

    def _dossier(self, **extra):
        return RegulatoryDossier.objects.create(
            company=self.co_a, devis=self.devis_a,
            regime_8221='declaration_bt', created_by=self.user_a, **extra)

    def test_creation_chantier_etranger_400(self):
        avant = RegulatoryDossier.objects.count()
        r = self.api.post(URL, {
            'devis': self.devis_a.id, 'regime_8221': 'declaration_bt',
            'chantier': self.chantier_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('chantier', r.data)
        self.assertNotIn(b'CH-ASEC26-B-SECRET', r.content)
        self.assertEqual(RegulatoryDossier.objects.count(), avant)

        # Sœur FG271 : la régularisation 8221 porte la même FK.
        avant = Regularisation8221.objects.count()
        r = self.api.post(URL_REGUL, {
            'devis': self.devis_a.id, 'regime_8221': 'declaration_bt',
            'chantier': self.chantier_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('chantier', r.data)
        self.assertEqual(Regularisation8221.objects.count(), avant)

    def test_patch_chantier_etranger_400(self):
        dossier = self._dossier(chantier=self.chantier_a)
        r = self.api.patch(f'{URL}{dossier.id}/',
                           {'chantier': self.chantier_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('chantier', r.data)
        self.assertNotIn(b'CH-ASEC26-B-SECRET', r.content)
        dossier.refresh_from_db()
        self.assertEqual(dossier.chantier_id, self.chantier_a.id)

    def test_id_inexistant_400(self):
        r = self.api.post(URL, {
            'devis': self.devis_a.id, 'regime_8221': 'declaration_bt',
            'chantier': 999999999,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('chantier', r.data)

        dossier = self._dossier()
        r = self.api.patch(f'{URL}{dossier.id}/',
                           {'chantier': 999999999}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('chantier', r.data)
        dossier.refresh_from_db()
        self.assertIsNone(dossier.chantier_id)

    def test_chantier_societe_ok(self):
        r = self.api.post(URL, {
            'devis': self.devis_a.id, 'regime_8221': 'declaration_bt',
            'chantier': self.chantier_a.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(
            RegulatoryDossier.objects.get(pk=r.data['id']).chantier_id,
            self.chantier_a.id)

        dossier = self._dossier()
        r = self.api.patch(f'{URL}{dossier.id}/',
                           {'chantier': self.chantier_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        dossier.refresh_from_db()
        self.assertEqual(dossier.chantier_id, self.chantier_a.id)
