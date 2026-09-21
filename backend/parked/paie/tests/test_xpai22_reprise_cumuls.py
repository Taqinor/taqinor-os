"""Tests XPAI22 — Reprise des cumuls (go-live en cours d'année).

Couvre : le dry-run signale les matricules inconnus sans rien écrire, le
commit crée un cumul pour un matricule connu, complète un cumul EXISTANT mais
encore vide (``nombre_bulletins == 0``), et ne modifie JAMAIS un cumul déjà
calculé depuis de vrais bulletins validés.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import CumulAnnuel, PeriodePaie, ProfilPaie
from apps.paie.services import (
    commit_reprise_cumuls, dry_run_reprise_cumuls, ensure_defaults,
    generer_bulletin, recalculer_cumul_annuel, valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


CSV_HEADER = (
    'matricule;annee;brut;brut_imposable;net_imposable;ir;cnss_salariale;'
    'amo_salariale;cimr_salariale;frais_professionnels;net_a_payer;'
    'charges_patronales;provision_conges;conges_acquis;conges_pris\n'
)


def _csv(*lignes):
    return (CSV_HEADER + '\n'.join(lignes)).encode('utf-8')


class DryRunRepriseCumulsTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai22-dryrun')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='R1', nom='Nom', prenom='P')

    def test_matricule_connu_sans_alerte(self):
        contenu = _csv(
            'R1;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = dry_run_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(resultat['total_lignes'], 1)
        self.assertEqual(resultat['matricules_inconnus'], [])

    def test_matricule_inconnu_signale(self):
        contenu = _csv(
            'ZZZ;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = dry_run_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(len(resultat['matricules_inconnus']), 1)
        self.assertEqual(
            resultat['matricules_inconnus'][0]['matricule'], 'ZZZ')

    def test_dry_run_ne_cree_rien(self):
        contenu = _csv(
            'R1;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        dry_run_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(
            CumulAnnuel.objects.filter(company=self.co).count(), 0)


class CommitRepriseCumulsTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai22-commit')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='R2', nom='Nom', prenom='Q')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def test_cree_cumul_pour_matricule_connu(self):
        contenu = _csv(
            'R2;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = commit_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(resultat['crees'], 1)
        self.assertEqual(resultat['ignores'], [])
        cumul = CumulAnnuel.objects.get(company=self.co, profil=self.profil)
        self.assertEqual(cumul.brut, Decimal('120000.00'))
        self.assertEqual(cumul.ir, Decimal('5000.00'))

    def test_ignore_matricule_inconnu(self):
        contenu = _csv(
            'INCONNU;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = commit_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(resultat['crees'], 0)
        self.assertEqual(len(resultat['ignores']), 1)

    def test_complete_cumul_vide_existant(self):
        # Cumul déjà créé (import antérieur), toujours à 0 bulletin.
        CumulAnnuel.objects.create(
            company=self.co, profil=self.profil, annee=2026,
            brut=Decimal('0'), nombre_bulletins=0)
        contenu = _csv(
            'R2;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = commit_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(resultat['completes'], 1)
        self.assertEqual(resultat['crees'], 0)
        cumul = CumulAnnuel.objects.get(company=self.co, profil=self.profil)
        self.assertEqual(cumul.brut, Decimal('120000.00'))

    def test_ne_jamais_ecraser_cumul_deja_calcule(self):
        # Un cumul RÉEL (nombre_bulletins > 0) via un vrai bulletin validé.
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        bulletin = generer_bulletin(self.profil, periode)
        valider_bulletin(bulletin)
        recalculer_cumul_annuel(self.profil, 2026)
        cumul_avant = CumulAnnuel.objects.get(
            company=self.co, profil=self.profil, annee=2026)
        self.assertGreater(cumul_avant.nombre_bulletins, 0)
        brut_reel = cumul_avant.brut

        contenu = _csv(
            'R2;2026;999999;999999;999999;999999;999999;999999;0;999999;'
            '999999;999999;999999;18;5')
        resultat = commit_reprise_cumuls(contenu, 'cumuls.csv', self.co)
        self.assertEqual(resultat['crees'], 0)
        self.assertEqual(resultat['completes'], 0)
        self.assertEqual(len(resultat['ignores']), 1)
        cumul_apres = CumulAnnuel.objects.get(
            company=self.co, profil=self.profil, annee=2026)
        self.assertEqual(cumul_apres.brut, brut_reel)

    def test_isolation_societe(self):
        autre_co = make_company('xpai22-autre')
        contenu = _csv(
            'R2;2026;120000;115000;100000;5000;5000;2500;0;3000;95000;'
            '15000;10000;18;5')
        resultat = commit_reprise_cumuls(contenu, 'cumuls.csv', autre_co)
        # Matricule R2 appartient à self.co, pas autre_co → inconnu là-bas.
        self.assertEqual(resultat['crees'], 0)
        self.assertEqual(len(resultat['ignores']), 1)
