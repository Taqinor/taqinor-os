"""NTESG4 — Rapport ESG PDF GRI-lite : omission stricte des piliers/sources
sans donnée, bandeau permanent, page-count stable.

``rapport_esg_sections`` est testée SANS dépendance WeasyPrint (logique pure
de sélection des sections) ; le rendu PDF réel (page-count via ``fitz``) est
gardé par ``skipUnless`` comme le reste de la suite qui dépend de WeasyPrint
(cf. ``apps/paie/tests/test_bulletins_periode_pdf.py``).
"""
from datetime import date
from unittest import skipUnless

from django.test import TestCase, tag

from testkit.factories import CompanyFactory

from apps.esg.models import PeriodeReportingESG
from apps.esg.pdf import BANNIERE, rapport_esg_sections

try:
    import weasyprint  # noqa: F401
    import fitz  # noqa: F401
    _PDF_LIBS_DISPONIBLES = True
except ImportError:
    _PDF_LIBS_DISPONIBLES = False


def _make_periode(company):
    return PeriodeReportingESG.objects.create(
        company=company, libelle='T1 2026',
        date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31))


class RapportEsgSectionsTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_empty_company_has_only_garde_section(self):
        periode = _make_periode(self.company)
        sections = rapport_esg_sections(periode)
        self.assertEqual([s['type'] for s in sections], ['garde'])

    def test_indicateurs_section_omits_empty_piliers(self):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=1, annee=2026)
        periode = _make_periode(self.company)
        sections = rapport_esg_sections(periode)
        indic_section = next(
            s for s in sections if s['type'] == 'indicateurs')
        self.assertIn('environnement', indic_section['piliers'])
        self.assertNotIn('social', indic_section['piliers'])
        self.assertNotIn('gouvernance', indic_section['piliers'])

    def test_objectifs_section_present_only_if_objectif_exists(self):
        from apps.esg.models import ObjectifESGTrajectoire

        periode = _make_periode(self.company)
        self.assertNotIn(
            'objectifs', [s['type'] for s in rapport_esg_sections(periode)])
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E1',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        sections_after = rapport_esg_sections(periode)
        self.assertIn('objectifs', [s['type'] for s in sections_after])

    def test_frozen_period_uses_snapshot_not_live_recompute(self):
        from apps.qhse.models import IndicateurESG

        from apps.esg import services

        indicateur = IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=1, annee=2026)
        periode = _make_periode(self.company)
        services.figer_periode(periode)
        indicateur.delete()  # la source disparaît APRÈS le figeage.
        periode.refresh_from_db()
        sections = rapport_esg_sections(periode)
        # Le pilier reste visible : lu depuis le snapshot gelé, pas recalculé.
        indic_section = next(
            s for s in sections if s['type'] == 'indicateurs')
        self.assertIn('environnement', indic_section['piliers'])


@tag('pdf')
class RapportEsgPdfRenderTests(TestCase):
    """Rendu PDF réel — sauté si WeasyPrint/fitz absents de l'environnement."""

    @skipUnless(_PDF_LIBS_DISPONIBLES, 'WeasyPrint/fitz indisponibles')
    def test_pdf_bytes_and_banner_present(self):
        from apps.esg.pdf import generer_rapport_esg_pdf

        company = CompanyFactory()
        periode = _make_periode(company)
        pdf_bytes = generer_rapport_esg_pdf(periode)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        try:
            self.assertEqual(doc.page_count, 1)  # société vide → 1 page garde.
            full_text = ''.join(page.get_text() for page in doc)
            self.assertIn(BANNIERE, full_text)
        finally:
            doc.close()
