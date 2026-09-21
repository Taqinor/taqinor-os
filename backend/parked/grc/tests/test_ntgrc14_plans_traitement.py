"""NTGRC14 — plans de traitement du risque + suivi des retards.

Garanties : un plan dont l'échéance est passée et qui n'est pas fait remonte
dans `plans_en_retard` (calcul sur la DATE, pas sur le statut stocké), tout
est scopé société, et un plan ne peut pas pointer le risque d'une autre
société.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.grc.models import PlanTraitementRisque
from apps.grc.selectors import plans_en_retard
from apps.grc.services import creer_risque
from authentication.models import Company
from testkit.base import TenantAPITestCase


class RetardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC14 SA', slug='ntgrc14')
        cls.autre = Company.objects.create(nom='NTGRC14 B', slug='ntgrc14-b')
        cls.risque = creer_risque(cls.company, titre='Risque test')

    def _plan(self, company=None, risque=None, **kw):
        params = {'action': 'Mettre en place un double contrôle'}
        params.update(kw)
        return PlanTraitementRisque.objects.create(
            company=company or self.company,
            risque=risque or self.risque, **params)

    def test_echeance_passee_et_non_fait_remonte(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        en_retard = self._plan(echeance=hier)
        self._plan(echeance=timezone.now().date() +
                   timezone.timedelta(days=10))
        self.assertEqual(
            [p.pk for p in plans_en_retard(self.company)], [en_retard.pk])

    def test_un_plan_fait_nest_jamais_en_retard(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        plan = self._plan(echeance=hier,
                          statut=PlanTraitementRisque.STATUT_FAIT)
        self.assertEqual(list(plans_en_retard(self.company)), [])
        self.assertFalse(plan.est_en_retard())

    def test_le_retard_ne_depend_pas_du_statut_stocke(self):
        """Un statut « en cours » périmé ne masque pas le retard réel."""
        hier = timezone.now().date() - timezone.timedelta(days=30)
        plan = self._plan(echeance=hier,
                          statut=PlanTraitementRisque.STATUT_EN_COURS)
        self.assertTrue(plan.est_en_retard())
        self.assertIn(plan, list(plans_en_retard(self.company)))

    def test_un_plan_sans_echeance_nest_jamais_en_retard(self):
        plan = self._plan()
        self.assertFalse(plan.est_en_retard())
        self.assertEqual(list(plans_en_retard(self.company)), [])

    def test_selector_borne_a_la_societe(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        risque_autre = creer_risque(self.autre, titre='Autre')
        self._plan(company=self.autre, risque=risque_autre, echeance=hier)
        self.assertEqual(list(plans_en_retard(self.company)), [])

    def test_lavancement_est_borne_a_0_100(self):
        plan = self._plan(avancement_pct=250)
        self.assertEqual(plan.avancement_pct, 100)

    def test_le_cout_estime_est_un_decimal(self):
        plan = self._plan(cout_estime=Decimal('1250.50'))
        plan.refresh_from_db()
        self.assertEqual(plan.cout_estime, Decimal('1250.50'))


class EndpointPlansTests(TenantAPITestCase):
    BASE = '/api/django/grc/plans-traitement-risque/'

    def setUp(self):
        super().setUp()
        self.risque = creer_risque(self.company, titre='Risque')

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe(self):
        r = self._admin().post(
            self.BASE,
            {'risque': self.risque.pk, 'action': 'Former les équipes',
             'avancement_pct': 30},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        plan = PlanTraitementRisque.objects.get(pk=r.data['id'])
        self.assertEqual(plan.company, self.company)

    def test_un_plan_ne_peut_pas_pointer_le_risque_dune_autre_societe(self):
        etranger = creer_risque(self.other_company, titre='Etranger')
        r = self._admin().post(
            self.BASE, {'risque': etranger.pk, 'action': 'X'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('risque', r.data)

    def test_avancement_hors_bornes_nomme_le_champ(self):
        r = self._admin().post(
            self.BASE,
            {'risque': self.risque.pk, 'action': 'X', 'avancement_pct': 300},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('avancement_pct', r.data)

    def test_endpoint_en_retard(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        PlanTraitementRisque.objects.create(
            company=self.company, risque=self.risque, action='X',
            echeance=hier)
        r = self._admin().get(f'{self.BASE}en-retard/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertTrue(r.data['results'][0]['en_retard'])
