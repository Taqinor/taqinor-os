"""Tests XCTR5 — Journal des cycles de facturation récurrente + exceptions.

Couvre :
- chaque tentative de facturation trace une ligne (généré/échec) ;
- garde anti double-facturation : jamais deux ``genere`` pour la même période ;
- ``rejouer_cycle`` re-tente un échec EXACTEMENT une fois avec succès ;
- API : liste/exceptions + action ``rejouer`` (201 succès, 400 hors garde, rôle).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Facture

from apps.contrats import services
from apps.contrats.models import Contrat, CycleFacturationLog, EcheancierContrat

User = get_user_model()

CYCLES = "/api/django/contrats/cycles-facturation/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_setup(company, *, client=True, facturation_active=True,
               montant="1200"):
    cli = Client.objects.create(company=company, nom="Client SARL") if client \
        else None
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("120000"),
        type_contrat="om", statut="actif",
        client_id=cli.id if cli else None,
        date_debut=timezone.localdate() - timedelta(days=10))
    ech = EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=facturation_active)
    ligne = services.ajouter_ligne_echeance(
        ech, date_echeance=timezone.localdate(), montant=Decimal(montant))
    return contrat, ech, ligne


class EnregistrerCycleTests(TestCase):
    def setUp(self):
        self.co = make_company("cyclelog-svc", "CycleLogSvc")
        self.user = make_user(self.co, "cyclelog-svc-admin")

    def test_journalise_succes(self):
        contrat, ech, ligne = make_setup(self.co, montant="1000")
        facture = services.facturer_ligne_echeance_journalisee(
            ligne, user=self.user)
        log = CycleFacturationLog.objects.get(
            company=self.co, source_id=contrat.id)
        self.assertEqual(log.statut, CycleFacturationLog.Statut.GENERE)
        self.assertEqual(log.facture_id, facture.id)
        self.assertEqual(log.source_type,
                         CycleFacturationLog.SourceType.CONTRAT)

    def test_journalise_echec(self):
        contrat, ech, ligne = make_setup(self.co, facturation_active=False)
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance_journalisee(ligne, user=self.user)
        log = CycleFacturationLog.objects.get(
            company=self.co, source_id=contrat.id)
        self.assertEqual(log.statut, CycleFacturationLog.Statut.ECHEC)
        self.assertTrue(log.motif)

    def test_garde_anti_double_facturation(self):
        """Jamais deux 'genere' pour le même (source, période)."""
        contrat, ech, ligne = make_setup(self.co, montant="1000")
        services.facturer_ligne_echeance_journalisee(ligne, user=self.user)
        # Un second `enregistrer_cycle` explicite pour la même période et le
        # même statut 'genere' doit être refusé.
        with self.assertRaises(services.RejeuError):
            services.enregistrer_cycle(
                self.co,
                source_type=CycleFacturationLog.SourceType.CONTRAT,
                source_id=contrat.id,
                periode=ligne.date_echeance.isoformat(),
                statut=CycleFacturationLog.Statut.GENERE,
            )
        self.assertEqual(
            CycleFacturationLog.objects.filter(
                company=self.co, source_id=contrat.id,
                statut=CycleFacturationLog.Statut.GENERE).count(),
            1)


class RejouerCycleTests(TestCase):
    def setUp(self):
        self.co = make_company("cyclelog-rejeu", "CycleLogRejeu")
        self.user = make_user(self.co, "cyclelog-rejeu-admin")

    def test_rejeu_reussi_une_seule_fois(self):
        contrat, ech, ligne = make_setup(
            self.co, facturation_active=False, montant="1500")
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance_journalisee(ligne, user=self.user)
        log = CycleFacturationLog.objects.get(
            company=self.co, source_id=contrat.id)
        self.assertEqual(log.statut, CycleFacturationLog.Statut.ECHEC)

        # Activer la facturation puis rejouer : succès.
        ech.facturation_active = True
        ech.save(update_fields=['facturation_active'])
        facture = services.rejouer_cycle(log, user=self.user)
        self.assertIsNotNone(facture.id)
        log.refresh_from_db()
        self.assertEqual(log.nb_tentatives, 2)

        # Une seule facture au total pour cette échéance.
        self.assertEqual(
            Facture.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            CycleFacturationLog.objects.filter(
                company=self.co, source_id=contrat.id,
                statut=CycleFacturationLog.Statut.GENERE).count(),
            1)

        # Rejouer une seconde fois lève (déjà généré / ligne déjà facturée).
        with self.assertRaises(services.RejeuError):
            services.rejouer_cycle(log, user=self.user)

    def test_rejeu_refuse_hors_echec(self):
        contrat, ech, ligne = make_setup(self.co, montant="800")
        services.facturer_ligne_echeance_journalisee(ligne, user=self.user)
        log = CycleFacturationLog.objects.get(
            company=self.co, statut=CycleFacturationLog.Statut.GENERE)
        with self.assertRaises(services.RejeuError):
            services.rejouer_cycle(log, user=self.user)


class CycleFacturationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("cyclelog-api", "CycleLogApi")
        self.admin = make_user(self.co, "cyclelog-api-admin")

    def test_liste_scopee_societe(self):
        contrat, ech, ligne = make_setup(self.co, montant="900")
        services.facturer_ligne_echeance_journalisee(ligne, user=self.admin)
        api = auth(self.admin)
        res = api.get(CYCLES)
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.data.get('results', res.data)), 1)

    def test_action_rejouer_succes(self):
        contrat, ech, ligne = make_setup(
            self.co, facturation_active=False, montant="1100")
        with self.assertRaises(services.FacturationError):
            services.facturer_ligne_echeance_journalisee(
                ligne, user=self.admin)
        log = CycleFacturationLog.objects.get(
            company=self.co, source_id=contrat.id)
        ech.facturation_active = True
        ech.save(update_fields=['facturation_active'])

        api = auth(self.admin)
        res = api.post(f"{CYCLES}{log.id}/rejouer/", {}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertIsNotNone(res.data['facture_id'])

    def test_action_rejouer_400_hors_garde(self):
        contrat, ech, ligne = make_setup(self.co, montant="700")
        services.facturer_ligne_echeance_journalisee(ligne, user=self.admin)
        log = CycleFacturationLog.objects.get(
            company=self.co, statut=CycleFacturationLog.Statut.GENERE)
        api = auth(self.admin)
        res = api.post(f"{CYCLES}{log.id}/rejouer/", {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_role_gate(self):
        contrat, ech, ligne = make_setup(self.co, montant="500")
        services.facturer_ligne_echeance_journalisee(ligne, user=self.admin)
        commercial = make_user(self.co, "cyclelog-api-com", role="commercial")
        api = auth(commercial)
        res = api.get(CYCLES)
        self.assertEqual(res.status_code, 403)
