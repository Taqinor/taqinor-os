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
    build_devis_whatsapp, build_single_devis_whatsapp, devis_recipient_phone,
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
        # ADVS42 — le lien vise la page, plus le PDF brut.
        self.assertIn('/proposition/', resp.data['url'])
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

    def test_no_phone_409_keeps_status(self):
        client_no_phone = Client.objects.create(
            company=self.company, nom='SansTel')
        devis = self._devis(client=client_no_phone)
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 409)
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

    def test_numero_du_lead_prime_sur_le_client(self):
        """AMSG33 — lead (WhatsApp A) lié à un client (téléphone B) : l'aperçu
        vise A ; lead sans numéro ou devis sans lead : téléphone du client."""
        client_b = Client.objects.create(
            company=self.company, nom='ClientB', telephone='+212600000002')
        lead_a = Lead.objects.create(
            company=self.company, nom='LeadA', whatsapp='+212600000001')
        devis = self._devis(client=client_b, lead=lead_a)
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/whatsapp-preview/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['phone'], '+212600000001')
        sans_num = Lead.objects.create(company=self.company, nom='SansNum')
        self.assertEqual(devis_recipient_phone(
            self._devis(client=client_b, lead=sans_num)), '+212600000002')
        self.assertEqual(devis_recipient_phone(
            self._devis(client=client_b)), '+212600000002')

    def test_lead_perdu_ou_archive_tout_envoi_409(self):
        """AMSG35 (D-ACVI-7) — devis d'un lead perdu ou archivé : les gestes
        d'envoi répondent 409 nommé, 0 mail, 0 lien, brouillon ; témoin
        contactable inchangé."""
        from django.core import mail
        from apps.ventes.domain.envoi import MOTIF_LEAD_PERDU_ARCHIVE
        self.client_obj.email = 'idrissi@example.com'
        self.client_obj.save(update_fields=['email'])
        perdu = Lead.objects.create(company=self.company, nom='Perdu', perdu=True)
        archive = Lead.objects.create(
            company=self.company, nom='Archive', is_archived=True)
        gestes = [('whatsapp-preview/', {}), ('whatsapp/', {}), ('envoyer-email/', {}),
                  ('share-link/', {'envoi': True}), ('pdf-partage/', {}), ('pdf-partage/', None)]
        for lead in (perdu, archive):
            devis = self._devis(lead=lead)
            base = f'/api/django/ventes/devis/{devis.id}/'
            for chemin, corps in gestes:
                with self.subTest(lead=lead.nom, chemin=chemin, get=corps is None):
                    resp = (self.api.get(base + chemin) if corps is None
                            else self.api.post(base + chemin, corps, format='json'))
                    self.assertEqual(resp.status_code, 409, resp.content)
                    self.assertEqual(str(resp.data['detail']), MOTIF_LEAD_PERDU_ARCHIVE)
            devis.refresh_from_db()
            self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
            self.assertIsNone(devis.date_envoi)
            self.assertFalse(ShareLink.objects.filter(devis=devis).exists())
        self.assertEqual(len(mail.outbox), 0)
        temoin = self._devis(lead=self.lead)
        resp = self.api.post(
            f'/api/django/ventes/devis/{temoin.id}/whatsapp-preview/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_lead_oppose_tout_envoi_409(self):
        """ACVI102 (D-ACVI-7) — les six gestes d'envoi d'un devis de lead opposé :
        409 nommé, 0 mail, 0 EmailLog, brouillon ; déjà envoyé : 409 aussi."""
        from django.core import mail
        from apps.crm.selectors import MOTIF_CONTACT_REFUSE
        from apps.ventes.models import EmailLog
        self.client_obj.email = 'idrissi@example.com'
        self.client_obj.save(update_fields=['email'])
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        devis = self._devis(lead=self.lead)
        base = f'/api/django/ventes/devis/{devis.id}/'
        gestes = [('whatsapp-preview/', {}), ('whatsapp/', {}), ('envoyer-email/', {}),
                  ('share-link/', {'envoi': True}), ('pdf-partage/', {}), ('pdf-partage/', None)]
        for chemin, corps in gestes:
            with self.subTest(chemin=chemin, get=corps is None):
                resp = (self.api.get(base + chemin) if corps is None
                        else self.api.post(base + chemin, corps, format='json'))
                self.assertEqual(resp.status_code, 409, resp.content)
                self.assertEqual(str(resp.data['detail']), MOTIF_CONTACT_REFUSE)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(devis.date_envoi)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailLog.objects.filter(devis=devis).count(), 0)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        self.assertEqual(self._post(devis).status_code, 409)

    def test_lead_oppose_refus_sans_lien_ni_gamme(self):
        """ACVI112 — e-mail et lien d'envoi d'un devis de lead opposé : 409
        AVANT tout effet — 0 ShareLink, mode de gamme jamais appliqué, 0 mail."""
        from unittest import mock
        from django.core import mail
        from apps.crm.selectors import MOTIF_CONTACT_REFUSE
        from apps.ventes.models import ShareLink
        self.client_obj.email = 'idrissi@example.com'
        self.client_obj.save(update_fields=['email'])
        self.lead.ne_plus_contacter = True
        self.lead.save(update_fields=['ne_plus_contacter'])
        devis = self._devis(lead=self.lead)
        base = f'/api/django/ventes/devis/{devis.id}/'
        with mock.patch('apps.ventes.views.devis_envoi._appliquer_gamme_envoi') as gamme:
            for chemin, corps in (('envoyer-email/', {}), ('share-link/', {'envoi': True})):
                with self.subTest(chemin=chemin):
                    resp = self.api.post(base + chemin, corps, format='json')
                    self.assertEqual(resp.status_code, 409, resp.content)
                    self.assertEqual(str(resp.data['detail']), MOTIF_CONTACT_REFUSE)
        gamme.assert_not_called()
        self.assertEqual(ShareLink.objects.filter(devis=devis).count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        devis.refresh_from_db()
        self.assertEqual((devis.statut, devis.date_envoi), (Devis.Statut.BROUILLON, None))


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

    def test_lien_vise_la_page_proposition(self):
        # ADVS42 — la page (code d'accès, sections, signer), jamais le PDF brut.
        rf = RequestFactory().get('/')
        message, link = build_single_devis_whatsapp(rf, self.devis, 'fr')
        self.assertIn('/proposition/%s' % link['token'], link['url'])
        self.assertIn(link['url'], message)
        self.assertNotIn('/public/document/', message)
        # Même jeton, et voie lead (CRM) : même lien.
        lead = Lead.objects.create(company=self.company, nom='Naciri')
        message_lead, liens = build_devis_whatsapp(rf, lead, [self.devis], 'fr')
        self.assertEqual(liens[0]['token'], link['token'])
        self.assertEqual(liens[0]['url'], link['url'])
        self.assertNotIn('/public/document/', message_lead)

    def test_lien_rdv_resolu_pour_un_devis_de_lead(self):
        """APAR84 (C-APAR-VER-030) — ``{lien_rdv}`` du modèle « devis
        unique » est résolu (lien de réservation du lead), comme la voie lead ;
        sans lead : vide, jamais l'accolade littérale."""
        from apps.crm.models import BookingLink
        from apps.parametres.models import MessageTemplate
        MessageTemplate.objects.create(
            company=self.company, cle='devis_unique',
            corps_fr='Devis {reference} : {lien} Prenez RDV : {lien_rdv}')
        rf = RequestFactory().get('/')
        message, _link = build_single_devis_whatsapp(rf, self.devis, 'fr')
        self.assertNotIn('{lien_rdv}', message)
        self.assertTrue(message.rstrip().endswith('Prenez RDV :'))
        self.assertEqual(BookingLink.objects.count(), 0)
        lead = Lead.objects.create(company=self.company, nom='Naciri',
                                   prenom='Sara', stage=stages.NEW)
        Devis.objects.filter(pk=self.devis.pk).update(lead=lead)
        self.devis.refresh_from_db()
        message, _link = build_single_devis_whatsapp(rf, self.devis, 'fr')
        self.assertNotIn('{lien_rdv}', message)
        booking = BookingLink.objects.get()
        self.assertEqual(booking.lead_id, lead.pk)
        self.assertIn(booking.token, message)

    def test_expiry_and_reuse_of_link(self):
        rf = RequestFactory().get('/')
        _, link1 = build_single_devis_whatsapp(rf, self.devis, 'fr')
        _, link2 = build_single_devis_whatsapp(rf, self.devis, 'fr')
        # Un lien encore valide est réutilisé, pas dupliqué.
        self.assertEqual(link1['token'], link2['token'])
        share = ShareLink.objects.get(token=link1['token'])
        self.assertTrue(share.is_valid)
        self.assertGreater(share.expires_at, timezone.now())
