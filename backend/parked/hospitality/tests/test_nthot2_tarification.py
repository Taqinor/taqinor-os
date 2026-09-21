"""NTHOT2 — Tarification saisonnière (rack/corporate/ota).

Done = une date en haute saison avec plan spécifique renvoie le bon prix, une
date sans plan retombe sur le tarif rack.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import PlanTarifaire, TypeChambre

from .helpers import auth, make_company, make_user


class PrixApplicableTests(TestCase):
    def setUp(self):
        self.co = make_company('hot-tarif', 'Hôtel tarif')
        self.type_std = TypeChambre.objects.create(
            company=self.co, libelle='Standard', capacite_max=2)
        # Tarif rack "par défaut", large plage de dates.
        PlanTarifaire.objects.create(
            company=self.co, type_chambre=self.type_std,
            canal=PlanTarifaire.Canal.RACK,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 12, 31),
            prix_nuit_ht=Decimal('500'),
        )
        # Plan haute saison spécifique (corporate), plage plus étroite.
        PlanTarifaire.objects.create(
            company=self.co, type_chambre=self.type_std,
            canal=PlanTarifaire.Canal.CORPORATE,
            date_debut=datetime.date(2026, 7, 1),
            date_fin=datetime.date(2026, 8, 31),
            prix_nuit_ht=Decimal('900'),
        )

    def test_haute_saison_avec_plan_specifique(self):
        prix = services.prix_applicable(
            self.type_std, datetime.date(2026, 7, 15))
        self.assertEqual(prix, Decimal('900'))

    def test_date_sans_plan_specifique_retombe_sur_rack(self):
        prix = services.prix_applicable(
            self.type_std, datetime.date(2026, 3, 1))
        self.assertEqual(prix, Decimal('500'))

    def test_canal_explicite_priorite_sur_defaut(self):
        PlanTarifaire.objects.create(
            company=self.co, type_chambre=self.type_std,
            canal=PlanTarifaire.Canal.OTA,
            date_debut=datetime.date(2026, 7, 1),
            date_fin=datetime.date(2026, 8, 31),
            prix_nuit_ht=Decimal('850'),
        )
        prix = services.prix_applicable(
            self.type_std, datetime.date(2026, 7, 15), canal='ota')
        self.assertEqual(prix, Decimal('850'))

    def test_aucun_plan_renvoie_none(self):
        prix = services.prix_applicable(
            self.type_std, datetime.date(2020, 1, 1))
        self.assertIsNone(prix)


class PlanTarifaireApiTests(TestCase):
    BASE = '/api/django/hospitality/plans-tarifaires/'

    def setUp(self):
        self.co_a = make_company('hot-tarif-a', 'A')
        self.co_b = make_company('hot-tarif-b', 'B')
        self.user_a = make_user(self.co_a, 'hot-tarif-a-user')
        self.user_b = make_user(self.co_b, 'hot-tarif-b-user')
        self.type_a = TypeChambre.objects.create(
            company=self.co_a, libelle='Standard')

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'type_chambre': self.type_a.id,
            'canal': 'rack',
            'date_debut': '2026-01-01',
            'date_fin': '2026-12-31',
            'prix_nuit_ht': '500',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanTarifaire.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company, self.co_a)

    def test_tenant_isolation(self):
        PlanTarifaire.objects.create(
            company=self.co_a, type_chambre=self.type_a,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 12, 31),
            prix_nuit_ht=Decimal('500'),
        )
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)
