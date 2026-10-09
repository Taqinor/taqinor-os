"""ACRM15 (C-ACRM-010) — la file WhatsApp en masse passe par les GARDES et
la discipline de rendu des relances.

Sonde V_VC LSVC3-3 : « Préparer WhatsApp » sur une sélection rendait un
message au lead « ne plus contacter » (count 1), et le gabarit « Réservez
votre visite : {lien_rdv} » partait avec un blanc final. Désormais : les
leads opposés, perdus ou archivés sortent dans ``skipped`` avec leur motif,
aucun lien de réservation n'est créé pour eux, et une phrase dont le
placeholder n'a pas de valeur réelle est OMISE.

POST réel de la vue ``bulk`` ; aucun mock.
"""
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import BookingLink, Lead, MessageTemplate

User = get_user_model()
URL = '/api/django/crm/leads/bulk/'


class BulkWhatsappGardesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM15 Solaire', slug='acrm15-bulk')
        self.user = User.objects.create_user(
            username='acrm15-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.a = Lead.objects.create(
            company=self.company, nom='Oppose', prenom='A', owner=self.user,
            telephone='+212661151501', ne_plus_contacter=True)
        self.b = Lead.objects.create(
            company=self.company, nom='Perdu', prenom='B', owner=self.user,
            telephone='+212661151502', perdu=True, is_archived=True)
        self.c = Lead.objects.create(
            company=self.company, nom='Normal', prenom='C', owner=self.user,
            telephone='+212661151503')
        self.tpl = MessageTemplate.objects.create(
            company=self.company, nom='RDV', langue='fr',
            corps='Bonjour {prenom}. Réservez votre visite : {lien_rdv}')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))

    def _preparer(self):
        resp = self.api.post(URL, {
            'action': 'prepare_whatsapp',
            'ids': [self.a.pk, self.b.pk, self.c.pk],
            'template_id': self.tpl.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data

    def test_oppose_exclu(self):
        data = self._preparer()
        self.assertEqual([q['lead_id'] for q in data['queue']], [self.c.pk])
        motifs = {s['id']: s['reason'] for s in data['skipped']}
        self.assertEqual(motifs.get(self.a.pk), 'ne plus contacter')
        self.assertFalse(BookingLink.objects.filter(lead=self.a).exists())

    def test_perdu_archive_exclu(self):
        data = self._preparer()
        motifs = {s['id']: s['reason'] for s in data['skipped']}
        self.assertEqual(motifs.get(self.b.pk), 'perdu/archivé')
        self.assertFalse(BookingLink.objects.filter(lead=self.b).exists())

    def test_phrase_lien_vide_omise(self):
        data = self._preparer()
        [ligne] = data['queue']
        texte = unquote(ligne['wa_url'].split('text=', 1)[-1])
        self.assertIn('Bonjour C', texte)
        if 'Réservez votre visite' in texte:
            # Le lien existe : il suit la phrase.
            self.assertRegex(texte, r'Réservez votre visite : \S+')
        self.assertFalse(texte.rstrip().endswith(':'))
