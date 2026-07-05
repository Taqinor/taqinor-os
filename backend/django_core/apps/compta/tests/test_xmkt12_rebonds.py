"""XMKT12 — Gestion des rebonds hard/soft.

Couvre : un hard bounce supprime immédiatement, un soft répété (>= seuil)
finit supprimé, la raison est visible sur la trace du destinataire, une
plainte spam supprime immédiatement, no-op sur destinataire inconnu, payloads
webhook simulés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, EnvoiCampagne, RebondSoft

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RebondsTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt12', 'XMKT12')

    def test_hard_bounce_supprime_immediatement(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['bad@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='bad@x.ma',
            evenement='bounce', bounce_type='hard',
            raison_smtp='550 mailbox not found')
        self.assertTrue(services.est_supprime(self.co, 'bad@x.ma'))
        envoi = EnvoiCampagne.objects.get(campagne=camp, destinataire='bad@x.ma')
        self.assertEqual(envoi.raison_smtp, '550 mailbox not found')

    def test_soft_bounce_repete_finit_supprime(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['soft@x.ma'])
        for _ in range(2):
            services.webhook_brevo_evenement(
                self.co, campagne_id=camp.id, destinataire='soft@x.ma',
                evenement='bounce', bounce_type='soft')
        self.assertFalse(services.est_supprime(self.co, 'soft@x.ma'))
        self.assertEqual(
            RebondSoft.objects.get(
                company=self.co, destinataire='soft@x.ma').compte, 2)
        # 3e rebond soft : atteint le seuil par défaut (3) → supprimé.
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='soft@x.ma',
            evenement='bounce', bounce_type='soft')
        self.assertTrue(services.est_supprime(self.co, 'soft@x.ma'))

    def test_seuil_soft_configurable(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['soft2@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='soft2@x.ma',
            evenement='bounce', bounce_type='soft', max_rebonds_soft=1)
        self.assertTrue(services.est_supprime(self.co, 'soft2@x.ma'))

    def test_plainte_spam_supprime_immediatement(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['spam@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='spam@x.ma',
            evenement='complaint')
        self.assertTrue(services.est_supprime(self.co, 'spam@x.ma'))

    def test_no_op_sur_destinataire_inconnu(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        result = services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='inconnu@x.ma',
            evenement='bounce', bounce_type='hard')
        self.assertIsNone(result)
        self.assertFalse(services.est_supprime(self.co, 'inconnu@x.ma'))

    def test_webhook_endpoint_payload_hard_bounce(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['hard@x.ma'])
        api = APIClient()
        resp = api.post('/api/django/compta/webhooks/brevo/', {
            'campagne_id': camp.id, 'destinataire': 'hard@x.ma',
            'event': 'bounce', 'bounce_type': 'hard',
            'reason': '550 permanent failure',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(services.est_supprime(self.co, 'hard@x.ma'))

    def test_isolation_multi_tenant_compteur_soft(self):
        other = make_company('xmkt12-b', 'XMKT12-B')
        camp_a = Campagne.objects.create(
            company=self.co, nom='A', canal=Campagne.Canal.EMAIL)
        camp_b = Campagne.objects.create(
            company=other, nom='B', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp_a, destinataires=['shared@x.ma'])
        services.envoyer_campagne(camp_b, destinataires=['shared@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp_a.id, destinataire='shared@x.ma',
            evenement='bounce', bounce_type='soft')
        self.assertEqual(
            RebondSoft.objects.get(
                company=self.co, destinataire='shared@x.ma').compte, 1)
        self.assertFalse(
            RebondSoft.objects.filter(
                company=other, destinataire='shared@x.ma').exists())
