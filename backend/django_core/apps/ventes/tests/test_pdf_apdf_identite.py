"""APDF2 (C-APDF-001) — le moteur legacy (étude, Devis final, une-page) suit
la règle de virement du résidentiel : société identifiée sans RIB ni banque →
aucune barre « Virement bancaire » ; RIB du profil → sa ligne ; aucun profil
→ la ligne historique (byte-identique). Une seule fonction
(``quote_engine.identite.ligne_rib``), appelée par les deux moteurs.

Rendu réel du moteur legacy (``build_quote_data`` puis
``generate_premium_pdf`` ; seul l'appel WeasyPrint final est remplacé par la
capture du HTML) ; aucune doublure du moteur.

Test-du-test : remettre ``ENT_RIB_LINE = _ENT_DEFAULT_RIB_LINE`` quand rib
et banque sont vides ⇒ ``test_legacy_etude_final_sans_rib_aucune_ligne``
échoue.
"""
from django.test import SimpleTestCase, TestCase

from apps.parametres.models import CompanyProfile
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import identite
from apps.ventes.quote_engine.residential import trust
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


class RibTenantTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf2-co', nom='APDF2')
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            nom='SOLAIRE EXEMPLE SARL', ice='001111111000011', rib='',
            banque='')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-APDF2-1', etude_params=dict(DEUX_OPTIONS))

    def _html(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(
            {'devis_final': True, 'include_etude': True,
             'include_calepinage': False}))
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_apdf2_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_legacy_etude_final_sans_rib_aucune_ligne(self):
        html = self._html()
        self.assertTrue(html)
        for interdit in ('Saham', '022 780', 'TAQINOR SOLUTION',
                         'Virement bancaire'):
            self.assertNotIn(interdit, html)

    def test_legacy_rib_profil_imprime(self):
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            rib='011 780 0000123456789012 34')
        html = self._html()
        self.assertIn('Virement bancaire', html)
        self.assertIn('RIB 011 780 0000123456789012 34', html)
        self.assertIn('SOLAIRE EXEMPLE SARL', html)
        self.assertNotIn('Saham', html)


class RegleUniqueTests(SimpleTestCase):
    def test_sans_profil_ligne_historique(self):
        G._apply_entreprise(None)
        self.assertEqual(G.ENT_RIB_LINE, G._ENT_DEFAULT_RIB_LINE)
        self.assertIn('Saham Bank', G.ENT_RIB_LINE)
        self.assertIn('TAQINOR SOLUTION', trust._ligne_rib({}))

    def test_meme_fonction_pour_les_deux_moteurs(self):
        for ent in ({'nom': 'X', 'ice': '1'}, {'nom': 'X', 'rib': '011'},
                    {'banque': 'BMCE'}, {}):
            with self.subTest(ent=ent):
                self.assertEqual(trust._ligne_rib({'entreprise': ent}),
                                 identite.ligne_rib(ent))
                G._apply_entreprise(ent)
                attendu = identite.ligne_rib(ent, gras=G._gras_rib_legacy)
                if any(ent.values()):
                    self.assertEqual(G.ENT_RIB_LINE, attendu)
        G._apply_entreprise(None)
