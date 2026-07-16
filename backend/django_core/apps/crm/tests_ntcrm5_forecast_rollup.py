"""NTCRM5 — Roll-up hiérarchique du forecast (par commercial → équipe → total)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import EquipeCommerciale, ForecastEntry, Lead, ObjectifCommercial
from apps.crm.selectors import forecast_rollup
from apps.roles.models import Role

User = get_user_model()


class ForecastRollupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM5', slug='taqinor-ntcrm5')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.manager = User.objects.create_user(
            username='manager_ntcrm5', password='x', company=self.company, role=self.role)
        self.coms = [
            User.objects.create_user(
                username=f'com_ntcrm5_{i}', password='x',
                company=self.company, role=self.role)
            for i in range(3)
        ]
        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe 5', responsable=self.manager)
        self.equipe.membres.set(self.coms)

        montants = [Decimal('10000'), Decimal('20000'), Decimal('30000')]
        for com, montant in zip(self.coms, montants):
            lead = Lead.objects.create(company=self.company, nom=f'Lead {com}', owner=com)
            ForecastEntry.objects.create(
                company=self.company, lead=lead,
                categorie=ForecastEntry.Categorie.COMMIT, montant_prevu=montant)

    def test_total_exact_par_categorie_pour_une_equipe(self):
        result = forecast_rollup(self.company)
        equipe_data = next(e for e in result['equipes'] if e['equipe_id'] == self.equipe.id)
        self.assertEqual(equipe_data['totals']['commit'], Decimal('60000'))
        self.assertEqual(result['total_societe']['commit'], Decimal('60000'))

    def test_ecart_vs_objectif_equipe_si_existe(self):
        # Objectifs CA_SIGNE individuels des 3 membres, MÊME période — la
        # cible d'équipe est leur somme (45000), comparée au total forecast
        # (60000, aucun filtre de periode ici -> tous les leads comptent).
        for com in self.coms:
            ObjectifCommercial.objects.create(
                company=self.company, owner=com,
                metric=ObjectifCommercial.Metric.CA_SIGNE,
                period_type='month', period_year=2026, period_month=7,
                cible=Decimal('15000'))
        result = forecast_rollup(self.company)
        equipe_data = next(e for e in result['equipes'] if e['equipe_id'] == self.equipe.id)
        self.assertEqual(equipe_data['cible_objectif'], Decimal('45000'))
        self.assertEqual(
            equipe_data['ecart_vs_objectif'], Decimal('60000') - Decimal('45000'))

    def test_pas_dobjectif_ecart_none(self):
        result = forecast_rollup(self.company)
        equipe_data = next(e for e in result['equipes'] if e['equipe_id'] == self.equipe.id)
        self.assertIsNone(equipe_data['cible_objectif'])
        self.assertIsNone(equipe_data['ecart_vs_objectif'])

    def test_manager_ne_voit_que_ses_equipes(self):
        autre_manager = User.objects.create_user(
            username='autre_manager_ntcrm5', password='x',
            company=self.company, role=self.role)
        EquipeCommerciale.objects.create(
            company=self.company, nom='Autre équipe', responsable=autre_manager)
        result = forecast_rollup(self.company, manager=self.manager)
        self.assertEqual(len(result['equipes']), 1)
        self.assertEqual(result['equipes'][0]['equipe_id'], self.equipe.id)
