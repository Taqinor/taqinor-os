"""NTSAN37 — Annulation & no-show avec pénalité paramétrable : le calcul du
délai d'annulation est correct, et la facturation de pénalité reste
désactivée tant que le paramètre n'est pas explicitement activé.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import (
    FactureSante, ParametragePenaliteAnnulation, Patient, Praticien,
    RendezVous)
from apps.sante.services import annuler_rendez_vous

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


class AnnulerRendezVousServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-annul-co', 'Clinique Annulation')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Z')
        self.patient = Patient.objects.create(company=self.company, nom='X')
        self.rdv = RendezVous.objects.create(
            company=self.company, patient=self.patient, praticien=self.praticien,
            date_heure_debut=timezone.make_aware(dt.datetime(2026, 8, 10, 9, 0)),
            duree_min=30)

    def test_delai_annulation_computed_correctly(self):
        date_annulation = timezone.make_aware(dt.datetime(2026, 8, 9, 9, 0))
        rdv, _ = annuler_rendez_vous(
            self.rdv, annule_par='patient', date_annulation=date_annulation)

        self.assertEqual(rdv.statut, RendezVous.Statut.ANNULE)
        self.assertEqual(rdv.annule_par, 'patient')
        self.assertEqual(rdv.delai_annulation_h, 24.0)

    def test_penalty_disabled_by_default_even_within_delay(self):
        """Aucun ParametragePenaliteAnnulation configuré = jamais de
        pénalité, quel que soit le délai."""
        date_annulation = timezone.make_aware(dt.datetime(2026, 8, 10, 8, 0))
        rdv, penalite_applicable = annuler_rendez_vous(
            self.rdv, annule_par='patient', date_annulation=date_annulation)

        self.assertEqual(rdv.delai_annulation_h, 1.0)
        self.assertFalse(penalite_applicable)
        self.assertFalse(
            FactureSante.objects.filter(company=self.company).exists())

    def test_penalty_stays_disabled_while_actif_false(self):
        ParametragePenaliteAnnulation.objects.create(
            company=self.company, actif=False, delai_min_h=24)

        date_annulation = timezone.make_aware(dt.datetime(2026, 8, 10, 8, 0))
        rdv, penalite_applicable = annuler_rendez_vous(
            self.rdv, annule_par='patient', date_annulation=date_annulation)

        self.assertFalse(penalite_applicable)

    def test_penalty_applicable_when_actif_and_within_delay(self):
        ParametragePenaliteAnnulation.objects.create(
            company=self.company, actif=True, delai_min_h=24,
            montant_penalite_ttc='100.00')

        date_annulation = timezone.make_aware(dt.datetime(2026, 8, 10, 8, 0))
        rdv, penalite_applicable = annuler_rendez_vous(
            self.rdv, annule_par='patient', date_annulation=date_annulation)

        self.assertTrue(penalite_applicable)
        # Jamais de facturation automatique dans ce lot (DECISION founder).
        self.assertFalse(
            FactureSante.objects.filter(company=self.company).exists())

    def test_penalty_not_applicable_when_cancelled_early_enough(self):
        ParametragePenaliteAnnulation.objects.create(
            company=self.company, actif=True, delai_min_h=24)

        date_annulation = timezone.make_aware(dt.datetime(2026, 8, 1, 9, 0))
        rdv, penalite_applicable = annuler_rendez_vous(
            self.rdv, annule_par='clinique', date_annulation=date_annulation)

        self.assertFalse(penalite_applicable)


class RendezVousAnnulerApiTests(TestCase):
    def setUp(self):
        self.company = make_company('sante-annul-api-co', 'Clinique Annulation API')
        self.user = make_user(self.company, 'sante-annul-api')
        self.praticien = Praticien.objects.create(
            company=self.company, nom='Dr. Y')
        self.patient = Patient.objects.create(company=self.company, nom='W')
        self.rdv = RendezVous.objects.create(
            company=self.company, patient=self.patient, praticien=self.praticien,
            date_heure_debut=timezone.make_aware(dt.datetime(2026, 8, 10, 9, 0)),
            duree_min=30)

    def test_annuler_action_sets_statut_and_returns_delai(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/sante/rendezvous/{self.rdv.id}/annuler/',
            {'annule_par': 'patient'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'annule')
        self.assertIn('penalite_applicable', resp.data)
        self.assertFalse(resp.data['penalite_applicable'])

    def test_annuler_rejects_invalid_annule_par(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/sante/rendezvous/{self.rdv.id}/annuler/',
            {'annule_par': 'autre'}, format='json')

        self.assertEqual(resp.status_code, 400)
