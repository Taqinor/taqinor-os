"""AUD507 — un contrat RÉSILIÉ/EXPIRÉ ne reçoit plus d'avenant.

``creer_avenant`` n'avait AUCUN test de statut, contrairement à
``renouveler_contrat`` qui refuse explicitement RESILIE/EXPIRE via
``_statuts_non_renouvelables()``. Un avenant FINANCIER (``montant_delta``)
était donc créable sur un contrat MORT — et il changeait bel et bien
``Contrat.montant``. ``appliquer_indexation`` héritait du même trou puisqu'il
appelle ce service sans contrôle.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats import services
from apps.contrats.models import Avenant, Contrat, PartieContrat
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestAvenantGardeStatut(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud507-{n}', nom=f'AUD507 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud507-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self, statut):
        contrat = Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD507-{next(_seq)}', objet='Maintenance',
            statut=statut, montant=Decimal('12000'))
        for i in range(2):
            PartieContrat.objects.create(
                company=self.company, contrat=contrat,
                nom=f'Partie {i}', ordre=i)
        return contrat

    def _creer_avenant(self, contrat, montant_delta='5000'):
        return self.api.post(
            f'{BASE}/{contrat.id}/creer-avenant/',
            {'objet': 'Révision', 'montant_delta': montant_delta},
            format='json')

    def test_avenant_refuse_sur_un_contrat_resilie(self):
        """ROUGE avant le correctif : 201, et Contrat.montant changeait sur un
        contrat MORT."""
        contrat = self._contrat(Contrat.Statut.RESILIE)
        resp = self._creer_avenant(contrat)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('résilié', resp.data['detail'].lower())
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('12000'))
        self.assertFalse(Avenant.objects.filter(contrat=contrat).exists())

    def test_avenant_refuse_sur_un_contrat_expire(self):
        contrat = self._contrat(Contrat.Statut.EXPIRE)
        resp = self._creer_avenant(contrat)
        self.assertEqual(resp.status_code, 400, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('12000'))

    def test_avenant_reste_possible_sur_un_contrat_actif(self):
        contrat = self._contrat(Contrat.Statut.ACTIF)
        resp = self._creer_avenant(contrat)
        self.assertEqual(resp.status_code, 201, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('17000'))

    def test_le_service_leve_une_erreur_typee(self):
        """Même patron que `RenouvellementError` : une exception dédiée, que
        la vue traduit en 400 — jamais un 500 ni un silence."""
        contrat = self._contrat(Contrat.Statut.RESILIE)
        with self.assertRaises(services.AvenantError):
            services.creer_avenant(contrat, objet='Révision',
                                   montant_delta=Decimal('5000'))

    def test_l_indexation_herite_de_la_garde(self):
        """`appliquer_indexation` appelle `creer_avenant` : la garde remonte
        automatiquement, sans second contrôle à maintenir."""
        from apps.contrats.models import IndexationPrix
        contrat = self._contrat(Contrat.Statut.RESILIE)
        indexation = IndexationPrix.objects.create(
            company=self.company, contrat=contrat, indice='ICC',
            valeur_base=Decimal('100'))
        with self.assertRaises(services.AvenantError):
            services.appliquer_indexation(
                indexation, valeur_actuelle=Decimal('110'))
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('12000'))
