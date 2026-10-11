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
from apps.parametres.models import CompanyProfile


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
        # CIQ644 — la pénalité n'est chiffrée que si la société a validé
        # l'engagement de production (CIQ622) : ces cas la valident.
        profil = CompanyProfile.get(company=self.company)
        profil.garantie_production_autorisee = True
        profil.garantie_production_validation = 'Juriste, 01/10/2026'
        profil.save()

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


class TestAsav101SlaApi(TestCase):
    """ASAV101 — SLA de disponibilité rendu utilisable : route company-scopée
    (responsable/admin), taux garanti saisi, écart conforme au contrat
    partagé ``contract_samples/sla_disponibilite.json``."""
    URL = '/api/django/monitoring/sla-disponibilite/'

    def setUp(self):
        import json
        from pathlib import Path

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        self.contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'sla_disponibilite.json').read_text(encoding='utf-8'))
        self.company, _ = Company.objects.get_or_create(
            slug='asav101-co', defaults={'nom': 'ASAV101 Co'})
        self.autre, _ = Company.objects.get_or_create(
            slug='asav101-b', defaults={'nom': 'ASAV101 B'})
        profil = CompanyProfile.get(company=self.company)
        profil.garantie_production_autorisee = True
        profil.garantie_production_validation = 'Juriste, 01/10/2026'
        profil.save()
        self.inst = make_inst(self.company, 'ASAV101-1')
        self.inst_b = make_inst(self.autre, 'ASAV101-B')

        def client_de(username, role, company):
            api = APIClient()
            api.force_authenticate(User.objects.create_user(
                username=username, password='x', role_legacy=role,
                company=company))
            return api
        self.api = client_de('asav101_resp', 'responsable', self.company)
        self.api_b = client_de('asav101_b', 'admin', self.autre)
        self.api_normal = client_de('asav101_n', 'normal', self.company)

    def _creer(self, **corps):
        data = {'installation': self.inst.id,
                'disponibilite_garantie_pct': '98',
                'compensation_mad_par_jour_indispo': '50'}
        data.update(corps)
        return self.api.post(self.URL, data, format='json')

    def test_creation_et_liste_au_contrat(self):
        r = self._creer(company=self.autre.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            SlaDisponibilite.objects.get(id=r.data['id']).company_id,
            self.company.id)
        lst = self.api.get(self.URL)
        attendu = self.contrat['exemple_liste']['reponse']
        self.assertEqual(set(lst.data), set(attendu))
        self.assertEqual(set(lst.data['results'][0]),
                         set(attendu['results'][0]))
        # Un seul SLA par système.
        self.assertEqual(self._creer().status_code, 400)

    def test_taux_garanti_obligatoire(self):
        r = self.api.post(self.URL, {'installation': self.inst.id},
                          format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('disponibilite_garantie_pct', r.data)
        r = self._creer(disponibilite_garantie_pct='0')
        self.assertEqual(r.status_code, 400)
        self.assertIn('disponibilite_garantie_pct', r.data)
        r = self._creer(installation=self.inst_b.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn('installation', r.data)

    def test_ecart_affirme_le_contrat_partage(self):
        from django.utils import timezone
        aujourdhui = timezone.localdate()
        for i in range(5):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=aujourdhui - timedelta(days=i), energy_kwh=Decimal('10'))
        sla_id = self._creer().data['id']
        r = self.api.get(f'{self.URL}{sla_id}/ecart/?window_days=10')
        self.assertEqual(r.status_code, 200, r.data)
        corps = r.json()
        self.assertEqual(set(corps), set(self.contrat['exemple']))
        self.assertTrue(corps['has_sla'])
        self.assertTrue(corps['sous_garantie'])
        # Nombres servis en JSON (jamais du texte) ; pénalité = tarif saisi.
        self.assertIsInstance(corps['ecart_pct'], (int, float))
        self.assertGreater(corps['penalite_mad'], 0)

    def test_autre_societe_404_et_normal_403(self):
        sla_id = self._creer().data['id']
        self.assertEqual(
            self.api_b.get(f'{self.URL}{sla_id}/').status_code, 404)
        self.assertEqual(
            self.api_b.get(f'{self.URL}{sla_id}/ecart/').status_code, 404)
        self.assertEqual(self.api_b.get(self.URL).data['count'], 0)
        self.assertEqual(self.api_normal.get(self.URL).status_code, 403)
