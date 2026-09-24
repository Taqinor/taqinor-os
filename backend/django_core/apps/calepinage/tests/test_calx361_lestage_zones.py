"""CALX361 — zones de vent et de neige par site, servies par la feuille de
lestage existante (``masse-lestage``, CALX17).

Ce qui est prouvé ici, SANS base (les réglages société sont substitués) :

* ÉQUIVALENCE (D12) : une société SANS ``zones`` reçoit exactement la sortie
  d'aujourd'hui — mêmes clés, mêmes lignes, aucune clé ``zone`` ajoutée ;
* ``normaliser_section_lestage`` accepte ``zones``/``zone_par_defaut``, garde
  l'exigence de source de chaque paramètre, refuse un paramètre qui n'est
  pas de SITE, un code en double, une zone par défaut inconnue — chaque
  refus nommant son champ ; l'exemple committé (contrat CALX340) traverse le
  normaliseur inchangé ;
* le calepinage désigne sa zone (``zoneLestage`` de son document), sinon la
  zone par défaut ; les paramètres de SITE viennent de la zone seule — une
  zone qui ne porte pas la charge de neige laisse la ligne de neige à
  ``None`` en la nommant, même si le jeu global en a une ;
* la zone retenue, son origine et ses sources sont ajoutées à la sortie ;
  chaque ligne calculée porte « paramètres saisis par <société>, référence
  <texte> » ;
* aucune constante n'entre dans ``services/lestage.py`` (le test de surface
  de CAL163 est rejoué ici).

Run :
    python manage.py test apps.calepinage.tests.test_calx361_lestage_zones -v2
"""
import ast
import copy
import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest import mock

from apps.calepinage.services import lestage
from apps.calepinage.services.parametres import ReglageInvalide

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'parametres_calepinage.json')
    .read_text(encoding='utf-8'))

SOURCE = 'Texte de référence saisi par la société (essai)'
SOURCE_ZONE = 'Carte de zones de la société (essai)'


def _saisie(valeur, source=SOURCE):
    return {'valeur': valeur, 'source': source}


def jeu_global():
    """Un jeu COMPLET à plat — des valeurs d'essai, aucune normative."""
    return {
        'masse_volumique_air_kg_m3': _saisie(1.2),
        'vitesse_vent_reference_m_s': _saisie(30),
        'categorie_terrain': _saisie('rase campagne'),
        'coefficient_terrain': _saisie(1),
        'coefficient_pression_soulevement': _saisie(1.5),
        'coefficient_pression_horizontal': _saisie(0.5),
        'coefficient_frottement': _saisie(0.4),
        'charge_neige_kn_m2': _saisie(0.2),
        'acceleration_pesanteur_m_s2': _saisie(9.81),
        'masse_structure_kg_par_module': _saisie(2.5),
    }


def zones():
    return [
        {'code': 'littoral', 'libelle': 'Littoral', 'commune_ou_region':
         'Casablanca-Settat', 'parametres': {
             'vitesse_vent_reference_m_s': _saisie(28, SOURCE_ZONE),
             'coefficient_terrain': _saisie(1.1, SOURCE_ZONE)}},
        {'code': 'atlas', 'libelle': 'Moyen Atlas', 'commune_ou_region':
         'Fès-Meknès', 'parametres': {
             'vitesse_vent_reference_m_s': _saisie(24, SOURCE_ZONE),
             'categorie_terrain': _saisie('rase campagne', SOURCE_ZONE),
             'coefficient_terrain': _saisie(1, SOURCE_ZONE),
             'charge_neige_kn_m2': _saisie(0.65, SOURCE_ZONE)}},
    ]


def calepinage(document=None):
    return SimpleNamespace(pk=1, company=SimpleNamespace(nom='Société Essai'),
                           roof_layout=document, devis_id=None,
                           resultat=None)


def servir(section, document=None):
    """``masse_et_lestage`` avec la section de lestage substituée."""
    sections = {'lestage': section}
    with mock.patch('apps.calepinage.selectors.parametres_de_societe',
                    return_value=sections):
        return lestage.masse_et_lestage(calepinage(document))


def lignes(sortie):
    return {ligne['code']: ligne for ligne in sortie['lestage']['lignes']}


def sortie_exemple_zone():
    """La sortie RÉELLE qui fonde ``exemple_zone`` du contrat
    ``calepinage_masse_lestage.json`` : jeu global + deux zones, la zone
    « atlas » désignée par le document, un module de fiche 2 000 × 1 000 mm
    et 22 kg (valeurs d'essai, aucune normative)."""
    section = lestage.normaliser_section_lestage(
        dict(jeu_global(), zones=zones(), zone_par_defaut='littoral'))
    cotes = {'longueur_mm': 2000, 'largeur_mm': 1000, 'poids_kg': 22}
    with mock.patch('apps.calepinage.selectors.parametres_de_societe',
                    return_value={'lestage': section}), \
            mock.patch('apps.stock.selectors.get_produit_scoped',
                       return_value=SimpleNamespace(nom='Module d’essai')), \
            mock.patch('apps.stock.selectors.dimensions_de_pose',
                       return_value=cotes):
        return lestage.masse_et_lestage(
            calepinage({'zoneLestage': 'atlas'}), produit_module_id=1)


class ContratExempleZoneTest(unittest.TestCase):
    """``exemple_zone`` du contrat EST la sortie du service (CALX362 le lit)."""

    def test_exemple_zone_est_la_sortie_reelle(self):
        contrat = json.loads(
            (RACINE_APP / 'contract_samples' / 'calepinage_masse_lestage.json')
            .read_text(encoding='utf-8'))
        self.assertEqual(sortie_exemple_zone(), contrat['exemple_zone'])
        self.assertNotIn('zone', contrat['exemple']['lestage'])
        self.assertNotIn('zone', contrat['exemple_vide']['lestage'])


class EquivalenceSansZonesTest(unittest.TestCase):
    """Une société sans zones : la sortie d'aujourd'hui, octet pour octet."""

    def _aujourd_hui(self, section):
        societe = 'Société Essai'
        return {
            'masse': lestage.masse_du_layout(None, poids_module_kg=None,
                                             designation_module='',
                                             section=section),
            'lestage': lestage.feuille_de_lestage(
                section, surface_module_m2=None, masse_module_kg=None,
                societe=societe),
        }

    def test_jeu_global_seul(self):
        section = lestage.normaliser_section_lestage(jeu_global())
        self.assertEqual(servir(section), self._aujourd_hui(section))
        self.assertNotIn('zone', servir(section)['lestage'])

    def test_section_vide(self):
        self.assertEqual(servir({}), self._aujourd_hui({}))

    def test_normalisation_d_un_jeu_sans_zones_inchangee(self):
        attendu = {cle: {'valeur': (valeur['valeur'].strip()
                                    if isinstance(valeur['valeur'], str)
                                    else float(valeur['valeur'])),
                         'source': valeur['source']}
                   for cle, valeur in jeu_global().items()}
        self.assertEqual(lestage.normaliser_section_lestage(jeu_global()),
                         attendu)


class NormalisationDesZonesTest(unittest.TestCase):

    def _refus(self, section):
        with self.assertRaises(ReglageInvalide) as refus:
            lestage.normaliser_section_lestage(section)
        return refus.exception

    def test_zones_et_defaut_acceptes(self):
        section = lestage.normaliser_section_lestage(
            dict(jeu_global(), zones=zones(), zone_par_defaut='littoral'))
        self.assertEqual([z['code'] for z in section['zones']],
                         ['littoral', 'atlas'])
        self.assertEqual(section['zone_par_defaut'], 'littoral')
        self.assertEqual(
            section['zones'][1]['parametres']['charge_neige_kn_m2'],
            {'valeur': 0.65, 'source': SOURCE_ZONE})

    def test_parametre_de_zone_sans_source(self):
        mauvaises = zones()
        mauvaises[1]['parametres']['charge_neige_kn_m2'] = {'valeur': 0.65}
        refus = self._refus({'zones': mauvaises})
        self.assertEqual(refus.champ,
                         'zones[1].parametres.charge_neige_kn_m2')
        self.assertIn('RÉFÉRENCE', str(refus))

    def test_parametre_qui_n_est_pas_de_site(self):
        mauvaises = zones()
        mauvaises[0]['parametres']['coefficient_frottement'] = _saisie(0.4)
        refus = self._refus({'zones': mauvaises})
        self.assertEqual(refus.champ,
                         'zones[0].parametres.coefficient_frottement')

    def test_code_en_double(self):
        mauvaises = zones()
        mauvaises[1]['code'] = 'littoral'
        self.assertEqual(self._refus({'zones': mauvaises}).champ,
                         'zones[1].code')

    def test_zone_sans_code_ni_libelle(self):
        self.assertEqual(self._refus({'zones': [{'libelle': 'X'}]}).champ,
                         'zones[0].code')
        self.assertEqual(self._refus({'zones': [{'code': 'x'}]}).champ,
                         'zones[0].libelle')

    def test_defaut_inconnu(self):
        refus = self._refus({'zones': zones(), 'zone_par_defaut': 'rif'})
        self.assertEqual(refus.champ, 'zone_par_defaut')
        self.assertEqual(self._refus({'zone_par_defaut': 'rif'}).champ,
                         'zone_par_defaut')

    def test_l_exemple_committe_traverse_le_normaliseur(self):
        publiee = CONTRAT['exemple']['lestage']
        self.assertTrue(publiee.get('zones'))
        self.assertEqual(lestage.normaliser_section_lestage(
            copy.deepcopy(publiee)), publiee)
        self.assertEqual(CONTRAT['exemple_vide']['lestage'], {})


class ZoneDuSiteTest(unittest.TestCase):

    def _section(self, **extra):
        return lestage.normaliser_section_lestage(
            dict(jeu_global(), zones=zones(), **extra))

    def test_zone_du_document_prime(self):
        sortie = servir(self._section(zone_par_defaut='littoral'),
                        {'zoneLestage': 'atlas'})
        zone = sortie['lestage']['zone']
        self.assertEqual(zone['code'], 'atlas')
        self.assertEqual(zone['origine'], 'document')
        self.assertEqual(zone['sources'], [SOURCE_ZONE])
        vent = {p['cle']: p for p in sortie['lestage']['parametres']}
        self.assertEqual(vent['vitesse_vent_reference_m_s']['valeur'], 24.0)
        self.assertEqual(vent['charge_neige_kn_m2']['valeur'], 0.65)

    def test_zone_par_defaut_sans_neige_ne_reprend_pas_le_global(self):
        sortie = servir(self._section(zone_par_defaut='littoral'))
        zone = sortie['lestage']['zone']
        self.assertEqual((zone['code'], zone['origine']),
                         ('littoral', 'defaut'))
        neige = lignes(sortie)['charge_neige_module']
        self.assertIsNone(neige['valeur'])
        self.assertIn('charge_neige_kn_m2', neige['manquants'])
        self.assertIn('Charge de neige', neige['mention'])
        self.assertIn('Littoral', neige['mention'])
        self.assertIn('Charge de neige', zone['motif'])

    def test_chaque_ligne_calculee_porte_sa_mention(self):
        sortie = servir(self._section(zone_par_defaut='littoral'))
        for code, ligne in lignes(sortie).items():
            if ligne['valeur'] is None:
                continue
            with self.subTest(code=code):
                self.assertTrue(ligne['mention'].startswith(
                    'paramètres saisis par Société Essai, référence '))
        dynamique = lignes(sortie)['pression_dynamique']
        self.assertIn(SOURCE_ZONE, dynamique['mention'])
        self.assertIn(SOURCE, dynamique['mention'])

    def test_aucune_zone_designable_le_global_s_applique_et_c_est_dit(self):
        sortie = servir(self._section())
        zone = sortie['lestage']['zone']
        self.assertIsNone(zone['code'])
        self.assertTrue(zone['motif'])
        vent = {p['cle']: p for p in sortie['lestage']['parametres']}
        self.assertEqual(vent['vitesse_vent_reference_m_s']['valeur'], 30.0)
        self.assertEqual(vent['charge_neige_kn_m2']['valeur'], 0.2)
        self.assertIsNotNone(lignes(sortie)['pression_dynamique']['valeur'])

    def test_zone_designee_inconnue_aucun_parametre_de_site(self):
        sortie = servir(self._section(), {'zoneLestage': 'rif'})
        zone = sortie['lestage']['zone']
        self.assertEqual(zone['code'], 'rif')
        self.assertIn('rif', zone['motif'])
        dynamique = lignes(sortie)['pression_dynamique']
        self.assertIsNone(dynamique['valeur'])
        self.assertIn('vitesse_vent_reference_m_s', dynamique['manquants'])


class AucuneConstanteNormativeTest(unittest.TestCase):

    def test_aucun_litteral_numerique_hors_formes(self):
        chemin = RACINE_APP / 'services' / 'lestage.py'
        intrus = [(noeud.lineno, noeud.value)
                  for noeud in ast.walk(ast.parse(
                      chemin.read_text(encoding='utf-8')))
                  if isinstance(noeud, ast.Constant)
                  and isinstance(noeud.value, (int, float))
                  and not isinstance(noeud.value, bool)
                  and noeud.value not in lestage.NOMBRES_DE_FORME]
        self.assertEqual(intrus, [])
