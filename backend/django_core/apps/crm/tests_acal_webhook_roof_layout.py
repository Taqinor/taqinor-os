"""ACAL305 (C-ACAL-005, D-ACAL-27) — le webhook public range ``roofLayout``.

Le tunnel du site émet le tracé MULTI-PANS du visiteur (document
``roof_layout`` v2, clé ``roofLayout`` du contrat
``contract_samples/tunnel_webhook_keys.json``). Le webhook le whiteliste, le
borne (≤ 64 Ko, ≤ 12 zones, ≤ 64 sommets par zone, chaque sommet nettoyé par
``_clean_roof_point``) et le range dans ``Lead.web_questionnaire['roof_layout']``
— à la création comme au renvoi (< 60 s). Hors bornes : clé ignorée, lead
créé normalement, jamais une erreur pour le visiteur.

Vrais POST sur ``website_lead_webhook`` avec la clé de test de
``tests_webhook.py`` ; aucun mock du mapping.

Run :
    python manage.py test apps.crm.tests_acal_webhook_roof_layout -v2
"""
import copy
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company
from core.events import lead_trace_toit_recu

from .models import Lead
from .tests_webhook import SECRET, payload_site


def _zone(i, n_sommets=4):
    base_lng, base_lat = -7.6001 + i * 0.0003, 33.4999
    sommets = [[base_lng, base_lat], [base_lng + 0.0002, base_lat],
               [base_lng + 0.0002, base_lat + 0.0002],
               [base_lng, base_lat + 0.0002]]
    while len(sommets) < n_sommets:
        sommets.append([base_lng + 0.0001, base_lat + 0.0001])
    return {'id': f'z{i + 1}', 'label': f'Pan {i + 1}',
            'roofType': 'pitched', 'pitchDeg': 15.0,
            'vertices': sommets[:n_sommets]}


def document_trois_pans():
    return {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'outline': [[33.4999, -7.6001], [33.4999, -7.5999],
                    [33.5001, -7.5999], [33.5001, -7.6001]],
        'activeAreaId': 'z1',
        'zones': [_zone(0), _zone(1), _zone(2)],
        'source': 'lead',
    }


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class RoofLayoutWebhookTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor Layout',
                                              slug='taqinor-layout-acal305')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        with self.settings(WEBSITE_LEADS_COMPANY_ID=self.company.pk):
            return self.client.post(
                self.url, data=json.dumps(data),
                content_type='application/json',
                HTTP_X_WEBHOOK_SECRET=SECRET)

    def _lead(self):
        return Lead.objects.get(company=self.company,
                                source=Lead.Source.SITE_WEB)

    @staticmethod
    def _layout(lead):
        return (lead.web_questionnaire or {}).get('roof_layout')

    def test_post_reel_range_roof_layout_borne(self):
        document = document_trois_pans()
        res = self.post(payload_site(roofLayout=copy.deepcopy(document)))
        self.assertEqual(res.status_code, 201, res.content)
        lead = self._lead()
        self.assertEqual(self._layout(lead), document)
        self.assertEqual(len(self._layout(lead)['zones']), 3)

    def test_document_hors_bornes_ignore_lead_cree(self):
        treize = document_trois_pans()
        treize['zones'] = [_zone(i) for i in range(13)]
        res = self.post(payload_site(roofLayout=treize))
        self.assertEqual(res.status_code, 201, res.content)
        lead = self._lead()
        self.assertEqual(lead.nom, 'Amina Benali')
        self.assertIsNone(self._layout(lead))

    def test_autres_bornes_ignorent_la_cle(self):
        cas = {
            'sommets': lambda d: d['zones'].__setitem__(0, _zone(0, 65)),
            'latitude': lambda d: d['zones'][0]['vertices'].__setitem__(
                0, [-7.6, 95.0]),
            'taille': lambda d: d.__setitem__('remplissage', 'x' * 70000),
        }
        for rang, (nom, alterer) in enumerate(cas.items()):
            with self.subTest(borne=nom):
                document = document_trois_pans()
                alterer(document)
                telephone = f'21266185{rang:04d}'
                res = self.post(payload_site(
                    roofLayout=document, phoneE164=f'+{telephone}'))
                self.assertEqual(res.status_code, 201, res.content)
                lead = Lead.objects.get(company=self.company,
                                        telephone=telephone)
                self.assertIsNone(self._layout(lead))

    def test_renvoi_complete_le_lead_existant(self):
        self.assertEqual(self.post(payload_site()).status_code, 201)
        lead = self._lead()
        self.assertIsNone(self._layout(lead))

        document = document_trois_pans()
        with mock.patch.object(lead_trace_toit_recu, 'send') as envoi:
            res = self.post(payload_site(roofLayout=copy.deepcopy(document)))
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(self._layout(lead), document)
        envoi.assert_called_once()
        self.assertEqual(envoi.call_args.kwargs['lead'].pk, lead.pk)

        # Rejeu à l'identique : inchangé.
        self.post(payload_site(roofLayout=copy.deepcopy(document)))
        lead.refresh_from_db()
        self.assertEqual(self._layout(lead), document)

        # Un renvoi plus pauvre (sans tracé) n'efface jamais le document, et
        # un autre document n'écrase jamais celui déjà reçu.
        self.post(payload_site(city='Rabat', surfaceType='terrasse'))
        autre = document_trois_pans()
        autre['zones'] = autre['zones'][:1]
        self.post(payload_site(city='Fès', roofLayout=autre))
        lead.refresh_from_db()
        self.assertEqual(self._layout(lead), document)

    def test_sans_roof_layout_inchange(self):
        res = self.post(payload_site())
        self.assertEqual(res.status_code, 201, res.content)
        lead = self._lead()
        self.assertNotIn('roof_layout', lead.web_questionnaire or {})
