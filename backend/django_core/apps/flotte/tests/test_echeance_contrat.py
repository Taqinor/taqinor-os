"""Tests XFLT2 — Génération des coûts récurrents de contrat.

Couvre :
- Modèle ``EcheanceContrat`` : ``unique_together`` (contrat, period),
  validation ``clean`` (société du contrat).
- Service ``generer_couts_contrat(company, period)`` :
  - deux exécutions sur la même période ne créent qu'une ligne (idempotence) ;
  - montant respecté (= ``montant_recurrent`` du contrat) ;
  - contrat hors période (date_debut/date_fin) ignoré ;
  - contrat sans date_fin (durée indéterminée) toujours actif ;
  - scope société (contrat d'une autre société jamais touché) ;
  - période invalide lève ``ValueError``.
- Management command ``generer_couts_contrats`` (idempotent, --company,
  --period).
"""
import datetime

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.flotte.models import ContratVehicule, EcheanceContrat, Vehicule
from apps.flotte.services import generer_couts_contrat


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_vehicule(company, immat="EC-1"):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")


class EcheanceContratModelTests(TestCase):
    def setUp(self):
        self.co = make_company("ecc-model", "Ecc Model")
        self.veh = make_vehicule(self.co, "EMOD")
        self.contrat = ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            montant_recurrent=3000)

    def test_unique_together_contrat_period(self):
        EcheanceContrat.objects.create(
            company=self.co, contrat=self.contrat, period="2026-06",
            date_echeance=datetime.date(2026, 6, 1), montant=3000)
        with self.assertRaises(Exception):
            EcheanceContrat.objects.create(
                company=self.co, contrat=self.contrat, period="2026-06",
                date_echeance=datetime.date(2026, 6, 1), montant=3000)

    def test_contrat_autre_societe_rejete(self):
        autre = make_company("ecc-model-b", "Ecc Model B")
        veh_b = make_vehicule(autre, "B")
        contrat_b = ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1))
        echeance = EcheanceContrat(
            company=self.co, contrat=contrat_b, period="2026-06",
            date_echeance=datetime.date(2026, 6, 1))
        with self.assertRaises(ValidationError):
            echeance.full_clean()


class GenererCoutsContratServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ecc-svc", "Ecc Svc")
        self.veh = make_vehicule(self.co, "ESVC")

    def test_deux_executions_meme_periode_une_ligne(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=4500)
        r1 = generer_couts_contrat(self.co, "2026-07")
        r2 = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(r1['nb_creees'], 1)
        self.assertEqual(r2['nb_creees'], 0)
        self.assertEqual(r2['nb_existantes'], 1)
        self.assertEqual(EcheanceContrat.objects.count(), 1)

    def test_montant_respecte(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=5250.50)
        generer_couts_contrat(self.co, "2026-07")
        echeance = EcheanceContrat.objects.get()
        self.assertEqual(float(echeance.montant), 5250.50)
        self.assertEqual(echeance.period, "2026-07")
        self.assertEqual(echeance.date_echeance, datetime.date(2026, 7, 1))

    def test_contrat_pas_encore_commence_ignore(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2027, 1, 1), montant_recurrent=1000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 0)
        self.assertEqual(EcheanceContrat.objects.count(), 0)

    def test_contrat_deja_termine_ignore(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2024, 1, 1),
            date_fin=datetime.date(2026, 1, 1), montant_recurrent=1000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 0)

    def test_contrat_sans_date_fin_toujours_actif(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2020, 1, 1), date_fin=None,
            montant_recurrent=1000)
        result = generer_couts_contrat(self.co, "2030-12")
        self.assertEqual(result['nb_contrats_actifs'], 1)
        self.assertEqual(result['nb_creees'], 1)

    def test_scope_societe(self):
        autre = make_company("ecc-svc-b", "Ecc Svc B")
        veh_b = make_vehicule(autre, "B")
        ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=1000)
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=2000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 1)
        self.assertEqual(
            EcheanceContrat.objects.filter(company=autre).count(), 0)

    def test_periode_invalide_leve_valueerror(self):
        with self.assertRaises(ValueError):
            generer_couts_contrat(self.co, "not-a-period")


class GenererCoutsContratsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company("ecc-cmd", "Ecc Cmd")
        self.veh = make_vehicule(self.co, "ECMD")
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=1500)

    def test_command_idempotent(self):
        call_command('generer_couts_contrats', period='2026-08')
        call_command('generer_couts_contrats', period='2026-08')
        self.assertEqual(
            EcheanceContrat.objects.filter(period='2026-08').count(), 1)

    def test_command_filtre_company(self):
        autre = make_company("ecc-cmd-b", "Ecc Cmd B")
        veh_b = make_vehicule(autre, "B")
        ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=999)
        call_command(
            'generer_couts_contrats', company='ecc-cmd', period='2026-09')
        self.assertEqual(
            EcheanceContrat.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            EcheanceContrat.objects.filter(company=autre).count(), 0)
