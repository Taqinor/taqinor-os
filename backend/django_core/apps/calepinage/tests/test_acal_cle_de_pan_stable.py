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


def _pan_pose(positions, numeros=None):
    """ACAL648 — un pan dont les modules sont POSÉS (``panels``), numérotés
    ou non ; ``positions`` = les abscisses des modules restants."""
    panneaux = [dict({'cx': cx, 'cy': 0.0}, **({'n': numeros[i]} if numeros
                                               else {}))
                for i, cx in enumerate(positions)]
    layout = _layout(len(panneaux))
    layout['zones'][0]['geometry']['panels'] = panneaux
    return layout


#: ACAL648 — chaîne 2 imposée sur les modules 4 à 10.
CHAINE_2_SUR_4_A_10 = tuple(
    {'module': 'zA#%d' % n, 'chaine': 2, 'mppt': 1, 'onduleur': 1}
    for n in range(4, 11))


#: ACAL649 — la même affectation, ENREGISTRÉE avec le centre de chaque module
#: (le serveur le mémorise : ``memoriser_centres``) — module n° i en x = i.
CHAINE_2_AVEC_CENTRES = tuple(
    dict(ligne, cx=float(n), cy=0.0)
    for ligne, n in zip(CHAINE_2_SUR_4_A_10, range(4, 11)))


def _manuels(layout, imposee=CHAINE_2_SUR_4_A_10):
    """Les abscisses des modules qui portent l'affectation manuelle."""
    table = affectation(_conception(layout), imposee=imposee)
    panneaux = layout['zones'][0]['geometry']['panels']
    return [panneaux[rang]['cx'] for rang, ligne in enumerate(table)
            if ligne['source'] == 'affectation manuelle']


class ChainesManuellesComportementTest(SimpleTestCase):
    """ACAL648 — ce que fait le code AUJOURD'HUI quand le document change
    sous une affectation manuelle (le nom de chaque test le dit)."""

    POSITIONS = [float(i) for i in range(1, 11)]  # module n° i en x = i
    SANS_LE_3 = [x for x in POSITIONS if x != 3.0]

    def test_retrait_au_milieu_non_numerote_decale_l_affectation(self):
        # Mesuré : la clé suit le RANG ; le module physique 4 devient #3 et
        # perd sa chaîne, le 5 hérite de celle du 4 (décalage silencieux).
        self.assertEqual(_manuels(_pan_pose(self.SANS_LE_3)),
                         [5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    def test_retrait_au_milieu_non_numerote_garde_les_modules_4_a_10(self):
        # ACAL649 — avec le centre mémorisé de chaque ligne, les modules
        # physiques 4 à 10 gardent la chaîne 2 après le retrait du module 3.
        self.assertEqual(_manuels(_pan_pose(self.SANS_LE_3),
                                  CHAINE_2_AVEC_CENTRES),
                         [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    def test_le_reancrage_est_nomme_et_rien_n_est_obsolete(self):
        bloc, avertissements = bloc_electrique(
            _conception(_pan_pose(self.SANS_LE_3)),
            imposee=CHAINE_2_AVEC_CENTRES)

        self.assertEqual(bloc['affectation_obsolete'], [])
        self.assertTrue(any('ont changé de chaîne, voir Affectation' in a
                            for a in avertissements), avertissements)

    def test_cx_sans_cy_est_refuse_en_nommant_le_champ(self):
        from apps.calepinage.services.chaines import (
            AffectationInvalide, normaliser_affectation_imposee,
        )

        with self.assertRaises(AffectationInvalide) as capture:
            normaliser_affectation_imposee([
                {'module': 'zA#4', 'chaine': 2, 'cx': 4.0}])
        self.assertEqual(capture.exception.champ, 'cx')

    def test_memoriser_centres_complete_depuis_le_document(self):
        from apps.calepinage.services.chaines import memoriser_centres

        reglages = memoriser_centres(
            {'affectation_manuelle': list(CHAINE_2_SUR_4_A_10)},
            _pan_pose(self.POSITIONS))

        centres = [(ligne['cx'], ligne['cy'])
                   for ligne in reglages['affectation_manuelle']]
        self.assertEqual(centres, [(float(n), 0.0) for n in range(4, 11)])

    def test_memoriser_centres_garde_le_centre_deja_memorise(self):
        from apps.calepinage.services.chaines import memoriser_centres

        stockee = {'affectation_manuelle': [
            dict(CHAINE_2_SUR_4_A_10[0], cx=4.0, cy=0.0)]}
        reglages = memoriser_centres(
            {'affectation_manuelle': [dict(CHAINE_2_SUR_4_A_10[0])]},
            _pan_pose(self.SANS_LE_3), stockee)

        self.assertEqual(reglages['affectation_manuelle'][0]['cx'], 4.0)

    def test_retrait_au_milieu_numerote_garde_les_modules_4_a_10(self):
        # Le document NUMÉROTÉ avant le retrait : la clé suit n, rien ne
        # glisse (preuve que les deux cas ci-dessus voient la numérotation).
        numeros = [int(x) for x in self.SANS_LE_3]
        self.assertEqual(_manuels(_pan_pose(self.SANS_LE_3, numeros)),
                         [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])

    def test_pas_change_memes_numeros_garde_l_affectation_par_numero(self):
        # Pas de pose changé (1,5 au lieu de 1), mêmes numéros 1…10 : la
        # chaîne 2 reste sur les numéros 4 à 10, à leurs nouvelles places.
        positions = [1.5 * i for i in range(1, 11)]
        self.assertEqual(_manuels(_pan_pose(positions, list(range(1, 11)))),
                         positions[3:])

    def test_pas_change_numeros_neufs_rend_toute_l_affectation_obsolete(self):
        # Numéros neufs (11…20) : aucune clé imposée ne désigne plus un
        # module — tout est publié ``affectation_obsolete``, rien n'est
        # appliqué.
        layout = _pan_pose([1.5 * i for i in range(1, 11)],
                           list(range(11, 21)))
        self.assertEqual(_manuels(layout), [])
        bloc, _a = bloc_electrique(_conception(layout),
                                   imposee=CHAINE_2_SUR_4_A_10)
        self.assertEqual(len(bloc['affectation_obsolete']), 7)

    # Revue lot 8 (suite ACAL1720) — un centre mémorisé sans AUCUN module à moins d'un demi-pas.
    def _pose_retenue(self):
        """Pivot n 1…10 (x = 1…10) + X n° 11 à x = 11 ; la variante retenue porte n° 11 sur Y, à x = 20."""
        pivot = _pan_pose(self.POSITIONS + [11.0], list(range(1, 12)))
        retenue = _pan_pose(self.POSITIONS + [20.0], list(range(1, 12)))
        ligne = {'module': 'zA#11', 'chaine': 2, 'mppt': 1, 'onduleur': 1}
        return pivot, retenue, ligne

    def test_centre_sans_module_la_ligne_est_obsolete_jamais_appliquee_a_y(self):
        from apps.calepinage.services.chaines import memoriser_centres

        pivot, retenue, ligne = self._pose_retenue()
        stockee = memoriser_centres({'affectation_manuelle': [ligne]}, pivot)['affectation_manuelle']
        self.assertEqual((stockee[0]['cx'], stockee[0]['cy']), (11.0, 0.0))  # le centre de X
        self.assertEqual(_manuels(retenue, stockee), [])  # jamais sur Y (zA#11 à x = 20)
        bloc, _a = bloc_electrique(_conception(retenue), imposee=stockee)
        self.assertEqual(bloc['affectation_obsolete'],
                         [{'module': 'zA#11', 'motif': 'module introuvable'}])
        refus = verdict_affectation(_conception(retenue), stockee)
        self.assertTrue(any('zA#11' in r and 'obsolète' in r for r in refus), refus)

    def test_module_a_moins_d_un_demi_pas_garde_sa_ligne(self):
        _pivot, retenue, _ligne = self._pose_retenue()
        proche = [{'module': 'zA#4', 'chaine': 2, 'mppt': 1, 'onduleur': 1, 'cx': 4.2, 'cy': 0.0}]
        self.assertEqual(_manuels(retenue, proche), [4.0])
        bloc, _a = bloc_electrique(_conception(retenue), imposee=proche)
        self.assertEqual(bloc['affectation_obsolete'], [])

    def test_ligne_sans_centre_memorise_comportement_d_avant(self):
        # Ligne d'avant ``memoriser_centres`` : elle suit son numéro, comme avant.
        _pivot, retenue, ligne = self._pose_retenue()
        self.assertEqual(_manuels(retenue, [ligne]), [20.0])


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
