"""ATOT8 (C-ATOT-006) — le statut de paiement d'une facture se DÉRIVE de son
reste dû par un service unique `recalculer_statut_paiement`, appelé après
création et annulation d'avoir : « payée » si et seulement si
`montant_du` ≤ 0.

Rejoue la sonde V1 TFAC-6 : aujourd'hui une facture payée grâce à un avoir
reste `payee` avec 30 000 dus quand l'avoir est annulé, et une facture que
l'avoir solde reste `emise` avec 0 dû. Endpoints réels, aucun mock (le
récepteur de test ne fait que COMPTER `facture_payee`).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_statut_derive"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class StatutDeriveTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT8 Co', slug=f'atot8-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Statut', prenom='ATOT8',
            email=f'atot8-{_nxt()}@example.invalid')
        self.admin = User.objects.create_user(
            username=f'atot8_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Remise ATOT8', sku=f'ATOT8-{_nxt()}',
            prix_vente=Decimal('0'), quantite_stock=0)
        # La ligne produit du devis porte son produit du catalogue
        # (`LigneFacture.produit` est NOT NULL : sans lui, facturer-complet → 500).
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT8', sku=f'ATOT8K-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.payees = []
        from core.events import facture_payee

        def _compter(sender, instance=None, **kwargs):
            self.payees.append(instance.pk)
        self._recepteur = _compter
        facture_payee.connect(_compter, weak=False)
        self.addCleanup(facture_payee.disconnect, _compter)

    def _facture(self, paiements=()):
        from apps.ventes.models import Devis, Facture, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT8-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': [
                {'montant': m, 'date_paiement': date.today().isoformat(),
                 'mode_paiement': 'virement'} for m in paiements]},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['facture_id'])

    def _avoir(self, facture, ht='25000'):
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'lignes': [{'designation': 'Avoir partiel', 'quantite': '1',
                         'prix_unitaire': ht, 'taux_tva': '20',
                         'produit': self.produit.id}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def test_avoir_qui_solde_passe_payee(self):
        from apps.ventes.models import Facture
        facture = self._facture(paiements=['120000'])
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.montant_du, Decimal('30000.00'))
        self._avoir(facture)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertEqual(self.payees.count(facture.pk), 1)
        # Rejouer le recalcul : aucun second événement.
        from apps.ventes.domain.encaissements import recalculer_statut_paiement
        recalculer_statut_paiement(facture)
        self.assertEqual(self.payees.count(facture.pk), 1)

    def test_annuler_avoir_rouvre_payee(self):
        from apps.ventes.models import Facture
        facture = self._facture()
        avoir_id = self._avoir(facture)
        from apps.ventes.domain.encaissements import encaisser_sur_facture
        encaisser_sur_facture(
            facture=Facture.objects.get(pk=facture.pk),
            donnees={'montant': Decimal('120000.00'),
                     'date_paiement': date.today(), 'mode': 'virement',
                     'reference': ''},
            user=self.admin)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        r = self.api.post(f'/api/django/ventes/avoirs/{avoir_id}/annuler/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture = Facture.objects.get(pk=facture.pk)
        self.assertIn(facture.statut,
                      (Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
        self.assertEqual(facture.montant_du, Decimal('30000.00'))
