"""U4 — Partager un devis par WhatsApp le marque « envoyé » et fait avancer le
funnel CRM (→ QUOTE_SENT).

Couvre, via le service ``mark_devis_sent`` (le SEUL chemin de changement de
statut, règle #4) et l'endpoint ``whatsapp-devis`` qui l'appelle :

  * brouillon → envoyé + horodatage ``date_envoi`` posé une fois ;
  * avance du lead lié vers QUOTE_SENT via l'événement ``devis_sent`` ;
  * idempotence (re-partage = no-op, pas de second horodatage/événement) ;
  * jamais de régression d'un devis déjà accepté / refusé ;
  * isolation multi-société (un devis d'une autre société n'est jamais touché).

Les noms d'étapes viennent de ``apps.crm.stages`` (STAGES.py — jamais codés en
dur, règle #2).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.services import mark_devis_sent

User = get_user_model()


def make_company(slug='u4-co', nom='U4 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestMarkDevisSentService(TestCase):
    """Le service ``mark_devis_sent`` — l'unique transition brouillon → envoyé."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')

    def _devis(self, statut=Devis.Statut.BROUILLON, lead=None):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{statut}-{id(statut)}',
            client=self.client_obj, lead=lead, statut=statut)

    def test_brouillon_flips_to_envoye_and_stamps_date(self):
        devis = self._devis()
        self.assertIsNone(devis.date_envoi)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNotNone(devis.date_envoi)

    def test_writes_chatter_entry(self):
        devis = self._devis()
        mark_devis_sent(devis=devis, user=None)
        act = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.new_value, 'Envoyé')
        self.assertEqual(act.company, self.company)

    def test_advances_linked_lead_to_quote_sent(self):
        lead = Lead.objects.create(
            company=self.company, nom='Funnel', stage=stages.NEW)
        devis = self._devis(lead=lead)
        mark_devis_sent(devis=devis, user=None)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'QUOTE_SENT')

    def test_idempotent_on_already_envoye(self):
        devis = self._devis()
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        first_stamp = devis.date_envoi
        before = DevisActivity.objects.filter(devis=devis).count()
        # Deuxième appel : aucun changement, pas de second horodatage/chatter.
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.date_envoi, first_stamp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=devis).count(), before)

    def test_never_downgrades_accepted_devis(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNone(devis.date_envoi)

    def test_never_downgrades_refused_devis(self):
        devis = self._devis(statut=Devis.Statut.REFUSE)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.REFUSE)

    def test_does_not_regress_lead_already_signed(self):
        # Un lead déjà SIGNED ne recule pas vers QUOTE_SENT à l'envoi.
        lead = Lead.objects.create(
            company=self.company, nom='Signed', stage='SIGNED')
        devis = self._devis(lead=lead)
        mark_devis_sent(devis=devis, user=None)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')


class TestWhatsAppDevisFlipsSent(TestCase):
    """L'endpoint ``whatsapp-devis`` marque chaque devis partagé « envoyé »."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u4_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            telephone='0612345678', stage=stages.NEW)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        self.d1 = Devis.objects.create(
            company=self.company, reference='DEV-U4-1',
            client=self.client_obj, lead=self.lead)

    def _url(self):
        return f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/'

    def test_sharing_flips_devis_to_envoye(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ENVOYE)
        self.assertIsNotNone(self.d1.date_envoi)

    def test_sharing_advances_lead_to_quote_sent(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        # Une entrée d'historique auto a tracé l'avance du funnel.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, field='stage').exists())

    def test_sharing_does_not_regress_accepted_devis(self):
        self.d1.statut = Devis.Statut.ACCEPTE
        self.d1.save(update_fields=['statut'])
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ACCEPTE)

    def test_resharing_is_idempotent(self):
        self.api.post(self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.d1.refresh_from_db()
        first_stamp = self.d1.date_envoi
        before = DevisActivity.objects.filter(devis=self.d1).count()
        self.api.post(self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.date_envoi, first_stamp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=self.d1).count(), before)


class TestCrossTenantIsolation(TestCase):
    """Un devis d'une autre société n'est jamais marqué envoyé via ce chemin."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u4_iso', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Local', telephone='0612345678')

        self.other = make_company('u4-other', 'Other Co')
        self.other_client = Client.objects.create(
            company=self.other, nom='Foreign')
        self.foreign_devis = Devis.objects.create(
            company=self.other, reference='DEV-FOR-1',
            client=self.other_client, statut=Devis.Statut.BROUILLON)

    def test_foreign_devis_id_is_rejected_and_untouched(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/',
            {'devis_ids': [self.foreign_devis.id]}, format='json')
        # L'endpoint refuse un devis hors société/hors lead (400) — et surtout
        # le devis étranger n'est PAS passé à « envoyé ».
        self.assertEqual(resp.status_code, 400)
        self.foreign_devis.refresh_from_db()
        self.assertEqual(self.foreign_devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(self.foreign_devis.date_envoi)
