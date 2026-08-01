"""Tests AOF109 — mode « administratif » de l'arrêté en lettres.

Un arrêté mal orthographié est un motif de rejet d'offre : ces tests sont des
ASSERTIONS DORÉES, pas des tests de couverture. Chaque chaîne attendue est
écrite à la main d'après les règles typographiques françaises, puis confrontée
au moteur — jamais l'inverse.

Ce fichier prouve trois choses :

1. **Les montants réels du dossier AO sortent exactement comme sur l'arrêté**
   (4 999 920 · 4 166 600 · 5 413 680 · 5 219 280), plus les cas frontières
   exigés par la tâche (zéro · 80 · 100 · 1 000 000 · décimales).
2. **Le mode par défaut n'a pas bougé d'un caractère** : les assertions
   historiques (quittance `ventes` XFAC9, reçu de note de frais `compta`
   ZACC8) sont recopiées ici et doivent rester vraies — le mode administratif
   est un mode NEUF, il ne casse aucun appelant existant.
3. **`core.nombre_lettres` reste une fondation pure** : l'ajout n'introduit
   aucun import Django ni app métier (le test de pureté vit dans
   `test_nombre_lettres.py`, celui-ci vérifie qu'aucune dépendance n'a été
   ajoutée par la nouvelle surface).

POINT DE VALIDATION FONDATEUR (avant industrialisation, cf. « Done = » d'AOF109) :
deux choix d'usage sont figés ici et se retournent en une ligne s'il en décide
autrement — (a) la liaison « DE » quand le montant s'arrête pile sur un
million/milliard (« UN MILLION DE DIRHAMS », paramètre ``liaison_de``), et
(b) l'accord singulier de la devise sur zéro et un (« ZÉRO DIRHAM »,
« UN DIRHAM »). Les deux formes sont testées, la seconde branche via
``liaison_de=False``.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_nombre_lettres_administratif -v 2
"""
import ast
import inspect
from decimal import Decimal

from django.test import SimpleTestCase

from core import nombre_lettres as fondation
from core.nombre_lettres import (
    MODE_ADMINISTRATIF,
    MODE_DEFAUT,
    montant_en_lettres,
    montant_en_lettres_administratif,
)


class ArreteMontantsReelsDuDossierTests(SimpleTestCase):
    """Les quatre montants du dossier AO FRDISI, à la lettre près."""

    def test_4_999_920(self):
        # Le montant cité dans l'énoncé de la tâche : c'est LA chaîne de
        # référence de tout le mode administratif.
        self.assertEqual(
            montant_en_lettres_administratif(4_999_920),
            'QUATRE MILLIONS NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE '
            'NEUF CENT VINGT DIRHAMS')

    def test_4_166_600(self):
        # « SIX CENTS » : le 's' se pose, rien de numéral ne suit.
        self.assertEqual(
            montant_en_lettres_administratif(4_166_600),
            'QUATRE MILLIONS CENT SOIXANTE-SIX MILLE SIX CENTS DIRHAMS')

    def test_5_413_680(self):
        # « SIX CENT QUATRE-VINGTS » : « cent » perd son 's' (un nombre suit),
        # « quatre-vingts » le garde (rien ne suit).
        self.assertEqual(
            montant_en_lettres_administratif(5_413_680),
            'CINQ MILLIONS QUATRE CENT TREIZE MILLE '
            'SIX CENT QUATRE-VINGTS DIRHAMS')

    def test_5_219_280(self):
        self.assertEqual(
            montant_en_lettres_administratif(5_219_280),
            'CINQ MILLIONS DEUX CENT DIX-NEUF MILLE '
            'DEUX CENT QUATRE-VINGTS DIRHAMS')

    def test_les_quatre_montants_ne_contiennent_aucun_trait_dunion_de_classe(self):
        # Le défaut que la tâche corrige : relier les CLASSES par des traits
        # d'union. Aucun tiret ne doit toucher « MILLE »/« MILLIONS »/« CENT ».
        for montant in (4_999_920, 4_166_600, 5_413_680, 5_219_280):
            texte = montant_en_lettres_administratif(montant)
            for interdit in ('-MILLE', 'MILLE-', '-MILLION', 'MILLIONS-',
                             '-CENT ', ' CENT-'):
                self.assertNotIn(
                    interdit, texte,
                    f'{montant} : « {interdit} » est un trait d\'union de '
                    f'classe, interdit dans un arrêté ({texte})')


class ArreteCasFrontieresTests(SimpleTestCase):
    """Zéro, 80, 100, 1 000 000 et les décimales — les pièges de l'arrêté."""

    def test_zero(self):
        # « zéro » commande le SINGULIER en français.
        self.assertEqual(montant_en_lettres_administratif(0),
                         'ZÉRO DIRHAM')
        self.assertEqual(montant_en_lettres_administratif(Decimal('0.00')),
                         'ZÉRO DIRHAM')

    def test_zero_centime_nest_jamais_ecrit(self):
        # Un arrêté n'écrit pas « et zéro centime » : la mention est OMISE.
        for montant in (Decimal('0'), Decimal('100.00'), Decimal('4999920.00')):
            self.assertNotIn('CENTIME',
                             montant_en_lettres_administratif(montant))

    def test_80_prend_le_s(self):
        self.assertEqual(montant_en_lettres_administratif(80),
                         'QUATRE-VINGTS DIRHAMS')

    def test_80_perd_le_s_devant_mille_le_garde_devant_millions(self):
        # « mille » est un adjectif numéral (pas de 's'), « millions » un nom.
        self.assertEqual(montant_en_lettres_administratif(80_000),
                         'QUATRE-VINGT MILLE DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(80_000_000),
                         'QUATRE-VINGTS MILLIONS DE DIRHAMS')

    def test_100(self):
        self.assertEqual(montant_en_lettres_administratif(100),
                         'CENT DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(200),
                         'DEUX CENTS DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(201),
                         'DEUX CENT UN DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(200_000),
                         'DEUX CENT MILLE DIRHAMS')

    def test_1_000_000(self):
        # « million » est un NOM : il appelle la préposition « de ».
        self.assertEqual(montant_en_lettres_administratif(1_000_000),
                         'UN MILLION DE DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(2_000_000),
                         'DEUX MILLIONS DE DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(1_000_000_000),
                         'UN MILLIARD DE DIRHAMS')

    def test_liaison_de_desactivable(self):
        # Branche de repli si le fondateur préfère l'usage sans préposition.
        self.assertEqual(
            montant_en_lettres_administratif(1_000_000, liaison_de=False),
            'UN MILLION DIRHAMS')

    def test_mille_ne_prend_jamais_la_liaison_de(self):
        # « mille » est un adjectif : « MILLE DIRHAMS », jamais « DE DIRHAMS ».
        self.assertEqual(montant_en_lettres_administratif(1_000),
                         'MILLE DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(100_000),
                         'CENT MILLE DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(2_500_000),
                         'DEUX MILLIONS CINQ CENT MILLE DIRHAMS')

    def test_decimales(self):
        self.assertEqual(
            montant_en_lettres_administratif(Decimal('1250.50')),
            'MILLE DEUX CENT CINQUANTE DIRHAMS ET CINQUANTE CENTIMES')
        self.assertEqual(
            montant_en_lettres_administratif(Decimal('1234.56')),
            'MILLE DEUX CENT TRENTE-QUATRE DIRHAMS ET '
            'CINQUANTE-SIX CENTIMES')
        self.assertEqual(
            montant_en_lettres_administratif(Decimal('4999920.75')),
            'QUATRE MILLIONS NEUF CENT QUATRE-VINGT-DIX-NEUF MILLE '
            'NEUF CENT VINGT DIRHAMS ET SOIXANTE-QUINZE CENTIMES')

    def test_centime_au_singulier(self):
        self.assertEqual(montant_en_lettres_administratif(Decimal('0.01')),
                         'ZÉRO DIRHAM ET UN CENTIME')
        self.assertEqual(montant_en_lettres_administratif(Decimal('1.01')),
                         'UN DIRHAM ET UN CENTIME')

    def test_arrondi_au_centime_et_valeur_absolue(self):
        self.assertEqual(montant_en_lettres_administratif(Decimal('1.005')),
                         'UN DIRHAM ET UN CENTIME')
        self.assertEqual(montant_en_lettres_administratif(Decimal('-12')),
                         'DOUZE DIRHAMS')

    def test_accepte_float_int_et_chaine(self):
        attendu = 'DOUZE DIRHAMS ET CINQUANTE CENTIMES'
        self.assertEqual(montant_en_lettres_administratif(12.5), attendu)
        self.assertEqual(montant_en_lettres_administratif('12.50'), attendu)
        self.assertEqual(montant_en_lettres_administratif(Decimal('12.5')),
                         attendu)


class ArreteOrthographeFrancaiseTests(SimpleTestCase):
    """Les règles que le mode par défaut orthographie mal."""

    def test_liaison_et_sans_traits_dunion(self):
        # 21, 31…61 et 71 prennent « et », sans traits d'union.
        self.assertEqual(montant_en_lettres_administratif(21),
                         'VINGT ET UN DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(31),
                         'TRENTE ET UN DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(61),
                         'SOIXANTE ET UN DIRHAMS')

    def test_soixante_et_onze_corrige_le_defaut_historique(self):
        # LE défaut nommé par AOF108 : le mode par défaut rend
        # « Soixante-onze », l'arrêté écrit « SOIXANTE ET ONZE ».
        self.assertEqual(montant_en_lettres_administratif(71),
                         'SOIXANTE ET ONZE DIRHAMS')
        self.assertEqual(montant_en_lettres(71), 'Soixante-onze dirhams')

    def test_quatre_vingts_ne_prend_pas_la_liaison_et(self):
        self.assertEqual(montant_en_lettres_administratif(81),
                         'QUATRE-VINGT-UN DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(91),
                         'QUATRE-VINGT-ONZE DIRHAMS')

    def test_traits_dunion_dans_les_composes_17_a_99(self):
        # Les seuls traits d'union légitimes : à l'intérieur d'un composé < 100.
        self.assertEqual(montant_en_lettres_administratif(17),
                         'DIX-SEPT DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(99),
                         'QUATRE-VINGT-DIX-NEUF DIRHAMS')
        self.assertEqual(montant_en_lettres_administratif(180),
                         'CENT QUATRE-VINGTS DIRHAMS')

    def test_devise_au_singulier_sur_zero_et_un(self):
        self.assertEqual(montant_en_lettres_administratif(1),
                         'UN DIRHAM')
        self.assertEqual(montant_en_lettres_administratif(2),
                         'DEUX DIRHAMS')

    def test_majuscules_accentuees(self):
        # L'usage administratif français conserve l'accent sur la capitale.
        self.assertIn('ZÉRO', montant_en_lettres_administratif(0))

    def test_minuscules_optionnelles(self):
        # Pour un prix unitaire en lettres au fil du texte, pas en capitales.
        self.assertEqual(
            montant_en_lettres_administratif(4_999_920, majuscules=False),
            'Quatre millions neuf cent quatre-vingt-dix-neuf mille '
            'neuf cent vingt dirhams')

    def test_devises_alternatives(self):
        self.assertEqual(montant_en_lettres_administratif(1_250, devise='MAD'),
                         'MILLE DEUX CENT CINQUANTE MAD')
        self.assertEqual(
            montant_en_lettres_administratif(Decimal('2.05'), devise='euros'),
            'DEUX EUROS ET CINQ CENTS')
        # Devise inconnue : utilisée telle quelle, traitée comme invariable.
        self.assertEqual(
            montant_en_lettres_administratif(1, devise='francs CFA'),
            'UN FRANCS CFA')

    def test_sous_unite_forcee(self):
        self.assertEqual(
            montant_en_lettres_administratif(Decimal('1.05'),
                                             sous_unite='centimes'),
            'UN DIRHAM ET CINQ CENTIMES')


class ModeParDefautInchangeTests(SimpleTestCase):
    """Non-régression : aucun appelant existant ne bouge (AOF109 est additif)."""

    def test_assertions_historiques_xfac9_et_zacc8(self):
        # Recopiées telles quelles de test_xfac9_recu_paiement (quittance) —
        # ce sont ces chaînes que la quittance et le reçu de note de frais
        # impriment aujourd'hui en production.
        self.assertEqual(
            montant_en_lettres(Decimal('1250.50')),
            'Mille-deux-cent-cinquante dirhams et cinquante centimes')
        self.assertEqual(
            montant_en_lettres(Decimal('5000.00')), 'Cinq-mille dirhams')
        self.assertTrue(montant_en_lettres(Decimal('1000')).startswith('Mille'))

    def test_mode_defaut_explicite_identique_a_lomission(self):
        for valeur in ('0', '80', '100', '1000000', '1250.50', '4999920'):
            self.assertEqual(
                montant_en_lettres(Decimal(valeur), mode=MODE_DEFAUT),
                montant_en_lettres(Decimal(valeur)))

    def test_mode_defaut_relie_toujours_par_traits_dunion(self):
        # La preuve que le nouveau mode n'a PAS déteint sur l'ancien.
        self.assertEqual(montant_en_lettres(4_999_920),
                         'Quatre-millions-neuf-cent-quatre-vingt-dix-neuf-'
                         'mille-neuf-cent-vingt dirhams')

    def test_mode_defaut_garde_ses_parametres_de_devise(self):
        self.assertEqual(
            montant_en_lettres(Decimal('2.05'), devise='euros',
                               sous_unite='cents'),
            'Deux euros et cinq cents')


class RoutageDuModeTests(SimpleTestCase):
    """Le paramètre `mode` route sans dupliquer la logique."""

    def test_mode_administratif_delegue_a_la_fonction_dediee(self):
        for valeur in (0, 80, 100, 1_000_000, Decimal('1250.50'), 4_999_920):
            self.assertEqual(
                montant_en_lettres(valeur, mode=MODE_ADMINISTRATIF),
                montant_en_lettres_administratif(valeur))

    def test_mode_administratif_accorde_la_sous_unite_par_defaut(self):
        # La valeur par défaut 'centimes' de la signature historique vaut
        # « laisse la devise décider » : le singulier doit rester accordé.
        self.assertEqual(
            montant_en_lettres(Decimal('0.01'), mode=MODE_ADMINISTRATIF),
            'ZÉRO DIRHAM ET UN CENTIME')

    def test_mode_administratif_transmet_la_devise(self):
        self.assertEqual(
            montant_en_lettres(1_250, devise='MAD', mode=MODE_ADMINISTRATIF),
            'MILLE DEUX CENT CINQUANTE MAD')

    def test_mode_inconnu_leve_une_erreur(self):
        with self.assertRaises(ValueError):
            montant_en_lettres(100, mode='officiel')


class FondationResteePureTests(SimpleTestCase):
    """Le mode administratif n'ajoute aucune dépendance à la fondation."""

    def test_aucun_import_django_ni_app(self):
        arbre = ast.parse(inspect.getsource(fondation))
        modules = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules += [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules.append(noeud.module or '')
        for module in modules:
            racine = module.split('.', 1)[0]
            self.assertNotIn(
                racine, ('django', 'apps', 'authentication', 'rest_framework'),
                f'`core.nombre_lettres` doit rester pur (import : {module})')
