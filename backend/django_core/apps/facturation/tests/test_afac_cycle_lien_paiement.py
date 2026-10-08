"""AFAC23 (C-AFAC-018 + C-AFAC-023) — le cycle de vie du lien de paiement suit
celui de la facture.

  * annulation et solde (paiement, avoir, abandon) ferment les liens actifs
    par UN service `fermer_liens_paiement` ;
  * `pay_page` répond `annule` (montant 0.00) sur une facture annulée ;
  * le webhook se replie sur `montant_a_payer` (jamais le montant figé du
    lien) et ne passe le lien PAYÉ que si la facture est soldée.

Rejoue FPAY-2 (facture annulée : page « 1200.00 en_attente »), L2-C-AFAC-018
(avoir total : lien en_attente) et FPAY-8 (repli sur le montant figé, lien
payé après un paiement partiel). Endpoints réels ; seul le fournisseur est un
double enregistré dans le registre le temps du test.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_cycle_lien_paiement"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class _FournisseurDouble:
    """Fournisseur de test : confirme le paiement avec le montant configuré."""
    key = 'afac23_double'
    label = 'Double de test AFAC23'
    montant = None
    ref = ''

    def create_session(self, link, request=None):
        return {'pay_url': None, 'provider_ref': ''}

    def verify_webhook(self, link, payload):
        return {'paid': True, 'provider_ref': type(self).ref,
                'montant': type(self).montant}


class CycleLienPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Facture, LigneFacture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC23 Co', slug=f'afac23-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac23_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cycle', prenom='AFAC23',
            email=f'afac23-{_nxt()}@example.invalid')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AFAC23-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC23-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.public = APIClient()
        from apps.ventes.domain.encaissements import create_payment_link
        self.lien = create_payment_link(facture=self.facture)

    def _page(self):
        r = self.public.get(f'/api/django/public/pay/{self.lien.token}/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def _webhook(self, montant, ref=''):
        from apps.ventes.payments import providers
        from apps.ventes.models import PaymentLink
        PaymentLink.objects.filter(pk=self.lien.pk).update(
            provider=_FournisseurDouble.key)
        _FournisseurDouble.montant = montant
        _FournisseurDouble.ref = ref
        with patch.dict(providers._REGISTRY,
                        {_FournisseurDouble.key: _FournisseurDouble}):
            return self.public.post(
                f'/api/django/public/pay/{self.lien.token}/webhook/', {},
                format='json')

    def test_annuler_ferme_lien(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/annuler/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.statut, 'annule')
        page = self._page()
        self.assertEqual(page['statut'], 'annule')
        self.assertEqual(page['montant'], '0.00')
        # Rejouer l'annulation : rien de plus.
        self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/annuler/', {},
            format='json')
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.statut, 'annule')

    def test_solde_manuel_ferme_lien(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/enregistrer-paiement/',
            {'montant': '1200.00', 'mode': 'virement',
             'date_paiement': timezone.localdate().isoformat()},
            format='json')
        self.assertIn(r.status_code, (200, 201), r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, 'payee')
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.statut, 'annule')
        page = self._page()
        self.assertEqual(page['montant'], '0.00')

    def test_avoir_total_ferme_lien(self):
        r = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-avoir/',
            {'motif': 'Annulation commerciale'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.statut, 'annule')
        self.assertEqual(self._page()['montant'], '0.00')

    def test_webhook_sans_montant_paie_le_reste(self):
        from apps.ventes.models import NoteDebit, Paiement
        NoteDebit.objects.create(
            company=self.company, reference=f'ND-AFAC23-{_nxt()}',
            facture=self.facture, client=self.client_obj, statut='emise',
            motif='Complément', montant_ht=Decimal('166.67'),
            montant_tva=Decimal('33.33'), montant_ttc=Decimal('200.00'))
        r = self._webhook(None, ref='PSP-AFAC23-1')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        paiements = Paiement.objects.filter(facture=self.facture)
        self.assertEqual([p.montant for p in paiements], [Decimal('1400.00')])
        self.facture.refresh_from_db()
        self.lien.refresh_from_db()
        self.assertEqual(self.facture.statut, 'payee')
        self.assertEqual(self.lien.statut, 'paye')
        # Rejouer : aucun second paiement.
        self._webhook(None, ref='PSP-AFAC23-1')
        self.assertEqual(Paiement.objects.filter(
            facture=self.facture).count(), 1)

    def test_webhook_partiel_lien_reste_ouvert(self):
        from apps.ventes.models import Paiement
        r = self._webhook('500', ref='PSP-AFAC23-2')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        self.assertEqual(
            [p.montant for p in Paiement.objects.filter(facture=self.facture)],
            [Decimal('500.00')])
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.statut, 'en_attente')
        page = self._page()
        self.assertFalse(page['paye'])
        self.assertEqual(page['montant'], '700.00')
        # Rejeu de la MÊME confirmation partielle : pas de second paiement.
        self._webhook('500', ref='PSP-AFAC23-2')
        self.assertEqual(Paiement.objects.filter(
            facture=self.facture).count(), 1)
