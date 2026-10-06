"""CIQ327 — aucune annexe de rétractation « signé à domicile » (loi 31-08)
sur un devis commercial ou industriel.

La loi 31-08 vise les besoins non professionnels (art. 2) : la règle porte
sur le MODE (jamais sur ``type_client``). Test sur le VRAI chemin :
bon de commande coché → ``build_quote_data`` → document legacy COMPLET
(``generate_devis_premium.generate_premium_pdf``, patron
``test_quote_engine_formats._render``) ; le résidentiel garde l'annexe.
"""
from django.test import TestCase

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '12', '1500'),
    ('Onduleur réseau 6 kW', '1', '9000'),
]
ANNEXE = 'Rétractation — Réf.'


class SansAnnexeCi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._n = 0

    def _devis(self, mode):
        from apps.ventes.models import BonCommande
        self._n += 10
        devis = make_devis(self.company, self.user, self.client_obj, LIGNES,
                           reference=f'DEV-CIQ327-{self._n:04d}')
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        BonCommande.objects.create(
            company=self.company, reference=f'BC-CIQ327-{self._n:04d}',
            devis=devis, client=self.client_obj, signe_au_domicile=True)
        devis.refresh_from_db()
        return devis

    def _html_legacy_complet(self, data):
        from apps.ventes.quote_engine import generate_devis_premium as G
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_ciq327.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def test_commercial_et_industriel_sans_annexe(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode)
                self.assertTrue(devis.bon_commande.signe_au_domicile)
                data = build_quote_data(devis, {'pdf_mode': 'full'})
                self.assertFalse(data['signe_au_domicile'])
                html = self._html_legacy_complet(data)
                self.assertNotIn(ANNEXE, html)

    def test_residentiel_garde_l_annexe(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('residentiel')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(data['signe_au_domicile'])
        self.assertIn(ANNEXE, self._html_legacy_complet(data))
