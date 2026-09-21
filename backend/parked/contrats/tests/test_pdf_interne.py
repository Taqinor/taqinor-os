"""Tests CONTRAT11 — Rendu PDF INTERNE du contrat (hors /proposal).

Le PDF interne est un PDF de TRAVAIL : ce n'est jamais un PDF de devis client
(``/proposal`` reste l'unique chemin des PDF de devis). On vérifie :
- ``_contrat_html`` (pur, sans WeasyPrint) : fusionne le contrat, échappe le
  HTML, ne laisse aucun jeton brut.
- L'endpoint GET /contrats/<id>/pdf/ renvoie ``application/pdf`` (WeasyPrint
  mocké pour rester rapide et sans dépendance lourde au test).
- Accès réservé Responsable/Admin, isolation multi-tenant.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat

User = get_user_model()

BASE = "/api/django/contrats/contrats/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class ContratHtmlTests(TestCase):
    """``_contrat_html`` est pur (pas de WeasyPrint) — testable partout."""

    def setUp(self):
        self.co = make_company("pdf-html", "Html")
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Contrat O&M", reference="C-77",
        )
        PartieContrat.objects.create(
            company=self.co, contrat=self.contrat,
            type_partie=PartieContrat.TypePartie.CLIENT, nom="Client X",
        )

    def test_html_contient_objet_et_reference(self):
        html = services._contrat_html(self.contrat)
        self.assertIn("Contrat O&amp;M", html)  # & échappé
        self.assertIn("C-77", html)

    def test_html_ne_laisse_aucun_jeton_brut(self):
        html = services._contrat_html(self.contrat)
        self.assertNotIn("{{", html)
        self.assertNotIn("}}", html)

    def test_html_echappe_contenu(self):
        contrat = Contrat.objects.create(
            company=self.co, objet="<script>x</script>", reference="C-X",
        )
        html = services._contrat_html(contrat)
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)


class PdfEndpointTests(TestCase):
    """L'endpoint /pdf/ renvoie application/pdf (WeasyPrint mocké)."""

    def setUp(self):
        self.co = make_company("pdf-ep", "EP")
        self.admin = make_user(self.co, "pdf-ep-admin", role="admin")
        self.contrat = Contrat.objects.create(
            company=self.co, objet="Endpoint PDF", reference="C-EP",
        )

    @patch("apps.contrats.services.rendre_contrat_pdf", return_value=b"%PDF-1.4 fake")
    def test_pdf_endpoint_renvoie_pdf(self, _mock):
        api = auth(self.admin)
        resp = api.get(f"{BASE}{self.contrat.id}/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("C-EP.pdf", resp["Content-Disposition"])
        self.assertEqual(resp.content, b"%PDF-1.4 fake")

    @patch("apps.contrats.services.rendre_contrat_pdf", return_value=b"%PDF")
    def test_role_normal_refuse(self, _mock):
        normal = make_user(self.co, "pdf-ep-normal", role="normal")
        api = auth(normal)
        resp = api.get(f"{BASE}{self.contrat.id}/pdf/")
        self.assertEqual(resp.status_code, 403)

    @patch("apps.contrats.services.rendre_contrat_pdf", return_value=b"%PDF")
    def test_isolation_autre_societe_404(self, _mock):
        co_b = make_company("pdf-ep-b", "B")
        admin_b = make_user(co_b, "pdf-ep-admin-b", role="admin")
        api = auth(admin_b)
        resp = api.get(f"{BASE}{self.contrat.id}/pdf/")
        self.assertEqual(resp.status_code, 404)
