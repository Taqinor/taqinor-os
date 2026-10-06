# -*- coding: utf-8 -*-
"""ACAL123 — la simulation accepte le profil d'horizon TEL QUE l'écran
l'enregistre (``roof_layout.horizonProfile``, forme v2 camelCase).

Constat C-ACAL-029. L'onglet Horizon (``HorizonPanel.jsx``) et l'atelier
public (``prefill.ts serializeHorizonProfile``) écrivent ``{source, points:
[{azimuthDeg, heightDeg}], hauteurMaxDeg}`` (contrat ``roof_layout_v2
$defs/horizonProfile``). La simulation passait ce dict TEL QUEL à PVGIS et à
l'étape « horizon », qui attendent ``azimut_face_deg``/``hauteur_deg`` :
``SimulationRefusee(champ='horizon[0]', « Le point d'horizon n°1 est
illisible »)``. Désormais ``services/horizon.py::profil_depuis_document``
convertit, et ``construire_contexte`` comme ``_fournisseur_meteo``
l'appellent.

Le VRAI ``ClientPvgis`` tourne (transport factice qui rejoue une réponse
PVGIS committée et ENREGISTRE l'URL) : c'est lui qui rééchantillonne et
valide le profil — un client double qui ne lit pas le format serait vert à
tort. Le profil du test est validé contre le schéma du contrat.

Run :
    python manage.py test apps.calepinage.tests.test_acal_horizon_document
"""
from __future__ import annotations

import copy
import json
import pathlib
import urllib.parse

from django.test import SimpleTestCase

from apps.calepinage.services import pvgis_serie
from apps.calepinage.services.horizon import profil_depuis_document
from apps.calepinage.services.simulation import (
    SimulationRefusee, construire_contexte, simuler_calepinage,
)
from apps.calepinage.tests.test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage,
)

ICI = pathlib.Path(__file__).resolve().parent
FIXTURE = ICI / 'fixtures_pvgis' / 'seriescalc_casablanca_sud_composantes.json'
FIXTURE_PVCALC = ICI / 'fixtures_pvgis' / 'pvcalc_optimalangles_casablanca.json'
SCHEMA = ICI.parent / 'contract_samples' / 'roof_layout_v2.schema.json'

#: La fenêtre de la réponse committée (une année, 2020).
REGLAGES_2020 = copy.deepcopy(REGLAGES)
REGLAGES_2020['simulation']['fenetre_annees'] = {
    'valeur': [2020, 2020], 'source': 'note interne',
    'reference': 'base PVGIS disponible'}


def profil_document(directions=8, hauteur=5.0):
    """Le profil tel que l'onglet Horizon l'enregistre — forme du contrat."""
    pas = 360.0 / directions
    return {
        'source': 'saisie',
        'points': [{'azimuthDeg': rang * pas, 'heightDeg': hauteur}
                   for rang in range(directions)],
        'hauteurMaxDeg': hauteur,
    }


def valider_contre_le_contrat(profil):
    """Le profil respecte ``$defs/horizonProfile`` (et ``horizonPoint``)."""
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    defs = schema['$defs']
    forme = defs['horizonProfile']
    assert set(profil) <= set(forme['properties']), profil
    assert set(forme['required']) <= set(profil), profil
    assert profil['source'] in forme['properties']['source']['enum']
    point_def = defs['horizonPoint']
    for point in profil['points']:
        assert set(point) <= set(point_def['properties']), point
        assert set(point_def['required']) <= set(point), point
        mini = point_def['properties']['azimuthDeg']['minimum']
        maxi = point_def['properties']['azimuthDeg']['maximum']
        assert mini <= point['azimuthDeg'] <= maxi, point
    return profil


def layout_avec(profil):
    return {
        'version': 2,
        'pin': {'lat': 33.5731, 'lng': -7.5898},
        'zones': [
            {'id': 'a', 'label': 'PAN-A',
             'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
                          'family': 'surimposition'}},
        ],
        'horizonProfile': profil,
    }


class TransportEnregistre:
    """Le transport FACTICE du vrai client : il rejoue, il note les URL."""

    def __init__(self):
        self.appels = []
        self.serie = FIXTURE.read_text(encoding='utf-8')
        self.pvcalc = FIXTURE_PVCALC.read_text(encoding='utf-8')

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        if '/seriescalc?' in url:
            return 200, self.serie
        return 200, self.pvcalc

    def params_seriescalc(self):
        url = next(u for u in self.appels if '/seriescalc?' in u)
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def client_reel(transport):
    return pvgis_serie.ClientPvgis(
        transport=transport, cache=pvgis_serie._Cache(),
        limiteur=pvgis_serie._Limiteur(par_seconde=10 ** 6),
        dormir=lambda _s: None)


def simuler(profil):
    transport = TransportEnregistre()
    calepinage = _Calepinage(layout=layout_avec(profil))
    rendu = simuler_calepinage(
        calepinage, client=client_reel(transport), materiel=MATERIEL,
        reglages=REGLAGES_2020, enregistrer=False)
    return rendu['blocs'], transport, calepinage


class ProfilDuDocumentTest(SimpleTestCase):

    def test_simulation_accepte_le_profil_du_document(self):
        profil = valider_contre_le_contrat(profil_document())
        blocs, transport, calepinage = simuler(copy.deepcopy(profil))

        envoyes = transport.params_seriescalc()
        self.assertEqual(envoyes['userhorizon'], ['5,5,5,5,5,5,5,5'])
        self.assertEqual(envoyes['usehorizon'], ['1'])
        self.assertEqual(blocs['meteo']['horizon']['origine'], 'saisie')
        # Aucune écriture : le document garde sa forme v2 camelCase.
        self.assertEqual(calepinage.roof_layout['horizonProfile'], profil)

    def test_etape_horizon_lit_les_releves_du_document(self):
        contexte, _meta = construire_contexte(
            _Calepinage(layout=layout_avec(profil_document())),
            materiel=MATERIEL, reglages=REGLAGES_2020)
        horizon = contexte['horizon']
        self.assertEqual(horizon['source'], 'saisie')
        self.assertEqual(len(horizon['points']), 8)
        self.assertEqual(
            [p['azimut_face_deg'] for p in horizon['points']],
            [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
        self.assertEqual({p['hauteur_deg'] for p in horizon['points']}, {5.0})
        self.assertEqual(horizon['hauteur_max_deg'], 5.0)

        from apps.calepinage.services.etapes import horizon as etape
        self.assertEqual(len(etape._releves(etape._profil(contexte))), 8)

        blocs, _transport, _cal = simuler(profil_document())
        etape_horizon = next(e for e in blocs['cascade']['etapes']
                             if e['etape'] == 'horizon')
        self.assertNotIn('illisible', etape_horizon['motif_omission'] or '')

    def test_profil_partiel_refuse_tour_incomplet(self):
        with self.assertRaises(SimulationRefusee) as refus:
            simuler(profil_document(directions=2))
        self.assertEqual(refus.exception.champ, 'horizon')
        self.assertIn('faire le tour', str(refus.exception))

    def test_une_forme_service_deja_stockee_passe_telle_quelle(self):
        service = {'source': 'pvgis', 'hauteur_max_deg': 3.0,
                   'base_horizon': 'SRTM',
                   'points': [{'azimut_face_deg': 0.0, 'hauteur_deg': 3.0}]}
        self.assertEqual(profil_depuis_document(service), service)
        self.assertIsNone(profil_depuis_document(None))

    def test_azimut_360_du_contrat_est_le_nord(self):
        profil = profil_document()
        profil['points'][0]['azimuthDeg'] = 360.0
        converti = profil_depuis_document(profil)
        self.assertEqual(converti['points'][0]['azimut_face_deg'], 0.0)
