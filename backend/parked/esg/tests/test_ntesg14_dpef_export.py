"""NTESG14 — Export DPEF-friendly (gabarit texte structuré).

Critère d'acceptation : le document généré contient les 4 rubriques, les
sections sans données ERP sont clairement marquées à compléter.
"""
from datetime import date

from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory

from apps.esg.dpef_export import generer_dpef_texte
from apps.esg.models import DocumentPolitiqueESG, PeriodeReportingESG


class DpefExportTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _periode(self):
        return PeriodeReportingESG.objects.create(
            company=self.company, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))

    def test_contains_four_rubriques(self):
        texte = generer_dpef_texte(self._periode())
        for rubrique in (
                "1. Modèle d'affaires", '2. Risques ESG principaux',
                '3. Politiques et résultats', '4. Indicateurs clés'):
            self.assertIn(rubrique, texte)

    def test_bandeau_brouillon_present(self):
        texte = generer_dpef_texte(self._periode())
        self.assertIn('ne constitue pas une DPEF déposée', texte)

    def test_empty_sections_marked_a_completer(self):
        texte = generer_dpef_texte(self._periode())
        self.assertIn('À compléter manuellement', texte)
        self.assertIn(
            'Aucun document de politique RSE publié', texte)
        self.assertIn(
            'Aucun indicateur ESG disponible pour cette période', texte)

    def test_published_document_appears_in_politiques_section(self):
        DocumentPolitiqueESG.objects.create(
            company=self.company, libelle='Charte éthique',
            type_document='charte_ethique',
            statut=DocumentPolitiqueESG.Statut.PUBLIEE,
            date_publication=date(2026, 2, 1), date_revue=date(2026, 6, 1))
        texte = generer_dpef_texte(self._periode())
        self.assertIn('Charte éthique', texte)
        self.assertIn('2026-02-01', texte)

    def test_draft_document_omitted_from_politiques_section(self):
        DocumentPolitiqueESG.objects.create(
            company=self.company, libelle='Brouillon interne',
            type_document='charte_ethique',
            statut=DocumentPolitiqueESG.Statut.BROUILLON)
        texte = generer_dpef_texte(self._periode())
        self.assertNotIn('Brouillon interne', texte)

    def test_indicateurs_reflect_real_data(self):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=42,
            unite='MWh', annee=2026)
        texte = generer_dpef_texte(self._periode())
        self.assertIn('Énergie', texte)
        self.assertIn('42', texte)


class DpefExportApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/periodes-esg/'

    def test_dpef_endpoint_returns_markdown(self):
        periode = PeriodeReportingESG.objects.create(
            company=self.company, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        r = self.client_as().get(f'{self.BASE}{periode.id}/dpef/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/markdown', r['Content-Type'])
        contenu = r.content.decode('utf-8')
        self.assertIn('Déclaration de performance extra-financière', contenu)
