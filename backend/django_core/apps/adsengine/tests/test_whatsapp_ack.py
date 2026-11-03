"""CADV41 (D-CADV-5) — UN accusé WhatsApp utilitaire au lead Meta arrivé hors heures
qui a coché la case WhatsApp, journalisé sans valoir premier contact.

Nouveau fichier car : aucun module ne couvre l'envoi sortant. HTTP simulé : aucun
message réel ne part jamais de ces tests.
"""
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import whatsapp_ack
from apps.crm.models import Lead, LeadActivity
from core.events import meta_lead_captured

CASA = ZoneInfo('Africa/Casablanca')
SAMEDI_0310 = datetime(2026, 11, 7, 3, 10, tzinfo=CASA)
MARDI_1100 = datetime(2026, 11, 10, 11, 0, tzinfo=CASA)
TROIS_CLES = {
    'WHATSAPP_CLOUD_ACCESS_TOKEN': 'jeton-test',
    'WHATSAPP_CLOUD_PHONE_NUMBER_ID': '1234567890',
    'WHATSAPP_ACK_TEMPLATE': 'accuse_reception',
}


@override_settings(**TROIS_CLES, WHATSAPP_CLOUD_COMPANY_ID=None)
class AccuseHorsHeuresTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Accusé Co', slug='accuse-co')
        patcheur = mock.patch('apps.adsengine.whatsapp_ack.httpx.post')
        self.post = patcheur.start()
        self.addCleanup(patcheur.stop)

    def _lead(self, arrivee=SAMEDI_0310, telephone='+212612345678', **champs):
        champs.setdefault('whatsapp_opt_in', True)
        champs.setdefault('nom', 'Amina Alaoui')
        lead = Lead.objects.create(
            company=self.company, telephone=telephone, **champs)
        Lead.objects.filter(pk=lead.pk).update(date_creation=arrivee)
        lead.refresh_from_db()
        return lead

    def _emettre(self, lead, leadgen_id='lg-1', maintenant=SAMEDI_0310):
        with mock.patch.object(timezone, 'now', return_value=maintenant):
            with self.captureOnCommitCallbacks(execute=True):
                meta_lead_captured.send(
                    sender='crm.meta_lead_ads_webhook', lead=lead,
                    company=self.company, leadgen_id=leadgen_id,
                    ad_id='ad1', adset_id='as1', campaign_id='', form_id='f1',
                    created_time=None, is_organic=False)

    def _notes(self, lead):
        return LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE, body=whatsapp_ack.NOTE_ACCUSE)

    def test_un_seul_accuse_pour_un_lead_opt_in_hors_heures(self):
        avec_case = self._lead()
        sans_case = self._lead(
            telephone='+212612345679', whatsapp_opt_in=False, nom='Karim')
        self._emettre(avec_case)
        self._emettre(sans_case, leadgen_id='lg-2')

        self.assertEqual(self.post.call_count, 1)
        appel = self.post.call_args
        self.assertEqual(
            appel.args[0],
            f'{whatsapp_ack.GRAPH_BASE_URL}/1234567890/messages')
        self.assertEqual(
            appel.kwargs['headers']['Authorization'], 'Bearer jeton-test')
        corps = appel.kwargs['json']
        self.assertEqual(corps['to'], '212612345678')
        self.assertEqual(corps['type'], 'template')
        self.assertEqual(corps['template']['name'], 'accuse_reception')
        self.assertEqual(
            corps['template']['components'][0]['parameters'],
            [{'type': 'text', 'text': 'Amina'}])

        self.assertEqual(self._notes(avec_case).count(), 1)
        self.assertEqual(self._notes(sans_case).count(), 0)
        relu = Lead.objects.get(pk=avec_case.pk)
        self.assertIsNone(relu.first_contacted_at)

    def test_meme_leadgen_rejoue_rien_et_lead_relu_un_seul_accuse(self):
        lead = self._lead()
        self._emettre(lead)
        self._emettre(lead)  # rejeu webhook
        cache.clear()  # le filet de la note ne dépend pas du cache
        self._emettre(Lead.objects.get(pk=lead.pk))  # pull de rattrapage
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(self._notes(lead).count(), 1)
        self.assertIsNone(Lead.objects.get(pk=lead.pk).first_contacted_at)

    def test_oppose_ou_case_absente_rien(self):
        self._emettre(self._lead(ne_plus_contacter=True))
        self._emettre(
            self._lead(telephone='+212612345670', whatsapp_opt_in=None),
            leadgen_id='lg-2')
        self.post.assert_not_called()

    def test_heures_ouvrees_rien(self):
        lead = self._lead(arrivee=MARDI_1100)
        self._emettre(lead, maintenant=MARDI_1100)
        self.post.assert_not_called()
        self.assertEqual(self._notes(lead).count(), 0)

    def test_rattrapage_en_heures_ouvrees_ou_perime_rien(self):
        """Le pull rejoue 48 h de leads : un rattrapage tardif n'accuse rien."""
        self._emettre(self._lead(), maintenant=MARDI_1100)
        tard = self._lead(telephone='+212612345670')
        self._emettre(
            tard, leadgen_id='lg-2',
            maintenant=SAMEDI_0310 + whatsapp_ack.FRAICHEUR + timedelta(minutes=1))
        self.post.assert_not_called()

    def test_deja_contacte_rien(self):
        self._emettre(self._lead(first_contacted_at=SAMEDI_0310))
        self.post.assert_not_called()

    def test_sans_prenom_exploitable_rien(self):
        """Le nom de repli du formulaire n'est jamais un prénom."""
        self._emettre(self._lead(nom='Lead Meta Ads'))
        self.post.assert_not_called()

    def test_autre_societe_que_celle_du_numero_rien(self):
        with override_settings(WHATSAPP_CLOUD_COMPANY_ID=str(self.company.pk + 1)):
            self._emettre(self._lead())
        self.post.assert_not_called()

    def test_chacune_des_trois_variables_manquante_rien(self):
        for cle in TROIS_CLES:
            with self.subTest(cle=cle), override_settings(**{cle: ''}):
                self._emettre(self._lead())
                self.post.assert_not_called()

    def test_echec_http_journalise_rien_et_ne_casse_pas_la_capture(self):
        lead = self._lead()
        self.post.side_effect = whatsapp_ack.httpx.ConnectError('injoignable')
        self._emettre(lead)  # ne lève pas
        self.assertEqual(self._notes(lead).count(), 0)
        self.post.side_effect = None
        self._emettre(lead)  # le rattrapage suivant retente
        self.assertEqual(self.post.call_count, 2)
        self.assertEqual(self._notes(lead).count(), 1)
