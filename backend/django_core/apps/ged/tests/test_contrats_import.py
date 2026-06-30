"""GED38 — Contrats d'import + tests d'intégration de la surface GED.

Vérifie :
  * la frontière cross-app : `apps.ged.models` n'importe AUCUN modèle d'une app
    business-core (les liaisons sont des FK chaîne ; les lectures/écritures
    cross-app passent par `selectors`/`services`) — miroir du contrat
    import-linter `ged-models-decoupled` ;
  * toutes les routes GED (anciennes + nouvelles GED31/32/35/36) se résolvent ;
  * la surface publique `services`/`selectors` expose bien les points d'entrée
    attendus (régression : un renommage casse ce test, pas un import caché).
"""
import ast
import inspect
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from apps.ged import selectors, services


class GedImportBoundaryTests(TestCase):
    """GED38 — `apps.ged.models` ne dépend d'aucun modèle business-core."""

    FORBIDDEN = (
        'apps.crm.models', 'apps.ventes.models', 'apps.stock.models',
        'apps.sav.models', 'apps.installations.models',
    )

    def test_models_naimporte_aucun_modele_business_core(self):
        source = Path(inspect.getfile(services)).parent / 'models.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
        for mod in self.FORBIDDEN:
            self.assertNotIn(
                mod, imported,
                f'apps.ged.models importe {mod} (utiliser une FK chaîne).')


class GedRouteResolutionTests(TestCase):
    """GED38 — toutes les routes GED (dont les nouvelles) se résolvent."""

    def test_routes_principales_resolvent(self):
        for name in (
            'cabinet-list', 'folder-list', 'document-list',
            'documentversion-list', 'journalacces-list', 'quotastockage-list',
        ):
            # Lève NoReverseMatch si la route n'existe pas → échec explicite.
            self.assertTrue(reverse(name))

    def test_partage_public_resolu(self):
        self.assertTrue(reverse('ged-public-partage', args=['tok']))


class GedServiceSurfaceTests(TestCase):
    """GED38 — la surface publique services/selectors expose les entrées clés."""

    def test_services_exposes_points_dentree(self):
        for fn in (
            # GED25 purge
            'purger_corbeille_echue', 'purger_corbeille_toutes_societes',
            # GED31 scan-to-DMS
            'deposer_lot_scans', 'deposer_un_scan',
            # GED32 import en masse
            'importer_en_masse', 'parser_csv_metadonnees',
            # GED33 OCR pièces
            'ocr_extract_text', 'extraire_metadonnees_piece',
            # GED34 classification
            'classer_document', 'classer_heuristique',
            # GED35 journal
            'journaliser_acces',
            # GED36 quotas
            'usage_stockage_octets', 'quota_depasse', 'assert_quota_disponible',
        ):
            self.assertTrue(
                callable(getattr(services, fn, None)),
                f'services.{fn} manquant.')

    def test_selectors_exposent_journal(self):
        self.assertTrue(
            callable(getattr(selectors, 'journal_acces_for_company', None)))
