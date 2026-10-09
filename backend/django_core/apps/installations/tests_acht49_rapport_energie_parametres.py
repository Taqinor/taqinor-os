"""ACHT49 (C-ACHT-048) — paramètres du rapport de production validés avant
tout calcul : 400 FR nommant le champ, jamais un PDF à zéros, un 500 ou un
défaut substitué en silence ; chantier sans puissance refusé.

Rejoue CREC-6 (`?tarif=NaN` 500, `?tarif=-5` 200, `tarif=0` -> 1,40) et
CREC-7 (puissance None -> 200 PDF).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht49_rapport_energie_parametres"
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


class RapportEnergieParametresTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht49', defaults={'nom': 'Co ACHT49'})
        self.user = User.objects.create_user(
            username='resp-acht49', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ACHT49',
            email='acht49@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT49', client=client,
            puissance_installee_kwc=Decimal('6.60'))
        self.sans_puissance = Installation.objects.create(
            company=self.company, reference='CH-ACHT49-SP', client=client)

    def _get(self, inst, **params):
        return self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/rapport-energie/',
            params)

    def test_sans_parametre_pdf(self):
        r = self._get(self.inst)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_valeurs_invalides_400_nomme_le_champ(self):
        cas = [
            ({'tarif': 'NaN'}, 'tarif'),
            ({'rendement': 'Infinity'}, 'rendement'),
            ({'tarif': '-5'}, 'tarif'),
            ({'tarif': '0'}, 'tarif'),
            ({'co2': '-1'}, 'co2'),
            ({'nb_mois': '-3'}, 'nb_mois'),
            ({'date_debut': '2026-10-01', 'date_fin': '2026-01-01'},
             'date_fin'),
            ({'date_debut': 'hier'}, 'date_debut'),
        ]
        for params, champ in cas:
            r = self._get(self.inst, **params)
            self.assertEqual(r.status_code, 400, (params, r.content[:200]))
            self.assertIn(champ, r.data, params)

    def test_co2_zero_accepte(self):
        r = self._get(self.inst, co2='0')
        self.assertEqual(r.status_code, 200)

    def test_chantier_sans_puissance_refuse(self):
        r = self._get(self.sans_puissance)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Puissance installée non renseignée',
                      str(r.data))
