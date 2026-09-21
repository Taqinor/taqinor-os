"""Tests CONTRAT30 — Échéancier de paiement (en-tête + lignes).

Couvre :
- ``ajouter_ligne_echeance`` numérote en max+1 par échéancier (jamais count()+1)
  et recalcule ``montant_total`` (lignes annulées exclues).
- ``pointer_paiement_echeance`` pose statut + date côté serveur, idempotent, ne
  touche jamais ``Contrat.statut``.
- Sélecteurs scopés société.
- API : CRUD en-tête, action ajouter-ligne (numéro côté serveur), lecture seule
  des lignes + action pointer-paiement, scope société, rôle, montant_total non
  falsifiable.
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
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    LigneEcheance,
)

User = get_user_model()

ECHEANCIERS = "/api/django/contrats/echeanciers/"
LIGNES = "/api/django/contrats/lignes-echeance/"


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


def make_contrat(company):
    return Contrat.objects.create(
        company=company, objet="Contrat PPA", montant=Decimal("120000"),
        type_contrat="ppa", statut="actif",
        date_debut=timezone.localdate() - timedelta(days=10))


def make_echeancier(company, contrat):
    return EcheancierContrat.objects.create(
        company=company, contrat=contrat, libelle="Plan 12 mois",
        periodicite="mensuelle")


class EcheancierServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ech-svc", "EchSvc")
        self.contrat = make_contrat(self.co)
        self.ech = make_echeancier(self.co, self.contrat)

    def test_ajouter_ligne_numerote_max_plus_un(self):
        d = timezone.localdate()
        l1 = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        l2 = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d + timedelta(days=30),
            montant=Decimal("1000"))
        self.assertEqual(l1.numero, 1)
        self.assertEqual(l2.numero, 2)
        self.assertEqual(l1.company_id, self.co.id)

    def test_ajouter_ligne_max_plus_un_pas_count(self):
        d = timezone.localdate()
        services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        LigneEcheance.objects.filter(echeancier=self.ech, numero=1).delete()
        l3 = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        self.assertEqual(l3.numero, 3)

    def test_montant_total_recalcule(self):
        d = timezone.localdate()
        services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("2500"))
        self.ech.refresh_from_db()
        self.assertEqual(self.ech.montant_total, Decimal("3500"))

    def test_montant_total_exclut_annulees(self):
        d = timezone.localdate()
        ligne = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("2000"))
        ligne.statut = LigneEcheance.Statut.ANNULEE
        ligne.save(update_fields=["statut"])
        services.recalculer_total_echeancier(self.ech)
        self.ech.refresh_from_db()
        self.assertEqual(self.ech.montant_total, Decimal("2000"))

    def test_pointer_paiement(self):
        d = timezone.localdate()
        ligne = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        services.pointer_paiement_echeance(ligne)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, LigneEcheance.Statut.PAYEE)
        self.assertEqual(ligne.date_paiement, timezone.localdate())
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, "actif")

    def test_pointer_paiement_idempotent(self):
        d = timezone.localdate()
        ligne = services.ajouter_ligne_echeance(
            self.ech, date_echeance=d, montant=Decimal("1000"))
        services.pointer_paiement_echeance(ligne)
        d1 = ligne.date_paiement
        services.pointer_paiement_echeance(
            ligne, today=timezone.localdate() + timedelta(days=5))
        ligne.refresh_from_db()
        self.assertEqual(ligne.date_paiement, d1)


class EcheancierSelectorTests(TestCase):
    def test_scope_societe(self):
        co = make_company("ech-sel", "EchSel")
        contrat = make_contrat(co)
        ech = make_echeancier(co, contrat)
        autre_co = make_company("ech-sel-2", "EchSel2")
        autre = make_contrat(autre_co)
        make_echeancier(autre_co, autre)
        self.assertEqual(selectors.echeanciers_contrat(contrat).count(), 1)
        services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate(), montant=Decimal("100"))
        self.assertEqual(selectors.lignes_echeancier(ech).count(), 1)


class EcheancierApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ech-api", "EchApi")
        self.admin = make_user(self.co, "ech-api-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def test_creer_echeancier_company_serveur(self):
        api = auth(self.admin)
        res = api.post(
            ECHEANCIERS,
            {"contrat": self.contrat.id, "libelle": "Plan",
             "periodicite": "mensuelle", "montant_total": "999999",
             "company": 999},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        ech = EcheancierContrat.objects.get(id=res.data["id"])
        self.assertEqual(ech.company_id, self.co.id)  # pas 999
        self.assertEqual(ech.montant_total, Decimal("0"))  # pas 999999

    def test_ajouter_ligne_endpoint(self):
        ech = make_echeancier(self.co, self.contrat)
        api = auth(self.admin)
        res = api.post(
            f"{ECHEANCIERS}{ech.id}/ajouter-ligne/",
            {"date_echeance": str(timezone.localdate()), "montant": "1500",
             "numero": 99},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["numero"], 1)  # pas 99
        ech.refresh_from_db()
        self.assertEqual(ech.montant_total, Decimal("1500"))

    def test_lignes_lecture_seule_et_pointer(self):
        ech = make_echeancier(self.co, self.contrat)
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate(), montant=Decimal("100"))
        api = auth(self.admin)
        # POST direct sur la ressource ligne refusé (lecture seule).
        res_post = api.post(
            LIGNES, {"echeancier": ech.id, "numero": 5,
                     "date_echeance": str(timezone.localdate()),
                     "montant": "1"},
            format="json")
        self.assertEqual(res_post.status_code, 405, res_post.content)
        # Action pointer-paiement.
        res = api.post(
            f"{LIGNES}{ligne.id}/pointer-paiement/", {}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data["statut"], "payee")
        self.assertIsNotNone(res.data["date_paiement"])

    def test_scope_societe_endpoint(self):
        ech = make_echeancier(self.co, self.contrat)
        autre_co = make_company("ech-api-2", "EchApi2")
        autre_admin = make_user(autre_co, "ech-api-2-admin", role="admin")
        api = auth(autre_admin)
        res = api.get(f"{ECHEANCIERS}?contrat={self.contrat.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)
        # L'action ajouter-ligne est 404 hors société.
        res2 = api.post(
            f"{ECHEANCIERS}{ech.id}/ajouter-ligne/",
            {"date_echeance": str(timezone.localdate())}, format="json")
        self.assertEqual(res2.status_code, 404)

    def test_role_gate(self):
        commercial = make_user(self.co, "ech-api-com", role="commercial")
        api = auth(commercial)
        self.assertEqual(api.get(ECHEANCIERS).status_code, 403)
        self.assertEqual(api.get(LIGNES).status_code, 403)
