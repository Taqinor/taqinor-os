"""NTPRO12 — Répartition des charges locatives par tantièmes ou surface.

Couvre : la somme des quotes-parts des locaux occupés égale EXACTEMENT le
total des dépenses réelles (arrondi géré sur la dernière ligne), le mode
surface, le repli à parts égales sans base de répartition, et l'exclusion
des locaux non occupés.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Batiment, BudgetCharges, DepenseCharges, Local, Niveau, Site,
)
from apps.immobilier.services import repartir_charges

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntpro12RepartitionChargesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-rc-a', 'Immo RC A')
        self.admin_a = make_user(self.co_a, 'immo-rc-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        self.batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=self.batiment, numero='RDC')
        self.local1 = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01',
            statut=Local.Statut.LOUE, tantiemes=Decimal('300'),
            surface_m2=Decimal('60'))
        self.local2 = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-02',
            statut=Local.Statut.LOUE, tantiemes=Decimal('200'),
            surface_m2=Decimal('40'))
        # Local NON occupé — exclu de la répartition.
        Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-03',
            statut=Local.Statut.LIBRE, tantiemes=Decimal('500'))

        budget = BudgetCharges.objects.create(
            company=self.co_a, batiment=self.batiment, exercice=2026,
            poste=BudgetCharges.Poste.NETTOYAGE,
            montant_budgete_annuel=Decimal('12000.00'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=budget, date='2026-03-01',
            montant_reel=Decimal('1000.00'))
        DepenseCharges.objects.create(
            company=self.co_a, budget_charges=budget, date='2026-06-01',
            montant_reel=Decimal('1000.01'))

    def test_somme_quotes_parts_egale_exactement_le_total(self):
        data = repartir_charges(self.batiment, 2026)
        total_quotes_parts = sum(
            row['quote_part'] for row in data['par_local'])
        self.assertEqual(total_quotes_parts, data['total_depenses'])
        self.assertEqual(data['total_depenses'], Decimal('2000.01'))

    def test_locaux_non_occupes_exclus(self):
        data = repartir_charges(self.batiment, 2026)
        local_ids = {row['local_id'] for row in data['par_local']}
        self.assertEqual(local_ids, {self.local1.id, self.local2.id})

    def test_repartition_proportionnelle_aux_tantiemes(self):
        data = repartir_charges(self.batiment, 2026)
        par_id = {row['local_id']: row['quote_part'] for row in data['par_local']}
        # local1: 300/500 tantièmes ; local2: 200/500.
        self.assertEqual(par_id[self.local1.id], Decimal('1200.01'))
        self.assertEqual(par_id[self.local2.id], Decimal('800.00'))

    def test_mode_surface(self):
        self.batiment.mode_repartition = Batiment.ModeRepartition.SURFACE
        self.batiment.save(update_fields=['mode_repartition'])
        data = repartir_charges(self.batiment, 2026)
        self.assertEqual(data['mode_repartition'], 'surface')
        par_id = {row['local_id']: row['quote_part'] for row in data['par_local']}
        total_quotes_parts = sum(par_id.values())
        self.assertEqual(total_quotes_parts, data['total_depenses'])
        # local1: 60/100 surface ; local2: 40/100.
        self.assertEqual(par_id[self.local1.id], Decimal('1200.01'))
        self.assertEqual(par_id[self.local2.id], Decimal('800.00'))

    def test_sans_base_repartition_repli_parts_egales(self):
        Local.objects.filter(
            id__in=[self.local1.id, self.local2.id]
        ).update(tantiemes=None)
        data = repartir_charges(self.batiment, 2026)
        total_quotes_parts = sum(
            row['quote_part'] for row in data['par_local'])
        self.assertEqual(total_quotes_parts, data['total_depenses'])

    def test_sans_local_occupe_retourne_liste_vide(self):
        Local.objects.filter(
            id__in=[self.local1.id, self.local2.id]
        ).update(statut=Local.Statut.LIBRE)
        data = repartir_charges(self.batiment, 2026)
        self.assertEqual(data['par_local'], [])
        self.assertEqual(data['total_depenses'], Decimal('2000.01'))

    def test_api_endpoint_repartition_charges(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/batiments/{self.batiment.id}/'
            'repartition-charges/?exercice=2026')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['par_local']), 2)

    def test_api_sans_exercice_400(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/batiments/{self.batiment.id}/'
            'repartition-charges/')
        self.assertEqual(resp.status_code, 400)
