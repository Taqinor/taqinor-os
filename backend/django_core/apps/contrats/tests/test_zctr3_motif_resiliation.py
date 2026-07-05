"""Tests ZCTR3 — Référentiel éditable des motifs de résiliation (close reasons)
+ branchement churn.

Couvre :
- CRUD company-scopé de ``MotifResiliation`` (API), ``company`` posée côté
  serveur.
- ``resilier_contrat`` accepte ``motif_ref`` (en plus du texte libre), refuse
  un motif d'une autre société, l'ancien texte libre reste accepté seul.
- ``mouvements_mrr`` (XCTR7) ventile ``churn_par_motif`` par
  ``motif_ref.libelle`` quand présent, sinon replie sur le texte libre.
- Seeder idempotent (6 motifs standard, additif).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.management.commands.seed_motifs_resiliation import (
    seed_motifs_resiliation_for_company,
)
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    MotifResiliation,
    Resiliation,
)

User = get_user_model()

MOTIFS = "/api/django/contrats/motifs-resiliation/"


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


def make_contrat(company, montant="1000", statut=Contrat.Statut.ACTIF):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut=statut)


class MotifResiliationApiTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr3-api", "Zctr3Api")
        self.admin = make_user(self.co, "zctr3-api-admin", role="admin")

    def test_creer_company_posee_serveur(self):
        api = auth(self.admin)
        res = api.post(
            MOTIFS,
            {"code": "budget", "libelle": "Budget insuffisant",
             "company": 999}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        motif = MotifResiliation.objects.get(id=res.data["id"])
        self.assertEqual(motif.company_id, self.co.id)  # pas 999

    def test_filtre_actif(self):
        MotifResiliation.objects.create(
            company=self.co, code="a", libelle="A", actif=True)
        MotifResiliation.objects.create(
            company=self.co, code="b", libelle="B", actif=False)
        api = auth(self.admin)
        res = api.get(MOTIFS + "?actif=1")
        self.assertEqual(res.status_code, 200, res.content)
        codes = {row["code"] for row in res.data["results"]} \
            if "results" in res.data else {row["code"] for row in res.data}
        self.assertIn("a", codes)
        self.assertNotIn("b", codes)

    def test_unicite_code_par_societe(self):
        MotifResiliation.objects.create(
            company=self.co, code="dup", libelle="Dup 1")
        with self.assertRaises(Exception):
            MotifResiliation.objects.create(
                company=self.co, code="dup", libelle="Dup 2")


class ResilierContratMotifRefTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr3-svc", "Zctr3Svc")
        self.user = make_user(self.co, "zctr3-svc-admin", role="admin")
        self.autre_co = make_company("zctr3-autre", "Zctr3Autre")

    def test_resiliation_avec_motif_ref_meme_societe(self):
        motif = MotifResiliation.objects.create(
            company=self.co, code="prix", libelle="Prix trop élevé")
        contrat = make_contrat(self.co)
        resiliation = services.resilier_contrat(
            contrat, motif="texte libre additionnel", motif_ref=motif,
            auteur=self.user)
        self.assertEqual(resiliation.motif_ref_id, motif.id)
        self.assertEqual(resiliation.motif, "texte libre additionnel")

    def test_resiliation_motif_ref_autre_societe_refusee(self):
        motif_autre = MotifResiliation.objects.create(
            company=self.autre_co, code="prix", libelle="Prix trop élevé")
        contrat = make_contrat(self.co)
        with self.assertRaises(services.ResiliationError):
            services.resilier_contrat(
                contrat, motif_ref=motif_autre, auteur=self.user)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)
        self.assertFalse(Resiliation.objects.filter(contrat=contrat).exists())

    def test_resiliation_sans_motif_ref_texte_libre_seul_toujours_accepte(self):
        contrat = make_contrat(self.co)
        resiliation = services.resilier_contrat(
            contrat, motif="Raison en texte libre", auteur=self.user)
        self.assertIsNone(resiliation.motif_ref_id)
        self.assertEqual(resiliation.motif, "Raison en texte libre")


class MouvementsMrrChurnParMotifRefTests(TestCase):
    """XCTR7 ventile par ``motif_ref.libelle`` quand présent — ZCTR3."""

    def setUp(self):
        self.co = make_company("zctr3-mrr", "Zctr3Mrr")
        self.user = make_user(self.co, "zctr3-mrr-admin", role="admin")

    def _contrat_avec_mrr(self, montant_mensuel="1000"):
        contrat = make_contrat(self.co, montant=montant_mensuel)
        # ``montant_total`` est un cache posé CÔTÉ SERVEUR (recalculé par
        # ``services.recalculer_total_echeancier``/``ajouter_ligne_echeance`` —
        # jamais dérivé automatiquement des ``LigneEcheance``) : on le pose
        # directement à la création, comme ``test_mrr_mouvements.py``.
        EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True,
            statut=EcheancierContrat.Statut.ACTIF,
            montant_total=Decimal(montant_mensuel))
        from apps.contrats.models import LigneEcheance
        LigneEcheance.objects.create(
            company=self.co, echeancier=contrat.echeanciers.first(),
            numero=1, date_echeance=timezone.localdate() + timedelta(days=10),
            montant=Decimal(montant_mensuel))
        return contrat

    def test_churn_ventile_par_motif_ref_libelle(self):
        motif = MotifResiliation.objects.create(
            company=self.co, code="concurrent",
            libelle="Parti chez un concurrent")
        contrat = self._contrat_avec_mrr("1500")
        today = timezone.localdate()
        services.resilier_contrat(
            contrat, motif_ref=motif, date_effet=today, auteur=self.user,
            snapshot=False)

        res = selectors.mouvements_mrr(
            self.co, today - timedelta(days=1), today + timedelta(days=1))

        self.assertIn("Parti chez un concurrent", res["churn_par_motif"])
        self.assertLess(
            res["churn_par_motif"]["Parti chez un concurrent"], 0)

    def test_churn_replie_sur_texte_libre_sans_motif_ref(self):
        contrat = self._contrat_avec_mrr("800")
        today = timezone.localdate()
        services.resilier_contrat(
            contrat, motif="Client mécontent", date_effet=today,
            auteur=self.user, snapshot=False)

        res = selectors.mouvements_mrr(
            self.co, today - timedelta(days=1), today + timedelta(days=1))

        self.assertIn("Client mécontent", res["churn_par_motif"])


class SeedMotifsResiliationTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr3-seed", "Zctr3Seed")

    def test_seed_cree_6_motifs(self):
        created = seed_motifs_resiliation_for_company(self.co)
        self.assertEqual(created, 6)
        self.assertEqual(
            MotifResiliation.objects.filter(company=self.co).count(), 6)

    def test_seed_idempotent_ne_duplique_pas(self):
        seed_motifs_resiliation_for_company(self.co)
        created_second = seed_motifs_resiliation_for_company(self.co)
        self.assertEqual(created_second, 0)
        self.assertEqual(
            MotifResiliation.objects.filter(company=self.co).count(), 6)

    def test_seed_ne_touche_pas_un_motif_edite(self):
        seed_motifs_resiliation_for_company(self.co)
        motif = MotifResiliation.objects.get(company=self.co, code="prix")
        motif.libelle = "Prix — édité par le fondateur"
        motif.save(update_fields=['libelle'])

        seed_motifs_resiliation_for_company(self.co)

        motif.refresh_from_db()
        self.assertEqual(motif.libelle, "Prix — édité par le fondateur")
