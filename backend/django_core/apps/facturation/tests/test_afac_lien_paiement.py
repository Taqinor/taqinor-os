"""AFAC21 (C-AFAC-017, C-AFAC-020) — le lien « Payer en ligne » est
utilisable par le client : ``pay_url`` ABSOLU vers ``/payer/<token>`` (jamais
``/api/…`` relatif ; sans base absolue, aucun lien), clé ``provider`` validée
contre la liste blanche (400 sans lien créé), ``mock_tokenized`` hors du
registre de production, ``pay_page`` à la forme de ``paiement_public.json``.

Rejoue les sondes FPAY-1 (pay_url relatif → JSON DRF), L2-C-AFAC-017
(e-mail « régler dès maintenant : /api/django/public/pay/… », QR relatif) et
FPAY-5 (mock_tokenized → 500 + lien orphelin ; 41 caractères → 500 ;
« nimporte » → 201). Services et endpoints réels ; seul l'envoi SMTP est
capturé (backend locmem de test).

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
BASE = '/api/django/ventes/factures'
CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class LienPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture, Paiement
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC21 Co', slug=f'afac21-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac21_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Lien', prenom='AFAC21',
            email=f'afac21-{_nxt()}@example.invalid')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur AFAC21',
            sku=f'AFAC21-{_nxt()}', prix_vente=Decimal('1000'),
            quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC21-{_nxt():04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), date_echeance=date.today())
        LigneFacture.objects.create(
            facture=self.facture, produit=produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('300'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lien(self, body=None):
        return self.api.post(f'{BASE}/{self.facture.id}/lien-paiement/',
                             body or {}, format='json')

    def _liens(self):
        from apps.ventes.models import PaymentLink
        return list(PaymentLink.objects.filter(facture=self.facture))

    # (1) ─────────────────────────────────────────────────────────────────
    def test_pay_url_absolu(self):
        with override_settings(PUBLIC_BASE_URL='https://erp.example.ma'):
            r = self._lien()
            self.assertEqual(r.status_code, 201, r.data)
            token = r.data['token']
            self.assertEqual(r.data['pay_url'],
                             f'https://erp.example.ma/payer/{token}')
            self.assertEqual(r.data['montant_a_payer'], '900.00')
            # Re-POST : même jeton, même URL ; un seul lien noop en attente.
            r2 = self._lien()
            self.assertEqual(r2.data['token'], token)
            self.assertEqual(r2.data['pay_url'], r.data['pay_url'])
        liens = self._liens()
        self.assertEqual(len(liens), 1)
        self.assertEqual(liens[0].provider, 'noop')
        self.assertEqual(liens[0].statut, 'en_attente')
        # Sans réglage : l'hôte de la requête, jamais un chemin relatif.
        r = self._lien()
        self.assertEqual(r.data['pay_url'],
                         f'http://testserver/payer/{token}')
        contrat = json.loads((CONTRATS / 'lien_paiement.json').read_text(
            encoding='utf-8'))
        self.assertEqual(set(r.data), set(contrat['exemple']))

    # (2) ─────────────────────────────────────────────────────────────────
    def test_provider_hors_liste_400_sans_lien(self):
        from apps.ventes.payments.providers import (
            _REGISTRY, available_providers, providers_lien_actifs,
        )
        for cle in ('mock_tokenized', 'nimporte', 'x' * 41, 12):
            with self.subTest(cle=cle):
                r = self._lien({'provider': cle})
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn('Fournisseur de paiement inconnu ou inactif',
                              r.data['detail'])
        self.assertEqual(self._liens(), [])
        self.assertNotIn('mock_tokenized', providers_lien_actifs())
        # Hors tests (TESTING faux) : le fournisseur de test disparaît.
        self.assertNotIn('mock_tokenized', _REGISTRY)
        with override_settings(TESTING=False):
            self.assertNotIn('mock_tokenized',
                             dict(available_providers()))

    # (3) ─────────────────────────────────────────────────────────────────
    def test_email_pre_echeance_jamais_relatif(self):
        from apps.ventes.email_service import send_pre_echeance_email
        with override_settings(PUBLIC_BASE_URL='https://erp.example.ma'):
            log = send_pre_echeance_email(self.facture)
            token = self._liens()[0].token
            self.assertIn(f'https://erp.example.ma/payer/{token}', log.corps)
        self.assertNotIn('/api/django/public/pay/', log.corps)
        # Sans base ni requête (cron) : l'e-mail part SANS lien.
        log = send_pre_echeance_email(self.facture)
        self.assertNotIn('/payer/', log.corps)
        self.assertNotIn('/api/', log.corps)

    def test_qr_facture_url_absolue(self):
        from apps.ventes.domain.encaissements import (
            create_payment_link, qr_svg_for_facture_pdf,
        )
        lien = create_payment_link(facture=self.facture)
        with override_settings(PUBLIC_BASE_URL='https://erp.example.ma'), \
                patch('apps.ventes.domain.encaissements.qr_svg_for') as qr:
            qr.return_value = '<svg/>'
            qr_svg_for_facture_pdf(self.facture)
            self.assertEqual(qr.call_args[0][0],
                             f'https://erp.example.ma/payer/{lien.token}')
            # CLAUSE CLIENT : QR = URL copiée à l'écran.
            r = self._lien()
            self.assertEqual(r.data['pay_url'], qr.call_args[0][0])

    # (4) ─────────────────────────────────────────────────────────────────
    def test_pay_page_forme_contrat(self):
        from apps.ventes.public.paiement_views import _company_rib
        token = self._lien().data['token']
        r = APIClient().get(f'/api/django/public/pay/{token}/')
        self.assertEqual(r.status_code, 200, r.data)
        contrat = json.loads((CONTRATS / 'paiement_public.json').read_text(
            encoding='utf-8'))
        self.assertEqual(set(r.data), set(contrat['exemple']))
        self.assertEqual(r.data['montant'], '900.00')
        self.assertEqual(r.data['rib'], _company_rib(self.company) or None)
