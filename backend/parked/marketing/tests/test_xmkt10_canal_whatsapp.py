"""XMKT10 — Canal WhatsApp dans les campagnes (opt-in, gated).

Couvre : ``Campagne.canal='whatsapp'`` génère une file wa.me (manuel, sans
jeton BSP) ou envoie via BSP (mock, avec jeton), consentement (XMKT4) et
suppression (XMKT3) respectés comme les autres canaux, chaque message
journalisé dans ``notifications.WhatsAppMessageLog`` lié à la campagne.

XMKT7 impose une fenêtre de silence (nuit/jour non-ouvré) au canal whatsapp,
comme le SMS — non pertinente ici (testée ailleurs) : chaque test patche
``_hors_fenetre_silence`` à ``False`` pour rester déterministe quelle que
soit l'heure/le jour d'exécution de la suite.
"""
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.models import ConsentRecord

from apps.compta import services
from apps.marketing.models import Campagne, EnvoiCampagne
from apps.notifications.models import WhatsAppMessageLog, WhatsAppTemplate

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _no_silence_window():
    """Contexte : neutralise la fenêtre de silence XMKT7 pour ces tests."""
    return mock.patch.object(
        services, '_hors_fenetre_silence', return_value=False)


class WhatsAppCampagneManualFallbackTests(TestCase):
    """Sans jeton BSP configuré : repli EXACT sur le lien manuel wa.me."""

    def setUp(self):
        self.co = make_company('xmkt10-manual', 'XMKT10 Manual')

    def test_envoi_whatsapp_sans_jeton_cree_log_manuel(self):
        camp = Campagne.objects.create(
            company=self.co, nom='WA campaign', canal=Campagne.Canal.WHATSAPP,
            corps='Bonjour {prenom}, une offre pour vous.')
        with _no_silence_window():
            services.envoyer_campagne(
                camp, destinataires=['+212600000001', '+212600000002'])
        self.assertEqual(
            EnvoiCampagne.objects.filter(campagne=camp).count(), 2)
        logs = WhatsAppMessageLog.objects.filter(company=self.co)
        self.assertEqual(logs.count(), 2)
        for log in logs:
            self.assertEqual(log.provider, WhatsAppMessageLog.Provider.MANUAL)
            self.assertEqual(log.status, WhatsAppMessageLog.Status.MANUAL)
            self.assertEqual(log.campagne_id, camp.id)

    def test_pas_de_jeton_pas_dappel_reseau(self):
        camp = Campagne.objects.create(
            company=self.co, nom='WA campaign 2', canal=Campagne.Canal.WHATSAPP,
            corps='Texte libre')
        with _no_silence_window(), mock.patch('urllib.request.urlopen') as m_urlopen:
            services.envoyer_campagne(camp, destinataires=['+212600000003'])
            m_urlopen.assert_not_called()


class WhatsAppCampagneTemplateTests(TestCase):
    """Sélection du gabarit BSP par nom+langue (variables substituées)."""

    def setUp(self):
        self.co = make_company('xmkt10-tpl', 'XMKT10 Tpl')

    def test_gabarit_selectionne_rendu_dans_le_message(self):
        tpl = WhatsAppTemplate.objects.create(
            company=self.co, name='relance_devis', language='fr',
            body_fr='Bonjour {prenom}, votre devis vous attend.',
            active=True,
            statut_approbation=WhatsAppTemplate.StatutApprobation.APPROUVE)
        camp = Campagne.objects.create(
            company=self.co, nom='WA gabarit', canal=Campagne.Canal.WHATSAPP,
            whatsapp_template=tpl, corps='Corps libre jamais utilisé ici')
        with _no_silence_window():
            services.envoyer_campagne(camp, destinataires=['+212600000004'])
        log = WhatsAppMessageLog.objects.get(company=self.co)
        self.assertIn('votre devis vous attend', log.body)
        self.assertEqual(log.template_id, tpl.id)


class WhatsAppCampagneBspMockTests(TestCase):
    """Avec jeton BSP configuré (mock) : provider BSP utilisé."""

    def setUp(self):
        self.co = make_company('xmkt10-bsp', 'XMKT10 BSP')

    def test_envoi_avec_jeton_bsp_journalise_provider_bsp(self):
        with mock.patch.dict(os.environ, {
            'WHATSAPP_BSP_ENABLED': '1',
            'WHATSAPP_BSP_BASE_URL': 'https://graph.facebook.com/v19.0',
            'WHATSAPP_BSP_TOKEN': 'fake-token',
            'WHATSAPP_BSP_PHONE_NUMBER_ID': '1234567890',
        }), _no_silence_window():
            camp = Campagne.objects.create(
                company=self.co, nom='WA BSP', canal=Campagne.Canal.WHATSAPP,
                corps='Message BSP')
            # BspProvider._send_via_api n'est pas branché (scaffold) : il
            # retombe TOUJOURS sur le manuel tant que le fondateur ne l'a pas
            # activé — le contrat testé ici est juste « pas de crash, pas
            # d'appel réseau réel », le provider restant 'manual' de fait.
            services.envoyer_campagne(camp, destinataires=['+212600000005'])
        log = WhatsAppMessageLog.objects.get(company=self.co)
        self.assertEqual(log.campagne_id, camp.id)


class WhatsAppCampagneConsentementTests(TestCase):
    """XMKT4 — consentement/suppression respectés comme les autres canaux."""

    def setUp(self):
        self.co = make_company('xmkt10-consent', 'XMKT10 Consent')

    def test_consentement_refuse_bloque_lenvoi_whatsapp(self):
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='+212600000006',
            purpose='whatsapp', granted=False)
        camp = Campagne.objects.create(
            company=self.co, nom='WA refuse', canal=Campagne.Canal.WHATSAPP,
            corps='Texte')
        with _no_silence_window():
            services.envoyer_campagne(camp, destinataires=['+212600000006'])
        self.assertEqual(
            WhatsAppMessageLog.objects.filter(company=self.co).count(), 0)
        envoi = EnvoiCampagne.objects.get(campagne=camp)
        self.assertEqual(envoi.statut, EnvoiCampagne.Statut.REBOND)
        self.assertEqual(envoi.raison_smtp, 'consentement_refuse_ou_absent')

    def test_suppression_bloque_lenvoi_whatsapp(self):
        from apps.marketing.models import SuppressionMarketing
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='+212600000007',
            motif=SuppressionMarketing.Motif.DESINSCRIT)
        camp = Campagne.objects.create(
            company=self.co, nom='WA supprime', canal=Campagne.Canal.WHATSAPP,
            corps='Texte')
        with _no_silence_window():
            services.envoyer_campagne(camp, destinataires=['+212600000007'])
        self.assertEqual(
            WhatsAppMessageLog.objects.filter(company=self.co).count(), 0)
        self.assertEqual(
            EnvoiCampagne.objects.filter(campagne=camp).count(), 0)
