"""QJ-FUNNEL (fondateur 09/09/2026) — `envoi: true` sur l'action share-link.

Le dialogue « Envoyer au client » de la fiche lead (copier le lien, WhatsApp
par devis) mintait le ShareLink sans jamais marquer le devis « envoyé » : le
document restait « brouillon » et le lead restait « Contacté » — alors que la
barre WhatsApp multi-devis (U4) et l'email (QJ14) passaient déjà par
``mark_devis_sent``. Le flag ``envoi: true`` branche ce dialogue sur LE même
chemin unique : statut brouillon → envoyé, date_envoi, chatter, événement
``devis_sent`` → funnel du lead à QUOTE_SENT + plan après-devis.

Sans le flag (aperçu interne, réglages niveau/OTP/sections), rien ne change —
byte-identique au comportement d'avant.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


class TestShareLinkEnvoi(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='qjfe-co', defaults={'nom': 'QJFE Co'})[0]
        self.user = User.objects.create_user(
            username='qjfe-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Envoi', stage=stages.CONTACTED)
        self.client_obj = Client.objects.get_or_create(
            company=self.company, nom='Client QJFE')[0]
        self.devis = Devis.objects.get_or_create(
            company=self.company, reference='DEV-QJFE-1',
            defaults={'client': self.client_obj, 'lead': self.lead,
                      'taux_tva': Decimal('20')},
        )[0]
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _post(self, body):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/',
            body, format='json')

    def test_envoi_true_marque_envoye_et_avance_le_funnel(self):
        resp = self._post({'envoi': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('token', resp.data)
        self.devis.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')
        self.assertIsNotNone(self.devis.date_envoi)
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_sans_flag_rien_ne_change(self):
        resp = self._post({'niveau': 'standard'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')
        self.assertIsNone(self.devis.date_envoi)
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_envoi_idempotent_sur_devis_deja_envoye(self):
        self._post({'envoi': True})
        self.devis.refresh_from_db()
        premiere_date = self.devis.date_envoi
        resp = self._post({'envoi': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        # Jamais re-stampé, jamais dégradé (mark_devis_sent, garde U4).
        self.assertEqual(self.devis.statut, 'envoye')
        self.assertEqual(self.devis.date_envoi, premiere_date)

    def test_envoi_ne_degrade_jamais_un_devis_accepte(self):
        self.devis.statut = 'accepte'
        self.devis.save(update_fields=['statut'])
        resp = self._post({'envoi': True})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')
