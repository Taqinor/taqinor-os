"""DC1 — l'identité société du PDF premium vient de CompanyProfile (multi-tenant).

Avant : le moteur imprimait en dur le RC/ICE/RIB/banque/adresse de Taqinor sur
CHAQUE devis, quelle que soit la société → fuite multi-tenant. Ces tests
prouvent qu'un devis d'une société au profil personnalisé rend SON identité et
JAMAIS le RIB/ICE/RC codés en dur de Taqinor.
"""
from django.test import TestCase

from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)


class TestDC1CompanyIdentity(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self):
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Batterie 5 kWh', '1', '14000'),
        ])

    def _capture_html(self, data):
        from apps.ventes.quote_engine import generate_devis_premium as G
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_dc1_identity_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def _set_profile(self, **fields):
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        for k, v in fields.items():
            setattr(p, k, v)
        p.save()
        return p

    def test_builder_exposes_entreprise_block(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self._set_profile(
            nom='SoleilPro SARL', ice='ICE-CUSTOM-999', rc='RC-CUSTOM-42',
            rib='RIB-CUSTOM-777', banque='Ma Banque',
            adresse='12 Avenue du Soleil, Marrakech',
            telephone='0555000111', email='pro@soleil.ma',
        )
        data = build_quote_data(self._devis())
        ent = data.get('entreprise')
        self.assertIsInstance(ent, dict)
        self.assertEqual(ent['nom'], 'SoleilPro SARL')
        self.assertEqual(ent['ice'], 'ICE-CUSTOM-999')
        self.assertEqual(ent['rib'], 'RIB-CUSTOM-777')

    def test_custom_company_identity_rendered(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self._set_profile(
            nom='SoleilPro SARL', ice='ICE-CUSTOM-999', rc='RC-CUSTOM-42',
            rib='RIB-CUSTOM-777', banque='Ma Banque',
            adresse='12 Avenue du Soleil, Marrakech',
            telephone='0555000111', email='pro@soleil.ma',
        )
        data = build_quote_data(self._devis())
        data['devis_final'] = True  # force le bloc RIB à s'afficher
        html = self._capture_html(data)
        # SON identité apparaît…
        self.assertIn('SoleilPro SARL', html)
        self.assertIn('ICE-CUSTOM-999', html)
        self.assertIn('RIB-CUSTOM-777', html)
        # …et JAMAIS l'identité codée en dur de Taqinor.
        self.assertNotIn('003799642000067', html)   # ICE Taqinor
        self.assertNotIn('SGMBMAMCXXX', html)        # BIC Taqinor
        self.assertNotIn('691213', html)             # RC Taqinor
        self.assertNotIn('0002720029379418', html)   # RIB Taqinor

    def test_custom_accent_color_applied(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self._set_profile(nom='SoleilPro SARL', couleur_principale='#123456')
        data = build_quote_data(self._devis())
        html = self._capture_html(data)
        self.assertIn('#123456', html)

    def test_no_identity_fields_keeps_default_rib(self):
        # Un profil dont seuls les champs d'identité légale sont vides garde le
        # RIB par défaut (BIC Taqinor) — le repli reste fonctionnel.
        from apps.ventes.quote_engine.builder import build_quote_data
        # profil vierge (nom = nom de la société, tout le reste vide)
        data = build_quote_data(self._devis())
        data['devis_final'] = True
        html = self._capture_html(data)
        # RIB par défaut conservé (aucun RIB/banque société renseigné)
        self.assertIn('SGMBMAMCXXX', html)
