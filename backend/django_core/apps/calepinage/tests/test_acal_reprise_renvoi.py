"""ACAL189 (C-ACAL-006) — le tracé public qui arrive au RENVOI (< 60 s).

Constat : un lead créé par le site SANS contour, puis complété par un second
POST du webhook (même téléphone, moins de 60 s) qui apporte ``roofOutline``,
n'ouvrait jamais de calepinage pré-tracé : ``lead_created`` avait été émis à
la création, quand il n'y avait rien à reprendre, et la branche « renvoi » du
webhook n'émettait rien.

Ce qui est tenu ici, par de VRAIS POST sur ``website_lead_webhook`` (clé de
test de ``apps/crm/tests_webhook.py``), aucun mock :
  * le second POST qui apporte un contour de 4 sommets émet
    ``core.events.lead_trace_toit_recu`` et le module ouvre UN calepinage
    pré-tracé dont ``zones[0].vertices`` a 4 sommets (relu par GET layout) ;
  * un second POST sans nouveau contour ne crée rien ;
  * le rejeu du second POST reste à UN calepinage (porte unique ACAL182) ;
  * un lead qui avait déjà un contour n'émet rien au renvoi.

Run :
    python manage.py test apps.calepinage.tests.test_acal_reprise_renvoi -v2
"""
from __future__ import annotations

import json
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.crm.tests_webhook import SECRET, payload_site
from core.events import lead_trace_toit_recu

from .test_api_liste import URL, BaseApiCalepinage

#: Le contour tel que le tunnel l'envoie : [lat, lng].
CONTOUR_4 = [[33.4999, -7.6001], [33.4999, -7.5999],
             [33.5001, -7.5999], [33.5001, -7.6001]]


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class RepriseAuRenvoiTest(BaseApiCalepinage):

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

    def test_second_post_avec_contour_ouvre_le_calepinage_pre_trace(self):
        premier = self._post(payload_site())
        self.assertEqual(premier.status_code, 201, premier.content)
        lead = self._lead_du_site()
        self.assertFalse(lead.roof_outline)
        self.assertEqual(self._calepinages(lead).count(), 0)

        second = self._post(payload_site(roofOutline=CONTOUR_4))
        self.assertEqual(second.status_code, 200, second.content)

        self.assertEqual(self._calepinages(lead).count(), 1)
        calepinage = self._calepinages(lead).get()
        reponse = self.api.get(f'{URL}{calepinage.pk}/layout/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        zones = reponse.data['roof_layout']['zones']
        self.assertEqual(len(zones[0]['vertices']), 4)

    def test_second_post_sans_nouveau_contour_ne_cree_rien(self):
        self.assertEqual(self._post(payload_site()).status_code, 201)
        lead = self._lead_du_site()
        with mock.patch.object(lead_trace_toit_recu, 'send') as envoi:
            second = self._post(payload_site(city='Rabat'))
        self.assertEqual(second.status_code, 200, second.content)
        envoi.assert_not_called()
        self.assertEqual(self._calepinages(lead).count(), 0)

    def test_rejeu_idempotent(self):
        self.assertEqual(self._post(payload_site()).status_code, 201)
        lead = self._lead_du_site()
        second = payload_site(roofOutline=CONTOUR_4)
        self.assertEqual(self._post(second).status_code, 200)
        self.assertEqual(self._calepinages(lead).count(), 1)
        # Rejeu à l'identique, puis un renvoi enrichi : jamais un second.
        self._post(second)
        self._post(payload_site(roofOutline=CONTOUR_4, city='Rabat'))
        self.assertEqual(self._calepinages(lead).count(), 1)

    def test_lead_qui_avait_deja_un_contour_n_emet_rien(self):
        premier = self._post(payload_site(roofOutline=CONTOUR_4))
        self.assertEqual(premier.status_code, 201, premier.content)
        lead = self._lead_du_site()
        with mock.patch.object(lead_trace_toit_recu, 'send') as envoi:
            self._post(payload_site(roofOutline=CONTOUR_4, city='Rabat'))
        envoi.assert_not_called()
        self.assertLessEqual(self._calepinages(lead).count(), 1)
