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
import re

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


class ReglagesSocieteTest(SimpleTestCase):
    """REP-sld-export — le DXF lit la check-list avec les MÊMES réglages
    société que le SVG (``sld.py``), jamais sans."""

    def test_le_dxf_passe_les_reglages_societe_a_la_checklist(self):
        from unittest import mock

        from apps.calepinage.services import electrique as _electrique
        from apps.calepinage.services import sld as _sld

        class _Arret(Exception):
            pass

        saisis = {}

        def _decides(conception, donnees, norme, **options):
            saisis.update(options)
            raise _Arret()

        conception = type('C', (), {'manquantes': (), 'micro_seul': False,
                                    'entree': None})()
        reglages = {'distance_separation_foudre_min_m': {'valeur': 1}}
        with mock.patch.object(_electrique, 'conception_du_calepinage',
                               return_value=(conception, {}, {}, None)), \
                mock.patch.object(_electrique, 'bloquants_nommes',
                                  return_value=[]), \
                mock.patch.object(_electrique, 'parametres_societe',
                                  return_value={}), \
                mock.patch.object(_electrique, '_reglages_electrique_societe',
                                  return_value=reglages), \
                mock.patch.object(_sld, 'resultat_et_gabarit_decides',
                                  side_effect=_decides):
            with self.assertRaises(_Arret):
                exporter_sld_dxf(object())
        self.assertIs(saisis.get('reglages'), reglages)


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


class CablageEffectifTest(SimpleTestCase):
    """DXF et PDF refusent et acceptent dans les MÊMES cas, jugés sur le
    câblage EFFECTIF (``sld_export._refuser_si_empeche`` →
    ``sld.bloquants_du_cablage``) : automatique forcé à 7 (5 × 7, 66,9 A sur
    l'entrée 1 d'un hybride 2 entrées à 54 A), manuel 12 + 12 | 11 valide."""

    MODULE_715 = {'vmp_v': 41.0, 'voc_v': 49.1, 'isc_a': 22.3, 'imp_a': 17.44,
                  'pmax_wc': 715.0, 'temp_coeff_voc_pct_c': -0.25,
                  'temp_coeff_pmax_pct_c': -0.35}
    DEYE_20K = {'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 750.0,
                'v_max_abs': 800.0, 'i_max_mppt_a': 36.0, 'ac_kw': 20.0,
                'phases': 3, 'isc_max_mppt_a': 54.0}

    def _conception(self):
        from apps.calepinage.services.chaines import concevoir_par_pan
        from apps.calepinage.services.electrique import temperatures_site

        return concevoir_par_pan(
            {'version': 2, 'zones': [{'id': 'z1', 'label': 'PAN-1', 'geometry': {
                'count': 35, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]},
            module_specs=self.MODULE_715, onduleur_specs=self.DEYE_20K,
            temperatures=temperatures_site(saisie={
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
            longueur_forcee=7)

    def _manuel(self):
        lignes, rang = [], 0
        for numero, (longueur, mppt) in enumerate(((12, 1), (12, 1), (11, 2)),
                                                  start=1):
            for _ in range(longueur):
                rang += 1
                lignes.append({'module': 'z1#%d' % rang, 'chaine': numero,
                               'mppt': mppt, 'onduleur': 1})
        return {'affectation_manuelle': lignes}

    def _exporter(self, format_, donnees):
        """``'produit'``, ou l'exception ``SldRefuse`` levée."""
        from unittest import mock

        from apps.calepinage.services import electrique as _electrique
        from apps.calepinage.services import sld as _sld
        from apps.calepinage.services.sld_export import exporter_sld_pdf

        class _Passe(Exception):
            pass

        def _passe(*_args, **_kwargs):
            raise _Passe()

        with mock.patch.object(_electrique, 'conception_du_calepinage',
                               return_value=(self._conception(), {}, donnees,
                                             None)), \
                mock.patch.object(_electrique, 'parametres_societe',
                                  return_value={}), \
                mock.patch.object(_electrique, '_reglages_electrique_societe',
                                  return_value={}), \
                mock.patch.object(_sld, 'resultat_et_gabarit_decides',
                                  side_effect=_passe), \
                mock.patch.object(_sld, 'document_electrique_du_calepinage',
                                  side_effect=_passe):
            try:
                (exporter_sld_dxf if format_ == 'dxf' else exporter_sld_pdf)(
                    object())
            except _Passe:
                return 'produit'   # la garde est passée : la pièce se compose
            except SldRefuse as refus:
                return refus
        raise AssertionError('ni produit ni refusé')

    def test_manuel_valide_sur_automatique_bloque_le_dxf_et_le_pdf_sortent(self):
        for format_ in ('dxf', 'pdf'):
            with self.subTest(format_=format_):
                self.assertEqual(self._exporter(format_, self._manuel()),
                                 'produit')

    def test_cablage_effectif_bloquant_refuse_les_deux_en_nommant(self):
        for format_ in ('dxf', 'pdf'):
            with self.subTest(format_=format_):
                refus = self._exporter(format_, {})
                self.assertIsInstance(refus, SldRefuse)
                self.assertEqual(refus.champ, 'Isc')
                self.assertIn('66,9 A', str(refus))
                self.assertIn('Aucun fichier', str(refus))


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


class SchemaPdfTest(SimpleTestCase):
    """ACAL1507 — le MÊME schéma, en PDF A3 : onduleur, coffrets, terre.

    ``render_pdf`` est remplacé (WeasyPrint n'existe pas sur ce poste) : on
    juge le HTML A3 qui lui est remis — celui que le PDF réel mettrait en page.
    """

    def _html_rendu(self, cartouche=None):
        from unittest import mock

        from core.electrique.schema_electrique import document_schema_electrique

        from apps.calepinage.services.sld_export import exporter_sld_pdf

        entree = _entree()
        document = document_schema_electrique(entree, concevoir(entree))
        capte = {}

        def _faux_pdf(html=None, **_options):
            capte['html'] = html
            return b'%PDF-faux'

        with mock.patch('core.pdf.render_pdf', _faux_pdf):
            octets = exporter_sld_pdf(object(), document=document,
                                      cartouche=cartouche)
        self.assertEqual(octets, b'%PDF-faux')
        return capte['html']

    def test_le_pdf_porte_l_onduleur_les_coffrets_et_la_terre(self):
        html = self._html_rendu({'client': 'Mme <Alami>',
                                 'reference': 'Villa 1',
                                 'date': '23/11/2026'})
        self.assertIn('@page{size:A3 landscape', html)
        self.assertIn('data-schema="electrique"', html)
        self.assertIn('Deye SUN-10K-SG05LP3', html)
        self.assertIn('Client : Mme &lt;Alami&gt;', html)
        self.assertIn('Référence : Villa 1', html)
        self.assertNotIn('plan de câblage', html.lower())

    def test_un_document_sans_onduleur_ne_produit_aucun_fichier(self):
        from apps.calepinage.services.sld_export import exporter_sld_pdf

        with self.assertRaises(SldRefuse) as refus:
            exporter_sld_pdf(object(), document={'onduleurs': []})
        self.assertEqual(refus.exception.champ, 'onduleur')

    def test_une_conception_incomplete_ne_produit_aucun_pdf(self):
        from apps.calepinage.services import electrique as _electrique
        from apps.calepinage.services.sld_export import exporter_sld_pdf

        original = _electrique.conception_du_calepinage
        _electrique.conception_du_calepinage = (
            lambda _c, **_o: (_ConceptionMuette(), {}, {}, None))
        try:
            with self.assertRaises(SldRefuse) as refus:
                exporter_sld_pdf(object())
        finally:
            _electrique.conception_du_calepinage = original
        self.assertEqual(refus.exception.champ, 'onduleur')
        self.assertIn('Aucun fichier', str(refus.exception))

    def test_la_route_pdf_existe_en_lecture(self):
        from django.urls import reverse

        from apps.calepinage.permissions import PeutVoirCalepinage
        from apps.calepinage.views.schema import SchemaUnifilaireMixin

        self.assertEqual(
            reverse('calepinage-schema-unifilaire-pdf', args=('1',)),
            '/api/django/calepinage/calepinages/1/schema-unifilaire.pdf/')
        self.assertIn(
            PeutVoirCalepinage,
            SchemaUnifilaireMixin.schema_unifilaire_pdf
            .kwargs['permission_classes'])


class SchemaPdfRevueTest(SimpleTestCase):
    """ACAL1507 (revue) — refus qui nomme le bon fichier et la vraie raison ; une seule lecture ;
    la page garde une marge de sécurité."""

    def _avec_conception(self, document_retourne):
        from unittest import mock

        from apps.calepinage.services import electrique as _electrique
        from apps.calepinage.services import sld as _sld
        from apps.calepinage.services import sld_export

        class _Propre:
            manquantes = ()
            micro_seul = False

        lectures = []

        def _lecture(_calepinage, **_options):
            lectures.append(1)
            return (_Propre(), {}, {}, None)

        recus = []

        def _document(_calepinage, *, lecture=None):
            recus.append(lecture)
            return document_retourne

        with mock.patch.object(_electrique, 'conception_du_calepinage', _lecture), \
                mock.patch.object(_sld, 'document_electrique_du_calepinage', _document), \
                mock.patch.object(_sld, 'bloquants_du_cablage', lambda *_a: []), \
                mock.patch.object(_sld, 'cartouche_du_calepinage', lambda _c: {}):
            with self.assertRaises(SldRefuse) as refus:
                sld_export.exporter_sld_pdf(object())
        return refus.exception, lectures, recus

    def test_le_refus_du_pdf_nomme_un_pdf_et_celui_du_dxf_un_dxf(self):
        from apps.calepinage.services.sld_export import _refuser_si_empeche

        muette = _ConceptionMuette()
        with self.assertRaises(SldRefuse) as pdf:
            _refuser_si_empeche(muette, {}, fichier='PDF')
        with self.assertRaises(SldRefuse) as dxf:
            _refuser_si_empeche(muette, {})
        self.assertIn("un PDF d'aspect officiel", str(pdf.exception))
        self.assertNotIn('DXF', str(pdf.exception))
        self.assertIn("un DXF d'aspect officiel", str(dxf.exception))

    def test_un_document_qui_n_a_pas_pu_etre_construit_ne_pretend_pas_qu_il_manque_un_onduleur(self):
        refus, _lectures, _recus = self._avec_conception(None)
        self.assertEqual(refus.champ, 'schema')
        self.assertIn('pas pu être construit', str(refus))
        self.assertNotIn('onduleur', str(refus))

    def test_un_document_sans_onduleur_dit_qu_aucun_onduleur_n_est_retenu(self):
        refus, _lectures, _recus = self._avec_conception({'onduleurs': []})
        self.assertEqual(refus.champ, 'onduleur')
        self.assertIn("aucun onduleur", str(refus))

    def test_la_conception_n_est_lue_qu_une_fois_et_partagee(self):
        _refus, lectures, recus = self._avec_conception(None)
        self.assertEqual(len(lectures), 1)
        self.assertEqual(len(recus), 1)
        self.assertIsNotNone(recus[0])

    def test_la_page_a_une_marge_de_securite(self):
        from apps.calepinage.services import sld_export as e

        total = e._CARTOUCHE_MM + e._DESSIN_MM
        self.assertLess(total, e._FEUILLE_HAUTEUR_MM)
        self.assertGreaterEqual(e._FEUILLE_HAUTEUR_MM - total, 5)
        # S3 — le dessin garde SA proportion (plus de boîte fixe qui le centrait avec une bande vide en haut) :
        # large, il prend la pleine largeur et colle au cartouche ; haut, sa hauteur ne dépasse jamais la place.
        for viewbox in ('0 0 1040 520', '0 0 1040 1400', '0 0 1040 380'):
            style = e._style_du_dessin('<svg viewBox="%s">' % viewbox)
            largeur, hauteur = [float(v) for v in re.findall(r'(?:width|height):([\d.]+)mm', style)]
            self.assertLessEqual(largeur, e._FEUILLE_LARGEUR_MM)
            self.assertLessEqual(hauteur, e._DESSIN_MM)
            self.assertAlmostEqual(largeur / hauteur, 1040 / float(viewbox.split()[-1]), places=2)
        self.assertIn('width:420.0mm', e._style_du_dessin('<svg viewBox="0 0 1040 520">'))
        self.assertEqual(e._style_du_dessin('<svg>'), 'svg{width:100%;}')
