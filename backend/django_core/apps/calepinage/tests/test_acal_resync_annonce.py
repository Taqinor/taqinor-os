"""ACAL38 (D-ACAL-1, C-ACAL-109) — « Resynchroniser le devis » depuis le module
annonce ENFIN ``layout_finalise``, UNE fois, sans rien réécrire du calepinage.

Catalogue tarifé réel, HTTP réel ; l'abonné crm (note au chatter du lead) est
le VRAI récepteur ; seul un compteur d'émissions est branché sur le signal.

Run :
    python manage.py test apps.calepinage.tests.test_acal_resync_annonce -v2
"""
import copy

from core import events

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout

from .test_api_liste import BaseApiCalepinage, url_detail

TOIT = {
    'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
               'obstacles': [], 'roofType': 'flat', 'pitch': 10,
               'azimuth': 180}],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


class ResyncAnnonceTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL38')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)
        self.base = url_detail(self.calepinage.pk)
        reponse = self.api.post(f'{self.base}generer-devis/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.emissions = []

        def compter(sender, devis=None, **kwargs):
            self.emissions.append(getattr(devis, 'pk', None))
        self._compteur = compter
        events.layout_finalise.connect(compter, weak=False,
                                       dispatch_uid='acal38_compteur')

    def tearDown(self):
        events.layout_finalise.disconnect(dispatch_uid='acal38_compteur')
        super().tearDown()

    def test_resync_module_emet_layout_finalise_une_fois_sans_version(self):
        modifie = copy.deepcopy(TOIT)
        modifie['result']['panels'] = 14
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.calepinage.refresh_from_db()
        document_avant = copy.deepcopy(self.calepinage.roof_layout)
        versions_avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()

        reponse = self.api.post(f'{self.base}sync-devis/', {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

        self.assertEqual(len(self.emissions), 1)
        self.assertEqual(self.emissions[0], self.calepinage.devis_id)
        self.calepinage.refresh_from_db()
        # Aucune version déposée par la resynchro, aucun document réécrit.
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), versions_avant)
        self.assertEqual(self.calepinage.roof_layout, document_avant)
        self.assertNotIn('_pans_geometry', self.calepinage.roof_layout)
