"""Tests XCTR6 — Prorata temporis sur avenant en cours de période.

Couvre :
- avenant à mi-période (jour J/2) → montants prorata exacts (hausse ET baisse) ;
- baisse → ``ventes.Avoir`` créé et lié à la dernière facture du contrat ;
- avenant à date d'échéance (fin de période) → aucun prorata ;
- ligne déjà facturée → ``ProrataError``.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Avoir

from apps.contrats import services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def make_contrat_ech(company, *, client=True, periodicite="mensuelle"):
    cli = Client.objects.create(company=company, nom="Client SARL") if client \
        else None
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal("12000"),
        type_contrat="om", statut="actif",
        client_id=cli.id if cli else None)
    ech = EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite=periodicite,
        facturation_active=True)
    return contrat, ech


class CalculerProrataTests(TestCase):
    def setUp(self):
        self.co = make_company("prorata-calc", "ProrataCalc")

    def test_hausse_mi_periode(self):
        contrat, ech = make_contrat_ech(self.co)
        # Période mensuelle [2026-06-01, 2026-07-01[ (30 jours réels).
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Extension périmètre",
            date_effet=timezone.datetime(2026, 6, 16).date(),  # mi-période
            montant_delta=Decimal("300"))
        calcul = services.calculer_prorata_avenant(avenant, ligne)
        self.assertEqual(calcul['jours_periode'], 30)
        self.assertEqual(calcul['jours_restants'], 15)
        # 300 * 15/30 = 150.00
        self.assertEqual(calcul['prorata'], Decimal('150.00'))

    def test_baisse_mi_periode(self):
        contrat, ech = make_contrat_ech(self.co)
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Réduction périmètre",
            date_effet=timezone.datetime(2026, 6, 16).date(),
            montant_delta=Decimal("-300"))
        calcul = services.calculer_prorata_avenant(avenant, ligne)
        self.assertEqual(calcul['prorata'], Decimal('-150.00'))

    def test_avenant_a_date_echeance_aucun_prorata(self):
        contrat, ech = make_contrat_ech(self.co)
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Avenant à échéance",
            date_effet=fin,  # exactement à la fin de période
            montant_delta=Decimal("300"))
        calcul = services.calculer_prorata_avenant(avenant, ligne)
        self.assertEqual(calcul['prorata'], Decimal('0.00'))

    def test_periodicite_unique_non_calculable(self):
        contrat, ech = make_contrat_ech(self.co, periodicite="unique")
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate(), montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Avenant", date_effet=timezone.localdate(),
            montant_delta=Decimal("300"))
        self.assertIsNone(services.calculer_prorata_avenant(avenant, ligne))


class AppliquerProrataTests(TestCase):
    def setUp(self):
        self.co = make_company("prorata-apply", "ProrataApply")
        self.user = make_user(self.co, "prorata-apply-admin")

    def test_hausse_cree_ligne_complementaire(self):
        contrat, ech = make_contrat_ech(self.co)
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Extension",
            date_effet=timezone.datetime(2026, 6, 16).date(),
            montant_delta=Decimal("300"))
        resultat = services.appliquer_prorata_avenant(
            avenant, ligne, auteur=self.user)
        self.assertIsNotNone(resultat['ligne_complementaire'])
        self.assertIsNone(resultat['avoir'])
        self.assertEqual(
            resultat['ligne_complementaire'].montant, Decimal('150.00'))
        self.assertEqual(
            resultat['ligne_complementaire'].date_echeance, fin)

    def test_baisse_cree_avoir_lie(self):
        contrat, ech = make_contrat_ech(self.co)
        # Facture une première échéance pour avoir une facture à créditer.
        ligne1 = services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate() - timedelta(days=30),
            montant=Decimal("1000"))
        facture = services.facturer_ligne_echeance(ligne1, user=self.user)

        fin = timezone.datetime(2026, 7, 1).date()
        ligne2 = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Réduction",
            date_effet=timezone.datetime(2026, 6, 16).date(),
            montant_delta=Decimal("-300"))
        resultat = services.appliquer_prorata_avenant(
            avenant, ligne2, auteur=self.user)
        self.assertIsNone(resultat['ligne_complementaire'])
        self.assertIsNotNone(resultat['avoir'])
        avoir = resultat['avoir']
        self.assertEqual(avoir.montant_ttc, Decimal('150.00'))
        self.assertEqual(avoir.facture_id, facture.id)
        self.assertEqual(Avoir.objects.filter(company=self.co).count(), 1)

    def test_baisse_sans_facture_anterieure_aucun_avoir(self):
        contrat, ech = make_contrat_ech(self.co)
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Réduction",
            date_effet=timezone.datetime(2026, 6, 16).date(),
            montant_delta=Decimal("-300"))
        resultat = services.appliquer_prorata_avenant(
            avenant, ligne, auteur=self.user)
        self.assertIsNone(resultat['avoir'])
        self.assertEqual(Avoir.objects.filter(company=self.co).count(), 0)

    def test_avenant_a_echeance_aucun_effet(self):
        contrat, ech = make_contrat_ech(self.co)
        fin = timezone.datetime(2026, 7, 1).date()
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=fin, montant=Decimal("1000"))
        avenant = services.creer_avenant(
            contrat, objet="Avenant fin de période", date_effet=fin,
            montant_delta=Decimal("300"))
        resultat = services.appliquer_prorata_avenant(
            avenant, ligne, auteur=self.user)
        self.assertIsNone(resultat['ligne_complementaire'])
        self.assertIsNone(resultat['avoir'])
        self.assertEqual(resultat['prorata'], Decimal('0.00'))

    def test_ligne_deja_facturee_refuse(self):
        contrat, ech = make_contrat_ech(self.co)
        ligne = services.ajouter_ligne_echeance(
            ech, date_echeance=timezone.localdate(), montant=Decimal("1000"))
        services.facturer_ligne_echeance(ligne, user=self.user)
        ligne.refresh_from_db()
        avenant = services.creer_avenant(
            contrat, objet="Avenant tardif",
            date_effet=timezone.localdate(), montant_delta=Decimal("100"))
        with self.assertRaises(services.ProrataError):
            services.appliquer_prorata_avenant(avenant, ligne, auteur=self.user)
