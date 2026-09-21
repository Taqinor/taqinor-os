"""Tests XPAI4 — 13e mois & gratifications + runs hors-cycle.

Couvre : prorata de présence (mois complets, embauche/sortie en cours
d'année), le run hors-cycle génère un bulletin de nature ``gratification``
par profil actif, cotisations/IR corrects, cumul annuel consolidé, isolation
tenant, et le garde-fou ``type_run`` sur ``PeriodePaie``.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import BulletinPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_gratification,
    ensure_defaults,
    generer_run_gratification,
    prorata_presence_annee,
    recalculer_cumul_annuel,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ProrataPresenceAnneeTests(TestCase):
    def test_annee_complete(self):
        mois, fraction = prorata_presence_annee(
            date(2020, 1, 1), None, 2026)
        self.assertEqual(mois, 12)
        self.assertEqual(fraction, Decimal('1.00'))

    def test_embauche_en_cours_annee(self):
        # Embauché le 1er juillet -> présent juillet à décembre = 6 mois.
        mois, fraction = prorata_presence_annee(
            date(2026, 7, 1), None, 2026)
        self.assertEqual(mois, 6)
        self.assertEqual(fraction, Decimal('0.50'))

    def test_sortie_en_cours_annee(self):
        # Présent jusqu'à fin mars -> 3 mois.
        mois, fraction = prorata_presence_annee(
            date(2020, 1, 1), date(2026, 3, 15), 2026)
        self.assertEqual(mois, 3)
        self.assertEqual(fraction, Decimal('0.25'))

    def test_hors_annee_zero(self):
        mois, fraction = prorata_presence_annee(
            date(2027, 1, 1), None, 2026)
        self.assertEqual(mois, 0)
        self.assertEqual(fraction, Decimal('0.00'))


class CalculerGratificationTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai4-calc')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='M1', nom='Nom', prenom='P',
            date_embauche=date(2020, 1, 1))
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)

    def test_pleine_annee_brut_egal_salaire_base(self):
        resultat = calculer_gratification(self.profil, self.periode)
        self.assertEqual(resultat['brut'], Decimal('10000.00'))
        self.assertEqual(resultat['mois_presence'], 12)
        self.assertGreater(resultat['cnss_salariale'], 0)
        self.assertGreater(resultat['net_a_payer'], 0)
        self.assertLess(resultat['net_a_payer'], resultat['brut'])

    def test_lignes_non_vides(self):
        resultat = calculer_gratification(self.profil, self.periode)
        codes = {ligne['code'] for ligne in resultat['lignes']}
        self.assertIn('GRATIF_13E', codes)


class GenererRunGratificationTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai4-run')
        ensure_defaults(self.co)
        self.dossier1 = DossierEmploye.objects.create(
            company=self.co, matricule='M1', nom='Un', prenom='P',
            date_embauche=date(2020, 1, 1), statut=DossierEmploye.Statut.ACTIF)
        self.profil1 = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier1,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        self.dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='M2', nom='Deux', prenom='P',
            date_embauche=date(2020, 1, 1), statut=DossierEmploye.Statut.ACTIF)
        self.profil2 = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier2,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'))
        # Profil inactif : ne doit pas générer de bulletin.
        self.dossier3 = DossierEmploye.objects.create(
            company=self.co, matricule='M3', nom='Trois', prenom='P',
            date_embauche=date(2020, 1, 1), statut=DossierEmploye.Statut.SORTI)
        self.profil3 = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier3,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)

    def test_genere_un_bulletin_par_profil_actif(self):
        bulletins = generer_run_gratification(self.periode)
        self.assertEqual(len(bulletins), 2)
        for b in bulletins:
            self.assertEqual(b.type_bulletin, BulletinPaie.TYPE_GRATIFICATION)
            self.assertEqual(b.statut, BulletinPaie.STATUT_BROUILLON)

    def test_refuse_periode_mensuelle(self):
        periode_mensuelle = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6,
            type_run=PeriodePaie.TYPE_RUN_MENSUEL)
        with self.assertRaises(ValueError):
            generer_run_gratification(periode_mensuelle)

    def test_cumul_annuel_consolide_apres_validation(self):
        bulletins = generer_run_gratification(self.periode)
        for b in bulletins:
            b.statut = BulletinPaie.STATUT_VALIDE
            b.save()
        cumul = recalculer_cumul_annuel(self.profil1, 2026)
        self.assertEqual(cumul.brut, Decimal('8000.00'))
        self.assertEqual(cumul.nombre_bulletins, 1)

    def test_periode_mensuelle_et_hors_cycle_coexistent(self):
        # Le couple unique (company, annee, mois, type_run) permet un run
        # hors-cycle sur le même (annee, mois) qu'un run mensuel.
        periode_mensuelle = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_MENSUEL)
        self.assertNotEqual(periode_mensuelle.id, self.periode.id)
        self.assertEqual(
            PeriodePaie.objects.filter(
                company=self.co, annee=2026, mois=12).count(), 2)

    def test_isolation_tenant(self):
        autre = make_company('xpai4-run-autre')
        ensure_defaults(autre)
        dossier = DossierEmploye.objects.create(
            company=autre, matricule='A1', nom='Autre', prenom='P',
            date_embauche=date(2020, 1, 1), statut=DossierEmploye.Statut.ACTIF)
        ProfilPaie.objects.create(
            company=autre, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('5000'))
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        bulletins = generer_run_gratification(periode_autre)
        self.assertEqual(len(bulletins), 1)
        self.assertEqual(bulletins[0].company_id, autre.id)
