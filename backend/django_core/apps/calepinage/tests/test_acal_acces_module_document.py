# -*- coding: utf-8 -*-
"""ACAL137 — la simulation lit l'accès solaire par module LÀ OÙ l'atelier
l'écrit : ``zones[].geometry.solarAccess`` du pan, méthode = OBJET du contrat.

Constat C-ACAL-072. ``_ombrage_du_document`` ne publiait que deux clés RACINE
(``solar_access`` / ``solarAccess``) qui n'existent dans aucun document, et
l'étape « Accès solaire, module par module » les lisait : elle s'omettait
toujours. Désormais ``etapes.acces_module.acces_du_pan`` lit la géométrie du
pan simulé (valeurs via ``ombrage_chaines.acces_par_module``, méthode et
hypothèses du même bloc) ; une méthode en CHAÎNE (ancienne forme) et une
période autre que l'année sont omises avec leur motif.

Le document est l'EXEMPLE du contrat ``roof_layout_v2`` (pas une fixture
écrite à la main), son pan « Pan Sud » portant l'accès sous la forme D04-T02.

Run :
    python manage.py test apps.calepinage.tests.test_acal_acces_module_document
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.etapes import acces_module
from apps.calepinage.services.simulation import (
    construire_contexte, simuler_calepinage,
)
from apps.calepinage.tests.test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage,
)
from apps.calepinage.tests.test_acal_multi_pans import _ClientParOrientation

CONTRAT = (pathlib.Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'roof_layout_v2.schema.json')

#: L'accès solaire du pan sous la forme D04-T02 (ACAL2) — celle du contrat.
ACCES = {
    'values': [0.9, 0.8],
    'method': {'horizon': False, 'rangees': False, 'resolution': 'annuelle',
               'description': 'Accès solaire annuel, ombrage proche seul'},
    'assumptions': {'periode': 'annee'},
    'computedAt': '2026-10-01T10:00:00Z',
}

#: Deux heures ensoleillées, composantes séparées.
SERIE = {
    'pas_minutes': 60,
    'points': [
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
         'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
         'gi_w_m2': 1000.0},
        {'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 12,
         'gb_i_w_m2': 400.0, 'gd_i_w_m2': 100.0, 'gr_i_w_m2': 0.0,
         'gi_w_m2': 500.0},
    ],
}


def document(acces=None):
    """L'exemple du contrat, réduit à son pan « Pan Sud » équipé."""
    exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
    doc = copy.deepcopy(exemple)
    pan = doc['zones'][0]
    pan['geometry']['solarAccess'] = copy.deepcopy(ACCES if acces is None
                                                   else acces)
    doc['zones'] = [pan]
    return doc


def contexte_du_pan(doc):
    """Le contexte que la simulation bâtit, sur le pan simulé."""
    contexte, meta = construire_contexte(
        _Calepinage(layout=doc), materiel=MATERIEL, reglages=REGLAGES)
    contexte['plan'] = meta['plans_equipes'][0]
    return contexte


def etape_acces(blocs):
    return next(e for e in blocs['cascade']['etapes']
                if e['etape'] == 'acces_module')


class AccesDuDocumentTest(SimpleTestCase):

    def test_acces_lu_dans_la_geometrie_du_pan(self):
        contexte = contexte_du_pan(document())
        # Aucune clé racine inventée : seul le document fait foi.
        self.assertNotIn('solar_access', contexte['ombrage'])
        self.assertNotIn('solarAccess', contexte['ombrage'])

        rendue, etape = acces_module.appliquer(SERIE, contexte)
        self.assertEqual(etape['motif_omission'], '')
        self.assertEqual(etape['entree']['acces_par_module'], [0.9, 0.8])
        self.assertAlmostEqual(etape['entree']['facteur_moyen'], 0.85)
        self.assertEqual(etape['entree']['methode']['resolution'], 'annuelle')
        self.assertAlmostEqual(rendue['points'][0]['gb_i_w_m2'], 800.0 * 0.85)

        # Bout en bout : la simulation réelle APPLIQUE l'étape au pan.
        rendu = simuler_calepinage(
            _Calepinage(layout=document()), client=_ClientParOrientation(),
            materiel=MATERIEL, reglages=REGLAGES, enregistrer=False)
        etape = etape_acces(rendu['blocs'])
        self.assertEqual(etape['motif_omission'], '')
        self.assertGreater(etape['perte_kwh'], 0.0)

    def test_methode_chaine_refusee_avec_motif(self):
        acces = dict(ACCES, method='shadingEngine roofPro11')
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_du_pan(document(acces)))
        self.assertIn('texte libre', etape['motif_omission'])
        self.assertIn('solarAccess.method', etape['motif_omission'])

    def test_periode_mensuelle_omise(self):
        acces = dict(ACCES, assumptions={'periode': 'mois'})
        _rendue, etape = acces_module.appliquer(
            SERIE, contexte_du_pan(document(acces)))
        self.assertIn('« mois »', etape['motif_omission'])
        self.assertIn('assumptions.periode', etape['motif_omission'])

    def test_la_matrice_reste_appliquee_quand_l_acces_est_refuse(self):
        # Un accès que l'étape n'applique pas n'écarte pas la matrice 12×24
        # (exclusivité de l'ordonnanceur, même règle que l'étape).
        from apps.calepinage.services import chaine_pertes

        refuse = contexte_du_pan(document(dict(ACCES, method='texte')))
        retenu = contexte_du_pan(document())
        self.assertFalse(chaine_pertes._acces_module_disponible(refuse))
        self.assertTrue(chaine_pertes._acces_module_disponible(retenu))

    def test_enregistrer_deux_fois_sans_geste_ne_perime_pas(self):
        # computedAt est VOLATIL : seul son changement ne bouge pas
        # l'empreinte de simulation (D-ACAL-4).
        _c1, meta1 = construire_contexte(
            _Calepinage(layout=document()), materiel=MATERIEL,
            reglages=REGLAGES)
        autre = document(dict(ACCES, computedAt='2026-10-02T08:00:00Z'))
        _c2, meta2 = construire_contexte(
            _Calepinage(layout=autre), materiel=MATERIEL, reglages=REGLAGES)
        self.assertEqual(meta1['hash_entree'], meta2['hash_entree'])
