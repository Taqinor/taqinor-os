"""NTSAN28 — Statistiques par acte et par convention : les totaux par
convention correspondent EXACTEMENT à la somme de
``FactureSante.part_tiers_payant_ttc`` groupée par convention.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import (
    ActeMedical, Admission, Convention, FactureSante, Patient, Praticien)
from apps.sante.selectors import statistiques_actes_et_conventions
from apps.sante.services import creer_facture_sante, realiser_acte

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class StatistiquesActesConventionsTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-stats-co', 'Clinique Stats')
        self.user = make_user(self.company, 'sante-stats-user')
        self.patient = Patient.objects.create(company=self.company, nom='X')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Z')
        self.admission = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien,
            date_admission=dt.datetime(2026, 8, 1, 9, 0))
        self.acte = ActeMedical.objects.create(
            company=self.company, libelle='Consultation', tarif_base_ttc='200.00')
        self.cnops = Convention.objects.create(
            company=self.company, nom='CNOPS', type=Convention.Type.CNOPS)
        self.cnss = Convention.objects.create(
            company=self.company, nom='CNSS', type=Convention.Type.CNSS)

        acte1 = realiser_acte(
            admission=self.admission, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=dt.datetime(2026, 8, 1, 9, 30))
        creer_facture_sante(
            admission=self.admission, actes_realises=[acte1],
            convention=self.cnops)

        admission2 = Admission.objects.create(
            company=self.company, patient=self.patient,
            praticien=self.praticien,
            date_admission=dt.datetime(2026, 8, 2, 9, 0))
        acte2 = realiser_acte(
            admission=admission2, patient=self.patient,
            praticien=self.praticien, acte=self.acte,
            date_realisation=dt.datetime(2026, 8, 2, 9, 30))
        creer_facture_sante(
            admission=admission2, actes_realises=[acte2], convention=self.cnss)

    def test_totals_by_convention_match_sum_of_part_tiers_payant(self):
        data = statistiques_actes_et_conventions(self.company)

        for row in data['par_convention']:
            attendu = FactureSante.objects.filter(
                company=self.company,
                convention_id=row['convention_id'],
            ).aggregate(total=Sum('part_tiers_payant_ttc'))['total']
            self.assertEqual(row['ca_tiers_payant'], attendu)

    def test_par_acte_reports_volume_and_ca(self):
        data = statistiques_actes_et_conventions(self.company)

        self.assertEqual(len(data['par_acte']), 1)
        row = data['par_acte'][0]
        self.assertEqual(row['acte_id'], self.acte.id)
        self.assertEqual(row['volume'], 2)
        self.assertEqual(row['chiffre_affaires'], self.acte.tarif_base_ttc * 2)

    def test_endpoint_scoped_by_tenant(self):
        api = auth(self.user)
        resp = api.get('/api/django/sante/factures-sante/statistiques/')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['par_convention']), 2)
