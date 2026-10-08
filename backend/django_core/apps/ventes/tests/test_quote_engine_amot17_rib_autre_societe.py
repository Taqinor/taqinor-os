"""AMOT17 (C-AMOT-016, volet legacy) — dès qu'une société a UN champ
d'identité, la ligne « Virement bancaire » ET la ligne de contact du moteur
legacy viennent de SON profil ou sont omises : jamais le RIB ni le contact de
TAQINOR (``0002720029379418``, « Saham », ``contact@taqinor.com``,
``+212 6 61 85 04 10``). Le profil TAQINOR complet rend sa ligne
byte-identique ; ``residential/trust._ligne_rib`` et le legacy appellent la
même règle (``quote_engine.identite``).

Rendu legacy réel (étude + Devis final et une-page) par ``build_quote_data``
puis ``generate_premium_pdf`` (seul WeasyPrint est remplacé par la capture du
HTML).

Test-du-test : remettre « ligne de contact reconstruite seulement si un
contact est fourni » ⇒ ``test_rendu_legacy_aucun_litteral_taqinor`` échoue.
"""
from django.test import SimpleTestCase, TestCase

from apps.parametres.models import CompanyProfile
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

INTERDITS = ('0002720029379418', 'Saham', 'contact@taqinor.com',
             '61&#160;85&#160;04&#160;10', '+212 6 61 85 04 10')


class RibAutreSocieteTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot17-co', nom='AMOT17')
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            nom='SOCIETE 43 SARL', ice='002222222000022', rib='', banque='',
            email='', telephone='')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-AMOT17-1', etude_params=dict(DEUX_OPTIONS))

    def _html(self, options):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(options))
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_amot17_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_rendu_legacy_aucun_litteral_taqinor(self):
        for options in ({'include_etude': True, 'devis_final': True,
                         'include_calepinage': False},
                        {'pdf_mode': 'onepage', 'devis_final': True}):
            with self.subTest(options=options):
                html = self._html(options)
                self.assertTrue(html)
                for interdit in INTERDITS:
                    self.assertNotIn(interdit, html)
                self.assertNotIn('Virement bancaire', html)


class LignesIdentiteTests(SimpleTestCase):
    def tearDown(self):
        G._apply_entreprise(None)

    def test_identifiee_sans_contact_ni_rib_tout_omis(self):
        G._apply_entreprise({'nom': 'SOCIETE 43 SARL', 'ice': '1'})
        self.assertEqual(G.ENT_RIB_LINE, '')
        self.assertEqual(G.ENT_CONTACT_LINE, '')
        self.assertEqual(G.ENT_ETUDE_CONTACT, '')

    def test_conseiller_sans_separateur_orphelin(self):
        G._apply_entreprise({'nom': 'SOCIETE 43 SARL'})
        G._apply_seller({'nom': 'Amine', 'telephone': '0600'})
        self.assertTrue(G.ENT_CONTACT_LINE.startswith('Votre conseiller'))

    def test_profil_taqinor_complet_ligne_rib_identique(self):
        G._apply_entreprise({
            'nom': 'TAQINOR SOLUTION', 'email': 'contact@taqinor.com',
            'telephone': '+212 6 61 85 04 10', 'banque': 'Saham Bank',
            'rib': '022 780 0002720029379418 74'})
        self.assertEqual(
            G.ENT_RIB_LINE,
            '<strong style="color:{cg7}">TAQINOR SOLUTION</strong> · '
            'Saham Bank · RIB 022 780 0002720029379418 74')
