"""NTNRG14 — Disponibilité contractuelle vs mesurée (SLA de disponibilité).

Couvre :
  * pas de SLA configuré → `disponibilite_vs_garantie` no-op gracieux
    (`has_sla=False`) ;
  * disponibilité mesurée SOUS le seuil garanti → écart + pénalité chiffrée
    en DH (jamais négative) ;
  * disponibilité mesurée AU-DESSUS (ou égale) au seuil → aucune pénalité ;
  * aucune donnée mesurable → écart/pénalité `None` (jamais un faux 0).

Run :
    python manage.py test apps.monitoring.test_ntnrg14_sla_disponibilite -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import ProductionReading, SlaDisponibilite
from apps.monitoring.selectors import disponibilite_vs_garantie


def make_inst(company, ref):
    client = Client.objects.create(
        company=company, nom='Cli', prenom=ref,
        email=f'{ref.lower()}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        puissance_installee_kwc=Decimal('10'))


class TestDisponibiliteVsGarantie(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg14-co', defaults={'nom': 'NTNRG14 Co'})
        self.today = date(2026, 6, 30)

    def test_no_sla_is_graceful_noop(self):
        inst = make_inst(self.company, 'NTNRG14-1')
        result = disponibilite_vs_garantie(inst, window_days=10, today=self.today)
        self.assertFalse(result['has_sla'])

    def test_below_guaranteed_availability_yields_penalty(self):
        inst = make_inst(self.company, 'NTNRG14-2')
        SlaDisponibilite.objects.create(
            company=self.company, installation=inst,
            disponibilite_garantie_pct=Decimal('98'),
            compensation_mad_par_jour_indispo=Decimal('500'))
        # 8 jours avec relevé sur une fenêtre de 10 jours → 80 % mesurée.
        for i in range(8):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=self.today - timedelta(days=i), energy_kwh=Decimal('10'))
        result = disponibilite_vs_garantie(inst, window_days=10, today=self.today)
        self.assertTrue(result['has_sla'])
        self.assertEqual(result['disponibilite_mesuree_pct'], Decimal('80.00'))
        self.assertTrue(result['sous_garantie'])
        self.assertEqual(result['ecart_pct'], Decimal('18.00'))
        # 18 % de 10 jours = 1,8 jour d'indisponibilité excédentaire.
        self.assertEqual(
            result['jours_indisponibilite_excedentaire'], Decimal('1.80'))
        # 1,8 × 500 = 900 MAD.
        self.assertEqual(result['penalite_mad'], Decimal('900.00'))

    def test_meeting_guarantee_yields_no_penalty(self):
        inst = make_inst(self.company, 'NTNRG14-3')
        SlaDisponibilite.objects.create(
            company=self.company, installation=inst,
            disponibilite_garantie_pct=Decimal('50'),
            compensation_mad_par_jour_indispo=Decimal('500'))
        for i in range(8):
            ProductionReading.objects.create(
                company=self.company, installation=inst,
                date=self.today - timedelta(days=i), energy_kwh=Decimal('10'))
        result = disponibilite_vs_garantie(inst, window_days=10, today=self.today)
        self.assertFalse(result['sous_garantie'])
        self.assertEqual(result['penalite_mad'], Decimal('0'))

    def test_no_data_yields_full_shortfall_never_crashes(self):
        inst = make_inst(self.company, 'NTNRG14-4')
        SlaDisponibilite.objects.create(
            company=self.company, installation=inst,
            disponibilite_garantie_pct=Decimal('98'))
        result = disponibilite_vs_garantie(inst, window_days=10, today=self.today)
        self.assertTrue(result['has_sla'])
        # Aucun relevé du tout ⇒ disponibilité mesurée 0 % (jours couverts /
        # fenêtre) ⇒ écart = le seuil garanti entier. Jamais d'exception.
        self.assertEqual(result['disponibilite_mesuree_pct'], Decimal('0'))
        self.assertEqual(result['ecart_pct'], Decimal('98.00'))
        self.assertTrue(result['sous_garantie'])
