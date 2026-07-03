"""QG8 — « Envoyer » un devis = le flux WhatsApp des leads (@action devis).

Couvre :
  * construction du lien wa.me + lien tokenisé (PDF CLIENT) + message FR ;
  * le devis passe brouillon → envoyé (mark_devis_sent, funnel avance) ;
  * idempotence + AUCUNE régression accepté / refusé / expiré ;
  * destinataire résolu depuis le client, sinon depuis le lead ;
  * pas de numéro → 400 sans changer le statut ;
  * multi-société : devis d'une autre société → 404.
"""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, ShareLink
from apps.ventes.utils.whatsapp import (
    build_single_devis_whatsapp, devis_recipient_phone,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DevisWhatsappActionTests(TestCase):
    def setUp(self):
        self.company = _company('qg8-co')
        self.user = _user(self.company, 'qg8-user')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Idrissi', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', stage=stages.NEW)
        self.api = _api(self.user)

    def _devis(self, statut=Devis.Statut.BROUILLON, client=None, lead=None):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-QG8-{id(statut) % 10000}',
            client=client if client is not None else self.client_obj,
            lead=lead, statut=statut)

    def _post(self, devis, api=None):
        return (api or self.api).post(
            f'/api/django/ventes/devis/{devis.id}/whatsapp/', {}, format='json')

    def test_builds_link_and_marks_sent(self):
        devis = self._devis(lead=self.lead)
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wa.me/212612345678', resp.data['wa_url'])
        self.assertIn('/document/', resp.data['url'])
        self.assertIn('DEV-QG8', resp.data['message'])
        self.assertEqual(resp.data['devis_statut'], Devis.Statut.ENVOYE)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNotNone(devis.date_envoi)
        # Un lien public a bien été frappé pour ce devis.
        self.assertTrue(ShareLink.objects.filter(devis=devis).exists())

    def test_advances_linked_lead_to_quote_sent(self):
        devis = self._devis(lead=self.lead)
        self._post(devis)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')

    def test_idempotent_second_call_no_regression(self):
        devis = self._devis(lead=self.lead)
        self._post(devis)
        devis.refresh_from_db()
        first_date = devis.date_envoi
        self._post(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.date_envoi, first_date)  # pas de re-stamp

    def test_never_downgrades_accepte(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_never_downgrades_refuse(self):
        devis = self._devis(statut=Devis.Statut.REFUSE)
        self._post(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.REFUSE)

    def test_no_phone_400_keeps_status(self):
        client_no_phone = Client.objects.create(
            company=self.company, nom='SansTel')
        devis = self._devis(client=client_no_phone)
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 400)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_cross_company_devis_404(self):
        other = _company('qg8-autre')
        etranger = _user(other, 'qg8-etranger')
        devis = self._devis(lead=self.lead)
        resp = self._post(devis, api=_api(etranger))
        self.assertEqual(resp.status_code, 404)

    def test_phone_resolves_from_lead_when_no_client_phone(self):
        client_no_phone = Client.objects.create(
            company=self.company, nom='SansTel2')
        lead = Lead.objects.create(
            company=self.company, nom='LeadTel', whatsapp='0698765432')
        devis = self._devis(client=client_no_phone, lead=lead)
        self.assertEqual(devis_recipient_phone(devis), '0698765432')


class BuildSingleDevisWhatsappTests(TestCase):
    """Le builder pur (message + lien) — utilisé par l'action."""

    def setUp(self):
        self.company = _company('qg8-build')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Naciri', prenom='Sara',
            telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QG8-B1',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)

    def test_message_contains_reference_and_token_link(self):
        rf = RequestFactory().get('/')
        message, link = build_single_devis_whatsapp(rf, self.devis, 'fr')
        self.assertIn('DEV-QG8-B1', message)
        self.assertIn(link['token'], message)
        self.assertTrue(link['token'])

    def test_expiry_and_reuse_of_link(self):
        rf = RequestFactory().get('/')
        _, link1 = build_single_devis_whatsapp(rf, self.devis, 'fr')
        _, link2 = build_single_devis_whatsapp(rf, self.devis, 'fr')
        # Un lien encore valide est réutilisé, pas dupliqué.
        self.assertEqual(link1['token'], link2['token'])
        share = ShareLink.objects.get(token=link1['token'])
        self.assertTrue(share.is_valid)
        self.assertGreater(share.expires_at, timezone.now())
