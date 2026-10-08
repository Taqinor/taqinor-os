"""AFAC21 (C-AFAC-017 + C-AFAC-020) — le lien « Payer en ligne » est
utilisable par le client.

  * `pay_url` ABSOLU vers la page client `/payer/<token>` (jamais l'API JSON
    relative) ; sans base absolue connue, aucun lien plutôt qu'un lien cassé ;
  * clé `provider` validée contre la liste blanche des fournisseurs de lien
    (400, aucun lien créé) ; `mock_tokenized` hors du registre de production ;
  * `pay_page` sert exactement la forme de `paiement_public.json`.

Rejoue les sondes FPAY-1 (pay_url relatif vers le JSON), L2-C-AFAC-017
(e-mail et QR relatifs) et FPAY-5 (`mock_tokenized` → 500 + lien orphelin ;
41 caractères → 500 ; `nimporte` → 201). Endpoints et services réels ; seul
l'envoi d'e-mail est capturé (backend locmem de Django).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_lien_paiement"
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'
BASE = 'https://erp.example.ma'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _contrat(nom):
    return json.loads((CONTRATS / nom).read_text(encoding='utf-8'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LienPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, Paiement
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC21 Co', slug=f'afac21-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac21_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Lien', prenom='AFAC21',
            email=f'afac21-{_nxt()}@example.invalid')
        ttc = Decimal('1200')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC21-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('300'), date_paiement=date(2026, 10, 1),
            mode='virement', created_by=self.user)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lien(self, corps=None):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/lien-paiement/',
            corps or {}, format='json')

    @override_settings(PUBLIC_BASE_URL=BASE)
    def test_pay_url_absolu(self):
        from apps.ventes.models import PaymentLink
        r = self._lien()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['pay_url'], f"{BASE}/payer/{r.data['token']}")
        self.assertEqual(r.data['montant_a_payer'], '900.00')
        self.assertEqual(set(r.data), set(_contrat('lien_paiement.json')['exemple']))
        # Re-POST : même jeton, même URL ; un seul lien noop en attente.
        r2 = self._lien()
        self.assertEqual(r2.data['token'], r.data['token'])
        self.assertEqual(r2.data['pay_url'], r.data['pay_url'])
        self.assertEqual(PaymentLink.objects.filter(
            facture=self.facture, provider='noop',
            statut='en_attente').count(), 1)

    @override_settings(PUBLIC_BASE_URL='')
    def test_pay_url_sans_reglage_suit_la_requete(self):
        r = self._lien()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['pay_url'],
                         f"http://testserver/payer/{r.data['token']}")

    def test_provider_hors_liste_400_sans_lien(self):
        from apps.ventes.models import PaymentLink
        from apps.ventes.payments import providers
        for cle in ('mock_tokenized', 'nimporte', 'x' * 41):
            r = self._lien({'provider': cle})
            self.assertEqual(r.status_code, 400, (cle, r.data))
            self.assertIn('Fournisseur de paiement inconnu ou inactif',
                          r.data['detail'])
        self.assertFalse(PaymentLink.objects.filter(
            facture=self.facture).exists())
        # Hors tests, le fournisseur de TEST n'est plus exposé.
        with override_settings(TESTING=False):
            cles = [k for k, _ in providers.available_providers()]
        self.assertNotIn('mock_tokenized', cles)

    @override_settings(PUBLIC_BASE_URL='')
    def test_email_pre_echeance_jamais_relatif(self):
        from apps.ventes.email_service import send_pre_echeance_email
        with patch('apps.ventes.email_service._send',
                   return_value=(True, '')) as envoi:
            log = send_pre_echeance_email(self.facture)
        self.assertTrue(envoi.called)
        self.assertNotIn('/api/django/public/pay/', log.corps)
        self.assertNotIn('/payer/', log.corps)
        with override_settings(PUBLIC_BASE_URL=BASE):
            with patch('apps.ventes.email_service._send',
                       return_value=(True, '')):
                log = send_pre_echeance_email(self.facture)
        from apps.ventes.models import PaymentLink
        lien = PaymentLink.objects.get(facture=self.facture,
                                       statut='en_attente')
        self.assertIn(f'{BASE}/payer/{lien.token}', log.corps)

    @override_settings(PUBLIC_BASE_URL=BASE)
    def test_qr_facture_url_absolue(self):
        from apps.ventes.domain.encaissements import qr_svg_for_facture_pdf
        r = self._lien()
        self.assertEqual(r.status_code, 201, r.data)
        with patch('apps.ventes.domain.encaissements.qr_svg_for') as qr:
            qr.return_value = '<svg/>'
            qr_svg_for_facture_pdf(self.facture)
        self.assertEqual(qr.call_args[0][0], r.data['pay_url'])

    @override_settings(COMPANY_RIB='011 780 0000123456789012 34')
    def test_pay_page_forme_contrat(self):
        r = self._lien()
        pub = APIClient().get(f"/api/django/public/pay/{r.data['token']}/")
        self.assertEqual(pub.status_code, 200, pub.data)
        self.assertEqual(set(pub.data),
                         set(_contrat('paiement_public.json')['exemple']))
        self.assertEqual(pub.data['montant'], '900.00')
        self.assertEqual(pub.data['rib'], '011 780 0000123456789012 34')
        self.assertNotIn('prix_achat', pub.data)
