"""Feature 1 — Envoyer par WhatsApp.

Couvre : normalisation du téléphone marocain, modèles de message éditables
(FR + Darija) avec placeholders, liens publics tokenisés expirants (30 j) vers
le PDF CLIENT (jamais de prix d'achat / marge), et les endpoints qui
construisent le lien wa.me prêt à envoyer (le commercial appuie sur Envoyer).
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.parametres.models import MessageTemplate
from apps.ventes.models import Devis, Facture, ShareLink
from apps.ventes.utils.phone import normalize_ma_phone
from apps.ventes.utils.whatsapp import render_message_template

User = get_user_model()


def make_company(slug='wa-co', nom='WA Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestPhoneNormalization(TestCase):
    def test_strips_leading_zero_and_adds_morocco_code(self):
        self.assertEqual(normalize_ma_phone('0612345678'), '212612345678')

    def test_keeps_already_international(self):
        self.assertEqual(normalize_ma_phone('+212612345678'), '212612345678')

    def test_strips_spaces_dashes_brackets_and_plus(self):
        self.assertEqual(
            normalize_ma_phone(' +212 (6) 12-34-56-78 '), '212612345678')

    def test_handles_double_zero_international_prefix(self):
        self.assertEqual(normalize_ma_phone('00212612345678'), '212612345678')

    def test_local_nine_digits_without_zero(self):
        self.assertEqual(normalize_ma_phone('612345678'), '212612345678')

    def test_empty_or_none_returns_none(self):
        self.assertIsNone(normalize_ma_phone(''))
        self.assertIsNone(normalize_ma_phone(None))
        self.assertIsNone(normalize_ma_phone('   '))


class TestMessageTemplate(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_default_returned_when_no_custom_row(self):
        # Aucune ligne en base → on renvoie le défaut FR du placeholder.
        corps = MessageTemplate.get_corps(
            self.company, 'devis_unique', 'fr')
        self.assertIn('{reference}', corps)
        self.assertIn('{lien}', corps)

    def test_custom_row_overrides_default(self):
        MessageTemplate.objects.create(
            company=self.company, cle='devis_unique',
            corps_fr='Salam {nom}, ton devis {reference} : {lien}')
        corps = MessageTemplate.get_corps(
            self.company, 'devis_unique', 'fr')
        self.assertTrue(corps.startswith('Salam'))

    def test_darija_falls_back_to_fr_when_empty(self):
        MessageTemplate.objects.create(
            company=self.company, cle='facture',
            corps_fr='FR text {lien}', corps_darija='')
        corps = MessageTemplate.get_corps(self.company, 'facture', 'darija')
        self.assertEqual(corps, 'FR text {lien}')

    def test_render_substitutes_placeholders_and_collapses_spaces(self):
        # {civilite} vide ne doit pas laisser de double espace.
        out = render_message_template(
            'Bonjour {civilite} {nom}, devis {reference} : {lien}',
            {'civilite': '', 'nom': 'Dupont',
             'reference': 'DEV-1', 'lien': 'http://x/t'})
        self.assertEqual(
            out, 'Bonjour Dupont, devis DEV-1 : http://x/t')


class TestShareLink(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-WA-1',
            client=self.client_obj)

    def test_token_is_long_and_unguessable(self):
        link = ShareLink.objects.create(
            company=self.company, devis=self.devis)
        self.assertGreaterEqual(len(link.token), 32)

    def test_for_devis_reuses_valid_link(self):
        a = ShareLink.for_devis(self.devis)
        b = ShareLink.for_devis(self.devis)
        self.assertEqual(a.pk, b.pk)

    def test_for_devis_creates_new_when_expired(self):
        old = ShareLink.for_devis(self.devis)
        old.expires_at = timezone.now() - timedelta(days=1)
        old.save(update_fields=['expires_at'])
        new = ShareLink.for_devis(self.devis)
        self.assertNotEqual(old.pk, new.pk)
        self.assertTrue(new.is_valid)

    def test_default_expiry_is_about_30_days(self):
        link = ShareLink.for_devis(self.devis)
        delta = link.expires_at - timezone.now()
        self.assertGreater(delta.days, 28)
        self.assertLessEqual(delta.days, 30)


class TestPublicDocumentEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-PUB-1',
            client=self.client_obj)

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-1.4 x')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/1/DEV-PUB-1.pdf')
    def test_valid_token_serves_pdf_without_login(self, m_gen, m_dl):
        link = ShareLink.for_devis(self.devis)
        # APIClient anonyme : aucun header d'auth.
        resp = APIClient().get(f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_unknown_token_is_404(self):
        resp = APIClient().get('/api/django/public/document/nope-nope/')
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_is_404(self):
        link = ShareLink.for_devis(self.devis)
        link.expires_at = timezone.now() - timedelta(days=1)
        link.save(update_fields=['expires_at'])
        resp = APIClient().get(f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_returns_clear_french_notice(self):
        # L854 : l'avis FR invite à demander un lien frais, sans aucune donnée
        # interne (référence, montants, etc.).
        link = ShareLink.for_devis(self.devis)
        link.expires_at = timezone.now() - timedelta(days=1)
        link.save(update_fields=['expires_at'])
        resp = APIClient().get(f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 404)
        detail = resp.data['detail']
        self.assertIn('expiré', detail)
        self.assertIn('TAQINOR', detail)
        # Aucune fuite de donnée interne dans l'avis.
        self.assertNotIn(self.devis.reference, detail)

    def test_unknown_token_returns_clear_french_notice(self):
        resp = APIClient().get('/api/django/public/document/nope-nope/')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('expiré', resp.data['detail'])

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-1.4 x')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/1/DEV-PUB-1.pdf')
    def test_pdf_response_carries_noindex_header(self, m_gen, m_dl):
        # L855 : le PDF public porte X-Robots-Tag: noindex.
        link = ShareLink.for_devis(self.devis)
        resp = APIClient().get(f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('noindex', resp['X-Robots-Tag'])

    def test_error_response_carries_noindex_header(self):
        # L855 : même les réponses d'erreur publiques restent non-indexables.
        resp = APIClient().get('/api/django/public/document/nope-nope/')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('noindex', resp['X-Robots-Tag'])


class TestLeadWhatsAppEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wa_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            telephone='0612345678')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        self.d1 = Devis.objects.create(
            company=self.company, reference='DEV-L-1',
            client=self.client_obj, lead=self.lead)
        self.d2 = Devis.objects.create(
            company=self.company, reference='DEV-L-2',
            client=self.client_obj, lead=self.lead)

    def _url(self):
        return f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/'

    def test_single_devis_builds_wa_url_with_public_link(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url'].startswith(
            'https://wa.me/212612345678?text='))
        # Un lien public a bien été créé pour ce devis.
        link = ShareLink.objects.filter(devis=self.d1).first()
        self.assertIsNotNone(link)
        self.assertIn(link.token, resp.data['message'])
        self.assertIn('DEV-L-1', resp.data['message'])

    def test_multiple_devis_uses_count_and_one_line_each(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id, self.d2.id]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        msg = resp.data['message']
        self.assertIn('DEV-L-1', msg)
        self.assertIn('DEV-L-2', msg)
        self.assertIn('2', msg)  # {n}

    def test_no_phone_is_400(self):
        self.lead.telephone = ''
        self.lead.whatsapp = ''
        self.lead.save(update_fields=['telephone', 'whatsapp'])
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_empty_selection_is_400(self):
        resp = self.api.post(self._url(), {'devis_ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_other_company_devis_rejected(self):
        other = make_company('wa-other', 'Other')
        oc = Client.objects.create(company=other, nom='X')
        foreign = Devis.objects.create(
            company=other, reference='DEV-X-1', client=oc)
        resp = self.api.post(
            self._url(), {'devis_ids': [foreign.id]}, format='json')
        self.assertEqual(resp.status_code, 400)


class TestFactureWhatsAppEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wa_resp2', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Sefrioui', telephone='0655443322')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-1', client=self.client_obj)

    def _url(self):
        return f'/api/django/ventes/factures/{self.facture.id}/whatsapp/'

    def test_builds_wa_url_for_facture(self):
        resp = self.api.post(self._url(), {'modele': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url'].startswith(
            'https://wa.me/212655443322?text='))
        self.assertIn('FAC-1', resp.data['message'])
        link = ShareLink.objects.filter(facture=self.facture).first()
        self.assertIsNotNone(link)

    def test_relance_uses_reminder_template(self):
        MessageTemplate.objects.create(
            company=self.company, cle='relance',
            corps_fr='RAPPEL {reference} {lien}')
        resp = self.api.post(self._url(), {'modele': 'relance'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('RAPPEL', resp.data['message'])

    def test_no_phone_is_400(self):
        self.client_obj.telephone = ''
        self.client_obj.save(update_fields=['telephone'])
        resp = self.api.post(self._url(), {'modele': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 400)


class TestMessagesSettingsApi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='wa_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = make_api(self.admin)

    def test_list_returns_all_keys_with_defaults(self):
        resp = self.api.get('/api/django/parametres/messages/')
        self.assertEqual(resp.status_code, 200, resp.data)
        cles = {row['cle'] for row in resp.data}
        self.assertEqual(cles, {
            'devis_unique', 'devis_multi_entete', 'devis_multi_ligne',
            'facture', 'relance'})
        unique = next(r for r in resp.data if r['cle'] == 'devis_unique')
        self.assertIn('{reference}', unique['corps_fr'])
        self.assertIn('placeholders', unique)

    def test_save_persists_and_is_reflected(self):
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'corps_fr': 'FR perso {lien}',
            'corps_darija': 'DR perso {lien}'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        again = self.api.get('/api/django/parametres/messages/')
        fac = next(r for r in again.data if r['cle'] == 'facture')
        self.assertEqual(fac['corps_fr'], 'FR perso {lien}')
        self.assertEqual(fac['corps_darija'], 'DR perso {lien}')

    def test_save_blocks_limited_tier_allows_responsable(self):
        # Palier limité (Utilisateur/normal) : ne peut pas enregistrer.
        limited = User.objects.create_user(
            username='wa_user', password='x', role_legacy='normal',
            company=self.company)
        api = make_api(limited)
        resp = api.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'corps_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

        # Responsable (promu) : enregistrement autorisé.
        resp_user = User.objects.create_user(
            username='wa_resp_save', password='x', role_legacy='responsable',
            company=self.company)
        api2 = make_api(resp_user)
        ok = api2.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'corps_fr': 'ok {lien}'}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)

    def test_unknown_key_rejected(self):
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'inconnu', 'corps_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── L775 — validation des placeholders whitelistés par clé ──
    def test_unsupported_placeholder_rejected_naming_token(self):
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture',
            'corps_fr': 'Bonjour {nom}, total {montant} : {lien}'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        # L'erreur FR nomme explicitement le token fautif.
        self.assertIn('{montant}', resp.data['detail'])
        # Rien n'a été persisté.
        self.assertFalse(
            MessageTemplate.objects.filter(
                company=self.company, cle='facture').exists())

    def test_unsupported_placeholder_in_darija_rejected(self):
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'corps_fr': 'OK {lien}',
            'corps_darija': 'Salam {foo}'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('{foo}', resp.data['detail'])
        self.assertIn('Darija', resp.data['detail'])

    def test_placeholder_not_allowed_for_this_key_rejected(self):
        # {lien} n'est PAS autorisé pour devis_multi_entete.
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'devis_multi_entete',
            'corps_fr': 'Bonjour {nom}, {n} devis : {lien}'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('{lien}', resp.data['detail'])

    def test_whitelisted_placeholders_accepted(self):
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture',
            'corps_fr': 'Bonjour {civilite} {nom}, facture {reference} : {lien}'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── L776 — réinitialisation au modèle par défaut ──
    def test_reset_restores_default_and_clears_override(self):
        from apps.parametres.models import MESSAGE_TEMPLATE_DEFAULTS
        # Personnalise d'abord les deux langues.
        self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'corps_fr': 'FR perso {lien}',
            'corps_darija': 'DR perso {lien}'}, format='json')
        # Réinitialise.
        resp = self.api.put('/api/django/parametres/messages/', {
            'cle': 'facture', 'reset': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            resp.data['corps_fr'], MESSAGE_TEMPLATE_DEFAULTS['facture'])
        self.assertEqual(resp.data['corps_darija'], '')
        # Persistance vérifiée via le listing.
        again = self.api.get('/api/django/parametres/messages/')
        fac = next(r for r in again.data if r['cle'] == 'facture')
        self.assertEqual(fac['corps_fr'], MESSAGE_TEMPLATE_DEFAULTS['facture'])
        self.assertEqual(fac['corps_darija'], '')


class TestWhatsAppChatterLogging(TestCase):
    """L856 — l'action « Envoyer par WhatsApp » est consignée au chatter de
    l'enregistrement, acteur et société posés côté serveur."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='wa_log', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            telephone='0612345678')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Idrissi', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-LOG-1',
            client=self.client_obj, lead=self.lead)
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-LOG-1',
            client=self.client_obj)

    def test_lead_devis_whatsapp_writes_note_to_chatter(self):
        from apps.crm.models import LeadActivity
        before = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/',
            {'devis_ids': [self.devis.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertEqual(LeadActivity.objects.filter(
            lead=self.lead).count(), before + 1)
        last = notes.order_by('-created_at').first()
        self.assertIn('WhatsApp', last.body)
        self.assertIn('DEV-LOG-1', last.body)
        # Acteur et société posés côté serveur.
        self.assertEqual(last.user, self.user)
        self.assertEqual(last.company, self.company)

    def test_facture_whatsapp_writes_note_to_chatter(self):
        from apps.ventes.models import FactureActivity
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/whatsapp/',
            {'modele': 'facture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        act = FactureActivity.objects.filter(
            facture=self.facture, kind=FactureActivity.Kind.NOTE).first()
        self.assertIsNotNone(act)
        self.assertIn('WhatsApp', act.body)
        self.assertIn('FAC-LOG-1', act.body)
        self.assertEqual(act.user, self.user)
        self.assertEqual(act.company, self.company)

    def test_facture_relance_whatsapp_notes_reminder(self):
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/whatsapp/',
            {'modele': 'relance'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        from apps.ventes.models import FactureActivity
        act = FactureActivity.objects.filter(
            facture=self.facture, kind=FactureActivity.Kind.NOTE).first()
        self.assertIsNotNone(act)
        self.assertIn('rappel', act.body)
