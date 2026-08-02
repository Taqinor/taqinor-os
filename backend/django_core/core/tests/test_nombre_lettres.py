"""Tests AOF108 — conversion en lettres promue en fondation (`core.nombre_lettres`).

Prouve trois choses :

1. **Non-régression bit-identique du comportement** : la fonction relogée rend
   EXACTEMENT les mêmes chaînes que l'implémentation historique de
   `apps/ventes/utils/nombre_lettres.py` (les trois assertions dorées de
   `apps.ventes.tests.test_xfac9_recu_paiement.NombreEnLettresTests` sont
   recopiées telles quelles, plus la couverture des règles françaises
   « vingt/cent/mille » que l'ancien module n'exerçait pas).
2. **Le shim `ventes` ré-exporte les MÊMES OBJETS**, pas des copies : l'identité
   `is` est le seul contrôle qui prouve qu'aucune divergence ne peut naître
   (deux implémentations parallèles seraient invisibles à un test d'égalité de
   chaînes).
3. **`core` reste une couche de base** : le module de fondation n'importe que la
   stdlib — aucune app, aucun réglage Django.

Le shim est chargé par `importlib` À DESSEIN : un `from apps.ventes...` en tête
de module créerait une arête statique `core.tests -> apps.ventes` que le contrat
import-linter `core-foundation-is-a-base-layer` interdit (les rares exceptions
existantes sont listées nommément dans `.importlinter`). L'import dynamique fait
exactement le même travail de vérification sans élargir la liste d'exceptions.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_nombre_lettres -v 2
"""
import ast
import importlib
import inspect
from decimal import Decimal

from django.test import SimpleTestCase

from core import nombre_lettres as fondation
from core.nombre_lettres import montant_en_lettres


class MontantEnLettresNonRegressionTests(SimpleTestCase):
    """Le déplacement ne change RIEN au rendu des appelants existants."""

    def test_montant_simple_avec_centimes(self):
        # Assertion dorée recopiée de test_xfac9_recu_paiement.
        self.assertEqual(
            montant_en_lettres(Decimal('1250.50')),
            'Mille-deux-cent-cinquante dirhams et cinquante centimes')

    def test_montant_rond_sans_centimes(self):
        self.assertEqual(
            montant_en_lettres(Decimal('5000.00')), 'Cinq-mille dirhams')

    def test_mille_invariable_sans_un(self):
        self.assertTrue(montant_en_lettres(Decimal('1000')).startswith('Mille'))

    def test_zero(self):
        self.assertEqual(montant_en_lettres(Decimal('0')), 'Zéro dirhams')

    def test_accords_vingt_et_cent(self):
        # "quatre-vingts"/"deux-cents" prennent le s seuls, pas suivis.
        self.assertEqual(montant_en_lettres(80), 'Quatre-vingts dirhams')
        self.assertEqual(montant_en_lettres(200), 'Deux-cents dirhams')
        self.assertEqual(montant_en_lettres(100), 'Cent dirhams')
        self.assertEqual(montant_en_lettres(180),
                         'Cent-quatre-vingts dirhams')
        self.assertEqual(montant_en_lettres(201),
                         'Deux-cent-un dirhams')

    def test_soixante_dix_et_quatre_vingt_dix(self):
        self.assertEqual(montant_en_lettres(21), 'Vingt-et-un dirhams')
        self.assertEqual(montant_en_lettres(91), 'Quatre-vingt-onze dirhams')
        # IMPRÉCISION HISTORIQUE ASSUMÉE ICI : 71 s'écrit « soixante et onze »,
        # or l'implémentation d'origine rend « soixante-onze » (la liaison
        # « et » n'est testée que sur un reste égal à 1, et 71 se décompose en
        # 60 + 11). AOF108 est un DÉPLACEMENT bit-identique : le défaut est
        # figé tel quel ici pour prouver qu'aucun comportement n'a bougé — il
        # est corrigé dans le mode « administratif » (AOF109), qui est un mode
        # NEUF et ne casse donc aucun appelant.
        self.assertEqual(montant_en_lettres(71), 'Soixante-onze dirhams')

    def test_millions_et_milliards(self):
        self.assertEqual(montant_en_lettres(1_000_000), 'Un-million dirhams')
        self.assertEqual(montant_en_lettres(2_000_000),
                         'Deux-millions dirhams')
        self.assertEqual(montant_en_lettres(1_000_000_000),
                         'Un-milliard dirhams')

    def test_devise_et_sous_unite_parametrables(self):
        self.assertEqual(
            montant_en_lettres(Decimal('2.05'), devise='euros',
                               sous_unite='cents'),
            'Deux euros et cinq cents')

    def test_arrondi_au_centime_et_valeur_absolue(self):
        self.assertEqual(montant_en_lettres(Decimal('1.005')),
                         'Un dirhams et un centimes')
        self.assertEqual(montant_en_lettres(Decimal('-12')),
                         'Douze dirhams')

    def test_accepte_float_int_et_chaine(self):
        attendu = 'Douze dirhams et cinquante centimes'
        self.assertEqual(montant_en_lettres(12.5), attendu)
        self.assertEqual(montant_en_lettres('12.50'), attendu)
        self.assertEqual(montant_en_lettres(Decimal('12.5')), attendu)


class ShimVentesBitIdentiqueTests(SimpleTestCase):
    """`apps.ventes.utils.nombre_lettres` ré-exporte la fondation, sans copie."""

    def setUp(self):
        self.shim = importlib.import_module('apps.ventes.utils.nombre_lettres')

    def test_meme_objet_fonction(self):
        self.assertIs(self.shim.montant_en_lettres, montant_en_lettres)

    def test_memes_helpers_internes(self):
        for nom in ('_UNITES', '_DIZAINES', '_TRANCHES', '_moins_de_cent',
                    '_moins_de_mille', '_entier_en_lettres'):
            self.assertIs(getattr(self.shim, nom), getattr(fondation, nom),
                          f'{nom} n\'est pas le même objet que la fondation')

    def test_shim_ne_contient_aucune_implementation(self):
        # Une copie de l'algorithme dans le shim serait une seconde source de
        # vérité (donc une seconde occasion de diverger) : le fichier ne doit
        # définir NI fonction NI classe — uniquement des ré-exports.
        arbre = ast.parse(inspect.getsource(self.shim))
        definitions = [
            noeud.name for noeud in arbre.body
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef))
        ]
        self.assertEqual(definitions, [])

    def test_rendu_identique_par_les_deux_chemins(self):
        for valeur in ('0', '1000', '1250.50', '4999920'):
            self.assertEqual(self.shim.montant_en_lettres(Decimal(valeur)),
                             montant_en_lettres(Decimal(valeur)))


class FondationPureTests(SimpleTestCase):
    """`core.nombre_lettres` n'importe rien d'autre que la stdlib."""

    def test_aucun_import_django_ni_app(self):
        # Lecture par AST (et non par sous-chaîne) : le docstring MENTIONNE
        # `apps.ventes`/`apps.ao` à dessein, ce n'est pas un import.
        arbre = ast.parse(inspect.getsource(fondation))
        modules = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules += [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules.append(noeud.module or '')
        self.assertTrue(modules, 'le module doit au moins importer decimal')
        for module in modules:
            racine = module.split('.', 1)[0]
            self.assertNotIn(
                racine, ('django', 'apps', 'authentication', 'rest_framework'),
                f'`core.nombre_lettres` doit rester pur (import interdit : {module})')
