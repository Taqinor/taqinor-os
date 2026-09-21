# -*- coding: utf-8 -*-
"""CALX235 — l'export DXF du schéma unifilaire.

CE QUE CE FICHIER ARME
----------------------
1. **Le document relu par ``ezdxf.read``** porte les QUATRE calques
   (``SLD_BLOCS``, ``SLD_LIAISONS``, ``SLD_TEXTES``, ``SLD_TABLEAU``), un
   texte par repère, et autant de liaisons que le SVG en dessine.
2. **Jamais une seconde géométrie** : une position éditée (CALX234) déplace
   le rectangle du DXF exactement comme elle déplace la boîte du SVG.
3. **Unités déclarées** : ``$INSUNITS`` en millimètres — un DXF sans unité
   s'ouvre en pouces chez la moitié des lecteurs.
4. **Reproductible** : deux exports des MÊMES entrées donnent les MÊMES
   octets.
5. **Fiche incomplète ⇒ aucun fichier**, et le refus NOMME le champ.

``@tag('slow')`` comme la tâche le demande (l'écriture d'un DXF complet
n'est pas une assertion de quelques microsecondes). ``SimpleTestCase`` :
aucune base de données — la conception est construite par le noyau pur et
passée au service par son court-circuit interne.

Run :
    python manage.py test apps.calepinage.tests.test_calx235_sld_dxf
"""
from __future__ import annotations

import io

from django.test import SimpleTestCase, tag

from core.electrique import concevoir
from core.electrique.schema import lignes_tableau
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

from apps.calepinage.services.sld import (
    SldRefuse, gabarit_de_schema, rendu_du_schema,
)
from apps.calepinage.services.sld_export import (
    CALQUE_BLOCS, CALQUE_LIAISONS, CALQUE_TABLEAU, CALQUE_TEXTES, CALQUES,
    MM_PAR_PX, exporter_sld_dxf,
)

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35,
                    designation='Canadian Solar 550 Wc')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0,
                        designation='Deye SUN-10K-SG05LP3')


def _entree():
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0)


def _relire(octets):
    import ezdxf

    return ezdxf.read(io.StringIO(octets.decode('utf-8')))


def _entites(document, calque):
    return [entite for entite in document.modelspace()
            if entite.dxf.layer == calque]


@tag('slow')
class ExportDxfTest(SimpleTestCase):
    """Le décor : une conception complète, son dessin, son DXF."""

    def setUp(self):
        self.entree = _entree()
        self.resultat = concevoir(self.entree)
        self.dessin = rendu_du_schema(self.entree, self.resultat)
        self.lignes = lignes_tableau(self.resultat)
        self.octets = exporter_sld_dxf(None, dessin=self.dessin,
                                       lignes=self.lignes)
        self.document = _relire(self.octets)

    def test_les_quatre_calques_sont_la(self):
        presents = {calque.dxf.name for calque in self.document.layers}
        for nom, _couleur in CALQUES:
            self.assertIn(nom, presents)

    def test_un_rectangle_par_bloc_dessine(self):
        self.assertEqual(len(_entites(self.document, CALQUE_BLOCS)),
                         len(self.dessin['blocs']))

    def test_un_texte_par_repere(self):
        textes = {entite.dxf.text
                  for entite in _entites(self.document, CALQUE_TEXTES)}
        reperes = {bloc['repere'] for bloc in self.dessin['blocs']
                   if bloc['repere']}
        self.assertTrue(reperes, 'Le dessin de test doit porter des '
                                 'repères, sinon le contrôle est vide.')
        self.assertEqual(reperes - textes, set())

    def test_autant_de_liaisons_que_le_svg(self):
        """Le SVG émet UNE pointe de flèche par liaison dessinée."""
        attendu = self.dessin['svg'].count('<polygon')
        self.assertEqual(len(_entites(self.document, CALQUE_LIAISONS)),
                         attendu)
        self.assertEqual(len(self.dessin['liaisons']), attendu)

    def test_la_nomenclature_est_celle_de_la_planche(self):
        textes = {entite.dxf.text
                  for entite in _entites(self.document, CALQUE_TABLEAU)}
        for ligne in self.lignes:
            for valeur in ligne:
                if valeur:
                    self.assertIn(valeur, textes)

    def test_les_unites_sont_declarees_en_millimetres(self):
        from ezdxf import units

        self.assertEqual(self.document.header['$INSUNITS'], units.MM)

    def test_la_planche_tient_dans_son_format(self):
        """Une planche A4 paysage fait ~297 mm de large, pas 1122."""
        largeur_mm = self.dessin['largeur'] * MM_PAR_PX
        self.assertAlmostEqual(largeur_mm, 296.9, places=1)
        for entite in _entites(self.document, CALQUE_BLOCS):
            for x, y, *_reste in entite.get_points():
                self.assertGreaterEqual(x, 0.0)
                self.assertLessEqual(x, largeur_mm)
                self.assertGreaterEqual(y, 0.0)


@tag('slow')
class GeometrieUniqueTest(SimpleTestCase):
    """2 — la position éditée du SVG est celle du DXF."""

    def test_un_bloc_deplace_l_est_aussi_dans_le_dxf(self):
        entree = _entree()
        resultat = concevoir(entree)
        edition = {'libelles': {}, 'reperes': {},
                   'positions': {'tgbt': {'x': 600.0, 'y': 300.0}}}
        dessin = rendu_du_schema(entree, resultat, edition=edition)
        document = _relire(exporter_sld_dxf(
            None, dessin=dessin, lignes=lignes_tableau(resultat)))
        hauteur = dessin['hauteur']
        attendu = (round(600.0 * MM_PAR_PX, 3),
                   round((hauteur - 300.0) * MM_PAR_PX, 3))
        coins = set()
        for entite in _entites(document, CALQUE_BLOCS):
            for x, y, *_reste in entite.get_points():
                coins.add((round(x, 3), round(y, 3)))
        self.assertIn(attendu, coins,
                      'Le coin haut-gauche du TGBT déplacé doit exister dans '
                      'le DXF : le DXF et le SVG ne peuvent pas diverger.')


@tag('slow')
class ReproductibleTest(SimpleTestCase):
    """4 — mêmes entrées, mêmes octets."""

    def test_deux_exports_donnent_le_meme_fichier(self):
        entree = _entree()
        resultat = concevoir(entree)
        dessin = rendu_du_schema(entree, resultat)
        lignes = lignes_tableau(resultat)
        premier = exporter_sld_dxf(None, dessin=dessin, lignes=lignes)
        second = exporter_sld_dxf(None, dessin=dessin, lignes=lignes)
        self.assertEqual(premier, second,
                         "Deux exports de la même conception diffèrent : un "
                         'dossier déposé ne peut plus prouver que la pièce '
                         "n'a pas bougé.")

    def test_un_dessin_different_donne_un_fichier_different(self):
        """La reproductibilité n'est pas une constante déguisée."""
        entree = _entree()
        resultat = concevoir(entree)
        lignes = lignes_tableau(resultat)
        sans = exporter_sld_dxf(None, dessin=rendu_du_schema(entree,
                                                             resultat),
                                lignes=lignes)
        avec = exporter_sld_dxf(
            None,
            dessin=rendu_du_schema(entree, resultat, edition={
                'libelles': {'tgbt': 'Tableau général'},
                'reperes': {}, 'positions': {}}),
            lignes=lignes)
        self.assertNotEqual(sans, avec)


class _ConceptionMuette:
    """Une conception dont la fiche onduleur manque — l'objet que le service
    électrique rend dans ce cas (``fiche_incomplete``, ``manquantes``)."""

    MANQUANTE = ("onduleur : aucune fiche onduleur n'est désignée sur ce "
                 'calepinage — la chaîne ne peut pas être conçue.')

    fiche_incomplete = True
    resultat = None
    entree = None
    chaines = ()
    manquantes = (MANQUANTE,)


@tag('slow')
class FicheIncompleteTest(SimpleTestCase):
    """5 — aucun fichier, et le refus NOMME le champ.

    Seule la FRONTIÈRE est remplacée (``conception_du_calepinage``, qui
    interroge le stock) : la détection de l'empêchement, le message et
    l'extraction du champ fautif sont bien ceux du service.
    """

    def test_une_conception_incomplete_ne_produit_aucun_fichier(self):
        from apps.calepinage.services import electrique as _electrique

        original = _electrique.conception_du_calepinage

        def _conception(_calepinage, **_options):
            return (_ConceptionMuette(), {}, {}, None)

        _electrique.conception_du_calepinage = _conception
        try:
            with self.assertRaises(SldRefuse) as refus:
                exporter_sld_dxf(object())
        finally:
            _electrique.conception_du_calepinage = original
        self.assertEqual(refus.exception.champ, 'onduleur')
        self.assertIn(_ConceptionMuette.MANQUANTE, str(refus.exception))
        self.assertIn('Aucun fichier', str(refus.exception))


class PorteHttpDxfTest(SimpleTestCase):
    """La route existe, en GET, gardée en LECTURE."""

    def test_l_action_est_decouverte_par_le_routeur(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        par_nom = {action.__name__: action
                   for action in CalepinageViewSet.get_extra_actions()}
        self.assertIn('schema_unifilaire_dxf', par_nom)
        self.assertEqual(set(par_nom['schema_unifilaire_dxf'].mapping),
                         {'get'})

    def test_le_chemin_est_une_sous_ressource_du_calepinage(self):
        from django.urls import reverse

        self.assertEqual(
            reverse('calepinage-schema-unifilaire-dxf', args=('1',)),
            '/api/django/calepinage/calepinages/1/schema-unifilaire.dxf/')

    def test_la_garde_est_celle_de_la_lecture(self):
        from apps.calepinage.permissions import PeutVoirCalepinage
        from apps.calepinage.views.schema import SchemaUnifilaireMixin

        self.assertIn(
            PeutVoirCalepinage,
            SchemaUnifilaireMixin.schema_unifilaire_dxf
            .kwargs['permission_classes'])


@tag('slow')
class GabaritNeutreTest(SimpleTestCase):
    """Sans norme, le DXF n'imprime pas plus de calibres que le SVG."""

    def test_aucune_section_dans_le_tableau_exporte(self):
        from apps.calepinage.services.norme import norme_applicable

        entree = _entree()
        resultat = concevoir(entree)
        gabarit = gabarit_de_schema(
            norme_applicable({'imagerie': {'pays': 'ma'}}))
        dessin = rendu_du_schema(entree, resultat, gabarit=gabarit)
        lignes = lignes_tableau(resultat, standard=gabarit['standard'])
        document = _relire(exporter_sld_dxf(None, dessin=dessin,
                                            lignes=lignes))
        textes = ' | '.join(entite.dxf.text
                            for entite in _entites(document,
                                                   CALQUE_TABLEAU))
        self.assertNotIn('mm²', textes)
        for protection in resultat.protections:
            if protection.calibre:
                self.assertNotIn(protection.calibre, textes)
