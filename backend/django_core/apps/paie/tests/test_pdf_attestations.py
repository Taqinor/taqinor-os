"""Tests PAIE34 — PDF bulletin conforme + attestations (salaire/travail/domic.).

Couvre (au niveau HTML, indépendant de WeasyPrint) :
* ``render_bulletin_html`` — le bulletin reprend le salarié, la période, les
  lignes et le net à payer.
* ``render_attestation_html`` — chaque type d'attestation (salaire/travail/
  domiciliation) produit le bon titre + corps ; type inconnu → ValueError.
* ``_fmt`` — formatage des montants avec séparateur de milliers.
* Multi-tenant — les helpers ne lisent que des champs publics.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import builders
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    generer_bulletin_stc,
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


class MentionsObligatoiresTests(TestCase):
    """AUD704 — identité employeur, date de paiement, jours/heures payés.

    ÉTAT AVANT LE FIX : ``render_bulletin_html``, lu intégralement, ne
    contenait AUCUN bloc employeur — et ``authentication.Company`` ne portait
    même pas les champs (seul ``nom``). Deux données qui EXISTAIENT déjà en
    base n'étaient pas imprimées non plus : ``PeriodePaie.date_paiement`` et
    ``ProfilPaie.jours_travail_mensuel``/``heures_travail_mensuel``.
    """

    def setUp(self):
        self.co = make_company('mentions')
        self.co.adresse = '12 rue des Ateliers, Casablanca'
        self.co.registre_commerce = 'RC 45678'
        self.co.identifiant_fiscal = 'IF 11223344'
        self.co.ice = '001234567000089'
        self.co.numero_cnss_employeur = 'CNSS-EMP-7788'
        self.co.save()
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='MEN1', nom='Mention', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), jours_travail_mensuel=26,
            heures_travail_mensuel=191,
            numero_cnss='12341234', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6,
            date_paiement=date(2026, 7, 5))
        self.bulletin = generer_bulletin(self.profil, self.periode)

    def test_identite_employeur_imprimee(self):
        html = builders.render_bulletin_html(self.bulletin)
        self.assertIn('12 rue des Ateliers, Casablanca', html)
        self.assertIn('RC 45678', html)
        self.assertIn('IF 11223344', html)
        self.assertIn('001234567000089', html)
        self.assertIn('CNSS-EMP-7788', html)

    def test_date_paiement_et_jours_payes_imprimes(self):
        html = builders.render_bulletin_html(self.bulletin)
        self.assertIn('Date de paiement', html)
        self.assertIn('5 juillet 2026', html)
        self.assertIn('Jours payés', html)
        self.assertIn('Heures payées', html)

    def test_mention_non_renseignee_nest_pas_imprimee_vide(self):
        """Rien n'est inventé : une mention absente ne s'imprime pas."""
        co = make_company('mentions-vides')
        ensure_defaults(co)
        dossier = DossierEmploye.objects.create(
            company=co, matricule='MEN2', nom='Vide', prenom='Test')
        profil = ProfilPaie.objects.create(
            company=co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        periode = PeriodePaie.objects.create(company=co, annee=2026, mois=6)
        bulletin = generer_bulletin(profil, periode)
        html = builders.render_bulletin_html(bulletin)
        self.assertNotIn('ICE :', html)
        self.assertNotIn('RC :', html)
        self.assertNotIn('Date de paiement', html)


class RecuStcTests(TestCase):
    """AUD702 — le reçu de solde de tout compte.

    ÉTAT AVANT LE FIX : ``stc_pdf`` documentait lui-même servir « le dernier
    bulletin STC… brouillon consultable avant validation, comme un aperçu »
    sans filtrer sur le statut, et ``render_stc_html`` imprimait pourtant « Je
    soussigné(e)… lui donne quittance, sans réserve ni restriction » avec deux
    blocs de signature, SANS aucune marque de projet — alors que
    ``generer_bulletin_stc`` supprime et recrée toutes les lignes tant que le
    bulletin est brouillon. Aucune mention protectrice (forclusion de soixante
    jours, deux exemplaires, récapitulatif détaillé) n'apparaissait dans le
    gabarit, et aucune cotisation salariale n'était détaillée.
    """

    def setUp(self):
        self.co = make_company('stc-pdf')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='STC1', nom='Sortant', prenom='Test',
            date_embauche=date(2020, 1, 1))
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            numero_cnss='55667788', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        self.bulletin = generer_bulletin_stc(
            self.profil, self.periode, motif='Démission')

    def test_brouillon_est_un_projet_sans_quittance(self):
        self.assertEqual(self.bulletin.statut, 'brouillon')
        self.assertFalse(builders.stc_est_definitif(self.bulletin))
        html = builders.render_stc_html(self.bulletin)
        self.assertIn('PROJET', html)
        self.assertIn('sans valeur juridique', html)
        # Le cœur du constat : ni quittance, ni signature, sur un brouillon.
        self.assertNotIn('donne quittance', html)
        self.assertNotIn("Signature du salarié", html)

    def test_valide_porte_quittance_et_mentions(self):
        valider_bulletin(self.bulletin)
        self.bulletin.refresh_from_db()
        self.assertTrue(builders.stc_est_definitif(self.bulletin))
        html = builders.render_stc_html(self.bulletin)
        self.assertIn('donne quittance', html)
        self.assertIn("Signature du salarié", html)
        # Mentions protectrices, absentes du gabarit avant AUD702.
        self.assertIn('soixante (60) jours', html)
        self.assertIn('deux exemplaires', html)
        self.assertNotIn('sans valeur juridique', html)

    def test_recu_detaille_les_retenues(self):
        """Le reçu hérite du fix AUD701 : les retenues sont détaillées."""
        html = builders.render_stc_html(self.bulletin)
        self.assertIn('Retenues salariales', html)
        self.assertIn('CNSS (part salariale)', html)
        self.assertIn('Total des retenues salariales', html)
