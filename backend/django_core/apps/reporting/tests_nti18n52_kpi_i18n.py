"""NTI18N52 — les deux KPI i18n dans le catalogue fermé ``KpiAlerte.Kpi``.

Critère de la tâche : les deux KPI apparaissent dans le picker d'alerte KPI et
se calculent SANS requête N+1 sur un jeu de 1000 devis.

Ce que ces tests PROUVENT :

* les deux valeurs sont dans le catalogue fermé ET proposées par
  ``kpis_disponibles`` (le picker) ;
* ``couverture_i18n_pct`` lit le DERNIER instantané NTI18N39 de SA société —
  et vaut ``None`` (jamais 0) tant qu'aucun instantané n'existe ;
* ``documents_non_fr_pct`` vaut ``None`` avec un motif documenté : aucune trace
  de la langue d'un PDF généré n'existe en base ;
* le coût en requêtes ne dépend PAS du nombre de devis : les deux KPI n'en
  lisent aucun (1 requête pour la couverture, 0 pour l'autre).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from core.models import I18nCoverageSnapshot

from . import i18n_kpi
from .kpi_alertes import _KPI_COMPUTERS, kpis_disponibles
from .models import KpiAlerte


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


class CatalogueTests(TestCase):
    def setUp(self):
        self.company = make_company('nti18n52-cat', 'NTI18N52 Catalogue')

    def test_les_deux_valeurs_sont_au_catalogue(self):
        self.assertIn('couverture_i18n_pct', KpiAlerte.Kpi.values)
        self.assertIn('documents_non_fr_pct', KpiAlerte.Kpi.values)

    def test_les_deux_sont_proposees_dans_le_picker(self):
        proposables = kpis_disponibles(self.company)
        self.assertIn('couverture_i18n_pct', proposables)
        self.assertIn('documents_non_fr_pct', proposables)

    def test_les_deux_ont_un_calculateur_branche(self):
        self.assertIn(KpiAlerte.Kpi.COUVERTURE_I18N_PCT, _KPI_COMPUTERS)
        self.assertIn(KpiAlerte.Kpi.DOCUMENTS_NON_FR_PCT, _KPI_COMPUTERS)

    def test_valeurs_tiennent_dans_max_length(self):
        champ = KpiAlerte._meta.get_field('kpi')
        for valeur in ('couverture_i18n_pct', 'documents_non_fr_pct'):
            self.assertLessEqual(len(valeur), champ.max_length)

    def test_alerte_creable_sur_le_kpi_i18n(self):
        alerte = KpiAlerte.objects.create(
            company=self.company, nom='Couverture i18n sous 30 %',
            kpi=KpiAlerte.Kpi.COUVERTURE_I18N_PCT,
            operateur=KpiAlerte.Operateur.INF, seuil=Decimal('30.00'))
        alerte.full_clean()
        self.assertEqual(alerte.kpi, 'couverture_i18n_pct')


class CouvertureI18nTests(TestCase):
    def setUp(self):
        self.company = make_company('nti18n52-a', 'NTI18N52 A')
        self.autre = make_company('nti18n52-b', 'NTI18N52 B')

    def _snap(self, company, semaine, pct):
        return I18nCoverageSnapshot.objects.create(
            company=company, semaine=semaine, couverture_pct=Decimal(pct),
            composants_total=200, composants_migres=50, chaines_en_dur=750)

    def test_none_sans_instantane(self):
        self.assertIsNone(i18n_kpi.couverture_i18n_pct(self.company))

    def test_lit_le_dernier_instantane(self):
        self._snap(self.company, date(2026, 9, 7), '20.0')
        self._snap(self.company, date(2026, 9, 14), '25.5')
        self.assertEqual(
            i18n_kpi.couverture_i18n_pct(self.company), Decimal('25.5'))

    def test_scope_a_la_societe(self):
        self._snap(self.autre, date(2026, 9, 14), '90.0')
        self.assertIsNone(i18n_kpi.couverture_i18n_pct(self.company))

    def test_calculateur_rend_un_decimal(self):
        self._snap(self.company, date(2026, 9, 14), '25.5')
        calc = _KPI_COMPUTERS[KpiAlerte.Kpi.COUVERTURE_I18N_PCT]
        self.assertEqual(calc(self.company, None), Decimal('25.5'))

    def test_calculateur_rend_none_sans_mesure(self):
        calc = _KPI_COMPUTERS[KpiAlerte.Kpi.COUVERTURE_I18N_PCT]
        self.assertIsNone(calc(self.company, None))


class DocumentsNonFrTests(TestCase):
    """Le KPI est ABSENT (None) et le motif est documenté — jamais un chiffre
    approché depuis une préférence client."""

    def setUp(self):
        self.company = make_company('nti18n52-doc', 'NTI18N52 Doc')

    def test_toujours_none_aujourdhui(self):
        self.assertIsNone(i18n_kpi.documents_non_fr_pct(self.company))
        calc = _KPI_COMPUTERS[KpiAlerte.Kpi.DOCUMENTS_NON_FR_PCT]
        self.assertIsNone(calc(self.company, None))

    def test_motif_documente(self):
        self.assertIn('DevisActivity', i18n_kpi.RAISON_DOCUMENTS_NON_FR)
        self.assertIn('proposal', i18n_kpi.RAISON_DOCUMENTS_NON_FR)

    def test_aucun_evenement_de_generation_dans_devisactivity(self):
        """Verrouille la PRÉMISSE du None : si un jour `DevisActivity.Kind`
        gagne un évènement de génération de document, ce test rougit et
        rappelle qu'il faut brancher le KPI pour de vrai."""
        from apps.ventes.models import DevisActivity
        self.assertEqual(
            set(DevisActivity.Kind.values),
            {'creation', 'modification', 'note'})


class CoutEnRequetesTests(TestCase):
    """Le coût ne dépend pas du volume de devis : aucun devis n'est lu."""

    def setUp(self):
        self.company = make_company('nti18n52-n1', 'NTI18N52 N+1')
        I18nCoverageSnapshot.objects.create(
            company=self.company, semaine=date(2026, 9, 14),
            couverture_pct=Decimal('25.5'), composants_total=200,
            composants_migres=50, chaines_en_dur=750)

    def test_couverture_une_seule_requete(self):
        with self.assertNumQueries(1):
            i18n_kpi.couverture_i18n_pct(self.company)

    def test_documents_non_fr_zero_requete(self):
        with self.assertNumQueries(0):
            i18n_kpi.documents_non_fr_pct(self.company)

    def test_les_deux_ensemble_une_seule_requete(self):
        with self.assertNumQueries(1):
            i18n_kpi.kpis_i18n(self.company)
