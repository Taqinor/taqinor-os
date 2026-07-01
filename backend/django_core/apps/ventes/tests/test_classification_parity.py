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

    # ── DC8 — PARITÉ à trois sources sur un jeu de fixtures partagé ────────────
    # Chaque désignation canonique doit être classée IDENTIQUEMENT par :
    #   1. les prédicats du builder (répartition options PDF),
    #   2. seed_catalogue.classify_categorie (catégorie catalogue),
    #   3. solar.js classifyProduct (auto-fill écran) — vérifié en lisant la
    #      fonction source et ses mots-clés (pas d'exécution JS).
    # Classe canonique -> (prédicat builder, catégorie seed, type solar.js)
    _FIXTURES = [
        ('Panneau Canadien Solar 710W', 'panneau'),
        ('Panneaux Jinko 550W', 'panneau'),
        ('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride'),
        ('Onduleur réseau Huawei 10kW Triphasé', 'onduleur_reseau'),
        ('Onduleur injection SUN2000 5kW', 'onduleur_reseau'),
        ('Batterie Deyness 5 kWh', 'batterie'),
    ]

    def test_dc8_builder_seed_parity_on_shared_fixtures(self):
        from apps.stock.management.commands import seed_catalogue as seed
        _seed_cat = {
            'panneau': 'Panneaux photovoltaïques',
            'onduleur_hybride': 'Onduleurs hybrides',
            'onduleur_reseau': 'Onduleurs réseau',
            'batterie': 'Batteries',
        }
        for nom, klass in self._FIXTURES:
            # 1. builder predicates — exactement une classe cœur solaire.
            is_panel = builder._is_panel(nom, '')
            is_hyb = builder._is_hybrid_inverter(nom)
            is_res = builder._is_reseau_inverter(nom)
            is_bat = builder._is_battery(nom)
            builder_klass = None
            if is_panel:
                builder_klass = 'panneau'
            elif is_hyb:
                builder_klass = 'onduleur_hybride'
            elif is_res:
                builder_klass = 'onduleur_reseau'
            elif is_bat:
                builder_klass = 'batterie'
            self.assertEqual(
                builder_klass, klass,
                f"builder classe « {nom} » comme {builder_klass}, attendu {klass}")
            # Un onduleur réseau/hybride n'est jamais une batterie et vice-versa.
            self.assertLessEqual(
                sum([is_panel, is_hyb, is_res, is_bat]), 1,
                f"« {nom} » tombe dans plusieurs classes cœur solaire")
            # 2. seed_catalogue.classify_categorie s'accorde.
            self.assertEqual(
                seed.classify_categorie(nom), _seed_cat[klass],
                f"seed_catalogue classe « {nom} » différemment du builder")
            # Panneau : is_panneau (taux 10 %) cohérent avec la classe panneau.
            self.assertEqual(seed.is_panneau(nom), klass == 'panneau')

    def test_dc8_solarjs_classify_logic_matches(self):
        # solar.js classifyProduct doit utiliser les MÊMES règles (mêmes
        # mots-clés, même ordre hybride-avant-réseau) que builder/seed.
        with open(SOLAR_JS, encoding='utf-8') as fh:
            src = fh.read()
        low = src.lower()
        # hybride testé AVANT réseau (sinon un hybride serait classé réseau).
        idx_hyb = low.find("'onduleur_hybride'")
        idx_res = low.find("'onduleur_reseau'")
        self.assertGreater(idx_hyb, -1)
        self.assertGreater(idx_res, -1)
        self.assertLess(idx_hyb, idx_res,
                        "solar.js doit classer l'hybride AVANT le réseau")
        # réseau reconnu par « reseau » OU « injection » (comme le builder).
        self.assertIn('injection', low)
        self.assertIn('reseau', low)
        # panneau/batterie présents.
        self.assertIn("'panneau'", low)
        self.assertIn("'batterie'", low)
