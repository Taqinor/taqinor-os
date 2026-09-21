# -*- coding: utf-8 -*-
"""CALX168 — l'effondrement I-V d'une chaîne ombrée, encadré par DEUX bornes.

CE QUI EST PROUVÉ ICI
---------------------
1. **Rien n'est supposé** : sans table d'affectation, sans document de
   toiture, sans accès solaire ou sans seuil de dérivation saisi, l'étape est
   OMISE en NOMMANT le champ manquant, et la série ressort INTACTE.
2. **Propriété** : une chaîne dont tous les modules ont le même accès rend
   exactement 0,0 % pour les DEUX bornes — au-dessus comme en dessous du
   seuil. L'ombre uniforme est déjà comptée par l'étape « accès module » ;
   cette étape ne mesure que l'EXCÉDENT.
3. **Propriété** : une chaîne de dix modules dont UN est à 0,2 perd, en borne
   basse, l'ordre de grandeur d'un module sur dix — jamais 80 % de la chaîne,
   qui est la borne HAUTE, celle du courant série sans diode.
4. **Invariant** : ``borne haute ≥ borne basse``, toujours — y compris dans le
   cas piège où dériver un module coûterait plus cher que de subir la
   contrainte de série.
5. **Micro-onduleur ou optimiseur** : la chaîne n'impose plus son courant,
   les deux bornes valent 0,0 % et la RAISON est publiée.
6. **Garde anti-forfait** : aucun facteur d'atténuation d'ombrage ne vit dans
   le module — les seules constantes numériques du fichier sont des
   arrondis, un pourcentage et des bornes de comparaison.
7. **Intégration** : par ``appliquer_chaine``, l'entrée de cascade du poste
   « mismatch_ombrage » porte l'excédent de la borne basse (lecture ISOLÉE de
   notre poste, jamais du total de la chaîne que d'autres lanes remplissent).

Aucune base de données, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx168_mismatch_ombrage
"""
from __future__ import annotations

import ast
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import LIBELLES, appliquer_chaine
from apps.calepinage.services.etapes import mismatch_ombrage
from apps.calepinage.services.ombrage_chaines import MOTIF_SANS_ACCES

POSTE = mismatch_ombrage.POSTE
LIBELLE = LIBELLES[POSTE]

#: Une méthode d'accès solaire COMPLÈTE, comme CALX158 l'exige du document.
METHODE = {'horizon': False, 'rangees': False,
           'nom': 'shadingEngine roofPro11'}

#: Deux heures de production, colonne d'énergie lisible : c'est le minimum
#: pour qu'un facteur électrique se voie dans la cascade.
SERIE = {
    'pas_minutes': 60,
    'colonne_energie': 'p_w',
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0, 'p_w': 4000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
         'gb_i_w_m2': 400.0, 'gd_i_w_m2': 100.0, 'gr_i_w_m2': 0.0,
         'gi_w_m2': 500.0, 'p_w': 2000.0},
    ],
}

#: Un seuil de dérivation SAISI, avec sa provenance — sans lui, rien.
SEUIL = {'valeur': 0.5, 'source': 'societe',
         'reference': 'Réglage société d\'essai'}


def layout_de(acces, *, pan='PAN-A'):
    """Un document de toiture v2 à un pan et ses accès solaires par module."""
    return {'zones': [{'label': pan, 'geometry': {
        'solarAccess': {'values': list(acces), 'method': dict(METHODE)}}}]}


def affectation_de(nombre, *, pan='PAN-A', chaine=1, **extra):
    """La table module → chaîne, au format de ``services/chaines.py``."""
    lignes = []
    for rang in range(1, nombre + 1):
        ligne = {'module': '%s#%d' % (pan, rang), 'pan': pan,
                 'chaine': chaine, 'onduleur': 1, 'mppt': 1,
                 'source': 'automatique'}
        ligne.update(extra)
        lignes.append(ligne)
    return lignes


def contexte_de(acces, *, seuil=SEUIL, pan='PAN-A', **extra):
    """Le contexte minimal que CALX5 posera pour cette étape."""
    contexte = {
        'affectation': affectation_de(len(acces), pan=pan),
        'ombrage': {'layout': layout_de(acces, pan=pan)},
        'reglages_simulation': ({} if seuil is None
                                else {mismatch_ombrage.CLE_REGLAGE: seuil}),
    }
    contexte.update(extra)
    return contexte


def bornes(entree):
    """``(excédent basse, excédent haute)`` en points de pourcentage."""
    return (entree['bornes']['basse']['excedent_pct'],
            entree['bornes']['haute']['excedent_pct'])


class OmissionsNommees(SimpleTestCase):
    """Une entrée absente NOMME son champ, et ne touche pas la série."""

    def test_sans_affectation(self):
        contexte = contexte_de([1.0, 0.4])
        contexte.pop('affectation')
        serie, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        self.assertIs(serie, SERIE)
        self.assertIn('affectation', etape['motif_omission'])
        self.assertIn(mismatch_ombrage.MOTIF_SANS_AFFECTATION,
                      etape['motif_omission'])
        self.assertIsNone(etape['source'])

    def test_sans_document_de_toiture(self):
        contexte = contexte_de([1.0, 0.4])
        contexte['ombrage'] = {}
        serie, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        self.assertIs(serie, SERIE)
        self.assertIn('ombrage.layout', etape['motif_omission'])

    def test_sans_acces_solaire(self):
        contexte = contexte_de([1.0, 0.4])
        contexte['ombrage']['layout'] = {'zones': [
            {'label': 'PAN-A', 'geometry': {}}]}
        serie, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        self.assertIs(serie, SERIE)
        self.assertIn(MOTIF_SANS_ACCES, etape['motif_omission'])

    def test_aucune_chaine_mesurable(self):
        """Tous les accès à ``null`` : aucune chaîne n'est mesurable."""
        contexte = contexte_de([None, None])
        serie, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        self.assertIs(serie, SERIE)
        self.assertIn(mismatch_ombrage.MOTIF_AUCUNE_CHAINE_MESURABLE,
                      etape['motif_omission'])

    def test_sans_seuil_saisi(self):
        serie, etape = mismatch_ombrage.appliquer(
            SERIE, contexte_de([1.0, 0.2], seuil=None))
        self.assertIs(serie, SERIE)
        self.assertIn(mismatch_ombrage.CLE_REGLAGE, etape['motif_omission'])
        self.assertIn(mismatch_ombrage.MOTIF_SEUIL_ABSENT,
                      etape['motif_omission'])

    def test_seuil_sans_source_ne_compte_pas(self):
        """Une valeur sans source n'est PAS une valeur saisie (D-CALX 7)."""
        seuil = {'valeur': 0.5, 'source': ''}
        _, etape = mismatch_ombrage.appliquer(
            SERIE, contexte_de([1.0, 0.2], seuil=seuil))
        self.assertIn(mismatch_ombrage.CLE_REGLAGE, etape['motif_omission'])

    def test_chaines_toutes_a_zero(self):
        """Des accès tous nuls ne définissent aucun excédent relatif."""
        serie, etape = mismatch_ombrage.appliquer(SERIE,
                                                  contexte_de([0.0, 0.0]))
        self.assertIs(serie, SERIE)
        self.assertIn(mismatch_ombrage.MOTIF_CHAINES_A_VIDE,
                      etape['motif_omission'])


class ProprietesDesBornes(SimpleTestCase):
    """Les propriétés que la tâche exige, chiffre par chiffre."""

    def test_acces_uniforme_rend_zero_pour_les_deux_bornes(self):
        for acces in (1.0, 0.8, 0.3):
            with self.subTest(acces=acces):
                serie, etape = mismatch_ombrage.appliquer(
                    SERIE, contexte_de([acces] * 6))
                self.assertEqual(etape['motif_omission'], '')
                self.assertEqual(bornes(etape['entree']), (0.0, 0.0))
                self.assertEqual(etape['entree']['facteur_applique'], 1.0)
                self.assertEqual(
                    round(sum(point['p_w'] for point in serie['points']), 6),
                    6000.0)

    def test_un_module_sur_dix_a_vingt_pourcent(self):
        acces = [1.0] * 9 + [0.2]
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte_de(acces))
        entree = etape['entree']
        basse = entree['bornes']['basse']
        haute = entree['bornes']['haute']

        # Borne basse : le module ombré sort de la chaîne, les neuf autres
        # produisent — un module sur dix, pas quatre cinquièmes.
        self.assertEqual(basse['perte_chaine_pct'], 10.0)
        self.assertLess(basse['perte_chaine_pct'], 80.0)
        # Borne haute : le courant de la chaîne tombe à celui du module le
        # moins éclairé — c'est là que 80 % apparaissent, et nulle part
        # ailleurs.
        self.assertEqual(haute['perte_chaine_pct'], 80.0)
        # L'excédent retenu dans la cascade est celui de la borne BASSE.
        self.assertEqual(entree['modele'],
                         mismatch_ombrage.MODELE_DERIVATION)
        self.assertAlmostEqual(basse['excedent_pct'], 2.174, places=3)
        self.assertAlmostEqual(entree['ecart_bornes_pct'],
                               haute['excedent_pct'] - basse['excedent_pct'],
                               places=3)
        self.assertEqual(entree['chaines'][0]['modules_derives'],
                         ['PAN-A#10'])

    def test_borne_haute_toujours_superieure_ou_egale(self):
        cas = (
            [1.0] * 4,
            [1.0, 0.9, 0.8, 0.7],
            [1.0] * 9 + [0.2],
            [0.49, 0.5],          # dériver coûterait plus que subir la série
            [0.2, 0.2, 1.0],
            [None, 1.0, 0.3],
            [0.51] * 3 + [0.49],
        )
        for acces in cas:
            with self.subTest(acces=acces):
                _, etape = mismatch_ombrage.appliquer(SERIE,
                                                      contexte_de(acces))
                basse, haute = bornes(etape['entree'])
                self.assertGreaterEqual(haute, basse)
                self.assertGreaterEqual(basse, 0.0)
                self.assertLessEqual(
                    etape['entree']['facteur_applique'], 1.0)

    def test_le_facteur_sapplique_a_la_serie(self):
        acces = [1.0] * 9 + [0.2]
        rendue, etape = mismatch_ombrage.appliquer(SERIE, contexte_de(acces))
        facteur = etape['entree']['facteur_applique']
        self.assertAlmostEqual(facteur, 9.0 / 9.2, places=6)
        self.assertAlmostEqual(
            sum(point['p_w'] for point in rendue['points']),
            6000.0 * (9.0 / 9.2), places=6)
        # Pureté : la série d'entrée n'a pas bougé d'un watt.
        self.assertEqual(sum(point['p_w'] for point in SERIE['points']),
                         6000.0)
        self.assertFalse(etape['gain'])

    def test_modules_sans_acces_ne_sont_pas_completes(self):
        """Un module ``null`` n'entre nulle part — jamais complété à 1."""
        _, etape = mismatch_ombrage.appliquer(
            SERIE, contexte_de([1.0, None, 0.2]))
        entree = etape['entree']
        self.assertEqual(entree['modules_mesures'], 2)
        self.assertEqual(entree['modules_sans_acces'], ['PAN-A#2'])

    def test_granularite_module_par_defaut(self):
        _, etape = mismatch_ombrage.appliquer(SERIE,
                                              contexte_de([1.0, 0.2]))
        entree = etape['entree']
        self.assertEqual(entree['granularite'], 'module')
        self.assertIsNone(entree['brins_proteges'])
        self.assertEqual(entree['hypothese'],
                         mismatch_ombrage.HYPOTHESE_MODULE)

    def test_granularite_brin_quand_la_fiche_le_publie(self):
        """Le champ est lu DÉFENSIVEMENT — dict aujourd'hui, objet demain."""
        class FicheObjet:
            brins_proteges = 3

        for fiche in ({'brins_proteges': 3}, FicheObjet()):
            with self.subTest(fiche=type(fiche).__name__):
                _, etape = mismatch_ombrage.appliquer(
                    SERIE, contexte_de([1.0, 0.2], fiche_module=fiche))
                entree = etape['entree']
                self.assertEqual(entree['granularite'], 'brin')
                self.assertEqual(entree['brins_proteges'], 3)
                self.assertIn('3', entree['hypothese'])

    def test_source_et_reference_du_seuil_voyagent(self):
        _, etape = mismatch_ombrage.appliquer(SERIE,
                                              contexte_de([1.0, 0.2]))
        self.assertEqual(etape['source'], 'societe')
        self.assertIn('PV*SOL', etape['reference'])
        self.assertIn('HelioScope', etape['reference'])
        self.assertEqual(
            etape['entree']['seuil_acces_derivation']['valeur'], 0.5)
        self.assertEqual(
            etape['entree']['seuil_acces_derivation']['cle'],
            mismatch_ombrage.CLE_REGLAGE)


class ChaineSansContrainte(SimpleTestCase):
    """Micro-onduleur ou optimiseur : la chaîne n'impose plus son courant."""

    def test_micro_onduleur_declare_sur_la_ligne(self):
        contexte = contexte_de([1.0] * 9 + [0.2])
        for ligne in contexte['affectation']:
            ligne['micro_onduleur'] = 'MICRO-ESSAI'
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        entree = etape['entree']
        self.assertEqual(bornes(entree), (0.0, 0.0))
        self.assertEqual(entree['facteur_applique'], 1.0)
        self.assertEqual(entree['chaines_sans_contrainte'][0]['raison'],
                         mismatch_ombrage.RAISON_SANS_CONTRAINTE)

    def test_optimiseur_declare_pour_tout_le_document(self):
        contexte = contexte_de([1.0] * 9 + [0.2],
                               fiche_optimiseur={'modeles': 'OPT-ESSAI'})
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        self.assertEqual(bornes(etape['entree']), (0.0, 0.0))
        self.assertTrue(etape['entree']['chaines'][0]['sans_contrainte'])

    def test_un_onduleur_de_chaine_ne_dispense_de_rien(self):
        """Une fiche onduleur n'est pas un micro-onduleur : rien n'est déduit."""
        contexte = contexte_de([1.0] * 9 + [0.2],
                               fiche_onduleur={'pac_kw': 5.0})
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        basse, _ = bornes(etape['entree'])
        self.assertGreater(basse, 0.0)


class PlusieursChainesEtPans(SimpleTestCase):
    """L'agrégation suit la partition RÉELLE, jamais une partition recalculée."""

    def test_deux_chaines_du_meme_pan(self):
        contexte = {
            'affectation': (affectation_de(2, chaine=1)
                            + affectation_de(2, chaine=2)),
            'ombrage': {'layout': layout_de([1.0, 1.0, 1.0, 0.4])},
            'reglages_simulation': {mismatch_ombrage.CLE_REGLAGE: SEUIL},
        }
        # Les rangs 1-2 vont à la chaîne 1, les rangs 3-4 à la chaîne 2 :
        # seule la SECONDE porte le module ombré.
        contexte['affectation'][2]['module'] = 'PAN-A#3'
        contexte['affectation'][3]['module'] = 'PAN-A#4'
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        entree = etape['entree']
        self.assertEqual(entree['chaines_mesurees'], 2)
        chaine_saine = next(c for c in entree['chaines']
                            if c['chaine'] == 1)
        chaine_ombree = next(c for c in entree['chaines']
                             if c['chaine'] == 2)
        self.assertEqual(chaine_saine['excedent_haute_pct'], 0.0)
        self.assertGreater(chaine_ombree['excedent_haute_pct'], 0.0)

    def test_le_pan_nomme_restreint_la_mesure(self):
        contexte = {
            'affectation': (affectation_de(2, pan='PAN-A', chaine=1)
                            + affectation_de(2, pan='PAN-B', chaine=1)),
            'ombrage': {'layout': {'zones': [
                layout_de([1.0, 1.0], pan='PAN-A')['zones'][0],
                layout_de([1.0, 0.2], pan='PAN-B')['zones'][0]]}},
            'reglages_simulation': {mismatch_ombrage.CLE_REGLAGE: SEUIL},
            'plan': {'cle': 'PAN-A'},
        }
        _, etape = mismatch_ombrage.appliquer(SERIE, contexte)
        entree = etape['entree']
        self.assertEqual(entree['pan'], 'PAN-A')
        self.assertEqual(entree['chaines_mesurees'], 1)
        self.assertEqual(bornes(entree), (0.0, 0.0))


class GardeAntiForfait(SimpleTestCase):
    """AUCUN facteur forfaitaire d'atténuation d'ombrage dans le module."""

    #: Les seules constantes numériques admises, et ce que chacune fait :
    #: 0/0.0 et 1 sont des bornes de comparaison, 100.0 convertit en
    #: pourcentage, 3 et 6 sont des nombres de décimales d'arrondi. Aucune
    #: n'est un coefficient de perte.
    ADMISES = {0, 1, 3, 6, 0.0, 1.0, 100.0}

    def source(self):
        chemin = pathlib.Path(mismatch_ombrage.__file__)
        return chemin.read_text(encoding='utf-8')

    def test_aucune_constante_numerique_de_perte(self):
        arbre = ast.parse(self.source())
        trouvees = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and not isinstance(
                    noeud.value, bool) and isinstance(
                        noeud.value, (int, float)):
                trouvees.add(noeud.value)
        self.assertTrue(
            trouvees <= self.ADMISES,
            'Constantes numériques inattendues dans le module : %s'
            % sorted(trouvees - self.ADMISES))

    def test_aucun_facteur_dattenuation_du_marche(self):
        texte = self.source()
        for interdit in ('0.33', '0,33', 'SMF', 'shading_mitigation'):
            self.assertNotIn(interdit, texte)


class DansLaCascade(SimpleTestCase):
    """Lecture ISOLÉE de notre poste — jamais le total de la chaîne."""

    def entree_du_poste(self, cascade):
        return next(etape for etape in cascade['etapes']
                    if etape['etape'] == POSTE)

    def test_le_poste_porte_lexcedent_de_la_borne_basse(self):
        contexte = contexte_de([1.0] * 9 + [0.2])
        _, cascade = appliquer_chaine(SERIE, contexte)
        notre = self.entree_du_poste(cascade)
        self.assertEqual(notre['motif_omission'], '')
        self.assertEqual(notre['libelle'], LIBELLE)
        self.assertEqual(notre['entree']['modele'],
                         mismatch_ombrage.MODELE_DERIVATION)
        attendu = notre['entree']['bornes']['basse']['excedent_pct']
        self.assertIsNotNone(notre['perte_pct'])
        # L'ordonnanceur arrondit les énergies au millième de kWh avant de
        # faire son rapport : la comparaison se fait à cette précision-là,
        # jamais au-delà.
        self.assertAlmostEqual(notre['perte_pct'], attendu, places=1)

    def test_le_poste_somet_sans_seuil_et_ne_coute_rien(self):
        contexte = contexte_de([1.0] * 9 + [0.2], seuil=None)
        _, cascade = appliquer_chaine(SERIE, contexte)
        notre = self.entree_du_poste(cascade)
        self.assertIn(mismatch_ombrage.CLE_REGLAGE, notre['motif_omission'])
        self.assertIsNone(notre['kwh_apres'])
        self.assertIsNone(notre['perte_pct'])
        self.assertIsNone(notre['entree'])
