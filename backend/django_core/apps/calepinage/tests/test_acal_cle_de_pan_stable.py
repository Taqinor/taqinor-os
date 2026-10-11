# -*- coding: utf-8 -*-
"""ACAL265 — une clé de pan STABLE (``zone.id``) et une clé de module stable.

LE CONSTAT (C-ACAL-051)
-----------------------
Six recopies « label, sinon id, sinon PAN-<rang> » nommaient les pans par
leur LIBELLÉ : renommer « Toit Sud » en « Pan 1 » détachait l'affectation
manuelle stockée sous « Toit Sud#4 », et réduire un pan faisait disparaître
la ligne « #10 » de la table SANS marque (sonde exécutée).

Ce qui est prouvé : la clé suit ``zone.id`` (le libellé n'est qu'un
affichage) ; une ligne manuelle devenue orpheline est publiée
``affectation_obsolete`` (et bloque la publication), jamais effacée ; le
plan de câblage, la lecture d'ombrage et le cheminement lisent LA même clé ;
la migration 0027 convertit les clés stockées (ambigu gardé + note).
"""
from __future__ import annotations

import copy
import importlib

from django.apps import apps as registre
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.cables import longueur_dc
from apps.calepinage.services.chaines import (
    affectation, bloc_electrique, concevoir_par_pan, verdict_affectation,
)
from apps.calepinage.services.documents.plan_cablage import _modules_du_plan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.ombrage_chaines import ombrage_des_chaines
from apps.calepinage.services.planche import geometrie_de_planche
from apps.calepinage.services.production import cle_de_pan
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage

MIGRATION = importlib.import_module(
    'apps.calepinage.migrations.0027_acal265_cles_de_pan_stables')

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}


def _layout(modules, label='Toit Sud'):
    return {'version': 2, 'zones': [{
        'id': 'zA', 'label': label,
        'geometry': {'count': modules, 'azimuthDeg': 180.0,
                     'tiltDeg': 15.0}}]}


def _conception(layout):
    return concevoir_par_pan(
        layout, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        module_designation='Module d essai',
        onduleur_designation='Onduleur d essai')


IMPOSEE = ({'module': 'zA#4', 'chaine': 2, 'mppt': 1, 'onduleur': 1},
           {'module': 'zA#10', 'chaine': 2, 'mppt': 1, 'onduleur': 1})


class CleDePanStableTest(SimpleTestCase):

    def test_renommer_ne_casse_pas_l_affectation(self):
        avant = {ligne['module']: ligne for ligne in affectation(
            _conception(_layout(10)), imposee=IMPOSEE)}
        self.assertEqual(avant['zA#4']['source'], 'affectation manuelle')
        self.assertEqual(avant['zA#4']['pan'], 'Toit Sud')

        # Renommé : la clé (zone.id) ne bouge pas, seul l'affichage change.
        apres = {ligne['module']: ligne for ligne in affectation(
            _conception(_layout(10, label='Pan 1')), imposee=IMPOSEE)}
        self.assertEqual(sorted(apres), sorted(avant))
        self.assertEqual(apres['zA#4']['source'], 'affectation manuelle')
        self.assertEqual(apres['zA#4']['chaine'], 2)
        self.assertEqual(apres['zA#4']['pan'], 'Pan 1')
        # Le repli PAN-<rang> ne sert qu'à un pan SANS id.
        self.assertEqual(cle_de_pan({'id': 'zA', 'label': 'Pan 1'}, 3), 'zA')
        self.assertEqual(cle_de_pan({'label': 'Pan 1'}, 3), 'PAN-3')

    def test_orpheline_publiee_obsolete(self):
        conception = _conception(_layout(9, label='Pan 1'))

        bloc, avertissements = bloc_electrique(conception, imposee=IMPOSEE)

        self.assertEqual(bloc['affectation_obsolete'],
                         [{'module': 'zA#10', 'motif': 'module introuvable'}])
        self.assertNotIn('zA#10', [ligne['module'] for ligne in bloc['affectation']])
        self.assertTrue(any('zA#10' in texte for texte in avertissements))
        # Le verdict (et donc verdict_publiable) la refuse en la nommant.
        refus = verdict_affectation(conception, IMPOSEE)
        self.assertTrue(any('zA#10' in texte for texte in refus))
        # Un pan SUPPRIMÉ : « pan inconnu ».
        bloc, _a = bloc_electrique(conception, imposee=(
            {'module': 'zZ#1', 'chaine': 1, 'mppt': 1, 'onduleur': 1},))
        self.assertEqual(bloc['affectation_obsolete'],
                         [{'module': 'zZ#1', 'motif': 'pan inconnu'}])

    def test_meme_cle_sur_les_lecteurs(self):
        # Panneaux NUMÉROTÉS avec un trou (n = 1, 2, 4) : la clé suit n.
        panneaux = [{'cx': 1.0 + 2.0 * i, 'cy': 1.0, 'n': n}
                    for i, n in enumerate((1, 2, 4))]
        layout = {
            'version': 2,
            'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
                        [33.5001, -7.6]],
            'panelWatt': 720,
            'zones': [{
                'id': 'zA', 'label': 'Pan 1',
                'vertices': [[-7.6, 33.5], [-7.5999, 33.5],
                             [-7.5999, 33.5001], [-7.6, 33.5001]],
                'geometry': {
                    'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 3,
                    'origin': [-7.6, 33.5], 'panels': panneaux,
                    'solarAccess': {'values': [1.0, 0.9, 0.5]}},
            }],
        }
        table = affectation(_conception(layout))
        cles = [ligne['module'] for ligne in table]
        self.assertEqual(cles, ['zA#1', 'zA#2', 'zA#4'])
        # Plan de câblage : mêmes repères.
        plan = _modules_du_plan(layout, geometrie_de_planche(layout))
        self.assertEqual([m['module'] for m in plan], cles)
        # Ombrage : l'accès du module n°4 est le 3e de la liste (0,5).
        lignes = [dict(ligne, chaine=1, mppt=1) for ligne in table]
        lecture = ombrage_des_chaines(layout, lignes)
        acces = {m['module']: m['acces'] for c in lecture['chaines']
                 for m in c['modules']}
        self.assertEqual(acces['zA#4'], 0.5)
        # Cheminement : saisi par la clé du pan, le renommage ne le perd pas.
        renomme = copy.deepcopy(layout)
        renomme['zones'][0]['label'] = 'Toit Est'
        _longueur, manques = longueur_dc(renomme, {
            'pans': {'zA': {'point_collecte': {'cx': 0.0, 'cy': 0.0}}},
            'descente_m': 3.0, 'liaison_coffret_onduleur_m': 2.0})
        self.assertFalse(any('point de collecte non saisi' in m
                             for m in manques), manques)


class MigrationIdempotenteTest(SimpleTestCase):
    """Lot 3 critique #7 — un pan dont le libellé EST l'id (ancienne clé ==
    nouvelle) : deux passes de la migration rendent la même entrée."""

    def test_libelle_egal_id_deux_passes_identiques(self):
        layout = {'zones': [{'id': 'a', 'label': 'a', 'geometry': {
            'panels': [{'n': 10}, {'n': 11}, {'n': 12}]}}]}
        entree = {'affectation_manuelle': [
            {'module': 'a#2', 'chaine': 1}, {'module': 'a#11', 'chaine': 1}]}

        premiere, non_app = MIGRATION.migrer_entree(entree, layout)
        apres = premiere or entree
        seconde, non_app_2 = MIGRATION.migrer_entree(apres, layout)

        self.assertIsNone(seconde)
        self.assertEqual(non_app, [])
        self.assertEqual(non_app_2, [])
        self.assertEqual([ligne['module'] for ligne in
                          apres['affectation_manuelle']], ['a#2', 'a#11'])


class MigrationClesDePanTest(BaseApiCalepinage):

    def test_migration_affectation(self):
        layout = {'version': 2, 'zones': [
            {'id': 'zA', 'label': 'Toit Sud',
             'geometry': {'count': 10, 'panels': [
                 {'cx': i, 'cy': 0, 'n': i + 1} for i in range(10)]}},
            {'id': 'zB', 'label': 'Garage', 'geometry': {'count': 4}},
            {'id': 'zC', 'label': 'Garage', 'geometry': {'count': 4}},
        ]}
        entree = {
            'affectation_manuelle': [
                {'module': 'Toit Sud#4', 'chaine': 2, 'mppt': 1,
                 'onduleur': 1},
                {'module': 'Garage#1', 'chaine': 3, 'mppt': 2,
                 'onduleur': 1},
            ],
            'cheminement': {'pans': {'Toit Sud': {'motif_parcours': 'x'}},
                            'descente_m': 3},
        }
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit',
            roof_layout=layout, resultat={'entree_electrique': entree})

        inventaire = MIGRATION.inventaire_cles_de_pan(registre)
        self.assertEqual(inventaire[0]['apres'], ['zA#4', 'Garage#1'])
        calepinage.refresh_from_db()
        self.assertEqual(  # dry-run : rien d'écrit
            calepinage.resultat['entree_electrique'], entree)

        MIGRATION.migrer_cles_de_pan(registre, None)

        calepinage.refresh_from_db()
        migree = calepinage.resultat['entree_electrique']
        self.assertEqual([ligne['module'] for ligne in migree['affectation_manuelle']],
                         ['zA#4', 'Garage#1'])  # ambigu : gardé tel quel
        self.assertEqual(list(migree['cheminement']['pans']), ['zA'])
        self.assertEqual(migree['cheminement']['descente_m'], 3)
        note = Activity.objects.get(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, kind='note')
        self.assertIn('Garage#1', note.body)

        # Idempotente : une seconde passe ne change rien (la ligne ambiguë
        # est seulement re-signalée).
        MIGRATION.migrer_cles_de_pan(registre, None)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat['entree_electrique'], migree)
        self.assertEqual(Activity.objects.filter(
            object_id=calepinage.pk, kind='note').count(), 2)

        # Réversible.
        MIGRATION.restaurer_cles_de_pan(registre, None)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat['entree_electrique'], entree)
