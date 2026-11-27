"""ACAL61 — le compte des surfaces de pose, partout le même.

Constat : ``chaines.pans_poses`` et ``production._pans_du_layout`` relisaient
chacun ``zones[]`` à leur façon — un champ au sol (``poseSurfaces``) y valait
0 module (la chaîne électrique, la bloc de pose et les livrables l'ignoraient)
et le compte d'un pan non pavé pouvait diverger d'un lecteur à l'autre.

Ils sont désormais deux adaptateurs MINCES de
``apps.ventes.services.pans_du_document`` (LA primitive, D-ACAL-5) : un champ
au sol de 340 modules vaut 340 partout, un pan non pavé vaut 0 partout.

Run :
    python manage.py test apps.calepinage.tests.test_acal_compte_surfaces_pose_partout -v2
"""
from __future__ import annotations

import io

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from apps.calepinage.services.chaines import _pans_poses
from apps.calepinage.services.production import _pans_du_layout
from apps.ventes.services import pans_du_document

SOL_340 = {
    'version': 2,
    'zones': [],
    'poseSurfaces': [{
        'id': 'champ-1', 'kind': 'sol', 'label': 'Champ sud',
        'moduleWc': 550, 'tiltDeg': 20, 'rowAzimuthDeg': 90,
        'engine': {'modules': 340},
    }],
}

PAN_NON_PAVE = {
    'version': 2,
    'zones': [{'id': 'z1', 'label': 'Pan sud', 'neededPanels': 12,
               'pitchDeg': 30, 'facingAzimuthDeg': 180}],
}


class CompteSurfacesPosePartoutTest(SimpleTestCase):

    def test_sol_seul_340_partout(self):
        primitive = pans_du_document(SOL_340)
        self.assertEqual([p['modules'] for p in primitive], [340])

        chaines = _pans_poses(SOL_340)
        self.assertEqual(len(chaines), 1)
        self.assertEqual(chaines[0].modules, 340)
        self.assertEqual(chaines[0].label, 'Champ sud')
        # Azimut de FACE = rangée + 90 (défaut gravé du contrat).
        self.assertEqual(chaines[0].azimut_deg, 180.0)
        self.assertEqual(chaines[0].inclinaison_deg, 20.0)
        self.assertEqual(chaines[0].source_orientation, 'geometrie')

        production = _pans_du_layout(SOL_340)
        self.assertEqual(sum(p['modules'] for p in production), 340)
        self.assertEqual(production[0]['kwc'], 187.0)
        self.assertEqual(production[0]['azimut_deg'], 180.0)

        # Le même compte que la primitive, à l'unité près, des deux côtés.
        self.assertEqual(sum(p.modules for p in chaines),
                         sum(p['modules'] for p in primitive))

    def test_pan_non_pave_zero_partout(self):
        primitive = pans_du_document(PAN_NON_PAVE)
        self.assertEqual([p['modules'] for p in primitive], [0])

        # neededPanels n'est JAMAIS un compte posé : rien à chaîner.
        self.assertEqual(_pans_poses(PAN_NON_PAVE), ())

        production = _pans_du_layout(PAN_NON_PAVE)
        self.assertEqual([p['modules'] for p in production], [0])
        self.assertIsNone(production[0]['kwc'])

    def test_orientation_saisie_du_toit(self):
        layout = {'version': 2, 'zones': [{
            'id': 'z1', 'label': 'Pan est', 'pitchDeg': 15,
            'facingAzimuthDeg': 90, 'geometry': {'count': 8}}]}

        pan, = _pans_poses(layout)

        self.assertEqual(pan.modules, 8)
        self.assertEqual(pan.azimut_deg, 90.0)
        self.assertEqual(pan.source_orientation, 'saisie')


class UneSurfaceNEstComptee1FoisTest(SimpleTestCase):
    """ACAL984 (5) — zone + champ au sol : 42 + 176 = 218, chacune UNE fois,
    pour la primitive, la chaîne et la production."""

    LAYOUT = {
        'version': 2, 'panelWatt': 720,
        'zones': [{'id': 'z1', 'label': 'Zone 1', 'pitchDeg': 20,
                   'facingAzimuthDeg': 180,
                   'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 20.0,
                                'panels': [{'cx': float(i), 'cy': 1.0}
                                           for i in range(42)]}}],
        'poseSurfaces': [{
            'id': 'champ-1', 'kind': 'sol', 'label': 'Champ au sol 1',
            'moduleWc': 550, 'tiltDeg': 20, 'rowAzimuthDeg': 90,
            'engine': {'modules': 176}}],
    }

    def test_218_egal_42_plus_176_chaque_surface_une_fois(self):
        pans = pans_du_document(self.LAYOUT)
        self.assertEqual([(p['cle'], p['modules']) for p in pans],
                         [('z1', 42), ('champ-1', 176)])
        self.assertEqual(sum(p['modules'] for p in pans), 218)

        chaines = _pans_poses(self.LAYOUT)
        self.assertEqual(sorted(p.modules for p in chaines), [42, 176])
        self.assertEqual(sum(p.modules for p in chaines), 218)
        production = _pans_du_layout(self.LAYOUT)
        self.assertEqual(sum(p['modules'] for p in production), 218,
                         'production : une surface comptée 0 ou 2 fois')


def _surface(kind, azimut, ident='s1'):
    return {'version': 2, 'zones': [], 'poseSurfaces': [
        {'id': ident, 'kind': kind, 'rowAzimuthDeg': azimut}]}


class EcartsAzimutSurfacesTest(SimpleTestCase):
    """ACAL1194 — la liste montrée à Reda avant ACAL921, sans base."""

    def _ecarts(self, layout):
        from apps.calepinage.management.commands.acal_dryrun_azimut_surfaces \
            import ecarts_azimut_surfaces
        return ecarts_azimut_surfaces(layout)

    def test_sol_180_lu_270_aujourd_hui_180_apres(self):
        ligne, = self._ecarts(_surface('sol', 180))
        self.assertEqual((ligne['saisi'], ligne['face_aujourdhui'],
                          ligne['face_apres']), (180.0, 270.0, 180.0))
        self.assertEqual((ligne['surface'], ligne['genre']), ('s1', 'sol'))
        # La règle recopiée est bien celle du lecteur d'aujourd'hui.
        layout = _surface('sol', 180)
        layout['poseSurfaces'][0].update(moduleWc=550, engine={'modules': 2})
        pan, = pans_du_document(layout)
        self.assertEqual(pan['azimut_deg'], ligne['face_aujourdhui'])

    def test_facade_90_lue_180_aujourd_hui_90_apres(self):
        ligne, = self._ecarts(_surface('facade', 90))
        self.assertEqual((ligne['face_aujourdhui'], ligne['face_apres']),
                         (180.0, 90.0))

    def test_surface_sans_azimut_numerique_rien(self):
        for valeur in (None, '180', True):
            self.assertEqual(self._ecarts(_surface('sol', valeur)), [])
        self.assertEqual(self._ecarts(PAN_NON_PAVE), [])
        self.assertEqual(self._ecarts(None), [])

    def test_sans_dry_run_refuse_avant_toute_lecture(self):
        with self.assertRaises(CommandError) as refus:
            call_command('acal_dryrun_azimut_surfaces', stdout=io.StringIO())
        self.assertIn('ajoutez --dry-run', str(refus.exception))


class CommandeAzimutSurfacesTest(TestCase):
    """ACAL1194 — la commande refuse sans --dry-run et n'écrit jamais."""

    def setUp(self):
        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        self.company = Company.objects.create(nom='Azimut Co',
                                              slug='azimut-co-1194')
        client = Client.objects.create(company=self.company, nom='Client')
        self.devis = Devis.objects.create(company=self.company, client=client,
                                          reference='DEV-202611-1194')
        self.oriente = Calepinage.objects.create(
            company=self.company, client=client, devis=self.devis,
            titre='Champ', roof_layout=_surface('sol', 180, 'champ-1'))
        Calepinage.objects.create(company=self.company, client=client,
                                  titre='Toit', roof_layout=PAN_NON_PAVE)

    def test_dry_run_liste_sans_ecrire(self):
        sortie = io.StringIO()
        with CaptureQueriesContext(connection) as requetes:
            call_command('acal_dryrun_azimut_surfaces', '--dry-run',
                         '--company', 'azimut-co-1194', stdout=sortie)
        ecritures = [r['sql'] for r in requetes.captured_queries
                     if r['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])
        lignes = sortie.getvalue().splitlines()
        self.assertEqual(lignes[0],
                         'DRY-RUN ACAL1194 (lecture seule) — aucune écriture')
        self.assertIn('%s | champ-1 (sol) | 180 | 270 | 180 | %s (%s)' % (
            self.oriente.pk, self.devis.pk, self.devis.statut), lignes)
        self.assertIn('1 surface(s) sur 1 calepinage(s) concernés.', lignes)
        self.assertIn('Devis liés par statut : %s 1.' % self.devis.statut,
                      lignes)
