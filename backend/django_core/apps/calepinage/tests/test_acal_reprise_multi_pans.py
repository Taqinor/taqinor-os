"""ACAL190 (C-ACAL-005, D-ACAL-27) — reprise MULTI-PANS du tracé public.

Un visiteur qui dessine trois pans sur /devis/mon-toit envoie le document
``roof_layout`` v2 (clé ``roofLayout``, rangée par le webhook dans
``Lead.web_questionnaire['roof_layout']``, ACAL305). ``lead_created``
déclenche ``reprendre_trace_public`` : le calepinage brouillon repris porte
autant de zones que de pans, vertices octet-identiques, épingle du document,
sans aucun chiffre ajouté. Un document INVALIDE (schéma ``roof_layout_v2``,
``io_layout.valider_document``) ⇒ repli À UNE zone depuis ``roof_outline`` +
ligne de chatter « Tracé multi-pans ignoré : <motif> ». Sans tracé : aucun
calepinage.

VRAIS POST sur ``website_lead_webhook`` (clé de test de
``apps/crm/tests_webhook.py``) — aucun ``web_questionnaire`` fabriqué.

Test-du-test : ignorer ``web_questionnaire['roof_layout']`` dans
``_document_transporte`` ⇒ ``test_trois_pans_donnent_trois_zones`` rougit
(1 zone depuis le contour).

Run :
    python manage.py test apps.calepinage.tests.test_acal_reprise_multi_pans
"""
from __future__ import annotations

import copy
import json

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.crm.tests_webhook import SECRET, payload_site
from apps.records.models import Activity

from .test_api_liste import URL, BaseApiCalepinage

#: Le contour tel que le tunnel l'envoie : [lat, lng].
CONTOUR_4 = [[33.4999, -7.6001], [33.4999, -7.5999],
             [33.5001, -7.5999], [33.5001, -7.6001]]


def _zone(i):
    base_lng, base_lat = -7.6001 + i * 0.0003, 33.4999
    return {'id': f'z{i + 1}', 'label': f'Pan {i + 1}',
            'roofType': 'pitched', 'pitchDeg': 15.0,
            'vertices': [[base_lng, base_lat], [base_lng + 0.0002, base_lat],
                         [base_lng + 0.0002, base_lat + 0.0002],
                         [base_lng, base_lat + 0.0002]]}


def document_trois_pans():
    return {
        'version': 2,
        'pin': {'lat': 33.50005, 'lng': -7.60005},
        'outline': copy.deepcopy(CONTOUR_4),
        'activeAreaId': 'z1',
        'zones': [_zone(0), _zone(1), _zone(2)],
        'source': 'lead',
    }


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class RepriseMultiPansTest(BaseApiCalepinage):

    def _post(self, data):
        with self.settings(WEBSITE_LEADS_COMPANY_ID=self.company.pk):
            return self.client.post(
                reverse('website-lead-webhook'), data=json.dumps(data),
                content_type='application/json',
                HTTP_X_WEBHOOK_SECRET=SECRET)

    def _lead_du_site(self):
        return Lead.objects.get(company=self.company,
                                source=Lead.Source.SITE_WEB)

    def _calepinages(self, lead):
        return Calepinage.objects.filter(lead_id=lead.pk)

    def _layout(self, calepinage):
        reponse = self.api.get(f'{URL}{calepinage.pk}/layout/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data['roof_layout']

    def _notes(self, calepinage):
        return list(Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk).values_list('body', flat=True))

    def test_trois_pans_donnent_trois_zones(self):
        document = document_trois_pans()
        reponse = self._post(payload_site(
            roofLayout=copy.deepcopy(document), roofOutline=CONTOUR_4))
        self.assertEqual(reponse.status_code, 201, reponse.content)
        lead = self._lead_du_site()
        self.assertEqual(self._calepinages(lead).count(), 1)

        layout = self._layout(self._calepinages(lead).get())
        self.assertEqual(len(layout['zones']), 3)
        for repris, envoye in zip(layout['zones'], document['zones']):
            self.assertEqual(repris['vertices'], envoye['vertices'])
        self.assertEqual(layout['pin'], document['pin'])
        self.assertEqual(layout.get('source'), 'lead')
        # Aucun chiffre ajouté : ni module, ni puissance, ni pente inventée.
        for cle in ('panelWatt', 'panelLengthM', 'panelWidthM', 'result'):
            self.assertNotIn(cle, layout)
        for zone, envoye in zip(layout['zones'], document['zones']):
            self.assertNotIn('result', zone)
            self.assertEqual(zone.get('pitchDeg'), envoye['pitchDeg'])

    def test_document_invalide_repli_une_zone_et_chatter(self):
        document = document_trois_pans()
        document['zones'][0]['roofType'] = 'dome'    # hors schéma v2
        reponse = self._post(payload_site(roofLayout=document,
                                          roofOutline=CONTOUR_4))
        self.assertEqual(reponse.status_code, 201, reponse.content)
        lead = self._lead_du_site()
        self.assertEqual(self._calepinages(lead).count(), 1)
        calepinage = self._calepinages(lead).get()

        layout = self._layout(calepinage)
        self.assertEqual(len(layout['zones']), 1)
        self.assertEqual(len(layout['zones'][0]['vertices']), 4)
        notes = [n for n in self._notes(calepinage)
                 if n.startswith('Tracé multi-pans ignoré : ')]
        self.assertEqual(len(notes), 1, self._notes(calepinage))
        self.assertIn('zones.0.roofType', notes[0])

    def test_sans_trace_aucun_calepinage(self):
        reponse = self._post(payload_site())
        self.assertEqual(reponse.status_code, 201, reponse.content)
        lead = self._lead_du_site()
        self.assertEqual(self._calepinages(lead).count(), 0)

    def test_rejeu_idempotent(self):
        donnees = payload_site(roofLayout=document_trois_pans(),
                               roofOutline=CONTOUR_4)
        premier = self._post(copy.deepcopy(donnees))
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self._post(copy.deepcopy(donnees))
        self.assertIn(second.status_code, (200, 201), second.content)
        lead = self._lead_du_site()
        self.assertEqual(self._calepinages(lead).count(), 1)
        self.assertEqual(len(self._layout(
            self._calepinages(lead).get())['zones']), 3)
