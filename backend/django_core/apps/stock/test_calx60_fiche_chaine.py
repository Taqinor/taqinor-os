"""CALX60 — la fiche technique porte ENFIN ce que la chaîne de pertes lit.

Ce que ces tests verrouillent :

* ÉQUIVALENCE — une fiche d'AVANT CALX60 (un objet qui ne porte AUCUN des 22
  champs neufs, exactement comme une doublure de test d'une autre app) publie
  le même bloc qu'avant : chaque clé neuve se relit à ``None`` et pas une
  seule clé ancienne ne bouge ;
* NOMS DE LECTURE — les champs sont publiés SOUS LE NOM QUE LES ÉTAPES
  LISENT : ``rendement_par_irradiance`` (CALX162), ``tolerance_pmax_*_pct``
  (CALX165), ``rendement_par_charge`` ← ``ond_courbe_rendement`` (CALX170),
  ``conso_nuit_w`` (CALX175), la sortie de l'optimiseur, le C-rate ;
* COURBES — une abscisse qui recule ou se répète est REFUSÉE en nommant
  l'index du point fautif, une liste vide aussi (ce serait une perte de 0 %
  inventée) ;
* SOURCE — chaque clé qu'un consommateur va chercher dans un bloc de fiche
  (``getattr(specs, '…')`` / ``specs.get('…')``) doit être une clé que
  ``specs_for_produit`` publie réellement. Les modules de lot 3 qui n'existent
  pas encore sont SAUTÉS et nommés par le test.

Aucune base : la fiche est une DOUBLURE, comme dans
``apps/ventes/tests/test_qjr137_rendement_batterie.py``. Tout s'exécute en
``SimpleTestCase``.

Run :
    python manage.py test apps.stock.test_calx60_fiche_chaine -v 2
"""
import re
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.stock.models import (
    valider_courbe_irradiance,
    valider_courbe_rendement_onduleur,
)
from apps.stock.selectors import specs_for_produit

# ── Les 22 colonnes ajoutées par la migration 0159_calx60_fiche_chaine_pertes,
# et la clé sous laquelle le sélecteur publie chacune. Deux demandes de
# l'énoncé ne créent PAS de colonne et ne figurent donc pas ici :
# ``ond_s_max_kva`` (déjà là depuis CAL115) et ``bat_eol_pct`` (la grandeur de
# ``bat_retention_fin_de_vie_pct``, CAL118, publiée sous la clé ``eol_pct``).
CHAMPS_CALX60 = {
    # Module — ce que lisent « niveau d'irradiance » et « qualité module ».
    'rendement_par_irradiance': 'rendement_par_irradiance',
    'tolerance_pmax_min_pct': 'tolerance_pmax_min_pct',
    'tolerance_pmax_max_pct': 'tolerance_pmax_max_pct',
    # Onduleur — courbe η(P), rendements publiés, consommation de veille.
    'ond_courbe_rendement': 'rendement_par_charge',
    'ond_rendement_max_pct': 'rendement_max_pct',
    'ond_rendement_cec_pct': 'rendement_cec_pct',
    'ond_conso_nuit_w': 'conso_nuit_w',
    # Batterie — C-rate, chimie, plage de température.
    'bat_c_rate_charge': 'c_rate_charge',
    'bat_c_rate_decharge': 'c_rate_decharge',
    'bat_chimie': 'chimie',
    'bat_temp_min_c': 'temp_min_c',
    'bat_temp_max_c': 'temp_max_c',
    # Optimiseur / micro-onduleur — LA SORTIE, que CAL116 n'avait pas.
    'opt_ac_kw': 'ac_kw',
    'opt_ac_tension_v': 'ac_tension_v',
    'opt_ac_i_max_a': 'ac_i_max_a',
    'opt_ac_unites_max_par_branche': 'ac_unites_max_par_branche',
    'opt_v_out_nominal_v': 'v_out_nominal_v',
    'opt_v_out_min': 'v_out_min',
    'opt_v_out_max': 'v_out_max',
    'opt_i_out_max_a': 'i_out_max_a',
    'opt_pmax_out_w': 'pmax_out_w',
    'opt_modules_max_par_chaine': 'modules_max_par_chaine',
}

CLES_PAR_TYPE = {
    'module': ('rendement_par_irradiance', 'tolerance_pmax_min_pct',
               'tolerance_pmax_max_pct'),
    'onduleur': ('rendement_par_charge', 'rendement_max_pct',
                 'rendement_cec_pct', 'conso_nuit_w'),
    'batterie': ('c_rate_charge', 'c_rate_decharge', 'chimie', 'temp_min_c',
                 'temp_max_c', 'eol_pct'),
    'optimiseur': ('ac_kw', 'ac_tension_v', 'ac_i_max_a',
                   'ac_unites_max_par_branche', 'v_out_nominal_v',
                   'v_out_min', 'v_out_max', 'i_out_max_a', 'pmax_out_w',
                   'modules_max_par_chaine'),
}


class _Fiche:
    """Doublure de ``FicheTechnique`` : tout attribut non posé vaut ``None``.

    ``absents`` déclare les attributs qui n'existent PAS DU TOUT sur l'objet —
    c'est ainsi qu'on rejoue une fiche d'avant la migration, et c'est aussi
    la forme des doublures de test des autres apps (elles ne portent que les
    champs qu'elles connaissent)."""

    def __init__(self, type_fiche, absents=(), **valeurs):
        self.type_fiche = type_fiche
        self._absents = frozenset(absents)
        for nom, valeur in valeurs.items():
            setattr(self, nom, valeur)

    def __getattr__(self, nom):
        if nom.startswith('_') or nom in self.__dict__.get('_absents', ()):
            raise AttributeError(nom)
        return None


class _FicheToutPorte:
    """Doublure qui porte TOUT attribut demandé, avec une valeur non nulle :
    sert à énumérer l'univers des clés que le sélecteur peut publier, sans
    avoir à le recopier à la main (donc sans risque de dérive)."""

    def __init__(self, type_fiche):
        self.type_fiche = type_fiche

    def __getattr__(self, nom):
        if nom.startswith('_'):
            raise AttributeError(nom)
        return Decimal('1')


class _Produit:
    def __init__(self, fiche):
        self.fiche_technique = fiche


def _cles_publiables():
    """L'univers des clés que ``specs_for_produit`` peut publier, tous types
    de fiche confondus — calculé depuis le sélecteur lui-même."""
    univers = set()
    for type_fiche in ('module', 'onduleur', 'batterie', 'optimiseur'):
        univers |= set(
            specs_for_produit(_Produit(_FicheToutPorte(type_fiche))))
    return univers


class EquivalenceFicheAncienne(SimpleTestCase):
    """Une fiche d'avant CALX60 ne change de comportement pour personne."""

    def test_chaque_cle_neuve_se_relit_a_none(self):
        for type_fiche, cles in CLES_PAR_TYPE.items():
            fiche = _Fiche(type_fiche, absents=CHAMPS_CALX60)
            specs = specs_for_produit(_Produit(fiche))
            for cle in cles:
                with self.subTest(type_fiche=type_fiche, cle=cle):
                    self.assertIsNone(specs.get(cle))
                    self.assertNotIn(cle, specs)

    def test_les_cles_anciennes_ne_bougent_pas(self):
        """Le bloc module d'une fiche nue est exactement ce qu'il était : les
        booléens à défaut, et rien d'autre (cf. CAL114)."""
        fiche = _Fiche('module', absents=CHAMPS_CALX60,
                       bifacial=False, pmax_wc=Decimal('550'))
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs, {'bifacial': False,
                                 'pmax_wc': Decimal('550')})

    def test_champ_present_mais_vide_reste_omis(self):
        """Colonne existante à NULL = non publiée. Jamais ``0`` : un 0 %
        affirmerait une perte mesurée que personne n'a saisie."""
        for type_fiche, cles in CLES_PAR_TYPE.items():
            specs = specs_for_produit(_Produit(_Fiche(type_fiche)))
            for cle in cles:
                with self.subTest(type_fiche=type_fiche, cle=cle):
                    self.assertNotIn(cle, specs)


class NomsLusParLesEtapes(SimpleTestCase):
    """Chaque champ saisi ressort SOUS LE NOM QUE L'ÉTAPE LIT."""

    def test_module_courbe_et_tolerance(self):
        courbe = [{'w_m2': 200, 'rendement_relatif_pct': 96.5},
                  {'w_m2': 1000, 'rendement_relatif_pct': 100}]
        fiche = _Fiche('module',
                       rendement_par_irradiance=courbe,
                       tolerance_pmax_min_pct=Decimal('0.00'),
                       tolerance_pmax_max_pct=Decimal('3.00'))
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs['rendement_par_irradiance'], courbe)
        self.assertEqual(specs['tolerance_pmax_min_pct'], Decimal('0.00'))
        self.assertEqual(specs['tolerance_pmax_max_pct'], Decimal('3.00'))

    def test_onduleur_courbe_publiee_sous_rendement_par_charge(self):
        courbe = [{'charge_pct': 20, 'rendement_pct': 96.0},
                  {'charge_pct': 100, 'rendement_pct': 97.8}]
        fiche = _Fiche('onduleur',
                       ond_courbe_rendement=courbe,
                       ond_rendement_max_pct=Decimal('98.0'),
                       ond_rendement_cec_pct=Decimal('97.5'),
                       ond_conso_nuit_w=Decimal('2.00'))
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs['rendement_par_charge'], courbe)
        self.assertNotIn('ond_courbe_rendement', specs)
        self.assertEqual(specs['rendement_max_pct'], Decimal('98.0'))
        self.assertEqual(specs['rendement_cec_pct'], Decimal('97.5'))
        self.assertEqual(specs['conso_nuit_w'], Decimal('2.00'))

    def test_batterie_c_rate_chimie_temperatures(self):
        fiche = _Fiche('batterie',
                       bat_c_rate_charge=Decimal('0.50'),
                       bat_c_rate_decharge=Decimal('1.00'),
                       bat_chimie='lfp',
                       bat_temp_min_c=Decimal('-10.0'),
                       bat_temp_max_c=Decimal('50.0'))
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs['c_rate_charge'], Decimal('0.50'))
        self.assertEqual(specs['c_rate_decharge'], Decimal('1.00'))
        self.assertEqual(specs['chimie'], 'lfp')
        self.assertEqual(specs['temp_min_c'], Decimal('-10.0'))
        self.assertEqual(specs['temp_max_c'], Decimal('50.0'))

    def test_chimie_vide_omise(self):
        """Chaîne vide = non saisie : omise, jamais une chaîne vide servie."""
        specs = specs_for_produit(_Produit(_Fiche('batterie',
                                                  bat_chimie='')))
        self.assertNotIn('chimie', specs)

    def test_eol_pct_vient_du_champ_de_retention_unique(self):
        """``eol_pct`` n'a PAS sa colonne : c'est
        ``bat_retention_fin_de_vie_pct`` (CAL118), publié sous les deux noms
        depuis UNE seule donnée."""
        fiche = _Fiche('batterie',
                       bat_retention_fin_de_vie_pct=Decimal('80.0'))
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs['eol_pct'], Decimal('80.0'))
        self.assertEqual(specs['retention_fin_de_vie_pct'], Decimal('80.0'))

    def test_sortie_optimiseur_et_micro_onduleur(self):
        fiche = _Fiche('optimiseur',
                       opt_pmax_in_w=Decimal('700.00'),
                       opt_ac_kw=Decimal('0.365'),
                       opt_ac_tension_v=Decimal('230.0'),
                       opt_ac_i_max_a=Decimal('1.60'),
                       opt_ac_unites_max_par_branche=13,
                       opt_v_out_nominal_v=Decimal('40.0'),
                       opt_v_out_min=Decimal('5.0'),
                       opt_v_out_max=Decimal('60.0'),
                       opt_i_out_max_a=Decimal('15.0'),
                       opt_pmax_out_w=Decimal('650.00'),
                       opt_modules_max_par_chaine=25)
        specs = specs_for_produit(_Produit(fiche))
        self.assertEqual(specs['ac_kw'], Decimal('0.365'))
        self.assertEqual(specs['ac_tension_v'], Decimal('230.0'))
        self.assertEqual(specs['ac_i_max_a'], Decimal('1.60'))
        self.assertEqual(specs['ac_unites_max_par_branche'], 13)
        self.assertEqual(specs['v_out_nominal_v'], Decimal('40.0'))
        self.assertEqual(specs['v_out_min'], Decimal('5.0'))
        self.assertEqual(specs['v_out_max'], Decimal('60.0'))
        self.assertEqual(specs['i_out_max_a'], Decimal('15.0'))
        self.assertEqual(specs['pmax_out_w'], Decimal('650.00'))
        self.assertEqual(specs['modules_max_par_chaine'], 25)
        # L'ENTRÉE de CAL116 reste publiée telle quelle.
        self.assertEqual(specs['pmax_in_w'], Decimal('700.00'))

    def test_un_type_de_fiche_ne_deborde_pas_sur_un_autre(self):
        """Les blocs restent disjoints : un module saisi jusqu'aux oreilles
        ne publie aucune clé d'onduleur, de batterie ou d'optimiseur."""
        fiche = _Fiche('module',
                       rendement_par_irradiance=[
                           {'w_m2': 1000, 'rendement_relatif_pct': 100}])
        specs = specs_for_produit(_Produit(fiche))
        for cle in (CLES_PAR_TYPE['onduleur'] + CLES_PAR_TYPE['batterie']
                    + CLES_PAR_TYPE['optimiseur']):
            self.assertNotIn(cle, specs)


class ControleDesCourbes(SimpleTestCase):
    """Une courbe s'interpole : son abscisse ne peut ni reculer ni se
    répéter, et une liste vide n'est pas une courbe."""

    def test_courbe_irradiance_croissante_acceptee(self):
        valider_courbe_irradiance([
            {'w_m2': 100, 'rendement_relatif_pct': 94.0},
            {'w_m2': 200, 'rendement_relatif_pct': 96.5},
            {'w_m2': 1000, 'rendement_relatif_pct': 100.0},
        ])

    def test_vide_et_none_acceptes(self):
        valider_courbe_irradiance(None)
        valider_courbe_irradiance('')
        valider_courbe_rendement_onduleur(None)

    def test_liste_vide_refusee(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance([])
        self.assertIn('vide', str(cm.exception))

    def test_abscisse_qui_recule_nomme_lindex(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance([
                {'w_m2': 200, 'rendement_relatif_pct': 96.5},
                {'w_m2': 800, 'rendement_relatif_pct': 99.0},
                {'w_m2': 400, 'rendement_relatif_pct': 98.0},
            ])
        message = str(cm.exception)
        self.assertIn('index 2', message)
        self.assertIn('index 1', message)
        self.assertIn('w_m2', message)

    def test_abscisse_repetee_refusee(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance([
                {'w_m2': 200, 'rendement_relatif_pct': 96.5},
                {'w_m2': 200, 'rendement_relatif_pct': 97.0},
            ])
        self.assertIn('index 1', str(cm.exception))

    def test_point_sans_ordonnee_refuse_en_nommant_la_cle(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance([{'w_m2': 200}])
        message = str(cm.exception)
        self.assertIn('index 0', message)
        self.assertIn('rendement_relatif_pct', message)

    def test_valeur_non_numerique_refusee(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance(
                [{'w_m2': '200', 'rendement_relatif_pct': 96.5}])
        self.assertIn('index 0', str(cm.exception))

    def test_liste_attendue(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_irradiance({'w_m2': 200})
        self.assertIn('LISTE', str(cm.exception))

    def test_une_courbe_par_tension_est_acceptee(self):
        """PV*SOL publie une courbe η(P) PAR tension d'entrée : la croissance
        s'exige DANS chaque courbe, pas entre elles."""
        valider_courbe_rendement_onduleur([
            {'charge_pct': 20, 'rendement_pct': 95.5, 'tension_v': 360},
            {'charge_pct': 100, 'rendement_pct': 97.6, 'tension_v': 360},
            {'charge_pct': 20, 'rendement_pct': 96.1, 'tension_v': 580},
            {'charge_pct': 100, 'rendement_pct': 98.1, 'tension_v': 580},
        ])

    def test_recul_dans_une_meme_tension_refuse(self):
        with self.assertRaises(ValidationError) as cm:
            valider_courbe_rendement_onduleur([
                {'charge_pct': 100, 'rendement_pct': 97.6, 'tension_v': 360},
                {'charge_pct': 20, 'rendement_pct': 95.5, 'tension_v': 360},
            ])
        self.assertIn('index 1', str(cm.exception))
        self.assertIn('charge_pct', str(cm.exception))


# ── Test de SOURCE : ce que les consommateurs vont chercher dans un bloc de
# fiche doit être une clé que le sélecteur publie vraiment. Les modules du lot
# 3 qui n'existent pas encore sont sautés ET nommés — le jour où leur lane
# atterrit, ce test se met à les contrôler sans qu'on y touche.
RACINE_APPS = Path(__file__).resolve().parent.parent

CONSOMMATEURS = (
    'calepinage/services/etapes/niveau_irradiance.py',
    'calepinage/services/etapes/qualite_module.py',
    'calepinage/services/etapes/onduleur.py',
    'calepinage/services/etapes/auxiliaires.py',
    'calepinage/services/micro_onduleurs.py',
    'calepinage/services/electrique.py',
)

#: Le porteur d'un bloc de fiche se nomme ``specs*`` ou ``fiche*`` (la forme
#: qu'emploient l'énoncé du plan et ``services/etapes/__init__.py``, qui pose
#: ``contexte['fiche_module']`` / ``contexte['fiche_onduleur']``).
RE_LECTURE_FICHE = re.compile(
    r"getattr\(\s*(?P<porteur_g>(?:specs|fiche)[A-Za-z0-9_]*)\s*,\s*"
    r"['\"](?P<cle_g>[a-z][a-z0-9_]*)['\"]"
    r"|(?P<porteur_p>(?:specs|fiche)[A-Za-z0-9_]*)\.get\(\s*"
    r"['\"](?P<cle_p>[a-z][a-z0-9_]*)['\"]"
)


class SourceDesConsommateurs(SimpleTestCase):

    def test_chaque_cle_lue_est_une_cle_publiee(self):
        publiables = _cles_publiables()
        absents = []
        lectures = []
        for relatif in CONSOMMATEURS:
            chemin = RACINE_APPS / relatif
            if not chemin.exists():
                absents.append(relatif)
                continue
            source = chemin.read_text(encoding='utf-8')
            for correspondance in RE_LECTURE_FICHE.finditer(source):
                cle = (correspondance.group('cle_g')
                       or correspondance.group('cle_p'))
                porteur = (correspondance.group('porteur_g')
                           or correspondance.group('porteur_p'))
                lectures.append((relatif, porteur, cle))

        manquantes = [(f, p, c) for f, p, c in lectures
                      if c not in publiables]
        self.assertEqual(
            manquantes, [],
            "Ces lectures ne correspondent à AUCUNE clé de "
            "specs_for_produit — l'étape sortirait omise à vie : "
            f"{manquantes}. Clés publiées : {sorted(publiables)}. "
            f"(Modules pas encore construits, donc non contrôlés : "
            f"{absents or 'aucun'}.)")

    def test_les_cles_que_le_lot_3_attend_sont_publiees(self):
        """Épingle explicite — les noms que CALX162/165/170/175 iront lire
        existent, même avant que leurs modules ne soient écrits."""
        publiables = _cles_publiables()
        for cle in ('rendement_par_irradiance', 'tolerance_pmax_min_pct',
                    'tolerance_pmax_max_pct', 'rendement_par_charge',
                    'rendement_euro_pct', 'conso_nuit_w', 'techno_cellule',
                    'noct_c', 'uc_w_m2k', 'uv_w_m3sk'):
            with self.subTest(cle=cle):
                self.assertIn(cle, publiables)
