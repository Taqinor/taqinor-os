"""ACAL326 — résidus AO retirés, colonne et index GARDÉS (D-ACAL-16).

Constat C-ACAL-141 (audit 2026-10-04) : le champ API inscriptible
``appel_offre`` du sérialiseur laissait tout client poser
``appel_offre_id=424242`` sur un calepinage alors que le module AO est
parqué (SOLMVP15). Le champ, ``journaliser_lien_appel_offre`` et
``selectors.calepinage_de_l_affaire`` sont retirés ; la colonne et son index
restent (retour d'AO sans perte, recette dans docs/parked-modules.md §7).

Run :
    python manage.py test apps.calepinage.tests.test_acal_ao_residus -v2
"""
from __future__ import annotations

from apps.calepinage import selectors
from apps.calepinage.models import Calepinage
from apps.calepinage.services import journal

from .test_api_liste import URL, BaseApiCalepinage, url_detail


class ResidusAoTest(BaseApiCalepinage):
    def test_patch_appel_offre_est_ignore_et_la_colonne_reste_vide(self):
        reponse = self.api.post(URL, {'client': self.client_a.pk,
                                      'appel_offre': 424242}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotIn('appel_offre', reponse.data)
        pk = reponse.data['id']
        self.assertIsNone(Calepinage.objects.get(pk=pk).appel_offre_id)

        # ACAL179 (même vague) rend le PATCH STRICT : une clé inconnue du
        # corps est refusée EN LA NOMMANT, jamais un 200 silencieux. Le champ
        # retiré par ACAL326 est donc refusé au PATCH et RIEN n'est écrit —
        # la colonne reste NULL, le titre du même corps n'est pas posé.
        reponse = self.api.patch(url_detail(pk), {'appel_offre': 424242,
                                                  'titre': 'Renommé'},
                                 format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('appel_offre', reponse.data)
        calepinage = Calepinage.objects.get(pk=pk)
        self.assertIsNone(calepinage.appel_offre_id)
        self.assertNotEqual(calepinage.titre, 'Renommé')

        reponse = self.api.patch(url_detail(pk), {'titre': 'Renommé'},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertNotIn('appel_offre', reponse.data)
        calepinage = Calepinage.objects.get(pk=pk)
        self.assertIsNone(calepinage.appel_offre_id)
        self.assertEqual(calepinage.titre, 'Renommé')
        self.assertNotIn('appel_offre',
                         self.api.get(url_detail(pk)).data)

    def test_la_colonne_et_l_index_existent_toujours(self):
        champ = Calepinage._meta.get_field('appel_offre_id')
        self.assertTrue(champ.null)
        index = {i.name: i.fields for i in Calepinage._meta.indexes}
        self.assertIn('cal_cal_co_ao_idx', index)
        self.assertIn('appel_offre_id', index['cal_cal_co_ao_idx'])
        self.assertFalse(hasattr(selectors, 'calepinage_de_l_affaire'))
        self.assertFalse(hasattr(journal, 'journaliser_lien_appel_offre'))

    def test_publicapi_expose_toujours_appel_offre_id_null(self):
        from apps.publicapi.calepinage_event_receivers import (
            charge_utile_simulation,
        )

        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Public')
        charge = charge_utile_simulation(calepinage)
        self.assertIn('appel_offre_id', charge)
        self.assertIsNone(charge['appel_offre_id'])
