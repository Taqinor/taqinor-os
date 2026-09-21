"""Tests YSUBS8 — Activation à la signature génère le plan de facturation.

Couvre :
- ``generer_echeancier_depuis_dates`` matérialise les ``LigneEcheance`` d'un
  échéancier récurrent (``facturation_active``) entre ``date_debut`` et
  ``date_fin`` du contrat, au pas de la ``periodicite``, montant =
  ``Contrat.montant``.
- Idempotence : un second appel ne duplique aucune ligne déjà présente.
- ``facturation_active=False`` → no-op (comportement actuel préservé).
- Dates de contrat manquantes → no-op.
- Périodicité ``unique`` → une seule échéance à ``date_debut``.
- Périodicité ``personnalisee`` (pas de pas standard) → no-op.
- ``activer_si_eligible`` (CONTRAT17) déclenche la génération à l'activation
  automatique quand un échéancier récurrent existe ; un contrat sans
  échéancier récurrent reste inchangé (comportement actuel).
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
    LigneEcheance,
    PartieContrat,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def make_contrat(company, montant="1000", date_debut=None, date_fin=None,
                 statut="actif"):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M mensuel", montant=Decimal(montant),
        type_contrat="om", statut=statut,
        date_debut=date_debut, date_fin=date_fin)


class GenererEcheancierDepuisDatesTests(TestCase):
    def setUp(self):
        self.co = make_company("ysubs8-svc", "Ysubs8Svc")
        self.user = make_user(self.co, "ysubs8-admin", role="admin")

    def test_contrat_mensuel_12_mois_genere_12_echeances(self):
        debut = timezone.localdate().replace(day=1)
        # 12 mois pile : de debut à debut+11 mois (dernier jour du 12e mois).
        fin = Contrat.ajouter_mois(debut, 12) - timedelta(days=1)
        contrat = make_contrat(
            self.co, montant="5000", date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True)

        lignes = services.generer_echeancier_depuis_dates(
            contrat, echeancier, auteur=self.user)

        self.assertEqual(len(lignes), 12)
        self.assertEqual(
            LigneEcheance.objects.filter(echeancier=echeancier).count(), 12)
        for ligne in LigneEcheance.objects.filter(echeancier=echeancier):
            self.assertEqual(ligne.montant, Decimal("5000"))
        echeancier.refresh_from_db()
        self.assertEqual(echeancier.montant_total, Decimal("60000"))
        self.assertTrue(
            ContratActivity.objects.filter(
                contrat=contrat, field='echeancier_genere').exists())

    def test_re_activation_ne_duplique_pas(self):
        debut = timezone.localdate().replace(day=1)
        fin = Contrat.ajouter_mois(debut, 3) - timedelta(days=1)
        contrat = make_contrat(
            self.co, montant="2000", date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True)

        premiere = services.generer_echeancier_depuis_dates(
            contrat, echeancier, auteur=self.user)
        seconde = services.generer_echeancier_depuis_dates(
            contrat, echeancier, auteur=self.user)

        self.assertEqual(len(premiere), 3)
        self.assertEqual(len(seconde), 0)
        self.assertEqual(
            LigneEcheance.objects.filter(echeancier=echeancier).count(), 3)

    def test_facturation_inactive_no_op(self):
        debut = timezone.localdate().replace(day=1)
        fin = Contrat.ajouter_mois(debut, 3) - timedelta(days=1)
        contrat = make_contrat(
            self.co, montant="2000", date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=False)

        lignes = services.generer_echeancier_depuis_dates(contrat, echeancier)
        self.assertEqual(lignes, [])
        self.assertEqual(
            LigneEcheance.objects.filter(echeancier=echeancier).count(), 0)

    def test_dates_contrat_manquantes_no_op(self):
        contrat = make_contrat(self.co, montant="2000")  # pas de dates
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True)
        lignes = services.generer_echeancier_depuis_dates(contrat, echeancier)
        self.assertEqual(lignes, [])

    def test_periodicite_unique_une_seule_echeance(self):
        debut = timezone.localdate()
        fin = debut + timedelta(days=30)
        contrat = make_contrat(
            self.co, montant="15000", date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.UNIQUE,
            facturation_active=True)
        lignes = services.generer_echeancier_depuis_dates(contrat, echeancier)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].date_echeance, debut)
        self.assertEqual(lignes[0].montant, Decimal("15000"))

    def test_periodicite_personnalisee_no_op(self):
        debut = timezone.localdate()
        fin = debut + timedelta(days=90)
        contrat = make_contrat(
            self.co, montant="3000", date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.PERSONNALISEE,
            facturation_active=True)
        lignes = services.generer_echeancier_depuis_dates(contrat, echeancier)
        self.assertEqual(lignes, [])


class ActivationGenereEcheancierTests(TestCase):
    """``activer_si_eligible`` (CONTRAT17) déclenche YSUBS8."""

    def setUp(self):
        self.co = make_company("ysubs8-act", "Ysubs8Act")
        self.user = make_user(self.co, "ysubs8-act-admin", role="admin")

    def _contrat_signe(self, date_debut=None, date_fin=None):
        contrat = Contrat.objects.create(
            company=self.co, objet="Contrat O&M", montant=Decimal("1000"),
            type_contrat="om", statut=Contrat.Statut.EN_APPROBATION,
            date_debut=date_debut, date_fin=date_fin)
        PartieContrat.objects.create(
            company=self.co, contrat=contrat,
            type_partie="client", nom="Client SARL", ordre=0)
        PartieContrat.objects.create(
            company=self.co, contrat=contrat,
            type_partie="prestataire", nom="Taqinor", ordre=1)
        return contrat

    def test_activation_genere_echeancier_recurrent(self):
        debut = timezone.localdate().replace(day=1)
        fin = Contrat.ajouter_mois(debut, 6) - timedelta(days=1)
        contrat = self._contrat_signe(date_debut=debut, date_fin=fin)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True)

        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire",
            auteur=self.user)

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)
        self.assertEqual(
            LigneEcheance.objects.filter(echeancier=echeancier).count(), 6)

    def test_contrat_sans_echeancier_reste_inchange(self):
        contrat = self._contrat_signe(date_debut=None, date_fin=None)
        services.signer_contrat(
            contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        res = services.signer_contrat(
            contrat, signataire_nom="Presta", role_signataire="prestataire",
            auteur=self.user)
        contrat.refresh_from_db()
        self.assertTrue(res["contrat_actif"])
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)
        self.assertEqual(
            EcheancierContrat.objects.filter(contrat=contrat).count(), 0)
