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
# Miroir backend de l'auto-remplissage écran (mêmes mots-clés, deux langages).
# QJR71/QJR74 — ON SCANNE LE DOMAINE, PLUS UN FICHIER. La garde visait
# `services.py` ; la vague M3 y a vidé tout corps métier (c'est désormais une
# pure façade de ré-exports) et le vivier batterie vit dans
# `domain/composition.py`. Un chemin épinglé rend ce genre de garde VERTE ET
# VIDE au premier déplacement : on lit donc toute la surface de production de
# `apps/ventes`, et la tolérance peut déménager sans que la garde mente.
BACKEND_VENTES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _source_production_ventes():
    """Le texte de tous les modules de production d'``apps/ventes``."""
    morceaux = []
    for racine, dossiers, fichiers in os.walk(BACKEND_VENTES):
        dossiers[:] = [d for d in dossiers
                       if d not in ('tests', 'migrations', '__pycache__')]
        for nom in fichiers:
            if not nom.endswith('.py') or nom.startswith('test'):
                continue
            with open(os.path.join(racine, nom), encoding='utf-8') as fh:
                morceaux.append(fh.read())
    return '\n'.join(morceaux).lower()


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
    # STKCAT22 (16/09/2026) — LES DEUX CAS QUI ONT RENDU CE TEST ROUGE, ET
    # POURQUOI ILS COMPTENT. « Module PV 550 W » et « JA Solar 550 Wc » sont
    # deux façons dont les vendeurs nomment RÉELLEMENT un panneau. Le moteur PDF
    # les classait panneau depuis le 19/08 ; ``classify_categorie`` les faisait
    # tomber dans le fourre-tout « Protection & accessoires » et ``is_panneau``
    # leur appliquait 20 % de TVA — sur un panneau photovoltaïque, qui est à
    # 10 % depuis la réforme. Trois lecteurs, trois réponses sur la même
    # désignation. Depuis STKCAT22 les trois lisent LA MÊME table partagée
    # (``core.product_roles.est_panneau``).
    _FIXTURES = [
        ('Panneau Canadien Solar 710W', 'panneau'),
        ('Panneaux Jinko 550W', 'panneau'),
        ('Module PV 550 W', 'panneau'),
        ('JA Solar 550 Wc', 'panneau'),
        ('Onduleur hybride Deye 5kW Monophasé', 'onduleur_hybride'),
        ('Onduleur réseau Huawei 10kW Triphasé', 'onduleur_reseau'),
        ('Onduleur injection SUN2000 5kW', 'onduleur_reseau'),
        ('Batterie Dyness 5 kWh', 'batterie'),
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


class TestToleranceOrthographeDyness(SimpleTestCase):
    """Tolérance de lecture « Deyness » / « Dyness » (fondateur, 2026-08-18).

    La marque de batteries s'écrit **Dyness** ; le catalogue historique écrivait
    « Deyness ». Le catalogue et les produits en base sont corrigés (seeder +
    migration de données `stock.0121`), mais les désignations FIGÉES des devis
    déjà émis — et les PDF déjà rendus — gardent l'ancienne graphie : ce sont des
    documents historiques, on ne les réécrit pas.

    Conséquence directe : tout code qui CLASSIFIE ou APPARIE par chaîne doit
    reconnaître les DEUX orthographes, sinon une vieille ligne cesserait d'être
    une batterie du jour où le catalogue est corrigé. Ce test verrouille cette
    tolérance à chaque point d'appariement.
    """
    _LES_DEUX = ('Batterie Dyness 5 kWh', 'Batterie Deyness 5 kWh')

    def test_les_deux_orthographes_restent_des_batteries(self):
        from apps.stock.management.commands import seed_catalogue as seed
        for nom in self._LES_DEUX:
            self.assertTrue(builder._is_battery(nom), nom)
            # et rien d'autre : jamais un onduleur ni un panneau.
            self.assertFalse(builder._is_hybrid_inverter(nom), nom)
            self.assertFalse(builder._is_reseau_inverter(nom), nom)
            self.assertFalse(builder._is_panel(nom, ''), nom)
            self.assertEqual(seed.classify_categorie(nom), 'Batteries', nom)

    def test_les_deux_orthographes_gardent_leur_badge_de_marque(self):
        # Le badge du PDF affiche la marque TELLE QU'ÉCRITE sur la ligne : un
        # vieux devis reste étiqueté « Deyness », un nouveau « Dyness ».
        self.assertEqual(
            builder._parse_marque('Batterie Dyness 5 kWh'), 'Dyness')
        self.assertEqual(
            builder._parse_marque('Batterie Deyness 5 kWh'), 'Deyness')
        # Le jeton long gagne toujours sur son sous-mot « Deye ».
        self.assertNotEqual(
            builder._parse_marque('Batterie Deyness 5 kWh'), 'Deye')

    def test_les_deux_orthographes_pointent_vers_la_meme_fiche(self):
        from apps.ventes.quote_engine.residential import theme
        for nom in self._LES_DEUX:
            self.assertEqual(theme.fiche_slug(nom), 'batterie-dyness', nom)

    def test_le_vivier_dauto_remplissage_tolere_les_deux(self):
        # La composition choisit les modules 5/10 kWh de la marque parmi toutes
        # les batteries du catalogue ; une base pas encore migrée ne doit pas
        # faire retomber ce vivier sur TOUTES les batteries (gel, lithium
        # générique…). Le vivier vit dans `domain/composition.py` depuis QJR74 —
        # d'où le balayage de toute la surface de production plutôt qu'un
        # fichier nommé.
        src = _source_production_ventes()
        for graphie in ("'dyness'", "'deyness'"):
            self.assertIn(
                graphie, src,
                f"apps/ventes a perdu la graphie {graphie} — une désignation "
                "historique cesserait d'alimenter le vivier batterie.")

    def test_solar_js_tolere_les_deux(self):
        # Miroir écran de la garde ci-dessus (même règle, deux langages).
        with open(SOLAR_JS, encoding='utf-8') as fh:
            src = fh.read().lower()
        for graphie in ("'dyness'", "'deyness'"):
            self.assertIn(
                graphie, src,
                f"solar.js a perdu la graphie {graphie} — il doit rester "
                "aligné avec le vivier backend d'apps/ventes.")


class TestStkcat22TablePanneauPartagee(SimpleTestCase):
    """STKCAT22 — UNE table de reconnaissance panneau, et le FISCAL intact.

    Le défaut réparé : « Module PV 550 W » était un panneau pour le moteur PDF,
    un « Protection & accessoires » pour la catégorie catalogue, et un produit à
    20 % pour la TVA. Trois lecteurs, trois réponses sur la MÊME désignation.
    Les trois lisent désormais ``core.product_roles.est_panneau``.

    CE QUE CE TEST PROTÈGE SURTOUT : l'élargissement n'a PAS touché au prédicat
    FISCAL du seeder. Une prestation qui porte le mot « panneau » dans son nom
    (« Nettoyage panneaux », « Pose panneaux ») ou un équipement d'une autre
    famille (« Panneau électrique ») reste à 20 % — la règle AUD201, qui existe
    parce que l'inverse fait facturer un taux de TVA faux.
    """

    #: Les prestations/équipements qui PORTENT le mot « panneau » sans en être.
    _PAS_DES_PANNEAUX = (
        'Nettoyage panneaux',
        'Pose panneaux',
        'Panneau électrique',
        'Tableau De Protection AC/DC',
    )

    def test_la_table_partagee_est_bien_la_source_du_moteur(self):
        from apps.ventes import solar_design
        from core.product_roles import PANNEAU_MARQUES, PANNEAU_MODULE_QUALIFIERS
        self.assertIs(solar_design._PANEL_BRANDS, PANNEAU_MARQUES)
        self.assertIs(solar_design._PANEL_MODULE_QUALIFIERS,
                      PANNEAU_MODULE_QUALIFIERS)

    def test_le_seeder_reconnait_ce_que_le_moteur_reconnait(self):
        from apps.stock.management.commands import seed_catalogue as seed
        for nom in ('Module PV 550 W', 'JA Solar 550 Wc',
                    'Panneau Canadien Solar 710W', 'Panneaux Jinko 550W'):
            with self.subTest(nom=nom):
                self.assertTrue(builder._is_panel(nom, ''))
                self.assertTrue(seed.is_panneau(nom))
                self.assertEqual(seed.classify_categorie(nom),
                                 'Panneaux photovoltaïques')

    def test_le_predicat_fiscal_garde_ses_exclusions(self):
        """AUD201 — TVA 20 % sur ce qui n'est pas un panneau PV. INTACT."""
        from decimal import Decimal

        from apps.stock.management.commands import seed_catalogue as seed
        for nom in self._PAS_DES_PANNEAUX:
            with self.subTest(nom=nom):
                self.assertFalse(
                    seed.is_panneau(nom),
                    '« %s » n\'est pas un panneau photovoltaïque : il doit '
                    'rester à 20 %% (AUD201).' % nom)
                self.assertEqual(seed.taux_tva_for(nom), Decimal('20.00'))
        self.assertFalse(seed.is_panneau(None))

    def test_la_categorie_recoit_les_memes_exclusions(self):
        """Une PRESTATION ne remonte plus dans la catégorie « Panneaux »."""
        from apps.stock.management.commands import seed_catalogue as seed
        for nom in self._PAS_DES_PANNEAUX:
            with self.subTest(nom=nom):
                self.assertNotEqual(seed.classify_categorie(nom),
                                    'Panneaux photovoltaïques')

    def test_une_autre_famille_ne_vole_pas_la_branche_panneau(self):
        """Une marque de panneau sur un onduleur/une batterie ne trompe rien.

        La reconnaissance « marque + wattage » est testée EN PREMIER dans
        ``classify_categorie`` : sans l'exclusion « autre famille », un
        « Onduleur Trina 5000W » y tomberait.
        """
        from apps.stock.management.commands import seed_catalogue as seed
        self.assertEqual(seed.classify_categorie('Onduleur Trina 5000W'),
                         'Onduleurs réseau')
        self.assertEqual(seed.classify_categorie('Batterie Jinko 5kWh 550W'),
                         'Batteries')
        self.assertFalse(seed.is_panneau('Onduleur Trina 5000W'))
        self.assertFalse(builder._is_panel('Onduleur Trina 5000W', ''))
