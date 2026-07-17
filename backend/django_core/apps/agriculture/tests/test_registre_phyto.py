"""Tests NTAGR7 — Registre phytosanitaire ONSSA imprimable (PDF).

Couvre : le PDF liste tous les traitements dans l'ordre chronologique avec
les colonnes réglementaires ONSSA (produit, matière active, n° AMM, dose,
DAR, récolte réelle, conformité), une campagne sans traitement produit un
PDF vide propre (pas d'erreur), l'action API est scopée société.

Skip si WeasyPrint/PyMuPDF sont absents de l'environnement (même garde que
``apps.paie.tests.test_bulletins_periode_pdf``) — le reste de la suite ne
teste le rendu PDF qu'au niveau HTML/texte.
"""
from unittest import skipUnless

from django.test import TestCase, tag

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, IntrantAgricole, Parcelle,
)
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user

try:
    import weasyprint  # noqa: F401
    import fitz  # noqa: F401
    _PDF_LIBS_DISPONIBLES = True
except ImportError:
    _PDF_LIBS_DISPONIBLES = False


def _pdf_text(pdf_bytes):
    # `fitz` est importé conditionnellement en tête de module (garde
    # `_PDF_LIBS_DISPONIBLES`) — cette fonction n'est appelée que depuis des
    # tests `@skipUnless(_PDF_LIBS_DISPONIBLES, ...)`, donc déjà disponible.
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


@tag('pdf')
class RegistrePhytoPdfTests(TestCase):
    def setUp(self):
        self.co = make_company('agr-phyto-a', 'Ferme Phyto A')
        self.admin = make_user(self.co, 'agr-phyto-admin-a', 'admin')
        exploitation = Exploitation.objects.create(company=self.co, nom='Domaine')
        parcelle = Parcelle.objects.create(
            company=self.co, exploitation=exploitation, nom='Parcelle Nord')
        self.campagne = CampagneCulturale.objects.create(
            company=self.co, parcelle=parcelle, culture='Vigne',
            date_recolte_prevue='2026-09-01')
        produit = Produit.objects.create(
            company=self.co, nom='Bouillie bordelaise', prix_vente=95)
        self.intrant = IntrantAgricole.objects.create(
            company=self.co, produit_id=produit.id, categorie='phyto',
            delai_avant_recolte_jours=14, matiere_active='Cuivre',
            numero_amm='AMM-9988', dose_reference_par_ha='3.5')

    @skipUnless(_PDF_LIBS_DISPONIBLES, 'WeasyPrint/PyMuPDF indisponibles ici')
    def test_registre_lists_traitements_chronologically(self):
        self.campagne.etapes.create(
            company=self.co, type_etape='traitement', date='2026-08-01',
            intrant=self.intrant)
        self.campagne.etapes.create(
            company=self.co, type_etape='traitement', date='2026-07-01',
            intrant=self.intrant)
        # Une étape non-traitement ne doit pas apparaître dans le registre.
        self.campagne.etapes.create(
            company=self.co, type_etape='irrigation', date='2026-07-15')

        api = auth(self.admin)
        resp = api.get(
            f'/api/django/agriculture/campagnes/{self.campagne.id}/registre-phyto-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

        texte = _pdf_text(resp.content)
        self.assertIn('Bouillie bordelaise', texte)
        self.assertIn('Cuivre', texte)
        self.assertIn('AMM-9988', texte)
        pos_1er = texte.find('2026-07-01')
        pos_2e = texte.find('2026-08-01')
        self.assertGreater(pos_1er, -1)
        self.assertGreater(pos_2e, -1)
        self.assertLess(pos_1er, pos_2e)

    @skipUnless(_PDF_LIBS_DISPONIBLES, 'WeasyPrint/PyMuPDF indisponibles ici')
    def test_registre_without_traitement_is_clean_empty_pdf(self):
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/agriculture/campagnes/{self.campagne.id}/registre-phyto-pdf/')
        self.assertEqual(resp.status_code, 200)
        texte = _pdf_text(resp.content)
        self.assertIn('Aucun traitement', texte)

    def test_registre_scoped_to_company(self):
        co_b = make_company('agr-phyto-b', 'Ferme Phyto B')
        admin_b = make_user(co_b, 'agr-phyto-admin-b', 'admin')
        api = auth(admin_b)
        resp = api.get(
            f'/api/django/agriculture/campagnes/{self.campagne.id}/registre-phyto-pdf/')
        self.assertEqual(resp.status_code, 404)
