"""CALX402 — la largeur d'allée de circulation SAISIE par la société, PAR
PAYS où elle pose.

LE CONSTAT (rappelé du plan) : la section ``degagements`` ne portait qu'une
allée technique UNIQUE sans pays ni nature (``allee_technique()``), et
aucune largeur de passage d'accès n'existe dans ce dépôt — ni les 36 pouces
américains qu'Aurora publie comme simple valeur usuelle modifiable, ni une
règle DTU, ni une prescription des services d'incendie française.

CE QUI EST PROUVÉ ICI :

* une société vierge garde ``degagements`` octet pour octet — la nouvelle
  clé ``allees_circulation`` n'apparaît QUE si elle est saisie ;
* une entrée d'``allees_circulation`` SANS ``source`` est refusée en
  NOMMANT exactement ``allees_circulation[0].source`` ;
* un pays non saisi rend ``(None, motif)`` — le motif NOMME le réglage
  manquant, jamais une largeur forfaitaire ;
* une entrée valide traverse la normalisation puis se relit par
  ``largeur_allee_circulation`` ;
* GARDE DE SURFACE : ``services/degagements.py`` ne porte AUCUNE largeur
  littérale nouvelle (aucun coefficient de circulation écrit en dur).

Aucune base de données : ``SimpleTestCase`` / ``unittest.TestCase`` purs.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx402_largeur_allee_pays -v2
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from django.test import SimpleTestCase

from apps.calepinage.services.degagements import (
    CLE_ALLEES_CIRCULATION, SECTION, largeur_allee_circulation,
    normaliser_section_degagements,
)
from apps.calepinage.services.parametres import ReglageInvalide


def _entree(pays='ma', largeur_m=1.2, source='société', reference=''):
    entree = {'pays': pays, 'largeur_m': largeur_m, 'source': source}
    if reference:
        entree['reference'] = reference
    return entree


class UneSocieteViergeGardeLaSectionOctetPourOctet(SimpleTestCase):
    """ÉQUIVALENCE : la nouvelle clé n'existe QUE si elle est saisie."""

    def test_la_section_vide_reste_vide(self):
        self.assertEqual(normaliser_section_degagements({}), {})
        self.assertEqual(normaliser_section_degagements(None), {})

    def test_une_section_sans_allees_circulation_n_en_gagne_aucune(self):
        propre = normaliser_section_degagements(
            {'cheminee': 0.6, 'retrait_rive_m': 0.4})
        self.assertNotIn(CLE_ALLEES_CIRCULATION, propre)
        self.assertEqual(propre, {'cheminee': 0.6, 'retrait_rive_m': 0.4})

    def test_pays_non_saisi_ne_recoit_aucune_largeur_par_defaut(self):
        """Ni 36 pouces, ni une valeur DTU/incendie : le dépôt n'en porte
        aucune — le pays absent rend ``None``, jamais un chiffre."""
        valeur, _motif = largeur_allee_circulation({}, pays='ma')
        self.assertIsNone(valeur)
        valeur, _motif = largeur_allee_circulation(None, pays='fr')
        self.assertIsNone(valeur)


class UneEntreeSansSourceEstRefuseeEnNommantLeChamp(SimpleTestCase):

    def test_le_champ_nomme_est_allees_circulation_0_source(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({
                CLE_ALLEES_CIRCULATION: [
                    {'pays': 'ma', 'largeur_m': 1.2},
                ],
            })
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[0].source')
        self.assertIn('source', str(refus.exception))

    def test_une_source_vide_est_refusee_de_la_meme_maniere(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({
                CLE_ALLEES_CIRCULATION: [
                    {'pays': 'ma', 'largeur_m': 1.2, 'source': '   '},
                ],
            })
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[0].source')

    def test_le_deuxieme_index_est_nomme_correctement(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({
                CLE_ALLEES_CIRCULATION: [
                    _entree(pays='ma'),
                    {'pays': 'fr', 'largeur_m': 1.5},
                ],
            })
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[1].source')


class UnPaysNonSaisiRendNoneEtNommeLeReglage(SimpleTestCase):

    def test_pays_absent_de_la_liste_rend_none(self):
        section = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [_entree(pays='ma')],
        })
        valeur, motif = largeur_allee_circulation(section, pays='fr')
        self.assertIsNone(valeur)
        self.assertIn('fr', motif)
        self.assertIn('allees_circulation', motif)
        self.assertIn(SECTION, motif)

    def test_aucun_pays_fourni_rend_none_et_le_dit(self):
        valeur, motif = largeur_allee_circulation({}, pays='')
        self.assertIsNone(valeur)
        self.assertIn('aucun pays', motif.lower())

    def test_la_casse_du_pays_est_insensible(self):
        section = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [_entree(pays='ma')],
        })
        valeur, _motif = largeur_allee_circulation(section, pays='MA')
        self.assertEqual(valeur, 1.2)


class UneEntreeValideTraverseEtSeRelit(SimpleTestCase):

    def test_la_normalisation_range_pays_en_minuscules(self):
        propre = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [_entree(pays='MA', largeur_m=1,
                                             reference='Consigne interne')],
        })
        self.assertEqual(propre[CLE_ALLEES_CIRCULATION], [{
            'pays': 'ma', 'largeur_m': 1.0, 'source': 'société',
            'reference': 'Consigne interne',
        }])

    def test_la_reference_est_optionnelle(self):
        propre = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [_entree(pays='ma')],
        })
        self.assertEqual(propre[CLE_ALLEES_CIRCULATION][0]['reference'], '')

    def test_la_lecture_cite_la_source_et_la_reference(self):
        section = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [_entree(
                pays='ma', largeur_m=1.4, source='société',
                reference='Consigne interne v2')],
        })
        valeur, phrase = largeur_allee_circulation(section, pays='ma')
        self.assertEqual(valeur, 1.4)
        self.assertIn('votre société', phrase)
        self.assertIn('Consigne interne v2', phrase)

    def test_deux_pays_distincts_se_relisent_chacun(self):
        section = normaliser_section_degagements({
            CLE_ALLEES_CIRCULATION: [
                _entree(pays='ma', largeur_m=1.2),
                _entree(pays='fr', largeur_m=1.5),
            ],
        })
        self.assertEqual(largeur_allee_circulation(section, pays='ma')[0],
                         1.2)
        self.assertEqual(largeur_allee_circulation(section, pays='fr')[0],
                         1.5)


class LaListeRefuseCeQuElleNeSaitPasRanger(SimpleTestCase):

    def test_pas_une_liste_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements(
                {CLE_ALLEES_CIRCULATION: {'pays': 'ma'}})
        self.assertEqual(refus.exception.champ, CLE_ALLEES_CIRCULATION)

    def test_une_entree_qui_n_est_pas_un_objet_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements(
                {CLE_ALLEES_CIRCULATION: ['ma']})
        self.assertEqual(refus.exception.champ, 'allees_circulation[0]')

    def test_une_cle_surnumeraire_est_refusee_en_la_nommant(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                {'pays': 'ma', 'largeur_m': 1.2, 'source': 'société',
                 'pompier': True},
            ]})
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[0].pompier')

    def test_un_pays_absent_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                {'largeur_m': 1.2, 'source': 'société'},
            ]})
        self.assertEqual(refus.exception.champ, 'allees_circulation[0].pays')

    def test_un_pays_mal_forme_est_refuse(self):
        for mauvais in ('maroc', 'M', '12', ''):
            with self.assertRaises(ReglageInvalide) as refus:
                normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                    {'pays': mauvais, 'largeur_m': 1.2, 'source': 'société'},
                ]})
            self.assertEqual(refus.exception.champ,
                             'allees_circulation[0].pays', mauvais)

    def test_une_largeur_non_numerique_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                {'pays': 'ma', 'largeur_m': 'large', 'source': 'société'},
            ]})
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[0].largeur_m')

    def test_une_largeur_nulle_ou_negative_est_refusee(self):
        for mauvaise in (0, -0.5):
            with self.assertRaises(ReglageInvalide) as refus:
                normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                    {'pays': 'ma', 'largeur_m': mauvaise,
                     'source': 'société'},
                ]})
            self.assertEqual(refus.exception.champ,
                             'allees_circulation[0].largeur_m', mauvaise)

    def test_une_reference_qui_n_est_pas_un_texte_est_refusee(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                {'pays': 'ma', 'largeur_m': 1.2, 'source': 'société',
                 'reference': 42},
            ]})
        self.assertEqual(refus.exception.champ,
                         'allees_circulation[0].reference')

    def test_un_pays_regle_deux_fois_est_refuse(self):
        with self.assertRaises(ReglageInvalide) as refus:
            normaliser_section_degagements({CLE_ALLEES_CIRCULATION: [
                _entree(pays='ma'), _entree(pays='ma', largeur_m=2.0),
            ]})
        self.assertEqual(refus.exception.champ, 'allees_circulation[1].pays')


class AucuneLargeurLitteraleNeEntreDansLeModule(unittest.TestCase):
    """Test de SURFACE : le module ne porte AUCUN chiffre de largeur écrit
    en dur — ni les 36 pouces américains, ni une valeur DTU/incendie. Les
    seuls littéraux numériques tolérés sont ceux du plancher d'atelier
    déjà en place (CAL71, non sourcés, inchangés par CALX402)."""

    #: Les littéraux du dossier AVANT CALX402 (chiffres de l'atelier
    #: existants, jamais une largeur de circulation) : 0 (comparaisons/
    #: bornes), 0.30 et 0.50 (dégagements/retrait de l'atelier, CAL71).
    NOMBRES_DE_FORME = (0, 0.3, 0.5)

    def test_aucun_litteral_numerique_hors_formes(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent
                  / 'services' / 'degagements.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        intrus = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(
                    noeud.value, (int, float)) and not isinstance(
                    noeud.value, bool):
                if noeud.value not in self.NOMBRES_DE_FORME:
                    intrus.append((noeud.lineno, noeud.value))
        self.assertEqual(
            intrus, [],
            "Constante numérique dans services/degagements.py : une "
            "largeur d'allée de circulation se SAISIT avec sa source, "
            "elle ne s'écrit jamais dans le code (CALX402).")


class LeNormaliseurResteBrancheEtLaCleAdmise(SimpleTestCase):
    """Le crochet de dispatch de CAL45 (``services/parametres.py``) n'a PAS
    changé de forme : la section ``degagements`` y pointe toujours vers
    ``normaliser_section_degagements`` — CALX402 étend la fonction, pas le
    crochet."""

    def test_le_normaliseur_est_toujours_enregistre(self):
        from apps.calepinage.services.parametres import _normaliseurs

        self.assertIs(_normaliseurs()[SECTION], normaliser_section_degagements)
