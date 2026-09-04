"""Tests XFLT2/AUD725 — Génération des coûts récurrents de contrat.

Couvre :
- Modèle ``EcheanceContrat`` (LEGACY, AUD725) : ``unique_together``
  (contrat, period), validation ``clean`` (société du contrat) — le modèle
  reste testé pour les lignes historiques déjà en base, mais n'est plus
  ALIMENTÉ par le service depuis AUD725.
- Service ``generer_couts_contrat(company, period)`` (AUD725 — écrit dans
  ``CoutVehicule``, catégorie ``contrat``, au lieu d'``EcheanceContrat``) :
  - AUD725 (RED avant fix) : le coût récurrent d'un contrat actif atteint
    désormais le grand livre (``CoutVehicule``) ET ``selectors.
    ledger_vehicule`` — avant le fix, aucune ligne n'apparaissait nulle part
    (ni ``CoutVehicule``, ni le ledger) tant que ``EcheanceContrat`` restait
    la seule cible d'écriture ;
  - deux exécutions sur la même période ne créent qu'une ligne (idempotence,
    via ``reference_piece`` déterministe) ;
  - montant respecté (= ``montant_recurrent`` du contrat, quantizé MAD) ;
  - contrat hors période (date_debut/date_fin) ignoré ;
  - contrat sans date_fin (durée indéterminée) toujours actif ;
  - scope société (contrat d'une autre société jamais touché) ;
  - un contrat dont le véhicule n'a pas encore d'``ActifFlotte`` est compté
    à part (``nb_sans_actif``), sans écriture, jamais perdu silencieusement ;
  - période invalide lève ``ValueError``.
- Management command ``generer_couts_contrats`` (idempotent, --company,
  --period).
"""
import datetime

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    ContratVehicule,
    CoutVehicule,
    EcheanceContrat,
    Vehicule,
)
from apps.flotte.selectors import ledger_vehicule
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
        self.actif = ActifFlotte.objects.create(
            company=self.co, vehicule=self.veh)

    def test_aud725_cout_atteint_le_grand_livre_et_le_ledger(self):
        """AUD725 — le coût récurrent d'un contrat de leasing apparaît dans
        ``CoutVehicule`` ET dans ``selectors.ledger_vehicule`` (le Cockpit
        Flotte / le ledger-TCO lisent CE modèle, jamais ``EcheanceContrat``).
        """
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            type_contrat=ContratVehicule.TypeContrat.LEASING,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=4500)

        # Avant fix : aucune ligne CoutVehicule, aucune ligne au ledger — le
        # coût du leasing n'atteignait ni le Cockpit Flotte ni le ledger/TCO.
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=self.co, categorie=CoutVehicule.Categorie.CONTRAT
            ).count(), 0)

        resultat = generer_couts_contrat(self.co, "2026-07")

        self.assertEqual(resultat['nb_creees'], 1)
        cout = CoutVehicule.objects.get(
            company=self.co, categorie=CoutVehicule.Categorie.CONTRAT)
        self.assertEqual(cout.actif_flotte_id, self.actif.id)
        self.assertEqual(float(cout.montant), 4500.0)
        self.assertEqual(cout.date, datetime.date(2026, 7, 1))

        # Jamais dans le modèle de repli périmé.
        self.assertEqual(EcheanceContrat.objects.count(), 0)

        ledger = ledger_vehicule(self.co, self.veh.id)
        sources_contrat = [
            ligne for ligne in ledger['lignes']
            if ligne['categorie'] == CoutVehicule.Categorie.CONTRAT]
        self.assertEqual(len(sources_contrat), 1)
        self.assertEqual(sources_contrat[0]['montant'], 4500.0)

    def test_deux_executions_meme_periode_une_ligne(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=4500)
        r1 = generer_couts_contrat(self.co, "2026-07")
        r2 = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(r1['nb_creees'], 1)
        self.assertEqual(r2['nb_creees'], 0)
        self.assertEqual(r2['nb_existantes'], 1)
        self.assertEqual(
            CoutVehicule.objects.filter(
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 1)

    def test_montant_respecte(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=5250.50)
        generer_couts_contrat(self.co, "2026-07")
        cout = CoutVehicule.objects.get(
            categorie=CoutVehicule.Categorie.CONTRAT)
        self.assertEqual(float(cout.montant), 5250.50)
        self.assertEqual(cout.date, datetime.date(2026, 7, 1))

    def test_contrat_pas_encore_commence_ignore(self):
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2027, 1, 1), montant_recurrent=1000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 0)
        self.assertEqual(
            CoutVehicule.objects.filter(
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 0)

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
        ActifFlotte.objects.create(company=autre, vehicule=veh_b)
        ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=1000)
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=2000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 1)
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=autre,
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 0)

    def test_contrat_sans_actif_flotte_compte_a_part(self):
        """AUD725 — un véhicule sans ``ActifFlotte`` (créé séparément) ne
        peut pas recevoir de ``CoutVehicule`` (FK non-nulle) : le contrat est
        compté dans ``nb_sans_actif``, jamais silencieusement perdu ni en
        échec."""
        veh_sans_actif = make_vehicule(self.co, "SANS-ACTIF")
        ContratVehicule.objects.create(
            company=self.co, vehicule=veh_sans_actif,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=1000)
        result = generer_couts_contrat(self.co, "2026-07")
        self.assertEqual(result['nb_contrats_actifs'], 1)
        self.assertEqual(result['nb_creees'], 0)
        self.assertEqual(result['nb_sans_actif'], 1)

    def test_periode_invalide_leve_valueerror(self):
        with self.assertRaises(ValueError):
            generer_couts_contrat(self.co, "not-a-period")


class GenererCoutsContratsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company("ecc-cmd", "Ecc Cmd")
        self.veh = make_vehicule(self.co, "ECMD")
        ActifFlotte.objects.create(company=self.co, vehicule=self.veh)
        ContratVehicule.objects.create(
            company=self.co, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=1500)

    def test_command_idempotent(self):
        call_command('generer_couts_contrats', period='2026-08')
        call_command('generer_couts_contrats', period='2026-08')
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=self.co,
                categorie=CoutVehicule.Categorie.CONTRAT,
                date=datetime.date(2026, 8, 1)).count(), 1)

    def test_command_filtre_company(self):
        autre = make_company("ecc-cmd-b", "Ecc Cmd B")
        veh_b = make_vehicule(autre, "B")
        ActifFlotte.objects.create(company=autre, vehicule=veh_b)
        ContratVehicule.objects.create(
            company=autre, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1), montant_recurrent=999)
        call_command(
            'generer_couts_contrats', company='ecc-cmd', period='2026-09')
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=self.co,
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 1)
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=autre,
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 0)


# ── AUD725 — Beat Celery mensuel (avant : ni beat ni bouton, et écrivait
#    dans un modèle jamais exposé) ─────────────────────────────────────────

class GenererCoutsContratMensuelTaskTests(TestCase):
    """Couvre ``apps.flotte.tasks.generer_couts_contrat_mensuel`` : boucle
    par société active, idempotence, isolation d'échec, et enregistrement
    dans ``erp_agentique.celery.app.conf.beat_schedule``."""

    def setUp(self):
        self.co_a = make_company("cc-task-a", "CC Task A")
        self.co_b = make_company("cc-task-b", "CC Task B")
        veh_a = make_vehicule(self.co_a, "TSKC-A")
        ActifFlotte.objects.create(company=self.co_a, vehicule=veh_a)
        ContratVehicule.objects.create(
            company=self.co_a, vehicule=veh_a,
            date_debut=datetime.date(2020, 1, 1), montant_recurrent=2500)
        # Société B : aucun contrat actif (aucun coût ne doit être créé).
        make_vehicule(self.co_b, "TSKC-B")

    def test_generates_couts_per_company(self):
        from apps.flotte.tasks import generer_couts_contrat_mensuel

        resultat = generer_couts_contrat_mensuel()
        self.assertGreaterEqual(resultat["societes"], 2)
        self.assertEqual(resultat["couts_crees"], 1)
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=self.co_a,
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 1)
        self.assertEqual(
            CoutVehicule.objects.filter(
                company=self.co_b,
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 0)

    def test_idempotent_second_run(self):
        from apps.flotte.tasks import generer_couts_contrat_mensuel

        generer_couts_contrat_mensuel()
        resultat = generer_couts_contrat_mensuel()
        self.assertEqual(resultat["couts_crees"], 0)
        self.assertEqual(
            CoutVehicule.objects.filter(
                categorie=CoutVehicule.Categorie.CONTRAT).count(), 1)

    def test_task_registered_in_beat_schedule(self):
        from erp_agentique.celery import app

        task_names = {e["task"] for e in app.conf.beat_schedule.values()}
        self.assertIn("flotte.generer_couts_contrat_mensuel", task_names)
