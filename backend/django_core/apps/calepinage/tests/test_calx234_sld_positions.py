# -*- coding: utf-8 -*-
"""CALX234 — les POSITIONS de blocs, persistées et passées jusqu'au dessin.

CE QUE CE FICHIER ARME
----------------------
1. **Le chemin ``devis=`` n'a pas bougé d'un octet.** La porte cross-app
   ``apps/ventes/selectors.py::schema_unifilaire_svg`` garde EXACTEMENT ses
   cinq paramètres (aucune ``positions`` ajoutée), ne dessine rien, et le
   chemin CALEPINAGE ne l'importe plus : il appelle le moteur directement.
   Sans édition, le SVG que le calepinage publie est IDENTIQUE, caractère
   pour caractère, à celui que la porte rend.
2. **Une position posée déplace le bloc** — dans ``blocs`` comme dans le SVG
   — et le VERROUILLE (le serpentin ne le recalcule plus).
3. **Une clef inconnue est refusée en la nommant**, et une position **hors
   planche** est refusée en nommant la clef ET la borne du format.
4. **La route sert GET et POST** sous le même ``url_path``, gardée par la
   permission à deux codes (lecture/écriture).

``SimpleTestCase`` : aucune base de données. Les tests de la VUE elle-même
(corps HTTP réel, société, 400) exigent une base et sont laissés à la CI.

Run :
    python manage.py test apps.calepinage.tests.test_calx234_sld_positions
"""
from __future__ import annotations

import ast
import inspect
import json
import pathlib
import re

from django.test import SimpleTestCase

from core.electrique import concevoir
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

from apps.calepinage.services.sld import (
    SldRefuse, enregistrer_edition_sld, rendu_du_schema,
)
from apps.calepinage.views.schema import CLES_SCHEMA

SERVICE_SLD = (pathlib.Path(__file__).resolve().parents[1]
               / 'services' / 'sld.py').read_text(encoding='utf-8')
CONTRAT_SLD = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_sld.json').read_text(encoding='utf-8'))

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35,
                    designation='Canadian Solar 550 Wc')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0,
                        designation='Deye SUN-10K-SG05LP3')


def _modules_importes(source):
    """Les modules RÉELLEMENT importés par ce fichier (``ast``, pas du texte).

    Une docstring qui NOMME la porte cross-app n'est pas un import : le
    contrôle porte sur le code, jamais sur la prose qui raconte l'histoire.
    """
    noms = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            noms.extend(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            noms.append(noeud.module)
    return noms


class CalepinageFactice:
    """Le pivot RÉDUIT à ce que le service touche."""

    def __init__(self, pk=11):
        self.pk = pk
        self.resultat = None
        self.sauvegardes = []

    def save(self, **kwargs):
        self.sauvegardes.append(kwargs)


class ScenarioPositions(SimpleTestCase):
    def setUp(self):
        self.entree = EntreeElectrique(
            module=MODULE, onduleur=ONDULEUR,
            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
            dc_m=30.0, ac_m=12.0)
        self.resultat = concevoir(self.entree)
        self.dessin = rendu_du_schema(self.entree, self.resultat)
        self.calepinage = CalepinageFactice()

    def _poser(self, corps):
        return enregistrer_edition_sld(self.calepinage, corps,
                                       dessin=self.dessin)

    def _bloc(self, dessin, clef):
        for bloc in dessin['blocs']:
            if bloc['clef'] == clef:
                return bloc
        self.fail('Bloc « %s » absent du dessin.' % clef)


class LeCheminDevisEstIntactTest(SimpleTestCase):
    """1 — ``apps/ventes`` n'est ni modifié, ni traversé."""

    def test_la_porte_cross_app_garde_ses_cinq_parametres(self):
        from apps.ventes.selectors import schema_unifilaire_svg

        signature = inspect.signature(schema_unifilaire_svg)
        self.assertEqual(
            list(signature.parameters),
            ['devis', 'entree', 'resultat', 'cartouche', 'standard'],
            "La porte du devis a gagné un paramètre : le SVG d'un devis ne "
            'peut plus être garanti identique.')

    def test_le_service_du_calepinage_n_importe_plus_la_porte(self):
        """Les IMPORTS, pas la prose : la docstring RACONTE la porte, le code
        ne l'atteint plus."""
        self.assertEqual(
            [nom for nom in _modules_importes(SERVICE_SLD)
             if nom.startswith('apps.ventes')], [])

    def test_la_vue_du_calepinage_n_importe_plus_la_porte(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'views'
                  / 'schema.py').read_text(encoding='utf-8')
        self.assertEqual(
            [nom for nom in _modules_importes(source)
             if nom.startswith('apps.ventes')], [])

    def test_sans_edition_le_dessin_est_celui_de_la_porte(self):
        """Non-régression : le calepinage publie le MÊME SVG qu'avant."""
        from apps.ventes.selectors import schema_unifilaire_svg

        entree = EntreeElectrique(
            module=MODULE, onduleur=ONDULEUR,
            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
            dc_m=30.0, ac_m=12.0)
        resultat = concevoir(entree)
        cartouche = {'client': 'Atlas', 'reference': 'CAL-1',
                     'date': '21/09/2026'}
        self.assertEqual(
            rendu_du_schema(entree, resultat, cartouche=cartouche)['svg'],
            schema_unifilaire_svg(entree=entree, resultat=resultat,
                                  cartouche=cartouche))


class UnePositionDeplaceLeBlocTest(ScenarioPositions):
    """2 — la surcharge de position du moteur devient atteignable."""

    def test_le_bloc_publie_porte_la_position_forcee(self):
        edition = self._poser({'positions': {'tgbt': {'x': 600, 'y': 300}}})
        bloc = self._bloc(rendu_du_schema(self.entree, self.resultat,
                                          edition=edition), 'tgbt')
        self.assertEqual((bloc['x'], bloc['y']), (600.0, 300.0))

    def test_le_bloc_deplace_est_verrouille(self):
        edition = self._poser({'positions': {'tgbt': {'x': 600, 'y': 300}}})
        bloc = self._bloc(rendu_du_schema(self.entree, self.resultat,
                                          edition=edition), 'tgbt')
        self.assertTrue(bloc['verrouille'],
                        'Sans verrou, le serpentin recalculerait la position '
                        'au prochain rendu.')

    def test_le_svg_dessine_la_boite_a_la_position_forcee(self):
        avant = self._bloc(self.dessin, 'tgbt')
        self.assertNotEqual((avant['x'], avant['y']), (600.0, 300.0))
        edition = self._poser({'positions': {'tgbt': {'x': 600, 'y': 300}}})
        svg = rendu_du_schema(self.entree, self.resultat,
                              edition=edition)['svg']
        groupe = re.search(r'<g data-bloc="tgbt".*?</g>', svg)
        self.assertIsNotNone(groupe, 'Le bloc TGBT a disparu du dessin.')
        self.assertIn('x="600" y="300"', groupe.group(0))

    def test_les_autres_blocs_ne_bougent_pas(self):
        edition = self._poser({'positions': {'tgbt': {'x': 600, 'y': 300}}})
        apres = rendu_du_schema(self.entree, self.resultat, edition=edition)
        for bloc in self.dessin['blocs']:
            if bloc['clef'] == 'tgbt':
                continue
            self.assertEqual(self._bloc(apres, bloc['clef']),
                             bloc,
                             'Déplacer un organe ne déplace que lui.')

    def test_la_position_est_persistee_sous_sa_cle_json(self):
        self._poser({'positions': {'tgbt': {'x': 600, 'y': 300}}})
        self.assertEqual(
            self.calepinage.resultat['sld_edition']['positions'],
            {'tgbt': {'x': 600.0, 'y': 300.0}})


class RefusDePositionTest(ScenarioPositions):
    """3 — clef inconnue et position hors planche, refusées EN LES NOMMANT."""

    def test_une_clef_inconnue_est_refusee_en_la_nommant(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'positions': {'coffret_ac': {'x': 10, 'y': 10}}})
        self.assertIn('coffret_ac', str(refus.exception))
        self.assertEqual(refus.exception.champ,
                         'edition.positions.coffret_ac')

    def test_le_champ_de_refus_est_celui_du_contrat(self):
        """Le contrat CALX204 décrit ce refus : même clef de champ."""
        attendu = sorted(CONTRAT_SLD['refus_clef_inconnue'])
        self.assertEqual(attendu, ['edition.positions.coffret_ac'])
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'positions': {'coffret_ac': {'x': 10, 'y': 10}}})
        self.assertEqual(refus.exception.champ, attendu[0])

    def test_une_position_hors_planche_nomme_la_clef_et_la_borne(self):
        largeur = self.dessin['largeur']
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'positions': {'tgbt': {'x': largeur + 50,
                                                'y': 100}}})
        message = str(refus.exception)
        self.assertIn('tgbt', message)
        self.assertIn('x', message)
        self.assertIn(str(int(largeur)), message)
        self.assertEqual(refus.exception.champ, 'edition.positions.tgbt')

    def test_une_position_negative_est_refusee(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'positions': {'tgbt': {'x': 10, 'y': -1}}})
        self.assertIn('y', str(refus.exception))

    def test_une_position_sans_y_est_refusee(self):
        with self.assertRaises(SldRefuse) as refus:
            self._poser({'positions': {'tgbt': {'x': 10}}})
        self.assertEqual(refus.exception.champ, 'edition.positions.tgbt')

    def test_un_refus_n_ecrit_rien(self):
        with self.assertRaises(SldRefuse):
            self._poser({'positions': {'tgbt': {'x': 99999, 'y': 0}}})
        self.assertEqual(self.calepinage.sauvegardes, [])


class PorteHttpTest(SimpleTestCase):
    """4 — la route sert GET et POST, sous le même chemin, bien gardée."""

    def test_l_action_est_decouverte_en_get_et_post(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        par_nom = {action.__name__: action
                   for action in CalepinageViewSet.get_extra_actions()}
        self.assertIn('schema_unifilaire', par_nom)
        self.assertEqual(set(par_nom['schema_unifilaire'].mapping),
                         {'get', 'post'})

    def test_le_chemin_est_celui_du_contrat(self):
        from django.urls import reverse

        route = CONTRAT_SLD['endpoint'].partition(' ')[2]
        self.assertEqual(
            reverse('calepinage-schema-unifilaire', args=('1',)),
            route.replace('<int:pk>', '1'))

    def test_la_garde_couvre_lecture_ET_ecriture(self):
        from apps.calepinage.permissions import PeutLireOuEcrireCalepinage
        from apps.calepinage.views.schema import SchemaUnifilaireMixin

        action = SchemaUnifilaireMixin.schema_unifilaire
        self.assertIn(PeutLireOuEcrireCalepinage,
                      action.kwargs['permission_classes'])

    def test_les_six_cles_de_reponse_sont_celles_du_contrat(self):
        self.assertEqual(sorted(CLES_SCHEMA),
                         sorted(CONTRAT_SLD['exemple']))
