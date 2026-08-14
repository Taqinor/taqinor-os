"""NTMKT44 — Notifications internes sur événements marketing clés
(au-delà de l'approbation NTMKT35).

Couvre : un détracteur NPS (score <= 6) notifie le commercial du lead avec
un lien vers la fiche, un promoteur/passif ne déclenche rien, une inscription
à un événement notifie le commercial du lead résolu, no-op sans owner —
service ET endpoint (bout en bout, aucun import direct de apps.compta).
"""
from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.marketing import services as mkt_services
from apps.marketing.models import EnqueteNPS, EvenementMarketing, InscriptionEvenement
from apps.notifications.models import Notification

from testkit.base import TenantAPITestCase

User = get_user_model()


def _company(slug):
    return Company.objects.create(slug=slug, nom=slug)


class NotifierSiNpsDetracteurTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            username='commercial-nps', password='x', company=self.company)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Client Fidèle')
        self.lead = Lead.objects.create(
            company=self.company, nom='Client Fidèle', owner=self.owner,
            email='fidele@ex.ma', client=self.client_crm)

    def _enquete(self, score, client_id=None):
        return EnqueteNPS.objects.create(
            company=self.company,
            client_id=client_id or self.client_crm.id, score=score)

    def test_detracteur_notifie_le_commercial_avec_lien_vers_le_lead(self):
        enquete = self._enquete(score=3)
        enquete.commentaire = 'Service décevant'
        owner_id = mkt_services.notifier_si_nps_detracteur(enquete)
        self.assertEqual(owner_id, self.owner.id)
        notif = Notification.objects.filter(recipient=self.owner).latest('id')
        self.assertIn('Client Fidèle', notif.title)
        self.assertIn(f'/crm/leads/{self.lead.id}', notif.link)

    def test_promoteur_ou_passif_ne_declenche_rien(self):
        for score in (7, 9, 10):
            enquete = self._enquete(score=score)
            resultat = mkt_services.notifier_si_nps_detracteur(enquete)
            self.assertIsNone(resultat)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), 0)

    def test_lead_sans_owner_ne_declenche_rien(self):
        autre_client = Client.objects.create(
            company=self.company, nom='Sans owner')
        Lead.objects.create(
            company=self.company, nom='Sans owner', client=autre_client)
        enquete = self._enquete(score=2, client_id=autre_client.id)
        resultat = mkt_services.notifier_si_nps_detracteur(enquete)
        self.assertIsNone(resultat)


class NotifierInscriptionEvenementTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            username='commercial-evt', password='x', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect Salon', owner=self.owner)
        self.evenement = EvenementMarketing.objects.create(
            company=self.company, nom='Salon Agricole',
            date_debut=timezone.now())

    def test_inscription_avec_lead_notifie_le_commercial(self):
        inscription = InscriptionEvenement.objects.create(
            company=self.company, evenement=self.evenement,
            nom='Prospect Salon', lead_id=self.lead.id, qr_token='tok-1')
        owner_id = mkt_services.notifier_inscription_evenement(inscription)
        self.assertEqual(owner_id, self.owner.id)
        notif = Notification.objects.filter(recipient=self.owner).latest('id')
        self.assertIn(f'/crm/leads/{self.lead.id}', notif.link)

    def test_inscription_sans_lead_ne_declenche_rien(self):
        inscription = InscriptionEvenement.objects.create(
            company=self.company, evenement=self.evenement,
            nom='Anonyme', qr_token='tok-2')
        self.assertIsNone(
            mkt_services.notifier_inscription_evenement(inscription))


class InscriptionPubliqueNotifianteEndpointTests(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            username='commercial-endpoint', password='x', company=self.company)
        # Lead PRÉ-EXISTANT partageant l'email de l'inscrit -> dédup XMKT28
        # le rattache à CE lead (donc à SON commercial), déterministe.
        self.lead = Lead.objects.create(
            company=self.company, nom='Karim Existant', owner=self.owner,
            email='karim@salon.ma')
        self.evenement = EvenementMarketing.objects.create(
            company=self.company, nom='Salon Agricole',
            date_debut=timezone.now())

    def test_inscription_publique_notifie_le_commercial(self):
        res = self.client.post(
            f'/api/django/marketing/evenements-marketing/{self.evenement.id}'
            '/inscription-publique/',
            data={'nom': 'Karim Existant', 'email': 'karim@salon.ma'},
            content_type='application/json')
        self.assertEqual(res.status_code, 201, res.content)
        notif = Notification.objects.filter(recipient=self.owner).latest('id')
        self.assertIn(f'/crm/leads/{self.lead.id}', notif.link)

    def test_reponse_conserve_le_meme_contrat_que_l_original(self):
        res = self.client.post(
            f'/api/django/marketing/evenements-marketing/{self.evenement.id}'
            '/inscription-publique/',
            data={'nom': 'Anonyme'}, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('id', data)
        self.assertIn('qr_token', data)
