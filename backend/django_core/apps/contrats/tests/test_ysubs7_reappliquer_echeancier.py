"""Tests YSUBS7 — Indexation qui re-tarife l'échéancier de facturation.

Couvre :
- ``reappliquer_montant_echeancier`` ajuste les ``LigneEcheance`` FUTURES
  non facturées du delta, recalcule ``montant_total``, journalise au chatter.
- Les échéances DÉJÀ facturées (``facture_id`` non NULL) restent intouchées.
- Les échéances PASSÉES (``date_echeance < date_effet``) restent intouchées.
- Delta nul = no-op.
- ``appliquer_indexation`` (CONTRAT32) déclenche automatiquement le
  re-tarifage et ``montant_total`` reflète le nouveau total.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    ContratActivity,
    EcheancierContrat,
    IndexationPrix,
    LigneEcheance,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def make_contrat(company, montant="120000"):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=30))


class ReappliquerMontantEcheancierTests(TestCase):
    def setUp(self):
        self.co = make_company("ysubs7-svc", "Ysubs7Svc")
        self.user = make_user(self.co, "ysubs7-admin", role="admin")
        self.contrat = make_contrat(self.co, montant="12000")
        self.echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=self.contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True,
            statut=EcheancierContrat.Statut.ACTIF)
        today = timezone.localdate()
        # Ligne déjà facturée (passée) — ne doit JAMAIS bouger.
        self.ligne_facturee = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=1,
            date_echeance=today - timedelta(days=10),
            montant=Decimal("1000"), facture_id=42)
        # Ligne future non facturée — DOIT être re-tarifée.
        self.ligne_future_1 = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=2,
            date_echeance=today + timedelta(days=20),
            montant=Decimal("1000"))
        self.ligne_future_2 = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=3,
            date_echeance=today + timedelta(days=50),
            montant=Decimal("1000"))
        # Ligne future mais ANNULÉE — ne doit pas bouger.
        self.ligne_annulee = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=4,
            date_echeance=today + timedelta(days=80),
            montant=Decimal("1000"), statut=LigneEcheance.Statut.ANNULEE)
        services.recalculer_total_echeancier(self.echeancier)

    def test_retarifie_lignes_futures_non_facturees(self):
        today = timezone.localdate()
        nb = services.reappliquer_montant_echeancier(
            self.contrat, delta=Decimal("100"), date_effet=today,
            auteur=self.user)
        self.assertEqual(nb, 2)

        self.ligne_facturee.refresh_from_db()
        self.assertEqual(self.ligne_facturee.montant, Decimal("1000"))

        self.ligne_future_1.refresh_from_db()
        self.assertEqual(self.ligne_future_1.montant, Decimal("1100"))

        self.ligne_future_2.refresh_from_db()
        self.assertEqual(self.ligne_future_2.montant, Decimal("1100"))

        self.ligne_annulee.refresh_from_db()
        self.assertEqual(self.ligne_annulee.montant, Decimal("1000"))

        self.echeancier.refresh_from_db()
        # 1000 (facturée) + 1100 + 1100 = 3200 (annulée exclue).
        self.assertEqual(self.echeancier.montant_total, Decimal("3200"))

        self.assertTrue(
            ContratActivity.objects.filter(
                contrat=self.contrat, field='echeancier_indexation').exists())

    def test_delta_nul_no_op(self):
        today = timezone.localdate()
        nb = services.reappliquer_montant_echeancier(
            self.contrat, delta=Decimal("0"), date_effet=today,
            auteur=self.user)
        self.assertEqual(nb, 0)
        self.ligne_future_1.refresh_from_db()
        self.assertEqual(self.ligne_future_1.montant, Decimal("1000"))
        self.assertFalse(
            ContratActivity.objects.filter(
                contrat=self.contrat, field='echeancier_indexation').exists())

    def test_date_effet_future_ignore_ligne_avant_effet(self):
        today = timezone.localdate()
        # date_effet APRÈS ligne_future_1 (mais avant ligne_future_2).
        date_effet = today + timedelta(days=40)
        nb = services.reappliquer_montant_echeancier(
            self.contrat, delta=Decimal("50"), date_effet=date_effet,
            auteur=self.user)
        self.assertEqual(nb, 1)
        self.ligne_future_1.refresh_from_db()
        self.assertEqual(self.ligne_future_1.montant, Decimal("1000"))
        self.ligne_future_2.refresh_from_db()
        self.assertEqual(self.ligne_future_2.montant, Decimal("1050"))


class ApplyIndexationRetarifeEcheancierTests(TestCase):
    """``appliquer_indexation`` (CONTRAT32) déclenche le re-tarifage — YSUBS7."""

    def setUp(self):
        self.co = make_company("ysubs7-idx", "Ysubs7Idx")
        self.user = make_user(self.co, "ysubs7-idx-admin", role="admin")
        self.contrat = make_contrat(self.co, montant="100000")
        self.echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=self.contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True,
            statut=EcheancierContrat.Statut.ACTIF)
        today = timezone.localdate()
        self.ligne_future = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=1,
            date_echeance=today + timedelta(days=15),
            montant=Decimal("8333.33"))
        services.recalculer_total_echeancier(self.echeancier)

    def test_indexation_avec_delta_retarifie_echeance_future(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        res = services.appliquer_indexation(
            idx, valeur_actuelle=Decimal("110"), auteur=self.user)
        self.assertIsNotNone(res["avenant"])
        self.assertEqual(res["lignes_reappliquees"], 1)

        self.ligne_future.refresh_from_db()
        self.assertEqual(
            self.ligne_future.montant, Decimal("8333.33") + res["delta"])

    def test_indexation_delta_nul_ne_retarifie_rien(self):
        idx = IndexationPrix.objects.create(
            company=self.co, contrat=self.contrat, indice="BTP",
            valeur_base=Decimal("100"), part_fixe=Decimal("0"))
        res = services.appliquer_indexation(
            idx, valeur_actuelle=Decimal("100"), auteur=self.user)
        self.assertIsNone(res["avenant"])
        self.assertEqual(res["lignes_reappliquees"], 0)
        self.ligne_future.refresh_from_db()
        self.assertEqual(self.ligne_future.montant, Decimal("8333.33"))
