"""PV40 — le schéma unifilaire en PDF (``?format=pdf``).

Deux garanties :

* le PDF sort du service de rendu PARTAGÉ ``core.pdf.render_pdf`` (ARC11) —
  jamais d'appel direct à WeasyPrint dans l'app, jamais le moteur de devis
  premium (règle #4) ; le mock porte donc sur ``core.pdf.render_pdf`` ;
* la planche prend le format A4/A3 PAYSAGE que le schéma se donne lui-même
  (largeur déclarée dans son ``viewBox``).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv40_schema_pdf -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import diagram_views as dv
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from core.electrique.schema import FORMAT_A3_PAYSAGE, FORMAT_A4_PAYSAGE

User = get_user_model()

_FAUX_PDF = b'%PDF-1.4 faux'


class FormatDePlancheTest(SimpleTestCase):
    """Le format de page suit la taille que le schéma se donne."""

    def test_brouillon_v1_tient_en_a4_paysage(self):
        from apps.ventes.single_line_diagram import build_single_line_svg
        svg = build_single_line_svg({"n_panneaux": 24})
        self.assertEqual(dv._largeur_svg(svg), 980.0)
        self.assertEqual(dv._format_planche(svg), "A4 landscape")

    def test_planche_du_noyau_a4(self):
        svg = '<svg viewBox="0 0 %s %s"></svg>' % FORMAT_A4_PAYSAGE
        self.assertEqual(dv._format_planche(svg), "A4 landscape")

    def test_planche_du_noyau_a3(self):
        svg = '<svg viewBox="0 0 %s %s"></svg>' % FORMAT_A3_PAYSAGE
        self.assertEqual(dv._format_planche(svg), "A3 landscape")

    def test_largeur_repli_sur_attribut_width(self):
        self.assertEqual(dv._largeur_svg('<svg width="1400" height="900">'),
                         1400.0)
        self.assertEqual(dv._largeur_svg(''), 0.0)
        self.assertEqual(dv._format_planche(''), "A4 landscape")

    def test_enveloppe_html_porte_le_format_et_le_svg(self):
        html = dv._pdf_html('<svg viewBox="0 0 980 260"><g/></svg>')
        self.assertIn("@page { size: A4 landscape; margin: 8mm; }", html)
        self.assertIn('<svg viewBox="0 0 980 260"><g/></svg>', html)
        # Pas de double échappement du littéral CSS 100%.
        self.assertIn("width: 100%;", html)


class SchemaPdfEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv40-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv40-autre")
        self.user = User.objects.create_user(
            username="pv40_vendeur", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV40", email="pv40@example.com")

    def _make_devis(self, company):
        devis = Devis.objects.create(
            company=company, reference="DV-PV40/1", client=self.crm_client,
            etude_params={"phases": 3, "injection": True})
        panneau = Produit.objects.create(
            company=company, nom="Panneau PV 550W mono",
            sku="PV40-PV-%s" % company.id, prix_vente=Decimal("1000"),
            prix_achat=Decimal("1"), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=Decimal("1000"))
        return devis

    def test_post_format_pdf_returns_pdf_bytes(self):
        with mock.patch('core.pdf.render_pdf',
                        return_value=_FAUX_PDF) as rendu:
            resp = self.api.post(
                "/api/django/ventes/schema-unifilaire/?format=pdf",
                {"n_panneaux": 12, "puissance_panneau_wc": 550},
                format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertEqual(resp.content, _FAUX_PDF)
        self.assertIn("schema-unifilaire.pdf", resp["Content-Disposition"])
        # Le rendu passe par le service PARTAGÉ, avec du HTML (pas un template).
        html = rendu.call_args.kwargs["html"]
        self.assertIn("@page { size: A4 landscape", html)
        self.assertIn("<svg", html)

    def test_get_devis_format_pdf(self):
        devis = self._make_devis(self.company)
        with mock.patch('core.pdf.render_pdf', return_value=_FAUX_PDF):
            resp = self.api.get(
                "/api/django/ventes/devis/%s/schema-unifilaire/?format=pdf"
                % devis.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertEqual(resp.content, _FAUX_PDF)
        # Le nom de fichier est assaini (« / » de la référence).
        self.assertIn("schema-unifilaire-DV-PV40-1.pdf",
                      resp["Content-Disposition"])

    def test_pdf_scope_societe(self):
        devis = self._make_devis(self.other)
        with mock.patch('core.pdf.render_pdf', return_value=_FAUX_PDF):
            resp = self.api.get(
                "/api/django/ventes/devis/%s/schema-unifilaire/?format=pdf"
                % devis.id)
        self.assertEqual(resp.status_code, 404)

    def test_pdf_ne_contient_aucun_prix(self):
        devis = self._make_devis(self.company)
        capture = {}

        def _faux_rendu(*args, **kwargs):
            capture["html"] = kwargs.get("html", "")
            return _FAUX_PDF

        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            self.api.get(
                "/api/django/ventes/devis/%s/schema-unifilaire/?format=pdf"
                % devis.id)
        self.assertNotIn("1000", capture["html"])
        self.assertNotIn("prix", capture["html"].lower())

    def test_svg_et_json_inchanges(self):
        devis = self._make_devis(self.company)
        svg = self.api.get(
            "/api/django/ventes/devis/%s/schema-unifilaire/" % devis.id)
        self.assertIn("image/svg+xml", svg["Content-Type"])
        js = self.api.get(
            "/api/django/ventes/devis/%s/schema-unifilaire/?format=json"
            % devis.id)
        self.assertEqual(js.data["params"]["n_panneaux"], 20)
