"""Parité des mots-clés de classification entre solar.js (front) et
quote_engine/builder.py (PDF) — la répartition des options PDF dépend des
désignations de ligne ; les deux jeux de prédicats DOIVENT rester alignés.

Ce test :
1. vérifie que les prédicats `_is_*` du builder classent un jeu canonique de
   désignations exactement comme attendu (réseau/injection, hybride, batterie,
   panneau) ;
2. lit le source de `solar.js` et confirme qu'il contient les mêmes mots-clés
   (batterie, hybride, reseau, injection, panneau/panneaux), de sorte qu'une
   dérive de l'un fasse échouer le test.
"""
import os

from django.test import SimpleTestCase

from apps.ventes.quote_engine import builder

# Racine du dépôt : .../backend/django_core/apps/ventes/tests → remonter de 5.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
SOLAR_JS = os.path.join(
    _REPO_ROOT, 'frontend', 'src', 'features', 'ventes', 'solar.js')


class TestClassificationParity(SimpleTestCase):
    def test_builder_predicates_classify_canonical_designations(self):
        # Réseau / injection.
        self.assertTrue(builder._is_reseau_inverter('Onduleur réseau 5kW'))
        self.assertTrue(builder._is_reseau_inverter('Onduleur injection 5kW'))
        self.assertFalse(builder._is_reseau_inverter('Onduleur hybride 5kW'))
        # Hybride.
        self.assertTrue(builder._is_hybrid_inverter('Onduleur hybride 5kW'))
        self.assertFalse(builder._is_hybrid_inverter('Onduleur réseau 5kW'))
        # Batterie.
        self.assertTrue(builder._is_battery('Batterie LiFePO4 5kWh'))
        self.assertFalse(builder._is_battery('Onduleur hybride'))
        # Panneau.
        self.assertTrue(builder._is_panel('Panneau PV 550W'))
        self.assertTrue(builder._is_panel('Panneaux PV', ''))
        self.assertFalse(builder._is_panel('Onduleur réseau'))

    def test_solarjs_keywords_present(self):
        with open(SOLAR_JS, encoding='utf-8') as fh:
            src = fh.read().lower()
        for keyword in ('batterie', 'hybride', 'reseau', 'injection',
                        'panneau'):
            self.assertIn(
                keyword, src,
                f"solar.js a perdu le mot-clé de classification « {keyword} » "
                "— il doit rester aligné avec quote_engine/builder.py.")
