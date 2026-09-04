"""Tests PAIE34 — PDF bulletin conforme + attestations (salaire/travail/domic.).

Couvre (au niveau HTML, indépendant de WeasyPrint) :
* ``render_bulletin_html`` — le bulletin reprend le salarié, la période, les
  lignes et le net à payer.
* ``render_attestation_html`` — chaque type d'attestation (salaire/travail/
  domiciliation) produit le bon titre + corps ; type inconnu → ValueError.
* ``_fmt`` — formatage des montants avec séparateur de milliers.
* Multi-tenant — les helpers ne lisent que des champs publics.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import builders
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class FormatTests(TestCase):
    def test_fmt_milliers(self):
        self.assertEqual(builders._fmt(Decimal('1234.5')), '1 234,50')
        self.assertEqual(builders._fmt(Decimal('0')), '0,00')
        self.assertEqual(builders._fmt(Decimal('-500')), '-500,00')


class BulletinHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('pdf')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='PDF1', nom='Salarié', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='RIB123', banque='BMCE',
            numero_cnss='99887766', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.bulletin)

    def test_bulletin_html(self):
        html = builders.render_bulletin_html(self.bulletin)
        self.assertIn('Bulletin de paie', html)
        self.assertIn('Salarié Test', html)
        self.assertIn('juin 2026', html)
        self.assertIn('99887766', html)
        # Au moins la ligne Salaire de base.
        self.assertIn('Salaire de base', html)
        self.assertIn('Net à payer', html)

    def test_attestation_salaire(self):
        html = builders.render_attestation_html(
            builders.TYPE_SALAIRE, self.profil, bulletin=self.bulletin)
        self.assertIn('Attestation de salaire', html)
        self.assertIn('Salarié Test', html)

    def test_attestation_travail(self):
        html = builders.render_attestation_html(
            builders.TYPE_TRAVAIL, self.profil)
        self.assertIn('Attestation de travail', html)
        self.assertIn('fait', html)

    def test_attestation_domiciliation(self):
        html = builders.render_attestation_html(
            builders.TYPE_DOMICILIATION, self.profil)
        self.assertIn('domiciliation irrévocable', html.lower())
        self.assertIn('RIB123', html)
        self.assertIn('BMCE', html)

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            builders.render_attestation_html('inconnu', self.profil)


class BulletinRetenuesSalarialesTests(TestCase):
    """AUD701 — CLIQUET LÉGAL sur le seul document remis au salarié.

    ÉTAT AVANT LE FIX (le rouge que ces tests ferment) : ``calculer_bulletin``
    n'émettait, sur ses ~14 ``lignes.append``, AUCUNE ligne CNSS/AMO/CIMR/IR
    salariale — ces montants étaient uniquement soustraits arithmétiquement du
    net — et ``render_bulletin_html`` passait directement du tableau des lignes
    à « Net à payer ». Un salarié à 10 000 MAD de base lisait donc « Salaire de
    base 10 000,00 » puis « Net à payer » sans une seule ligne d'explication,
    et voyait « Allocations familiales (part patronale) » imprimée EN POSITIF
    au milieu de ses gains.

    Ces tests échouent si une retenue salariale disparaît du rendu, si une
    charge patronale revient dans le corps du bulletin, ou si la chaîne
    Brut → retenues → net imposable → IR → net à payer perd un maillon.
    """

    def setUp(self):
        self.co = make_company('pdf-retenues')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='RET1', nom='Retenue', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            numero_cnss='11223344', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)

    def test_moteur_emet_les_retenues_salariales(self):
        """Le CONTRAT (contract_samples/bulletin_lignes.json) : les codes."""
        par_code = {
            ligne.code: ligne for ligne in self.bulletin.lignes.all()}
        for code in ('CNSS_SAL', 'AMO_SAL', 'IR'):
            self.assertIn(
                code, par_code,
                f'Le moteur n\'émet plus la retenue salariale {code} : le '
                f'bulletin remis au salarié redevient inexplicable.')
            self.assertGreater(par_code[code].montant, Decimal('0'))
        self.assertEqual(par_code['CNSS_SAL'].montant,
                         self.bulletin.cnss_salariale)
        self.assertEqual(par_code['AMO_SAL'].montant,
                         self.bulletin.amo_salariale)
        self.assertEqual(par_code['IR'].montant, self.bulletin.ir)

    def test_retenues_non_comptees_deux_fois(self):
        """Les lignes ajoutées sont un AFFICHAGE, jamais un second calcul."""
        # Le net à payer reste exactement brut − CNSS − AMO − CIMR − IR
        # (aucune retenue variable sur ce profil).
        b = self.bulletin
        attendu = (b.brut - b.cnss_salariale - b.amo_salariale
                   - b.cimr_salariale - b.ir)
        self.assertEqual(b.net_a_payer, attendu)
        self.assertEqual(b.retenues, Decimal('0.00'))

    def test_bulletin_html_trois_blocs(self):
        html = builders.render_bulletin_html(self.bulletin)
        self.assertIn('Gains', html)
        self.assertIn('Retenues salariales', html)
        self.assertIn('CNSS (part salariale)', html)
        self.assertIn('AMO (part salariale)', html)
        self.assertIn('Impôt sur le revenu', html)
        self.assertIn('Total des retenues salariales', html)

    def test_bulletin_html_chaine_complete(self):
        html = builders.render_bulletin_html(self.bulletin)
        for maillon in ('Brut', 'Brut imposable', 'Frais professionnels',
                        'Net imposable', 'Net à payer'):
            self.assertIn(maillon, html)

    def test_charges_patronales_hors_gains(self):
        """Une charge patronale n'est plus imprimée comme un gain."""
        html = builders.render_bulletin_html(self.bulletin)
        ctx = builders.bulletin_context(self.bulletin)
        codes_patronaux = {ligne['code'] for ligne in ctx['patronal']}
        self.assertIn('ALLOC_FAM', codes_patronaux)
        self.assertIn('FORMATION_PRO', codes_patronaux)
        self.assertNotIn(
            'ALLOC_FAM', {ligne['code'] for ligne in ctx['gains']})
        self.assertIn('NON déduites de votre net', html)

    def test_signe_des_lignes(self):
        """Un gain s'imprime en positif, une retenue avec son sens."""
        ctx = builders.bulletin_context(self.bulletin)
        par_code = {ligne['code']: ligne for ligne in ctx['lignes']}
        self.assertFalse(par_code['SB']['montant_signe'].startswith('-'))
        self.assertTrue(par_code['CNSS_SAL']['montant_signe'].startswith('-'))
        self.assertTrue(par_code['IR']['montant_signe'].startswith('-'))
