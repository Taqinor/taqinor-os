"""ACHT58 (C-ACHT-056) — un chantier clôturé ne gèle que les champs réellement
MODIFIÉS : une valeur identique à celle de l'instance, renvoyée par un client
qui envoie la fiche complète, est acceptée.

Rejoue CFRONT-2 : PATCH complet inchangé -> 400 dans les deux cas.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht58_gel_valeur_changee"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation
from apps.ventes.models import Client

User = get_user_model()
BASE = '/api/django/installations/chantiers'


class GelValeurChangeeTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht58', defaults={'nom': 'Co ACHT58'})
        self.user = User.objects.create_user(
            username='resp-acht58', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='ACHT58',
            email='acht58@example.invalid')
        self.clos = Installation.objects.create(
            company=self.company, reference='CH-ACHT58', client=self.client_obj,
            statut=Installation.Statut.CLOTURE, cloture_verrouillee=True,
            puissance_installee_kwc=Decimal('6.50'))
        self.clos_sans_puissance = Installation.objects.create(
            company=self.company, reference='CH-ACHT58-0',
            statut=Installation.Statut.CLOTURE, cloture_verrouillee=True)

    def test_patch_complet_inchange_accepte(self):
        corps = {
            'puissance_installee_kwc': '6.5', 'client': self.client_obj.id,
            'bom': [], 'devis': None, 'notes': 'Note à jour',
            'dossier_reference': 'DOS-1',
        }
        r = self.api.patch(f'{BASE}/{self.clos.id}/', corps, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.clos.refresh_from_db()
        self.assertEqual(self.clos.notes, 'Note à jour')
        self.assertEqual(self.clos.dossier_reference, 'DOS-1')
        self.assertEqual(self.clos.puissance_installee_kwc, Decimal('6.50'))

    def test_puissance_nulle_inchangee_acceptee(self):
        r = self.api.patch(
            f'{BASE}/{self.clos_sans_puissance.id}/',
            {'puissance_installee_kwc': None, 'notes': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_puissance_modifiee_refusee(self):
        r = self.api.patch(f'{BASE}/{self.clos.id}/',
                           {'puissance_installee_kwc': 7}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Chantier clôturé', str(r.data))
        self.clos.refresh_from_db()
        self.assertEqual(self.clos.puissance_installee_kwc, Decimal('6.50'))
