"""CALX104 câblage — un gabarit d'OBSTACLE peut enfin être ENREGISTRÉ.

LE CONSTAT
----------
L'atelier lit déjà les gabarits d'obstacle de la société dans la section
``zones_types`` : ``roofPro11/types.ts::lireGabaritsObstacle`` y cherche
``type``, ``forme``, ``longueur_m``, ``largeur_m``, ``rayon_m``, ``sommets``,
``hauteur_m``, ``retrait_m`` et ``source``. Mais la porte d'enregistrement
(``services/zones_reglementaires.py``) refusait QUATRE de ces clés comme
« réglage inconnu » : aucune société ne pouvait donc enregistrer un gabarit
d'obstacle, et le code qui les lit n'avait rien à lire.

CE QUI EST PROUVÉ ICI
---------------------
* les quatre clés (``type``, ``forme``, ``longueur_m``, ``rayon_m``) sont
  ADMISES et RANGÉES telles quelles ;
* elles restent OPTIONNELLES : un gabarit de ZONE enregistré avant cette
  tâche se relit à l'identique, clé pour clé (ÉQUIVALENCE) ;
* un type d'obstacle ou une forme HORS liste est REFUSÉ en nommant son champ
  (jamais traduit vers un voisin) ;
* la source reste obligatoire pour tout gabarit, obstacle compris ;
* l'échantillon de contrat committé
  (``contract_samples/parametres_calepinage.json``) porte un gabarit
  d'obstacle et il PASSE la normalisation.

Run :
    python manage.py test apps.calepinage.tests.test_calx104_gabarits_obstacle -v2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.calepinage.services.degagements import DEGAGEMENTS_ATELIER
from apps.calepinage.services.parametres import ReglageInvalide
from apps.calepinage.services.zones_reglementaires import (
    CLES,
    COTES_PAR_FORME,
    FORMES_OBSTACLE,
    FORMES_SANS_GENRE,
    GENRES,
    normaliser_section_zones_types,
)

ECHANTILLONS = (Path(__file__).resolve().parent.parent / 'contract_samples')
PARAMETRES = json.loads(
    (ECHANTILLONS / 'parametres_calepinage.json').read_text(encoding='utf-8'))

SOURCE = 'Consigne de pose interne v3, fiche souche'

#: Un gabarit de ZONE, exactement tel qu'il pouvait être enregistré AVANT.
BANDE = {
    'libelle': 'Bande coupe-feu',
    'nature': 'INTERDITE',
    'genre': 'bande',
    'largeur_m': 1.2,
    'cote': 'nord',
    'source': 'Arrêté préfectoral n° 2026-14, art. 7',
}

#: Un gabarit d'OBSTACLE : les quatre clés que l'atelier lit déjà.
SOUCHE = {
    'libelle': 'Souche de cheminée type',
    'nature': 'INTERDITE',
    'genre': 'bande',
    'largeur_m': 0.6,
    'retrait_m': 0.8,
    'hauteur_m': 1.1,
    'source': SOURCE,
    'type': 'cheminee',
    'forme': 'rectangle',
    'longueur_m': 0.9,
}


class ClesAdmisesTest(SimpleTestCase):
    """Les quatre clés de l'atelier sont dans la porte."""

    def test_les_quatre_cles_sont_admises(self):
        for cle in ('type', 'forme', 'longueur_m', 'rayon_m'):
            self.assertIn(cle, CLES)

    def test_les_formes_sont_bornees(self):
        self.assertEqual(FORMES_OBSTACLE,
                         ('rectangle', 'cercle', 'polygone'))


class NormalisationTest(SimpleTestCase):
    """Ce qui est saisi est RANGÉ tel quel ; rien n'est supposé."""

    def test_gabarit_obstacle_range_ses_quatre_cles(self):
        modele = normaliser_section_zones_types(
            {'souche': SOUCHE})['souche']
        self.assertEqual(modele['type'], 'cheminee')
        self.assertEqual(modele['forme'], 'rectangle')
        self.assertEqual(modele['longueur_m'], 0.9)
        self.assertEqual(modele['largeur_m'], 0.6)
        self.assertEqual(modele['hauteur_m'], 1.1)
        self.assertEqual(modele['retrait_m'], 0.8)
        self.assertEqual(modele['source'], SOURCE)

    def test_un_rayon_saisi_est_range(self):
        cercle = dict(SOUCHE, forme='cercle', rayon_m=0.35)
        modele = normaliser_section_zones_types(
            {'antenne': cercle})['antenne']
        self.assertEqual(modele['forme'], 'cercle')
        self.assertEqual(modele['rayon_m'], 0.35)

    def test_equivalence_un_gabarit_de_zone_est_inchange(self):
        """Les quatre clés sont OPTIONNELLES : aucune n'apparaît sans saisie."""
        modele = normaliser_section_zones_types(
            {'coupe_feu': BANDE})['coupe_feu']
        self.assertEqual(
            sorted(modele),
            ['cote', 'genre', 'hauteur_m', 'largeur_m', 'libelle', 'nature',
             'retrait_m', 'sommets', 'source'])

    def test_l_echantillon_committe_passe_la_porte(self):
        """Le contrat et la porte disent la MÊME chose."""
        section = PARAMETRES['exemple']['zones_types']
        self.assertIn('souche_type', section)
        normalise = normaliser_section_zones_types(section)
        self.assertEqual(normalise['souche_type']['type'], 'cheminee')
        self.assertEqual(normalise['souche_type']['forme'], 'rectangle')
        self.assertEqual(normalise['souche_type']['longueur_m'], 0.9)


class RefusTest(SimpleTestCase):
    """Chaque refus NOMME son champ — jamais un « non enregistré »."""

    def _refus(self, section, champ):
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types(section)
        self.assertEqual(ctx.exception.champ, champ)
        return str(ctx.exception)

    def test_type_inconnu_refuse_sous_son_champ(self):
        message = self._refus(
            {'souche': dict(SOUCHE, type='panneau_solaire')},
            'zones_types.souche.type')
        self.assertIn('panneau_solaire', message)
        # Le refus LISTE les types admis, ceux de l'atelier.
        for cle, _, _ in DEGAGEMENTS_ATELIER:
            self.assertIn(cle, message)

    def test_forme_inconnue_refusee_sous_son_champ(self):
        message = self._refus(
            {'souche': dict(SOUCHE, forme='ovale')},
            'zones_types.souche.forme')
        self.assertIn('ovale', message)
        self.assertIn('cercle', message)

    def test_longueur_negative_refusee(self):
        self._refus({'souche': dict(SOUCHE, longueur_m=-1)},
                    'zones_types.souche.longueur_m')

    def test_rayon_qui_n_est_pas_un_nombre_refuse(self):
        self._refus({'souche': dict(SOUCHE, rayon_m='grand')},
                    'zones_types.souche.rayon_m')

    def test_un_gabarit_obstacle_sans_source_reste_refuse(self):
        sans_source = dict(SOUCHE)
        sans_source.pop('source')
        self._refus({'souche': sans_source},
                    'zones_types.souche.source')


#: CALX104 câblage — un gabarit d'obstacle CIRCULAIRE, sans aucun `genre` de
#: zone : sa forme et son rayon disent déjà toute sa géométrie.
ANTENNE = {
    'libelle': 'Antenne parabolique type',
    'nature': 'INTERDITE',
    'source': SOURCE,
    'type': 'antenne',
    'forme': 'cercle',
    'rayon_m': 0.35,
    'hauteur_m': 0.9,
}

#: Le même, rectangulaire : deux cotes au lieu d'un rayon.
COFFRET = {
    'libelle': 'Coffret technique type',
    'nature': 'INTERDITE',
    'source': SOURCE,
    'forme': 'rectangle',
    'longueur_m': 0.8,
    'largeur_m': 0.4,
}


class GenreOptionnelTest(SimpleTestCase):
    """CALX104 câblage — `genre` n'est plus exigé d'un gabarit d'OBSTACLE.

    Avant : `genre` était obligatoire et borné au vocabulaire des ZONES
    (`bande`, `polygone`). Une souche ronde devait donc se déclarer « bande »
    pour entrer — une valeur fausse rangée dans un tiroir qui ne la décrit pas.
    """

    def test_seules_deux_formes_se_passent_de_genre(self):
        self.assertEqual(FORMES_SANS_GENRE, ('rectangle', 'cercle'))
        for forme in FORMES_SANS_GENRE:
            self.assertIn(forme, FORMES_OBSTACLE)
            self.assertIn(forme, COTES_PAR_FORME)

    def test_un_cercle_sans_genre_est_enregistre(self):
        modele = normaliser_section_zones_types(
            {'antenne': ANTENNE})['antenne']
        self.assertEqual(modele['forme'], 'cercle')
        self.assertEqual(modele['rayon_m'], 0.35)
        self.assertEqual(modele['type'], 'antenne')
        self.assertEqual(modele['source'], SOURCE)

    def test_un_rectangle_sans_genre_est_enregistre_avec_ses_deux_cotes(self):
        modele = normaliser_section_zones_types(
            {'coffret': COFFRET})['coffret']
        self.assertEqual(modele['forme'], 'rectangle')
        self.assertEqual(modele['longueur_m'], 0.8)
        self.assertEqual(modele['largeur_m'], 0.4)

    def test_aucun_vocabulaire_de_zone_n_est_invente(self):
        """Pas de `genre`, pas de `cote`, pas de `sommets` : ce n'est pas une
        zone réglementaire, et lui en donner les clés le ferait passer pour
        telle."""
        modele = normaliser_section_zones_types(
            {'antenne': ANTENNE})['antenne']
        for cle in ('genre', 'cote', 'sommets'):
            self.assertNotIn(cle, modele)

    def test_un_cercle_sans_rayon_est_refuse_en_le_nommant(self):
        sans_rayon = dict(ANTENNE)
        sans_rayon.pop('rayon_m')
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types({'antenne': sans_rayon})
        self.assertEqual(ctx.exception.champ, 'zones_types.antenne.rayon_m')

    def test_un_rectangle_sans_ses_deux_cotes_est_refuse_en_les_nommant(self):
        for champ in ('longueur_m', 'largeur_m'):
            incomplet = dict(COFFRET)
            incomplet.pop(champ)
            with self.assertRaises(ReglageInvalide) as ctx:
                normaliser_section_zones_types({'coffret': incomplet})
            self.assertEqual(ctx.exception.champ,
                             f'zones_types.coffret.{champ}')

    def test_ni_forme_ni_genre_reste_refuse_en_nommant_le_champ(self):
        nu = {'libelle': 'Objet sans forme', 'nature': 'INTERDITE',
              'source': SOURCE}
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types({'objet': nu})
        self.assertEqual(ctx.exception.champ, 'zones_types.objet.genre')
        message = str(ctx.exception)
        for admise in GENRES + FORMES_SANS_GENRE:
            self.assertIn(admise, message)

    def test_une_forme_polygone_exige_toujours_son_genre(self):
        """Le contour d'un polygone EST ce que le genre `polygone` porte
        (`sommets`) : deux chemins pour la même géométrie divergeraient."""
        polygone = dict(ANTENNE, forme='polygone')
        polygone.pop('rayon_m')
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types({'objet': polygone})
        self.assertEqual(ctx.exception.champ, 'zones_types.objet.genre')

    def test_la_source_reste_obligatoire_sans_genre(self):
        sans_source = dict(ANTENNE)
        sans_source.pop('source')
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types({'antenne': sans_source})
        self.assertEqual(ctx.exception.champ, 'zones_types.antenne.source')

    def test_un_genre_inconnu_reste_refuse(self):
        with self.assertRaises(ReglageInvalide) as ctx:
            normaliser_section_zones_types(
                {'souche': dict(SOUCHE, genre='cercle')})
        self.assertEqual(ctx.exception.champ, 'zones_types.souche.genre')
