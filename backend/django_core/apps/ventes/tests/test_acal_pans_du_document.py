"""ACAL59 (C-ACAL-035, C-ACAL-118, D-ACAL-5) — ``pans_du_document`` : un site
toit + champ au sol / ombrière est chiffré sur la SOMME des modules posés,
une surface sans puissance module est refusée en la nommant, un pan non pavé
ne compte jamais, et le ``result`` racine n'est jamais additionné aux zones.

Lecture PURE (``SimpleTestCase``) + le refus tel que le pré-vol le prononce.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_pans_du_document"
"""
import copy
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.geometrie import (
    extract_roof_config, lire_layout, modules_affleurants, pans_du_document,
    refus_des_pans, validate_composition_for_layout)
from apps.crm.models import Client
from apps.ventes.domain.taille import AutoDevisError
from apps.ventes.models import Devis
from authentication.models import Company

MIXTE = {
    'zones': [{'id': 'zA', 'label': 'Toit', 'geometry': {
        'count': 10, 'kwc': 7.2, 'azimuthDeg': 180, 'tiltDeg': 30,
        'panels': [{'cx': i, 'cy': 0} for i in range(10)]}}],
    'result': {'panels': 10, 'kwc': 7.2},
    'poseSurfaces': [{'id': 's1', 'kind': 'ombriere', 'label': 'Carport',
                      'moduleWc': 620, 'tiltDeg': 10, 'rowAzimuthDeg': 90,
                      'engine': {'modules': 60}}],
}


class PansDuDocument(SimpleTestCase):

    def test_site_mixte_somme(self):
        lecture = lire_layout(MIXTE)
        self.assertEqual(lecture.compte, 70)
        self.assertAlmostEqual(lecture.kwc, 7.2 + 60 * 0.620)
        toit, ombriere = lecture.pans
        self.assertEqual((toit['kind'], toit['modules']), ('toit', 10))
        self.assertEqual((ombriere['kind'], ombriere['modules']),
                         ('ombriere', 60))
        self.assertAlmostEqual(ombriere['kwc'], 37.2)
        # Azimut de FACE = rowAzimuthDeg + 90 (défaut gravé du contrat).
        self.assertEqual(ombriere['azimut_deg'], 180.0)
        self.assertEqual(toit['source'], 'geometry.panels')

    def test_surface_sans_puissance_refusee(self):
        sans = copy.deepcopy(MIXTE)
        del sans['poseSurfaces'][0]['moduleWc']
        refus = refus_des_pans(pans_du_document(sans))
        self.assertEqual(len(refus), 1)
        self.assertIn('Carport', refus[0])
        with self.assertRaises(AutoDevisError) as leve:
            validate_composition_for_layout(sans, None)
        self.assertEqual(leve.exception.field, 'poseSurfaces.0.moduleWc')
        self.assertIn('Carport', leve.exception.message)

    def test_pan_non_pave_ne_compte_pas(self):
        layout = {'zones': [{'id': 'zB', 'label': 'Annexe',
                             'geometry': {'count': 0},
                             'neededPanels': 12}]}
        pan, = pans_du_document(layout)
        self.assertEqual(pan['modules'], 0)
        self.assertIn('pan Annexe non pavé — non chiffré',
                      pan['avertissement'])
        self.assertEqual(lire_layout(layout).compte, 0)

    def test_zone_auto_devis_compte(self):
        # La zone SYNTHÉTIQUE de l'auto-devis ne porte que ``result`` (et
        # ``neededPanels``, jamais lu comme compte posé).
        layout = {'zones': [{'id': 'auto', 'label': 'Toit du client',
                             'neededPanels': 14,
                             'result': {'count': 14, 'kwc': 9.94}}],
                  'result': {'panels': 14, 'kwc': 9.94}}
        pan, = pans_du_document(layout)
        self.assertEqual((pan['modules'], pan['source']), (14, 'result.count'))
        self.assertEqual(lire_layout(layout).compte, 14)

    def test_result_racine_jamais_double(self):
        for panels in (10, 25, 0):
            with self.subTest(result_panels=panels):
                layout = copy.deepcopy(MIXTE)
                layout['result'] = {'panels': panels, 'kwc': 99.0}
                self.assertEqual(lire_layout(layout).compte, 70)
        # Sans aucune géométrie de zone, le result racine est le toit.
        self.assertEqual(lire_layout({'result': {'panels': 12}}).compte, 12)

    def test_pan_existant_jamais_vendu(self):
        """Critique D1 — un pan « existant » (modules déjà en place) n'entre
        ni au compte, ni au kWc, ni aux modèles, ni à la toiture du devis."""
        modules = [{'id': 'm1', 'libelle': 'P585', 'source': 'fiche',
                    'produitId': 7, 'pmaxWc': 585}]

        def pan(cle, nombre, **extra):
            return dict({'id': cle, 'label': cle, 'geometry': {
                'moduleId': 'm1', 'azimuthDeg': 180, 'tiltDeg': 20, 'flush': True,
                'count': nombre, 'kwc': round(nombre * 0.585, 3),
                'panels': [{'cx': i, 'cy': 0} for i in range(nombre)]}}, **extra)
        layout = {'scenario': 'reseau', 'panelWatt': 585, 'modules': modules,
                  'result': {'panels': 16, 'kwc': 9.36},
                  'zones': [pan('A', 10, existant=True, anneeMiseEnService=2019),
                            pan('B', 6)]}
        lecture = lire_layout(layout)
        self.assertEqual((lecture.compte, lecture.kwc), (6, 3.51))
        self.assertEqual(lecture.modeles, [{'produit_id': 7, 'watt': 585, 'count': 6}])
        self.assertEqual([p['cle'] for p in lecture.pans], ['B'])
        self.assertEqual(modules_affleurants(layout), 6)
        toiture = extract_roof_config(layout)
        self.assertEqual((toiture['nb_panneaux'], toiture['kwc']), (6, 3.51))
        self.assertEqual([p['nb_panneaux'] for p in toiture['pans']], [0, 6])
        # Le calepinage garde la primitive entière (production, chaînes).
        self.assertEqual([(p['cle'], p['modules'], p.get('existant'))
                          for p in pans_du_document(layout)],
                         [('A', 10, True), ('B', 6, None)])
        # Tout existant : rien à vendre, le ``result`` racine n'est pas relu.
        layout['zones'] = layout['zones'][:1]
        self.assertEqual((lire_layout(layout).compte, lire_layout(layout).kwc), (0, 0.0))


def _layout_pan_existant():
    """Critique D1 — pan A « existant » (10 modules en place) + pan B neuf (6)."""
    def pan(cle, nombre, **extra):
        return dict({'id': cle, 'label': cle, 'geometry': {
            'azimuthDeg': 180, 'tiltDeg': 20,
            'panels': [{'cx': i, 'cy': 0} for i in range(nombre)]}}, **extra)
    return {'panelWatt': 585, 'zones': [pan('A', 10, existant=True), pan('B', 6)]}


class PansExistantsDryRunPur(SimpleTestCase):
    def test_modules_des_pans_existants(self):
        from apps.ventes.management.commands.acal_dryrun_compte_layout import _modules_existants

        layout = _layout_pan_existant()
        self.assertEqual(_modules_existants(layout), 10)
        layout['zones'][0].pop('existant')
        self.assertEqual(_modules_existants(layout), 0)
        self.assertEqual(_modules_existants(None), 0)


class PansExistantsDryRun(TestCase):
    """Critique D1 — le dry-run du fondateur : les devis NON brouillon dont une
    zone est « existant », lus sans aucune écriture."""

    def setUp(self):
        self.co = Company.objects.create(nom='D1', slug='d1-existant')
        self.client_ = Client.objects.create(company=self.co, nom='Extension')

    def _devis(self, reference, layout, statut):
        return Devis.objects.create(company=self.co, client=self.client_,
                                    reference=reference, statut=statut, roof_layout=layout)

    def test_liste_les_envoyes_a_pan_existant_sans_rien_ecrire(self):
        envoye = self._devis('DEV-D1-ENV', _layout_pan_existant(), Devis.Statut.ENVOYE)
        self._devis('DEV-D1-BRO', _layout_pan_existant(), Devis.Statut.BROUILLON)
        neuf = _layout_pan_existant()
        neuf['zones'][0].pop('existant')
        self._devis('DEV-D1-NEUF', neuf, Devis.Statut.ENVOYE)

        sortie = StringIO()
        call_command('acal_dryrun_compte_layout', '--pans-existants', stdout=sortie)
        texte = sortie.getvalue()

        self.assertIn('DEV-D1-ENV | envoye | 10 | 6', texte)
        self.assertNotIn('DEV-D1-BRO', texte)
        self.assertNotIn('DEV-D1-NEUF', texte)
        self.assertIn('Devis concernés : 1', texte)
        envoye.refresh_from_db()
        self.assertEqual(envoye.roof_layout, _layout_pan_existant())
