"""Tests ZRH2 — Acquisition mensuelle automatique + report janvier des congés.

Couvre ``services.accruer_conges_mensuel`` / ``reporter_solde_janvier`` et la
commande ``accruer_conges`` : idempotence (2 exécutions du même mois ne
double-créditent pas), l'ancienneté majore le droit, le report janvier
transfère le solde restant une seule fois, isolation multi-société.
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company
from apps.rh import services
from apps.rh.models import DossierEmploye, SoldeConge


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_employe(company, matricule, date_embauche=None):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P',
        date_embauche=date_embauche,
        statut=DossierEmploye.Statut.ACTIF)


class AccrualServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh2-a', 'A')

    def test_credit_mensuel_simple(self):
        dossier = make_employe(
            self.company, 'ZRH2-1', date_embauche=date(2024, 1, 1))
        resultat = services.accruer_conges_mensuel(
            dossier, annee=2026, mois=1, apply=True)
        self.assertFalse(resultat['deja_acquis'])
        self.assertGreater(resultat['credite'], Decimal('0'))
        solde = SoldeConge.objects.get(
            company=self.company, employe=dossier, annee=2026)
        self.assertEqual(solde.mois_acquis, 1)
        self.assertEqual(solde.acquis, resultat['credite'])

    def test_idempotence_meme_mois(self):
        dossier = make_employe(
            self.company, 'ZRH2-2', date_embauche=date(2024, 1, 1))
        services.accruer_conges_mensuel(
            dossier, annee=2026, mois=3, apply=True)
        solde_apres_1 = SoldeConge.objects.get(
            company=self.company, employe=dossier, annee=2026).acquis
        resultat2 = services.accruer_conges_mensuel(
            dossier, annee=2026, mois=3, apply=True)
        self.assertTrue(resultat2['deja_acquis'])
        solde_apres_2 = SoldeConge.objects.get(
            company=self.company, employe=dossier, annee=2026).acquis
        self.assertEqual(solde_apres_1, solde_apres_2)

    def test_ancienne_majore_le_droit(self):
        recent = make_employe(
            self.company, 'ZRH2-3', date_embauche=date(2025, 6, 1))
        ancien = make_employe(
            self.company, 'ZRH2-4', date_embauche=date(2010, 6, 1))
        r_recent = services.accruer_conges_mensuel(
            recent, annee=2026, mois=6, apply=True)
        r_ancien = services.accruer_conges_mensuel(
            ancien, annee=2026, mois=6, apply=True)
        self.assertGreater(r_ancien['credite'], r_recent['credite'])

    def test_dry_run_ne_credite_pas(self):
        dossier = make_employe(
            self.company, 'ZRH2-5', date_embauche=date(2024, 1, 1))
        services.accruer_conges_mensuel(
            dossier, annee=2026, mois=1, apply=False)
        self.assertFalse(
            SoldeConge.objects.filter(
                company=self.company, employe=dossier, annee=2026).exists())

    def test_dry_run_ne_reporte_pas(self):
        # Dry-run (apply=False) : ne crée JAMAIS la ligne SoldeConge cible.
        dossier = make_employe(
            self.company, 'ZRH2-5b', date_embauche=date(2020, 1, 1))
        SoldeConge.objects.create(
            company=self.company, employe=dossier, annee=2025,
            acquis=Decimal('18'), report=Decimal('0'), pris=Decimal('5'))
        resultat = services.reporter_solde_janvier(
            dossier, annee_precedente=2025, annee_cible=2026, apply=False)
        self.assertEqual(resultat['reporte'], Decimal('13'))
        self.assertFalse(resultat['deja_applique'])
        self.assertFalse(
            SoldeConge.objects.filter(
                company=self.company, employe=dossier, annee=2026).exists())

    def test_report_janvier_transfere_une_seule_fois(self):
        dossier = make_employe(
            self.company, 'ZRH2-6', date_embauche=date(2020, 1, 1))
        SoldeConge.objects.create(
            company=self.company, employe=dossier, annee=2025,
            acquis=Decimal('18'), report=Decimal('0'), pris=Decimal('5'))
        resultat = services.reporter_solde_janvier(
            dossier, annee_precedente=2025, annee_cible=2026, apply=True)
        self.assertFalse(resultat['deja_applique'])
        self.assertEqual(resultat['reporte'], Decimal('13'))
        cible = SoldeConge.objects.get(
            company=self.company, employe=dossier, annee=2026)
        self.assertEqual(cible.report, Decimal('13'))

        resultat2 = services.reporter_solde_janvier(
            dossier, annee_precedente=2025, annee_cible=2026, apply=True)
        self.assertTrue(resultat2['deja_applique'])
        cible.refresh_from_db()
        self.assertEqual(cible.report, Decimal('13'))  # pas doublé.

    def test_report_plafonne(self):
        dossier = make_employe(
            self.company, 'ZRH2-7', date_embauche=date(2020, 1, 1))
        SoldeConge.objects.create(
            company=self.company, employe=dossier, annee=2025,
            acquis=Decimal('30'), report=Decimal('0'), pris=Decimal('0'))
        resultat = services.reporter_solde_janvier(
            dossier, annee_precedente=2025, annee_cible=2026,
            plafond=Decimal('10'), apply=True)
        self.assertEqual(resultat['reporte'], Decimal('10'))


class AccruerCongesCommandTests(TestCase):
    def setUp(self):
        self.company = make_company('zrh2-b', 'B')
        self.dossier = make_employe(
            self.company, 'ZRH2-CMD', date_embauche=date(2022, 1, 1))

    def test_commande_dry_run_par_defaut(self):
        out = StringIO()
        call_command(
            'accruer_conges', '--annee=2026', '--mois=4', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertFalse(
            SoldeConge.objects.filter(
                company=self.company, employe=self.dossier).exists())

    def test_commande_apply_credite(self):
        out = StringIO()
        call_command(
            'accruer_conges', '--annee=2026', '--mois=4', '--apply',
            stdout=out)
        self.assertIn('APPLIQUÉ', out.getvalue())
        solde = SoldeConge.objects.get(
            company=self.company, employe=self.dossier, annee=2026)
        self.assertEqual(solde.mois_acquis, 4)

    def test_isolation_societe(self):
        autre = make_company('zrh2-c', 'C')
        make_employe(autre, 'ZRH2-AUTRE', date_embauche=date(2022, 1, 1))
        call_command(
            'accruer_conges', '--annee=2026', '--mois=4', '--apply',
            f'--company={self.company.id}', stdout=StringIO())
        self.assertFalse(
            SoldeConge.objects.filter(company=autre).exists())
