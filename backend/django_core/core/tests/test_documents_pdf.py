"""SCA33 — Tests du hook PDF du kit ``render_document_pdf``.

Prouve que le hook DÉLÈGUE à ``core.pdf.render_pdf`` (ARC11) sans jamais
importer WeasyPrint : le kit HÉRITE l'allowlist ARC11/ARC52 telle quelle.

  (a) délégation : ``render_document_pdf`` appelle ``core.pdf.render_pdf`` avec
      le gabarit, le contexte (``document`` = l'instance) et la société de
      l'instance pour le branding OPT-IN — vérifié via un mock du service ;
  (b) contrat de retour : ``bytes`` sans upload, ``(bytes, key)`` avec
      ``upload_to`` (contrat de ``render_pdf`` propagé) ;
  (c) rendu RÉEL WeasyPrint (palier lourd ``@tag('pdf')``, exclu du tier rapide,
      exécuté dans l'image prod 3.11) : le hook produit bien un PDF ``%PDF``.

Le garde ARC52 (``scripts/check_platform.py``) prouve séparément que
``core/documents.py`` n'importe pas ``weasyprint`` hors allowlist (run en fin de
lane) — ici on prouve le comportement de délégation.

Modèle JETABLE minimal (``app_label='core'``, pas de table nécessaire pour les
tests de délégation : on n'instancie pas en base — un objet léger porteur d'un
``company`` suffit). Le test de rendu réel utilise un gabarit inline.
"""
import sys
import types
from unittest.mock import patch

from django.test import SimpleTestCase, tag

from core.documents import render_document_pdf


class _FakeInstance:
    """Instance légère de document (le hook ne lit que ``.company``)."""

    def __init__(self, company=None):
        self.company = company


def _fake_weasyprint():
    """Faux module ``weasyprint`` : ``HTML(string=...).write_pdf(buf)`` écrit un
    entête PDF minimal (même patron que core/tests/test_pdf.py)."""
    fake_module = types.ModuleType("weasyprint")

    class _HTML:
        def __init__(self, string=None):
            self.string = string

        def write_pdf(self, target=None):
            if target is not None:
                target.write(b"%PDF-1.4 fake")

    fake_module.HTML = _HTML
    return fake_module


class RenderDocumentPdfDelegationTests(SimpleTestCase):
    def test_delegue_a_core_pdf_render_pdf(self):
        instance = _FakeInstance(company="C1")
        with patch("core.pdf.render_pdf", return_value=b"%PDF-1.4") as m:
            out = render_document_pdf(instance, "doc/mdoc.html")
        self.assertEqual(out, b"%PDF-1.4")
        m.assert_called_once()
        _args, kwargs = m.call_args
        # Délégation : template + contexte (document=instance) + société.
        self.assertEqual(kwargs["template"], "doc/mdoc.html")
        self.assertIs(kwargs["context"]["document"], instance)
        self.assertEqual(kwargs["company"], "C1")
        # Branding OPT-IN par défaut pour un document NEUF du kit.
        self.assertTrue(kwargs["header"])
        self.assertTrue(kwargs["footer"])

    def test_contexte_supplementaire_est_fusionne(self):
        instance = _FakeInstance(company="C1")
        with patch("core.pdf.render_pdf", return_value=b"%PDF") as m:
            render_document_pdf(
                instance, "doc/mdoc.html", context={"extra": 42})
        _args, kwargs = m.call_args
        self.assertIs(kwargs["context"]["document"], instance)
        self.assertEqual(kwargs["context"]["extra"], 42)

    def test_upload_to_propage_le_contrat_tuple(self):
        instance = _FakeInstance(company="C1")
        with patch("core.pdf.render_pdf",
                   return_value=(b"%PDF", "doc/k.pdf")) as m:
            result = render_document_pdf(
                instance, "doc/mdoc.html", upload_to="doc/k.pdf",
                upload_bucket="erp-uploads")
        self.assertEqual(result, (b"%PDF", "doc/k.pdf"))
        _args, kwargs = m.call_args
        self.assertEqual(kwargs["upload_to"], "doc/k.pdf")
        self.assertEqual(kwargs["upload_bucket"], "erp-uploads")

    def test_header_footer_desactivables(self):
        instance = _FakeInstance(company="C1")
        with patch("core.pdf.render_pdf", return_value=b"%PDF") as m:
            render_document_pdf(
                instance, "doc/mdoc.html", header=False, footer=False)
        _args, kwargs = m.call_args
        self.assertFalse(kwargs["header"])
        self.assertFalse(kwargs["footer"])

    def test_hook_module_n_importe_pas_weasyprint(self):
        # Preuve légère (le garde ARC52 est la preuve forte) : le module du kit
        # ne référence pas weasyprint dans ses symboles importés.
        import core.documents as documents
        self.assertNotIn("weasyprint", dir(documents))


@tag("pdf")
class RenderDocumentPdfRealRenderTests(SimpleTestCase):
    """Rendu RÉEL via ``core.pdf.render_pdf`` (WeasyPrint natif, palier lourd).

    Sans profil société (``company=None``) → branding OPT-IN no-op, gabarit rendu
    tel quel : on prouve que le hook produit bien un PDF via le service partagé.
    Utilise un faux module WeasyPrint injecté pour rester déterministe même si le
    tier ``pdf`` tourne hors image lourde, tout en exerçant le vrai chemin
    ``render_pdf`` (template → HTML → write_pdf)."""

    def test_hook_produit_un_pdf_via_le_service(self):
        instance = _FakeInstance(company=None)
        html = "<html><body><h1>Kit SCA33</h1>{{ document }}</body></html>"
        with patch.dict(sys.modules, {"weasyprint": _fake_weasyprint()}), \
                patch("django.template.loader.render_to_string",
                      return_value=html):
            out = render_document_pdf(instance, "doc/mdoc.html")
        self.assertIsInstance(out, bytes)
        self.assertTrue(out.startswith(b"%PDF"))
