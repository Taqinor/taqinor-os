# -*- coding: utf-8 -*-
"""ACAL267 — la pose réelle est référencée par l'identifiant STABLE du pan.

LE CONSTAT (C-ACAL-051, sondes exécutées)
-----------------------------------------
``PoseReelle.pan`` était le LIBELLÉ : renommer « Toit Sud » en « Pan 1 »
détachait le relevé (écart total 0 « conforme » faux), deux pans de même
libellé partageaient UNE ligne, et le relevé d'un pan supprimé restait
compté dans les totaux (+4).

Base réelle, écrivains réels (``enregistrer_pose``, ``enregistrer_layout``),
route HTTP réelle pour le DELETE. Aucun mock.
"""
from __future__ import annotations

import importlib

from django.apps import apps as registre

from apps.calepinage.models import Calepinage, PoseReelle
from apps.calepinage.services.asbuilt import (
    MENTION_ORPHELIN, enregistrer_pose, etat_pose_reelle, version_depuis_ecarts,
)
from apps.calepinage.services.layout import enregistrer_layout

from .test_api_liste import BaseApiCalepinage, url_detail

MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0028_acal267_pose_reelle_zone_id')
RELEVE = '2026-10-01'


def _zone(ident, label, modules):
    return {'id': ident, 'label': label,
            'geometry': {'count': modules, 'azimuthDeg': 180.0,
                         'tiltDeg': 15.0}}


class PoseReelleZoneIdTest(BaseApiCalepinage):

    def _calepinage(self, *zones):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit',
            roof_layout={'version': 2, 'zones': list(zones)})

    def _ligne(self, calepinage, zone_id):
        return next(ligne for ligne in etat_pose_reelle(calepinage)['lignes']
                    if ligne['zone_id'] == zone_id)

    def test_renommage_suit_la_zone(self):
        calepinage = self._calepinage(_zone('zA', 'Toit Sud', 12))
        enregistrer_pose(calepinage, {'pan': 'Toit Sud', 'modules_poses': 12,
                                      'releve_le': RELEVE}, user=self.user)
        self.assertEqual(PoseReelle.objects.get(calepinage=calepinage)
                         .zone_id, 'zA')

        enregistrer_layout(calepinage, {'version': 2, 'zones': [
            _zone('zA', 'Pan 1', 12)]}, user=self.user)
        calepinage.refresh_from_db()

        etat = etat_pose_reelle(calepinage)
        ligne = self._ligne(calepinage, 'zA')
        self.assertEqual((ligne['pan'], ligne['modules_poses'],
                          ligne['ecart'], ligne['orphelin']),
                         ('Pan 1', 12, 0, False))
        self.assertEqual(etat['total_pose'], 12)
        self.assertEqual(len(etat['lignes']), 1)
        # La version figée depuis les écarts porte l'identifiant du pan.
        version, _creee = version_depuis_ecarts(calepinage, user=self.user)
        self.assertEqual(version.resultat['asbuilt']['lignes'][0]['zone_id'],
                         'zA')

    def test_libelles_dupliques_independants(self):
        calepinage = self._calepinage(_zone('z1', 'Pan A', 6),
                                      _zone('z2', 'Pan A', 4))
        enregistrer_pose(calepinage, {'pan': 'z1', 'modules_poses': 6,
                                      'releve_le': RELEVE}, user=self.user)
        enregistrer_pose(calepinage, {'pan': 'z2', 'modules_poses': 3,
                                      'releve_le': RELEVE}, user=self.user)

        self.assertEqual(PoseReelle.objects.filter(
            calepinage=calepinage).count(), 2)
        self.assertEqual(self._ligne(calepinage, 'z1')['modules_poses'], 6)
        self.assertEqual(self._ligne(calepinage, 'z2')['modules_poses'], 3)
        self.assertEqual(etat_pose_reelle(calepinage)['total_pose'], 9)
        # Le libellé ambigu ne désigne AUCUN pan : refus nommé.
        reponse = self.api.post(
            f'{url_detail(calepinage.pk)}pose-reelle/',
            {'pan': 'Pan A', 'modules_poses': 1, 'releve_le': RELEVE},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('pan', reponse.data)

    def test_orphelin_hors_totaux_et_retirable(self):
        calepinage = self._calepinage(_zone('z1', 'Pan A', 6),
                                      _zone('z2', 'Garage', 4))
        enregistrer_pose(calepinage, {'pan': 'z1', 'modules_poses': 6,
                                      'releve_le': RELEVE}, user=self.user)
        enregistrer_pose(calepinage, {'pan': 'z2', 'modules_poses': 4,
                                      'releve_le': RELEVE}, user=self.user)
        enregistrer_layout(calepinage, {'version': 2, 'zones': [
            _zone('z1', 'Pan A', 6)]}, user=self.user)
        calepinage.refresh_from_db()

        etat = etat_pose_reelle(calepinage)
        orphelin = self._ligne(calepinage, 'z2')
        self.assertTrue(orphelin['orphelin'])
        self.assertEqual(orphelin['libelle'], 'Garage')
        self.assertEqual(orphelin['mention'], MENTION_ORPHELIN)
        self.assertIsNone(orphelin['ecart'])
        self.assertEqual(etat['total_pose'], 6)  # hors totaux
        self.assertEqual(etat['total_prevu'], 6)

        url = f'{url_detail(calepinage.pk)}pose-reelle/z2/'
        self.assertEqual(self.api.delete(url).status_code, 204)
        self.assertFalse(PoseReelle.objects.filter(
            calepinage=calepinage, zone_id='z2').exists())
        absent = self.api.delete(url)
        self.assertEqual(absent.status_code, 404)
        self.assertEqual(absent.data,
                         {'detail': "Aucune pose réelle n'est saisie pour "
                                    "ce pan."})
        # Lecteur seul : pas de retrait ; autre société : introuvable.
        self.assertEqual(self.api_sans.delete(
            f'{url_detail(calepinage.pk)}pose-reelle/z1/').status_code, 403)
        self.assertEqual(self.api_autre.delete(
            f'{url_detail(calepinage.pk)}pose-reelle/z1/').status_code, 404)

    def test_orphelins_herites_a_point_ou_barre_retirables(self):
        """Lot 3 critique #4 — les ``zone_id`` hérités de la migration 0028
        (libellés « Toit N/E », « Pan 1.2 », ``pan:<libellé>``) se retirent :
        l'identifiant voyage ENCODÉ (``encodeURIComponent`` côté écran) et la
        route accepte points et barres."""
        from urllib.parse import quote

        calepinage = self._calepinage(_zone('z1', 'Pan A', 6))
        for zone_id in ('Toit N/E', 'Pan 1.2', 'pan:Pan 1.2'):
            PoseReelle.objects.create(
                company=self.company, calepinage=calepinage, pan=zone_id,
                zone_id=zone_id, modules_poses=3, releve_le=RELEVE)
        for zone_id in ('Toit N/E', 'Pan 1.2', 'pan:Pan 1.2'):
            with self.subTest(zone_id=zone_id):
                url = (f'{url_detail(calepinage.pk)}pose-reelle/'
                       f'{quote(zone_id, safe="")}/')
                reponse = self.api.delete(url)
                self.assertEqual(reponse.status_code, 204,
                                 getattr(reponse, 'data', reponse))
                self.assertFalse(PoseReelle.objects.filter(
                    calepinage=calepinage, zone_id=zone_id).exists())

    def test_retour_0028_dedoublonne_les_libelles(self):
        """Lot 3 critique #3 — deux relevés de même libellé (deux pans
        « Pan A ») : le retour arrière les rend uniques AVANT de rétablir
        ``uniq_pose_reelle_par_pan`` (jamais d'IntegrityError)."""
        calepinage = self._calepinage(_zone('z1', 'Pan A', 6),
                                      _zone('z2', 'Pan A', 4))
        autre = self._calepinage(_zone('z1', 'Pan A', 6))
        for cal, zone_id in ((calepinage, 'z1'), (calepinage, 'z2'),
                             (autre, 'z1')):
            PoseReelle.objects.create(
                company=self.company, calepinage=cal, pan='Pan A',
                zone_id=zone_id, modules_poses=3, releve_le=RELEVE)

        MIGRATION.dedoublonner_pan(registre, None)

        self.assertEqual(sorted(PoseReelle.objects.filter(
            calepinage=calepinage).values_list('pan', flat=True)),
            ['Pan A', 'Pan A (2)'])
        # Un autre calepinage garde son libellé (unicité PAR calepinage).
        self.assertEqual(list(PoseReelle.objects.filter(
            calepinage=autre).values_list('pan', flat=True)), ['Pan A'])

    def test_migration_rattache_par_libelle_sans_deviner(self):
        calepinage = self._calepinage(_zone('zA', 'Toit Sud', 12),
                                      _zone('zB', 'Garage', 4),
                                      _zone('zC', 'Garage', 4))
        unique = PoseReelle.objects.create(
            company=self.company, calepinage=calepinage, pan='Toit Sud',
            zone_id='', modules_poses=12, releve_le=RELEVE)
        # La migration lit le LIBELLÉ (``pan``) et réécrit ``zone_id`` : la
        # valeur de départ du second relevé est un simple bouche-trou (deux
        # ``zone_id`` vides violeraient la nouvelle unicité).
        ambigu = PoseReelle.objects.create(
            company=self.company, calepinage=calepinage, pan='Garage',
            zone_id='avant-migration', modules_poses=4, releve_le=RELEVE)

        MIGRATION.rattacher_zone_id(registre, None)

        unique.refresh_from_db()
        ambigu.refresh_from_db()
        self.assertEqual(unique.zone_id, 'zA')
        self.assertEqual(ambigu.zone_id, 'Garage')  # jamais deviné
        self.assertTrue(self._ligne(calepinage, 'Garage')['orphelin'])
