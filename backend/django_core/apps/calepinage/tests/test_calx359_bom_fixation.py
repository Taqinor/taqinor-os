"""CALX359 — la nomenclature de fixation d'un calepinage, et son export.

Ce qui est prouvé ici :

* les GRANDEURS sont lues sur le document : modules, rangées, pans,
  jonctions entre voisins, extrémités (2 par segment continu), longueur des
  rangées (étendue + pas RELEVÉ) — un trou coupe la rangée, un pan tourné
  groupe ses rangées selon son azimut (plein sud : exactement le groupement
  de ``rangees.rangees_du_pan``), un pan sans voisin ne publie pas de
  longueur et le NOMME ;
* le cœur PUR ``_lignes_de_fixation`` rend EXACTEMENT les lignes de
  l'exemple committé (contrat CALX335) ; une règle non saisie ou un
  paramètre déclaré à ``null`` sortent à ``quantite: None`` avec ``manquant``
  nommé, jamais une quantité de repli ; une quantité « u » s'arrondit à
  l'unité supérieure ; une référence circulaire ou vers un rôle absent est
  dite ;
* catalogue vide ⇒ la réponse EST ``exemple_vide`` ;
* aucune valeur normative dans ``services/fixation.py`` : un test de surface
  refuse toute constante numérique hors 0 / 1 / 2 ;
* en HTTP : la porte sert la sortie du service, borne le système à la
  société, et la feuille « Fixation » n'apparaît au classeur QUE si la
  société a un catalogue (D12).

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx359_bom_fixation -v2
"""
import ast
import copy
import json
import math
import pathlib
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage.services import fixation
from apps.calepinage.services.rangees import rangees_du_pan
import io
from apps.calepinage.models import (
    Calepinage, ComposantFixation, SystemeFixation,
)
from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_fixation_bom.json')
    .read_text(encoding='utf-8'))
#: ACAL81 sert ``systeme_source`` (posé par le contrat M0 ACAL1).
EXEMPLE_VIDE_SERVI = CONTRAT['exemple_vide']
PAS = 1.2


def layout(panneaux, azimut=180.0, pose=None, orients=None):
    """Un document minimal : un pan, ses centres posés (mètres, ENU).

    ``pose`` (ACAL601) : ``geometry.panelOrientation`` ; ``orients`` : la
    liste des ``panels[].orient``, dans l'ordre des centres."""
    document = _layout(panneaux, azimut)
    geometrie = document['zones'][0]['geometry']
    if pose is not None:
        geometrie['panelOrientation'] = pose
    for panneau, orient in zip(geometrie['panels'], orients or ()):
        panneau['orient'] = orient
    return document


def _layout(panneaux, azimut):
    return {
        'version': 2,
        'outline': [[33.5, -7.6], [33.5, -7.5998], [33.5002, -7.5998],
                    [33.5002, -7.6]],
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002],
                         [-7.6, 33.5002]],
            'geometry': {
                'azimuthDeg': azimut, 'tiltDeg': 15.0,
                'count': len(panneaux), 'origin': [-7.6, 33.5],
                'panels': [{'cx': x, 'cy': y} for x, y in panneaux],
            },
        }],
    }


def deux_rangees_de_cinq():
    return [(1.0 + PAS * k, y) for y in (1.0, 3.0) for k in range(5)]


def composant(libelle, role, unite, regle, produit_id=None):
    return SimpleNamespace(libelle=libelle, role=role, unite=unite,
                           regle=regle, produit_id=produit_id)


def composants_du_contrat():
    return [
        composant('Rail aluminium', 'rail', 'm',
                  {'base': 'longueur_rangees_m', 'facteur': 2,
                   'libelle_facteur': 'rails par rangée'}, 812),
        composant('Pince de milieu', 'pince_milieu', 'u',
                  {'base': 'jonctions', 'facteur': 2,
                   'libelle_facteur': 'rails par rangée'}, 813),
        composant('Pince de fin', 'pince_fin', 'u',
                  {'base': 'extremites', 'facteur': 2,
                   'libelle_facteur': 'rails par rangée'}, 814),
        composant('Crochet de toit', 'crochet', 'u',
                  {'base': 'role:rail', 'diviseur': None,
                   'libelle_diviseur': 'entraxe des crochets (m)'}, 815),
        composant('Embout de rail', 'embout', 'u', {}),
    ]


def grandeurs(**valeurs):
    base = {'modules': 10, 'rangees': 2, 'pans': 1, 'jonctions': 8,
            'extremites': 4, 'longueur_rangees_m': 13.2}
    base.update(valeurs)
    return {'valeurs': base, 'manquants': {}}


class SurfaceSansValeurNormativeTest(SimpleTestCase):

    def test_aucune_constante_hors_0_1_2(self):
        texte = (RACINE_APP / 'services' / 'fixation.py').read_text(
            encoding='utf-8')
        intrus = [(noeud.lineno, noeud.value)
                  for noeud in ast.walk(ast.parse(texte))
                  if isinstance(noeud, ast.Constant)
                  and isinstance(noeud.value, (int, float))
                  and not isinstance(noeud.value, bool)
                  and noeud.value not in (0, 1, 2)]
        self.assertEqual(
            intrus, [],
            "Constante numérique dans services/fixation.py : un pas, un "
            "entraxe ou un nombre de rails se SAISIT sur le composant, il ne "
            "s'écrit jamais dans le code (CALX359).")


class GrandeursDuDocumentTest(SimpleTestCase):

    def test_deux_rangees_de_cinq_plein_sud(self):
        lues = fixation._grandeurs_du_document(
            layout(deux_rangees_de_cinq(), pose='portrait'))
        self.assertEqual(lues['manquants'], {})
        valeurs = lues['valeurs']
        self.assertEqual(valeurs['modules'], 10)
        self.assertEqual(valeurs['rangees'], 2)
        self.assertEqual(valeurs['pans'], 1)
        self.assertEqual(valeurs['jonctions'], 8)
        self.assertEqual(valeurs['extremites'], 4)
        self.assertAlmostEqual(valeurs['longueur_rangees_m'], 12.0, places=2)

    def test_un_trou_coupe_la_rangee(self):
        panneaux = [(0.0, 1.0), (PAS, 1.0), (PAS * 3, 1.0), (PAS * 4, 1.0)]
        valeurs = fixation._grandeurs_du_document(layout(panneaux))['valeurs']
        self.assertEqual(valeurs['rangees'], 1)
        self.assertEqual(valeurs['jonctions'], 2)
        self.assertEqual(valeurs['extremites'], 4)
        self.assertAlmostEqual(valeurs['longueur_rangees_m'], 4.8, places=2)

    def test_pan_tourne_groupe_selon_son_azimut(self):
        azimut = 150.0
        angle = math.radians(azimut)
        pente = (math.sin(angle), math.cos(angle))
        rangee = (math.cos(angle), -math.sin(angle))
        panneaux = [(5 + k * PAS * rangee[0] + r * 2 * pente[0],
                     5 + k * PAS * rangee[1] + r * 2 * pente[1])
                    for r in (0, 1) for k in range(5)]
        valeurs = fixation._grandeurs_du_document(
            layout(panneaux, azimut))['valeurs']
        self.assertEqual(valeurs['rangees'], 2)
        self.assertEqual(valeurs['jonctions'], 8)
        self.assertAlmostEqual(valeurs['longueur_rangees_m'], 12.0, places=2)

    def test_plein_sud_meme_groupement_que_le_tableur(self):
        modules = [(1.0, 1.0), (2.2, 1.0), (1.0, 3.0), (2.2, 3.004),
                   (3.4, 5.0)]
        rangs = rangees_du_pan(modules)
        attendu = sorted(sorted(round(c[0], 6) for c in modules
                                if rangs[c] == rang)
                         for rang in set(rangs.values()))
        # Plein sud, l'axe de position est l'est RETOURNÉ : on compare la
        # PARTITION des modules en rangées, pas le signe de l'axe.
        obtenu = sorted(sorted(round(-position, 6) for position in rangee)
                        for rangee in fixation._rangees_orientees(modules,
                                                                  180.0))
        self.assertEqual(obtenu, attendu)

    def test_pan_sans_voisin_nomme_la_longueur(self):
        panneaux = [(1.0, 1.0), (1.0, 3.0)]
        lues = fixation._grandeurs_du_document(layout(panneaux))
        self.assertIsNone(lues['valeurs']['longueur_rangees_m'])
        self.assertIn('Pan Sud', lues['manquants']['longueur_rangees_m'])
        self.assertEqual(lues['valeurs']['jonctions'], 0)
        self.assertEqual(lues['valeurs']['extremites'], 4)

    def _rangees_orientees(self, orients, ordonnees=(1.0, 3.0, 5.0, 7.0, 9.0)):
        """Une rangée de trois modules par ordonnée, ``orients`` par rangée
        (une liste de trois poses pour une rangée mixte)."""
        panneaux, poses = [], []
        for y, pose in zip(ordonnees, orients):
            for k in range(3):
                panneaux.append((1.0 + PAS * k, y))
                poses.append(pose[k] if isinstance(pose, list) else pose)
        return panneaux, poses

    def test_bases_d_orientation_lues_sur_le_document(self):
        # ACAL569 — 2 rangées paysage et 3 rangées portrait.
        panneaux, poses = self._rangees_orientees(
            ['landscape'] * 2 + ['portrait'] * 3)
        lues = fixation._grandeurs_du_document(
            layout(panneaux, pose='mixed', orients=poses))
        valeurs = lues['valeurs']
        self.assertEqual(valeurs['rangees_paysage'], 2)
        self.assertEqual(valeurs['rangees_portrait'], 3)
        self.assertEqual(valeurs['modules_paysage'], 6)
        self.assertEqual(valeurs['modules_portrait'], 9)
        self.assertEqual(lues['manquants'], {})

    def test_regle_rangees_paysage_ne_compte_que_le_paysage(self):
        panneaux, poses = self._rangees_orientees(
            ['landscape'] * 2 + ['portrait'] * 3)
        grandeurs = fixation._grandeurs_du_document(
            layout(panneaux, pose='mixed', orients=poses))
        croise = composant('Rail croisé', 'rail', 'u',
                           {'base': 'rangees_paysage', 'facteur': 4})
        ligne = fixation._lignes_de_fixation([croise], grandeurs)[0]
        # 4 × 2 rangées paysage — et non 4 × 5 rangées.
        self.assertEqual(ligne['quantite'], 8)

    def test_rangee_mixte_compte_ses_modules_et_aucune_rangee(self):
        panneaux, poses = self._rangees_orientees(
            [['portrait', 'portrait', 'landscape'], 'portrait'],
            ordonnees=(1.0, 3.0))
        lues = fixation._grandeurs_du_document(
            layout(panneaux, pose='mixed', orients=poses))
        valeurs = lues['valeurs']
        self.assertEqual((valeurs['modules_portrait'],
                          valeurs['modules_paysage']), (5, 1))
        self.assertEqual((valeurs['rangees_portrait'],
                          valeurs['rangees_paysage']), (1, 0))
        self.assertEqual(sorted(lues['manquants']),
                         ['rangees_paysage', 'rangees_portrait'])
        self.assertIn('mixte', lues['manquants']['rangees_paysage'])

    def test_orientation_non_enregistree_nomme_le_pan(self):
        lues = fixation._grandeurs_du_document(layout(deux_rangees_de_cinq()))
        for base in ('modules_portrait', 'modules_paysage',
                     'rangees_portrait', 'rangees_paysage'):
            with self.subTest(base=base):
                self.assertIsNone(lues['valeurs'][base])
                self.assertIn('Pan Sud', lues['manquants'][base])
        self.assertEqual(lues['valeurs']['modules'], 10)  # inchangées

    def test_sans_conception_ou_sans_module_tout_est_nomme(self):
        for document in (None, {}, layout([])):
            with self.subTest(document=bool(document)):
                lues = fixation._grandeurs_du_document(document)
                self.assertTrue(all(valeur is None for valeur
                                    in lues['valeurs'].values()))
                self.assertTrue(all(motif.strip() for motif
                                    in lues['manquants'].values()))


def layout_deux_pans(existants, neufs, *, existant=True, annee=2019):
    """ACAL575 — Pan A (``existant``) puis Pan B neuf, mêmes dimensions."""
    document = layout(existants)
    zone_a = document['zones'][0]
    zone_a['label'] = 'Pan A'
    if existant is not None:
        zone_a['existant'] = existant
    if annee is not None:
        zone_a['anneeMiseEnService'] = annee
    zone_b = copy.deepcopy(zone_a)
    zone_b.update(id='z2', label='Pan B')
    zone_b.pop('existant', None)
    zone_b.pop('anneeMiseEnService', None)
    zone_b['geometry']['panels'] = [{'cx': x, 'cy': y} for x, y in neufs]
    zone_b['geometry']['count'] = len(neufs)
    document['zones'].append(zone_b)
    return document


class PanExistantExcluDeLaFixationTest(SimpleTestCase):
    """ACAL575 — les modules d'un pan « existant » ne se commandent pas."""

    def neufs(self):
        return [(1.0 + PAS * k, y) for y in (1.0, 3.0) for k in range(3)]

    def test_dix_existants_et_six_neufs_comptent_six(self):
        valeurs = fixation._grandeurs_du_document(
            layout_deux_pans(deux_rangees_de_cinq(), self.neufs()))['valeurs']
        self.assertEqual(valeurs['modules'], 6)
        self.assertEqual(valeurs['pans'], 1)
        self.assertEqual(valeurs['rangees'], 2)
        self.assertEqual(valeurs['jonctions'], 4)
        self.assertEqual(valeurs['extremites'], 4)
        self.assertAlmostEqual(valeurs['longueur_rangees_m'], 7.2, places=2)

    def test_un_pan_sans_la_cle_se_compte_comme_avant(self):
        valeurs = fixation._grandeurs_du_document(
            layout_deux_pans(deux_rangees_de_cinq(), self.neufs(),
                             existant=None))['valeurs']
        self.assertEqual(valeurs['modules'], 16)
        self.assertEqual(valeurs['pans'], 2)

    def test_tout_existant_n_a_aucun_module_a_commander(self):
        document = layout_deux_pans(deux_rangees_de_cinq(), self.neufs())
        document['zones'][1]['existant'] = True
        lues = fixation._grandeurs_du_document(document)
        self.assertTrue(all(v is None for v in lues['valeurs'].values()))


def avec_surface(document, kind, **surface):
    """ACAL578 — ajoute une surface de pose (repère local du moteur, mètres)."""
    document.setdefault('poseSurfaces', []).append(dict(
        {'id': f's{len(document.get("poseSurfaces", [])) + 1}', 'kind': kind,
         'label': f'Surface {kind}', 'contourM': [[0, 0], [10, 0], [10, 6], [0, 6]]},
        **surface))
    return document


def douze_tables():
    return {'modules': 48, 'tables': [{'x0': 0, 'y0': 2 * k, 'x1': 4, 'y1': 2 * k + 1}
                                      for k in range(12)]}


class TablesPoteauxPiedsTest(SimpleTestCase):
    """ACAL578 — bases ``tables``, ``poteaux`` et ``pieds``."""

    PIEUX = composant('Pieu', 'pieu', 'u', {'base': 'tables', 'facteur': 4,
                                            'libelle_facteur': 'pieux par table'})

    def test_douze_tables_fois_quatre_donnent_quarante_huit(self):
        document = avec_surface(layout(deux_rangees_de_cinq()), 'sol', engine=douze_tables())
        grandeurs = fixation._grandeurs_du_document(document)
        self.assertEqual(fixation._lignes_de_fixation([self.PIEUX], grandeurs)[0]['quantite'], 48)

    def test_champ_au_sol_seul_garde_ses_tables(self):
        document = avec_surface({'version': 2}, 'sol', engine=douze_tables())
        self.assertEqual(fixation._grandeurs_du_document(document)['valeurs']['tables'], 12)

    def test_contour_dix_sur_six_entraxe_deux_et_demi_treize_poteaux(self):
        contour = [(0, 0), (10, 0), (10, 6), (0, 6)]
        self.assertEqual(len(fixation._positions_appuis(contour, 2.5)), 13)
        document = avec_surface(layout(deux_rangees_de_cinq()), 'ombriere',
                                appuis={'pasM': 2.5, 'sectionM': 0.2})
        self.assertEqual(fixation._grandeurs_du_document(document)['valeurs']['poteaux'], 13)

    def test_entraxe_absent_nomme_la_grandeur(self):
        document = avec_surface(layout(deux_rangees_de_cinq()), 'ombriere',
                                appuis={'sectionM': 0.2})
        lues = fixation._grandeurs_du_document(document)
        self.assertIsNone(lues['valeurs']['poteaux'])
        self.assertIn('Entraxe des appuis non renseigné sur « Surface ombriere »',
                      lues['manquants']['poteaux'])

    def test_douze_modules_pas_1_15_portee_2_4_sept_pieds(self):
        # Mutant « ⌈m ÷ k⌉ sans le + 1 » : 6 pieds ⇒ échec.
        document = layout([(1.0 + 1.15 * k, 1.0) for k in range(12)])
        document['zones'][0]['porteeEntrePieds'] = {'valeurM': 2.4, 'source': 'notice, p. 4'}
        self.assertEqual(fixation._grandeurs_du_document(document)['valeurs']['pieds'], 7)

    def test_portee_non_saisie_nomme_le_pan(self):
        document = layout_deux_pans(deux_rangees_de_cinq(), deux_rangees_de_cinq(),
                                    existant=None)
        document['zones'][0]['porteeEntrePieds'] = {'valeurM': 2.4, 'source': 'notice'}
        lues = fixation._grandeurs_du_document(document)
        self.assertIsNone(lues['valeurs']['pieds'])
        self.assertIn('Portée entre pieds non saisie', lues['manquants']['pieds'])
        self.assertIn('Pan B', lues['manquants']['pieds'])

    def test_sans_surface_ni_portee_les_six_bases_inchangees(self):
        lues = fixation._grandeurs_du_document(layout(deux_rangees_de_cinq(), pose='portrait'))
        self.assertEqual(lues['manquants'], {})
        self.assertEqual((lues['valeurs']['modules'], lues['valeurs']['jonctions']), (10, 8))
        ligne = fixation._lignes_de_fixation(
            [composant('Pied', 'pied', 'u', {'base': 'pieds'})], lues)[0]
        self.assertIsNone(ligne['quantite'])
        self.assertIn('portée entre pieds', ligne['manquant'])


def avec_egout(document, hauteur=6.0, source='mesurée au télémètre', aretes=None):
    """ACAL598 — l'arête 0 du pan typée « égout », le pan rattaché au bâtiment B1."""
    zone = document['zones'][0]
    zone['edges'] = aretes if aretes is not None else [
        {'index': 0, 'type': 'egout'}, {'index': 1, 'type': 'rive'},
        {'index': 2, 'type': 'faitage'}, {'index': 3, 'type': 'rive'}]
    zone['buildingId'] = 'B1'
    document['buildings'] = [{'id': 'B1', 'label': 'Villa', 'hauteurM': hauteur, 'source': source}]
    return document


class EchafaudageTest(SimpleTestCase):
    """ACAL598 — bases ``longueur_egouts_m`` / ``facade_egouts_m2`` (rôle échafaudage)."""

    ECHAFAUDAGE = [
        composant('Échafaudage', 'echafaudage', 'm²', {'base': 'facade_egouts_m2'}),
        composant("Marge d'échafaudage en hauteur", 'echafaudage', 'm²',
                  {'base': 'longueur_egouts_m', 'facteur': 1.5,
                   'libelle_facteur': 'marge en hauteur (m)'}),
    ]

    def longueur_de_l_arete_0(self, document):
        from apps.calepinage.services.planche import geometrie_de_planche

        points = geometrie_de_planche(document)['pans'][0]['points']
        return math.dist(points[0], points[1])

    def test_egout_fois_six_metres_saisis(self):
        # Mutant « + 2 m ajoutés à la hauteur » : × 8 au lieu de × 6 ⇒ échec.
        document = avec_egout(layout(deux_rangees_de_cinq()))
        metres = self.longueur_de_l_arete_0(document)
        grandeurs = fixation._grandeurs_du_document(document)
        self.assertEqual(grandeurs['valeurs']['longueur_egouts_m'], round(metres, 2))
        self.assertEqual(grandeurs['valeurs']['facade_egouts_m2'], round(metres * 6.0, 2))
        surface, marge = fixation._lignes_de_fixation(self.ECHAFAUDAGE, grandeurs)
        self.assertEqual(surface['quantite'], round(metres * 6.0, 2))
        self.assertEqual(marge['quantite'], round(round(metres, 2) * 1.5, 2))
        self.assertIn('marge en hauteur (m)', marge['regle'])

    def test_hauteur_non_saisie_nommee(self):
        lues = fixation._grandeurs_du_document(
            avec_egout(layout(deux_rangees_de_cinq()), hauteur=None, source=None))
        self.assertIsNone(lues['valeurs']['facade_egouts_m2'])
        self.assertIn('Hauteur du bâtiment « Villa » non saisie', lues['manquants']['facade_egouts_m2'])
        ligne = fixation._lignes_de_fixation(self.ECHAFAUDAGE[:1], lues)[0]
        self.assertIsNone(ligne['quantite'])

    def test_hauteur_sans_source_reste_non_saisie(self):
        lues = fixation._grandeurs_du_document(
            avec_egout(layout(deux_rangees_de_cinq()), source=''))
        self.assertIsNone(lues['valeurs']['facade_egouts_m2'])

    def test_arete_non_typee_rend_none(self):
        document = layout_deux_pans(deux_rangees_de_cinq(), deux_rangees_de_cinq(), existant=None)
        avec_egout(document)
        document['zones'][1]['edges'] = [{'index': 0, 'type': 'inconnue'}]
        lues = fixation._grandeurs_du_document(document)
        self.assertIsNone(lues['valeurs']['longueur_egouts_m'])
        self.assertIn('Pan B', lues['manquants']['longueur_egouts_m'])

    def test_systeme_sans_echafaudage_lignes_d_aujourd_hui(self):
        sans = fixation._grandeurs_du_document(layout(deux_rangees_de_cinq(), pose='portrait'))
        avec = fixation._grandeurs_du_document(
            avec_egout(layout(deux_rangees_de_cinq(), pose='portrait')))
        self.assertEqual(fixation._lignes_de_fixation(composants_du_contrat(), avec),
                         fixation._lignes_de_fixation(composants_du_contrat(), sans))
        self.assertEqual(sans['manquants'], {})


class FixationParPanTest(SimpleTestCase):
    """ACAL592 - la nomenclature PAR PAN : memes regles, somme = globale."""

    def deux_pans(self, neufs_b=None, **options):
        six = [(1.0 + PAS * k, y) for y in (1.0, 3.0) for k in range(3)]
        quatre = neufs_b if neufs_b is not None else [
            (1.0 + PAS * k, y) for y in (1.0, 3.0) for k in range(2)]
        return layout_deux_pans(six, quatre, existant=None, annee=None,
                                **options)

    def composants(self):
        return [c for c in composants_du_contrat()
                if c.role in ('rail', 'pince_milieu')]

    def quantites(self, lignes):
        return {ligne['role']: ligne['quantite'] for ligne in lignes}

    def test_la_somme_des_rails_des_pans_egale_le_rail_global(self):
        document = self.deux_pans()
        par_pan = fixation._lignes_par_pan(document, self.composants())
        self.assertEqual(sorted(par_pan), ['z1', 'z2'])
        globales = self.quantites(fixation._lignes_de_fixation(
            self.composants(), fixation._grandeurs_du_document(document)))
        somme = sum(self.quantites(lignes)['rail']
                    for lignes in par_pan.values())
        self.assertAlmostEqual(somme, globales['rail'], delta=0.01 * 2)
        # Chaque pan porte SES grandeurs : 6 modules != 4 modules.
        self.assertNotEqual(self.quantites(par_pan['z1'])['rail'],
                            self.quantites(par_pan['z2'])['rail'])

    def test_la_pince_en_unite_u_est_arrondie_par_pan(self):
        par_pan = fixation._lignes_par_pan(self.deux_pans(), self.composants())
        # 2 rangees de 3 : 4 jonctions x 2 ; 2 rangees de 2 : 2 x 2.
        self.assertEqual(self.quantites(par_pan['z1'])['pince_milieu'], 8)
        self.assertEqual(self.quantites(par_pan['z2'])['pince_milieu'], 4)

    def test_un_pas_non_releve_nomme_le_pan_et_ne_met_pas_de_zero(self):
        document = self.deux_pans(neufs_b=[(1.0, 1.0), (1.0, 3.0)])
        par_pan = fixation._lignes_par_pan(document, self.composants())
        rail = next(ligne for ligne in par_pan['z2']
                    if ligne['role'] == 'rail')
        self.assertIsNone(rail['quantite'])
        self.assertIn('Pan B', rail['manquant'])
        # L'autre pan reste calculable.
        self.assertIsNotNone(self.quantites(par_pan['z1'])['rail'])

    def test_un_pan_existant_n_a_pas_d_encart(self):
        document = self.deux_pans()
        document['zones'][0]['existant'] = True
        par_pan = fixation._lignes_par_pan(document, self.composants())
        self.assertEqual(sorted(par_pan), ['z2'])

    def test_sans_conception_aucun_pan(self):
        self.assertEqual(fixation._lignes_par_pan(None, self.composants()), {})

    def test_composant_d_egout_l_encart_nomme_la_quantite_du_projet_ou_la_saisie(self):
        # ACAL1722 — une grandeur du PROJET : jamais « illisible sur le document ».
        echafaudage = EchafaudageTest.ECHAFAUDAGE
        document = avec_egout(layout(deux_rangees_de_cinq()))
        globale = fixation._lignes_de_fixation(echafaudage, fixation._grandeurs_du_document(document))
        for ligne, projet in zip(fixation._lignes_par_pan(document, echafaudage)['z1'], globale):
            self.assertIsNone(ligne['quantite'])
            self.assertEqual(ligne['manquant'], 'Quantité du projet : voir la nomenclature (%s m²).'
                             % fixation._fr(projet['quantite']))
        sans_hauteur = avec_egout(layout(deux_rangees_de_cinq()), hauteur=None, source=None)
        self.assertIn('Hauteur du bâtiment « Villa » non saisie',
                      fixation._lignes_par_pan(sans_hauteur, echafaudage)['z1'][0]['manquant'])
        for ligne in fixation._lignes_par_pan(layout(deux_rangees_de_cinq()), echafaudage)['z1']:
            self.assertEqual(ligne['manquant'], "Arêtes d'égout non typées sur ce pan : l'échafaudage "
                                                "n'est pas calculé.")

    def test_sans_societe_pas_de_systeme_donc_pas_d_encart(self):
        self.assertIsNone(fixation.fixation_par_pan(
            SimpleNamespace(company=None, roof_layout=self.deux_pans())))


class LignesDeFixationTest(SimpleTestCase):

    def test_rejoue_exactement_l_exemple_committe(self):
        lignes = fixation._lignes_de_fixation(
            composants_du_contrat(), grandeurs(), {812, 813, 814, 815})
        self.assertEqual(lignes, CONTRAT['exemple']['lignes'])

    def test_diviseur_saisi_calcule_et_arrondit_a_l_unite_superieure(self):
        composants = composants_du_contrat()
        composants[3].regle = dict(composants[3].regle, diviseur=0.8)
        crochet = fixation._lignes_de_fixation(composants, grandeurs())[3]
        self.assertEqual(crochet['quantite'], 33)
        self.assertIsNone(crochet['manquant'])
        self.assertEqual(crochet['regle'],
                         'quantité de « rail » ÷ 0,8 (entraxe des crochets (m))')
        composants[3].regle = dict(composants[3].regle, diviseur=0.7)
        crochet = fixation._lignes_de_fixation(composants, grandeurs())[3]
        self.assertEqual(crochet['quantite'], math.ceil(26.4 / 0.7))

    def test_reference_calculee_meme_declaree_apres(self):
        composants = list(reversed(composants_du_contrat()))
        lignes = fixation._lignes_de_fixation(composants, grandeurs())
        self.assertEqual([ligne['role'] for ligne in lignes],
                         ['embout', 'crochet', 'pince_fin', 'pince_milieu',
                          'rail'])
        self.assertEqual(lignes[4]['quantite'], 26.4)

    def test_grandeur_illisible_propage_son_motif(self):
        lues = {'valeurs': dict(grandeurs()['valeurs'],
                                longueur_rangees_m=None),
                'manquants': {'longueur_rangees_m': 'pas illisible (essai)'}}
        lignes = fixation._lignes_de_fixation(composants_du_contrat(), lues)
        self.assertIsNone(lignes[0]['quantite'])
        self.assertEqual(lignes[0]['manquant'], 'pas illisible (essai)')
        self.assertIsNone(lignes[3]['quantite'])
        self.assertIn('« rail »', lignes[3]['manquant'])

    def test_reference_circulaire_ou_absente(self):
        boucle = [composant('A', 'rail', 'm', {'base': 'role:crochet'}),
                  composant('B', 'crochet', 'u', {'base': 'role:rail'}),
                  composant('C', 'visserie', 'u', {'base': 'role:lest'})]
        lignes = fixation._lignes_de_fixation(boucle, grandeurs())
        self.assertTrue(all(ligne['quantite'] is None for ligne in lignes))
        self.assertIn('circulaire', lignes[0]['manquant'])
        self.assertIn('circulaire', lignes[1]['manquant'])
        self.assertIn("qu'aucun composant", lignes[2]['manquant'])

    def test_produit_etranger_publie_null(self):
        lignes = fixation._lignes_de_fixation(composants_du_contrat(),
                                              grandeurs(), {813})
        self.assertIsNone(lignes[0]['produit_id'])
        self.assertEqual(lignes[1]['produit_id'], 813)

    def test_jamais_zero_de_repli(self):
        for ligne in fixation._lignes_de_fixation(composants_du_contrat(),
                                                  grandeurs()):
            self.assertNotEqual(ligne['quantite'], 0)


class AlertesDePoseTest(SimpleTestCase):
    """ACAL568 — la pose DÉCLARÉE contre la zone de serrage de la fiche."""

    ZONE = {'serrage_min_mm': 345, 'serrage_max_mm': 415}

    def _alertes(self, controles, module=None):
        from apps.calepinage.services.controles_pose import _alertes

        return _alertes(controles, self.ZONE if module is None else module)

    def test_300_hors_345_415_sort_zone_serrage(self):
        alertes = self._alertes({'distance_rail_bord_mm': 300})
        self.assertEqual(
            [(a['code'], a['gravite']) for a in alertes],
            [('zone_serrage', 'alerte')])
        self.assertEqual(
            alertes[0]['message'],
            'Rail à 300 mm du bord, hors de la zone de serrage du module '
            '(345 à 415 mm).')

    def test_dans_la_zone_et_aux_bornes_aucune_alerte(self):
        for distance in (380, 345, 415):
            with self.subTest(distance=distance):
                self.assertEqual(
                    self._alertes({'distance_rail_bord_mm': distance}), [])

    def test_porte_a_faux_au_dessus_du_maximum(self):
        alertes = self._alertes({'porte_a_faux_rail_mm': 700,
                                 'porte_a_faux_max_mm': 400})
        self.assertEqual(alertes[0]['code'], 'porte_a_faux')
        self.assertEqual(alertes[0]['message'],
                         'Porte-à-faux du rail 700 mm, 400 mm admis.')
        # Au maximum exact : admis (un ``>=`` est un mutant).
        self.assertEqual(self._alertes({'porte_a_faux_rail_mm': 400,
                                        'porte_a_faux_max_mm': 400}), [])

    def test_zone_absente_nomme_ce_qui_manque_sans_zone_de_repli(self):
        alertes = self._alertes({'distance_rail_bord_mm': 300}, module={})
        self.assertEqual([a['gravite'] for a in alertes], ['info'])
        self.assertIn('Zone de serrage du module non saisie',
                      alertes[0]['message'])

    def test_sans_devis_le_module_pose_sur_le_pan_sert_la_zone_de_serrage(self):
        """ACAL1531 — pas de devis lié : le module POSÉ sur le pan (étape
        Panneaux) porte la zone de serrage de sa fiche ; « non saisie sur sa
        fiche » ne sort que si la fiche est réellement vide."""
        import contextlib
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.controles_pose import alertes_du_systeme

        layout = {'modules': [{'id': 'm1', 'produitId': 77, 'libelle': 'Jinko'}],
                  'zones': [{'geometry': {'moduleId': 'm1',
                                          'panels': [{'n': i} for i in range(12)]}}]}
        calepinage = SimpleNamespace(company=SimpleNamespace(pk=1), roof_layout=layout, pk=5)
        systeme = SimpleNamespace(controles_pose={'distance_rail_bord_mm': 300})
        electrique = 'apps.calepinage.services.electrique.'

        def alertes(fiche):
            retours = {
                'apps.stock.selectors.get_produit_scoped':
                    SimpleNamespace(pk=77, nom='Jinko', sku='x'),
                'apps.stock.selectors.specs_for_produit': fiche,
                electrique + 'entree_stockee': {},
                electrique + 'materiel_de_la_conception': {},
                electrique + '_designation': 'Jinko',
                electrique + 'famille_de_l_onduleur': None,
            }
            with contextlib.ExitStack() as pile:
                for cible, valeur in retours.items():
                    pile.enter_context(mock.patch(cible, return_value=valeur))
                return alertes_du_systeme(calepinage, systeme)

        rendu = alertes({'serrage_min_mm': 345, 'serrage_max_mm': 415})
        self.assertEqual([a['code'] for a in rendu], ['zone_serrage'])
        self.assertEqual(rendu[0]['message'],
                         'Rail à 300 mm du bord, hors de la zone de serrage '
                         'du module (345 à 415 mm).')
        vide = alertes({})
        self.assertIn('non saisie sur sa fiche', vide[0]['message'])

    def test_controles_vides_une_ligne_info(self):
        alertes = self._alertes({})
        self.assertEqual([a['gravite'] for a in alertes], ['info'])
        self.assertIn('non saisis', alertes[0]['message'])

    def test_validation_exige_une_source_et_des_nombres(self):
        from apps.calepinage.services.controles_pose import (
            erreur_de_controles_pose,
        )

        self.assertEqual(erreur_de_controles_pose({}), '')
        self.assertEqual(erreur_de_controles_pose(
            {'distance_rail_bord_mm': 300, 'source': 'notice X'}), '')
        self.assertIn('source', erreur_de_controles_pose(
            {'distance_rail_bord_mm': 300}))
        self.assertIn('nombre', erreur_de_controles_pose(
            {'distance_rail_bord_mm': 'trois', 'source': 'notice X'}))
        self.assertIn('inconnu', erreur_de_controles_pose({'autre': 1}))


class CatalogueVideTest(SimpleTestCase):

    def test_la_reponse_est_l_exemple_vide(self):
        calepinage = SimpleNamespace(company=None, roof_layout=None)
        systeme, refus = fixation.resoudre_systeme(calepinage.company)
        self.assertIsNone(systeme)
        self.assertEqual(fixation.bom_de_fixation(calepinage, systeme, refus),
                         EXEMPLE_VIDE_SERVI)

    def test_aucune_feuille_de_fixation_sans_catalogue(self):
        calepinage = SimpleNamespace(company=None, roof_layout=None)
        self.assertIsNone(fixation.table_fixation(calepinage))


# ── ORM — la CI est la gate de ces classes ─────────────────────────────────


def url_bom(pk, **params):
    suite = ''.join(f'?{cle}={valeur}' for cle, valeur in params.items())
    return f'{url_detail(pk)}bom-fixation/{suite}'


class BomFixationEnBase(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=layout(deux_rangees_de_cinq()))

    def _systeme(self, company=None, code='incline'):
        company = company or self.company
        systeme = SystemeFixation.objects.create(
            company=company, code=code, libelle=f'Système {code}',
            provenance='Notice fabricant (essai)')
        ComposantFixation.objects.create(
            company=company, systeme=systeme, role='rail', libelle='Rail',
            unite='m', source='Notice', ordre=1,
            regle={'base': 'longueur_rangees_m', 'facteur': 2})
        ComposantFixation.objects.create(
            company=company, systeme=systeme, role='pince_milieu',
            libelle='Pince de milieu', unite='u', source='Notice', ordre=2,
            regle={'base': 'jonctions', 'facteur': 2})
        return systeme

    def test_catalogue_vide_sert_l_exemple_vide(self):
        reponse = self.api.get(url_bom(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, EXEMPLE_VIDE_SERVI)

    def test_unique_systeme_actif_applique(self):
        systeme = self._systeme()
        reponse = self.api.get(url_bom(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['systeme']['id'], systeme.pk)
        self.assertEqual([ligne['quantite'] for ligne in reponse.data['lignes']],
                         [24.0, 16])
        # ACAL81 — la réponse porte aussi ``systeme_source`` (contrat).
        self.assertEqual(sorted(reponse.data),
                         ['alertes', 'lignes', 'refus', 'systeme',
                          'systeme_source'])  # alertes : ACAL568
        self.assertEqual(reponse.data['systeme_source'], 'parametre')

    def test_plusieurs_systemes_sans_choix_refus_nomme(self):
        self._systeme(code='a')
        choisi = self._systeme(code='b')
        reponse = self.api.get(url_bom(self.calepinage.pk))
        self.assertIsNone(reponse.data['systeme'])
        self.assertEqual(reponse.data['refus'][0]['champ'], 'systeme')
        reponse = self.api.get(url_bom(self.calepinage.pk,
                                       systeme=choisi.pk))
        self.assertEqual(reponse.data['systeme']['code'], 'b')

    def test_systeme_d_une_autre_societe_refuse(self):
        etranger = self._systeme(company=self.autre, code='etranger')
        reponse = self.api.get(url_bom(self.calepinage.pk,
                                       systeme=etranger.pk))
        self.assertIsNone(reponse.data['systeme'])
        self.assertEqual(reponse.data['refus'][0]['champ'], 'systeme')

    def test_calepinage_d_une_autre_societe_introuvable(self):
        reponse = self.api_autre.get(url_bom(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_feuille_fixation_au_classeur_seulement_avec_catalogue(self):
        from openpyxl import load_workbook

        from apps.calepinage.services.export_tableur import exporter_xlsx

        sans = load_workbook(io.BytesIO(exporter_xlsx(self.calepinage)))
        self.assertNotIn('Fixation', sans.sheetnames)
        self._systeme()
        avec = load_workbook(io.BytesIO(exporter_xlsx(self.calepinage)))
        self.assertEqual(avec.sheetnames[-1], 'Fixation')

    def test_rien_n_est_ecrit(self):
        self._systeme()
        avant = copy.deepcopy(self.calepinage.roof_layout)
        self.api.get(url_bom(self.calepinage.pk))
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, avant)
