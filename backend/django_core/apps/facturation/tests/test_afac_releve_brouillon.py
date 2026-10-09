"""AFAC40 (C-AFAC-032) — une facture BROUILLON n'existe pas pour le client :
ni le relevé de compte (écran, PDF, portail), ni la balance âgée du portail,
ni l'envoi mensuel automatique ne la comptent. UNE définition
(``recouvrement.STATUTS_HORS_RELEVE``) sert ``_releve_data`` et le portail.

Rejoue les sondes FDOC-1 / L2-C-AFAC-032 (`du = 1800.00` avec la ligne
« Brouillon », `solde_courant 1800.00`, un envoi « Relevé de compte » pour le
client au brouillon seul). APIClient + beat réel, e-mail locmem, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_releve_brouillon"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ReleveSansBrouillonTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC40 Co', slug=f'afac40-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac40_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_a = self._client('a')
        self._facture(self.client_a, 'emise', Decimal('1200'))
        self._facture(self.client_a, 'brouillon', Decimal('600'))

    def _client(self, suffixe):
        from apps.crm.models import Client
        return Client.objects.create(
            company=self.company, nom=f'Releve {suffixe}', prenom='AFAC40',
            email=f'afac40-{suffixe}-{_nxt()}@example.invalid',
            releve_mensuel_auto=True)

    def _facture(self, client, statut, ttc):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC40-{_nxt():04d}',
            client=client, statut=statut, taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def test_releve_exclut_brouillon(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_a.id}/releve/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['totaux']['du'], '1200.00')
        self.assertEqual(len(r.data['lignes']), 1)
        self.assertNotIn('Brouillon', [li['statut'] for li in r.data['lignes']])
        # CLAUSE PERSISTANCE : relecture identique.
        r2 = self.api.get(
            f'/api/django/ventes/clients/{self.client_a.id}/releve/')
        self.assertEqual(r2.data['totaux'], r.data['totaux'])

    def test_portail_solde_et_balance_sans_brouillon(self):
        from apps.ventes.selectors_facturation import releve_client_portail
        data = releve_client_portail(self.client_a)
        self.assertEqual(data['solde_courant'], '1200.00')
        total_balance = sum(Decimal(v) for v in data['balance_agee'].values())
        self.assertEqual(total_balance, Decimal('1200.00'))

    def test_releve_mensuel_brouillon_seul_aucun_envoi(self):
        from django.core import mail
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import releve_mensuel_reminders
        client_b = self._client('b')
        self._facture(client_b, 'brouillon', Decimal('600'))
        releve_mensuel_reminders()
        self.assertFalse(EmailLog.objects.filter(client=client_b).exists())
        destinataires = [d for m in mail.outbox for d in m.to]
        self.assertNotIn(client_b.email, destinataires)
        # CLAUSE PERSISTANCE : un second passage n'envoie toujours rien.
        releve_mensuel_reminders()
        self.assertFalse(EmailLog.objects.filter(client=client_b).exists())
