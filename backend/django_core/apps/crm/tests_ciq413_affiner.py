"""CIQ413 — relève « Affiner » : le site obtient le lien du questionnaire PRO
de SA soumission, et rien d'autre (contrat ``lead_affiner_pro.json``).

Run :
    python manage.py test apps.crm.tests_ciq413_affiner -v 2
"""
import json
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from . import stages
from .models import Lead, LeadActivity, QuestionnaireLien
from .public_affiner_views import NOTE_LIEN_AFFINER, PublicLeadAffinerThrottle
from .tests_webhook import SECRET, payload_site

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_affiner_pro.json').read_text(encoding='utf-8'))
PUBLIC_QUESTIONNAIRE = '/api/django/crm/public/questionnaire/{}/'


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class LeadAffinerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='CIQ413 Co',
                                              slug='ciq413-co')
        self.webhook_url = reverse('website-lead-webhook')

    def _soumettre(self, idem, **extra):
        res = self.client.post(
            self.webhook_url,
            data=json.dumps(payload_site(idempotencyKey=idem, **extra)),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 201, res.content)
        return Lead.objects.get(pk=res.json()['lead_id'])

    def _affiner(self, cle):
        return self.client.post(reverse('public-lead-affiner', args=[cle]))

    def test_lead_pro_new_recoit_un_jeton_du_contrat(self):
        lead = self._soumettre('idem-ciq413-pro-01', mode='professionnel')
        self.assertIn(lead.type_installation, ('commercial', 'industriel'))
        self.assertEqual(lead.stage, stages.NEW)
        res = self._affiner('idem-ciq413-pro-01')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(set(res.json()), set(CONTRAT['exemple']))
        lien = QuestionnaireLien.objects.get(lead=lead)
        self.assertEqual(res.json()['questionnaire_token'], lien.token)

    def test_meme_cle_deux_fois_meme_jeton_une_seule_note(self):
        lead = self._soumettre('idem-ciq413-pro-02', mode='professionnel')
        premier = self._affiner('idem-ciq413-pro-02').json()
        second = self._affiner('idem-ciq413-pro-02').json()
        self.assertEqual(premier, second)
        self.assertEqual(QuestionnaireLien.objects.filter(lead=lead).count(),
                         1)
        self.assertEqual(LeadActivity.objects.filter(
            lead=lead, body=NOTE_LIEN_AFFINER).count(), 1)

    def test_le_meme_404_octet_pour_octet(self):
        self._soumettre('idem-ciq413-resi-03')
        contacte = self._soumettre('idem-ciq413-cont-04',
                                   mode='professionnel',
                                   phoneE164='+212661000444')
        Lead.objects.filter(pk=contacte.pk).update(stage=stages.CONTACTED)
        reponses = [
            self._affiner('idem-ciq413-resi-03'),      # résidentiel
            self._affiner('idem-ciq413-cont-04'),      # déjà contacté
            self._affiner('idem-jamais-vue-ciq413'),   # clé inconnue
            self._affiner('abc'),                      # mal formée
        ]
        for res in reponses:
            self.assertEqual(res.status_code, 404)
        corps = {res.content for res in reponses}
        self.assertEqual(len(corps), 1)
        self.assertEqual(reponses[0].json(),
                         {'detail': CONTRAT['exemple_404']['detail']})

    def test_lead_anonymise_404(self):
        from .dsr_provider import LEAD_NOM_ANONYMISE
        lead = self._soumettre('idem-ciq413-anon-05', mode='professionnel')
        Lead.objects.filter(pk=lead.pk).update(nom=LEAD_NOM_ANONYMISE)
        self.assertEqual(self._affiner('idem-ciq413-anon-05').status_code,
                         404)

    def test_le_jeton_n_ouvre_que_des_sections_pro(self):
        self._soumettre('idem-ciq413-pro-06', mode='professionnel')
        jeton = self._affiner('idem-ciq413-pro-06').json()[
            'questionnaire_token']
        get = self.client.get(PUBLIC_QUESTIONNAIRE.format(jeton))
        self.assertEqual(get.status_code, 200, get.content)
        for section in get.json()['sections']:
            self.assertNotIn(section, ('occupation', 'equipements',
                                       'energie', 'toiture'))
        res = self.client.post(
            PUBLIC_QUESTIONNAIRE.format(jeton),
            data=json.dumps({'section': 'occupation',
                             'reponses': {'occupation_jour': 'present'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_throttle_actif(self):
        self._soumettre('idem-ciq413-pro-07', mode='professionnel')
        with mock.patch.object(PublicLeadAffinerThrottle, 'rate',
                               '2/minute'):
            codes = [self._affiner('idem-ciq413-pro-07').status_code
                     for _ in range(3)]
        self.assertEqual(codes[:2], [200, 200])
        self.assertEqual(codes[2], 429)
