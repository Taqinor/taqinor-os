"""ACAL143 — UN sélecteur ``ombrage_servi(devis_id, company)`` adossé à la
fraîcheur SERVIE, qui rend la perte d'ombrage PAR PAN.

Constats C-ACAL-075 / C-ACAL-078 : l'étude bancable du devis
(``apps/ventes/etude.py``) lisait la cascade STOCKÉE et la « validait » en
comparant son ``hash_entree`` à l'en-tête de la MÊME simulation — une
tautologie : une cascade calculée sur un autre toit passait toujours, et
seule la variante retenue était consultée.

Le sélecteur lit le résultat SERVI (``selectors.resultat_servi`` : verdict de
fraîcheur de GET resultat/, empreinte de simulation) et rend
``{perime, motif, par_pan, global}`` — ou ``None`` sans calepinage ou sans
simulation.

Calepinage RÉEL en base de test, simulé par la vraie chaîne (client rejoué),
aucun mock du sélecteur.

Run :
    python manage.py test apps.calepinage.tests.test_acal_ombrage_servi -v2
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import ombrage_servi
from apps.calepinage.selectors_devis import (
    MOTIF_SURFACES, contrat_depuis_servi, productible_pose_du_calepinage,
    productible_pose_servi)
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.simulation import simuler_calepinage
from apps.ventes.models import Devis

from .acal_livrables_helpers import patch_materiel
from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import MATERIEL


class OmbrageServiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1431')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        # Un accès solaire publié par le constructeur : l'étape « accès
        # module » s'applique, la perte d'ombrage est mesurée.
        layout['solarAccess'] = {'values': [0.9] * 24}
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Ombrage 143',
            roof_layout=layout)
        lier_devis(self.calepinage, self.devis.pk)
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
        self.calepinage.refresh_from_db()

    def test_frais_rend_la_perte_par_pan(self):
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)

        self.assertIsNotNone(servi)
        self.assertFalse(servi['perime'])
        self.assertEqual(sorted(servi['par_pan']), ['PAN-1', 'PAN-2'])
        attendu = {ligne['pan']: ligne['perte_ombrage_pct']
                   for ligne in self.calepinage.resultat['ombrage']
                   ['par_pan']}
        self.assertEqual(servi['par_pan'], attendu)
        self.assertIn('global', servi)

    def test_retouche_sans_resimuler_rend_perime(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        layout['zones'][0]['obstacles'] = [{'id': 'o1', 'heightM': 2.0}]
        self.calepinage.roof_layout = layout
        self.calepinage.save(update_fields=['roof_layout'])

        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)

        self.assertTrue(servi['perime'])
        self.assertTrue(servi['motif'])
        self.assertEqual(servi['par_pan'], {})
        self.assertIsNone(servi['global'])

    def test_conception_divergente_du_devis_rend_perime(self):
        """ACON21 — lien direct, empreinte du devis ≠ empreinte du
        calepinage (conception modifiée sans resynchroniser) : périmé,
        aucune perte ; empreintes égales : la perte est servie."""
        from apps.calepinage.selectors import MOTIF_CONCEPTION_DIVERGENTE

        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            layout_hash='b' * 64)
        Devis.objects.filter(pk=self.devis.pk).update(layout_hash='a' * 64)
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
        self.assertEqual(servi, {'perime': True,
                                 'motif': MOTIF_CONCEPTION_DIVERGENTE,
                                 'par_pan': {}, 'global': None})

        Devis.objects.filter(pk=self.devis.pk).update(layout_hash='b' * 64)
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)
        self.assertFalse(servi['perime'])
        self.assertEqual(sorted(servi['par_pan']), ['PAN-1', 'PAN-2'])

    def test_autre_societe_none(self):
        with patch_materiel():
            self.assertIsNone(ombrage_servi(self.devis.pk, self.autre))

    def test_jamais_simule_none(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1432')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk,
            titre='Jamais simulé', roof_layout=_layout(_zone(1, 8)))
        lier_devis(calepinage, devis.pk)

        with patch_materiel():
            self.assertIsNone(ombrage_servi(devis.pk, self.company))


# ── ACAL997 — le productible de la pose réelle (selectors_devis) ──────────
_CONTRAT_POSE = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_productible_pose.json').read_text(encoding='utf-8'))


def _servi_pose(*, complete=True, socle=(), kwc=71.0, p50=98576.0):
    """Un ``resultat_servi`` de la forme de ``calepinage_simulation.json``."""
    mensuel = _CONTRAT_POSE['exemple']['kwh_kwc_mensuel']
    return {
        'simule': True, 'simulation_perimee': False, 'motif': '',
        'calcule_le': '2026-11-21T09:30:00+01:00',
        'production': {
            'total': {'kwc': kwc, 'p50_kwh': p50, 'complete': complete,
                      'socle_manquant': list(socle)},
            'mensuel': [{'mois': i + 1, 'p50_kwh': round(v * kwc, 1)}
                        for i, v in enumerate(mensuel)],
            'par_pan': _CONTRAT_POSE['exemple']['pans'],
        },
        'cascade': {'etapes_omises': list(socle)},
    }


class ContratProductiblePoseTest(SimpleTestCase):
    """ACAL997 — la forme pure, sans base : contrat ACAL996 affirmé."""

    def _contrat(self, servi, kwc_document=71.0):
        return contrat_depuis_servi(servi, kwc_document,
                                    tolerance_kwc_ratio=0.02)

    def test_simule_complet_rend_le_contrat(self):
        rendu = self._contrat(_servi_pose())
        attendu = _CONTRAT_POSE['exemple']
        self.assertEqual(set(rendu), set(attendu))
        self.assertFalse(rendu['perime'])
        self.assertEqual(rendu['source'], 'calepinage_enregistre')
        self.assertEqual(rendu['kwh_kwc_annuel'], round(98576.0 / 71.0, 1))
        self.assertEqual(rendu['kwh_kwc_annuel'], attendu['kwh_kwc_annuel'])
        self.assertEqual(rendu['kwh_kwc_mensuel'], attendu['kwh_kwc_mensuel'])
        self.assertTrue(rendu['pertes_et_ombrage_inclus'])
        self.assertTrue(rendu['couvre_toutes_les_surfaces'])
        self.assertEqual(rendu['pans'], attendu['pans'])

    def test_cascade_incomplete_jamais_servie(self):
        rendu = self._contrat(_servi_pose(
            complete=False, socle=('salissure', 'mismatch_fabricant', 'lid')))
        self.assertEqual(set(rendu), set(_CONTRAT_POSE['exemple_incomplet']))
        self.assertTrue(rendu['perime'])
        self.assertEqual(rendu['motif'],
                         _CONTRAT_POSE['exemple_incomplet']['motif'])
        self.assertFalse(rendu['pertes_et_ombrage_inclus'])

    def test_kwc_partiels_perime(self):
        rendu = self._contrat(_servi_pose(), kwc_document=80.0)
        self.assertFalse(rendu['couvre_toutes_les_surfaces'])
        self.assertTrue(rendu['perime'])
        self.assertEqual(rendu['motif'], MOTIF_SURFACES)
        # Dans la tolérance passée par l'appelant : servi.
        dans = self._contrat(_servi_pose(), kwc_document=71.5)
        self.assertFalse(dans['perime'])

    def test_simulation_perimee_rend_le_contrat_perime(self):
        rendu = self._contrat({'simulation_perimee': True,
                               'motif': 'toit changé'})
        self.assertEqual(set(rendu), set(_CONTRAT_POSE['exemple_perime']))
        self.assertEqual((rendu['perime'], rendu['motif']),
                         (True, 'toit changé'))
        self.assertIsNone(rendu['kwh_kwc_annuel'])

    def test_jamais_simule_none(self):
        self.assertIsNone(self._contrat({'simule': False, 'production': None}))
        self.assertIsNone(self._contrat(None))


class ProductiblePoseServiTest(BaseApiCalepinage):
    """ACAL997 — calepinage RÉEL simulé par la vraie chaîne (patron
    ``OmbrageServiTest``)."""

    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202611-1997')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        layout['solarAccess'] = {'values': [0.9] * 24}
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Pose 997',
            roof_layout=layout)
        lier_devis(self.calepinage, self.devis.pk)
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
        self.calepinage.refresh_from_db()

    def _servi(self, company=None):
        with patch_materiel():
            return productible_pose_servi(
                self.devis.pk, company or self.company,
                tolerance_kwc_ratio=0.02)

    def test_frais_rend_le_contrat_et_egal_sans_devis(self):
        servi = self._servi()
        self.assertEqual(set(servi), set(_CONTRAT_POSE['exemple']))
        total = self.calepinage.resultat['production']['total']
        p50, kwc = float(total['p50_kwh']), float(total['kwc'])
        complet = total['complete'] is True
        self.assertEqual(servi['p50_kwh'], p50)
        self.assertEqual(servi['kwh_kwc_annuel'], round(p50 / kwc, 1))
        self.assertEqual(servi['pertes_et_ombrage_inclus'], complet)
        self.assertEqual(servi['perime'], not (
            complet and servi['couvre_toutes_les_surfaces']))
        with patch_materiel():
            sans_devis = productible_pose_du_calepinage(
                self.calepinage, tolerance_kwc_ratio=0.02)
        self.assertEqual(sans_devis, servi)

    def test_conception_changee_perime(self):
        from apps.calepinage.selectors import MOTIF_CONCEPTION_DIVERGENTE

        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            layout_hash='b' * 64)
        Devis.objects.filter(pk=self.devis.pk).update(layout_hash='a' * 64)
        servi = self._servi()
        self.assertTrue(servi['perime'])
        self.assertEqual(servi['motif'], MOTIF_CONCEPTION_DIVERGENTE)
        self.assertIsNone(servi['kwh_kwc_annuel'])

    def test_retouche_sans_resimuler_perime(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        layout['zones'][0]['obstacles'] = [{'id': 'o1', 'heightM': 2.0}]
        self.calepinage.roof_layout = layout
        self.calepinage.save(update_fields=['roof_layout'])
        servi = self._servi()
        self.assertTrue(servi['perime'])
        self.assertTrue(servi['motif'])

    def test_autre_societe_none(self):
        self.assertIsNone(self._servi(self.autre))
