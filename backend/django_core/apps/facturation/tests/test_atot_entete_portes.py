"""ATOT4 (C-ATOT-002) — `entete_facture_depuis_devis` porte la retenue de
garantie et la référence de commande client du devis, et il est appelé aux
quatre portes : la retenue et la réf. client suivent le devis quelle que soit
la porte (facture complète, BC, consolidée ; tranche = témoin inchangé).

Rejoue la sonde V1 TFAC-10 : aujourd'hui facture complète avec
`retenue_garantie_mad=None`, `montant_exigible=150 000`, réf. client vide.
Endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_entete_portes"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
PHRASE = 'sans effet sur la base taxable'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class EntetePortesTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT4 Co', slug=f'atot4-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Entete', prenom='ATOT4',
            email=f'atot4-{_nxt()}@example.invalid')
        # Produit de la ligne du devis : `LigneFacture.produit` est NOT NULL
        # et facturer-complet / consolider décomptent le stock.
        from apps.stock.models import Produit
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT4', sku=f'ATOT4K-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=1000)
        self.user = User.objects.create_user(
            username=f'atot4_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self):
        """Accepté, 125 000 HT @20 % = 150 000 TTC, retenue 5 %, réf.
        client BC-CLIENT-42, échéancier résidentiel 30/60/10."""
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT4-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel',
            retenue_garantie={'taux_pct': 5},
            reference_commande_client='BC-CLIENT-42')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _relire(self, pk):
        from apps.ventes.models import Facture
        return Facture.objects.get(pk=pk)

    def _assert_entete(self, facture, retenue, exigible):
        self.assertEqual(facture.retenue_garantie_mad, Decimal(retenue))
        self.assertEqual(Decimal(str(facture.montant_exigible)),
                         Decimal(exigible))
        self.assertIn('BC-CLIENT-42', facture.reference_commande_client)
        self.assertIn(PHRASE, facture.conditions_paiement)

    def test_facture_complete(self):
        devis = self._devis()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self._assert_entete(self._relire(r.data['facture_id']),
                            '7500.00', '142500.00')

    def test_facture_bc(self):
        from apps.ventes.models import BonCommande
        devis = self._devis()
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ATOT4-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = self._relire(r.data['id'])
        # La facture de BC n'est émise que par son geste dédié : le dû d'un
        # brouillon est son TTC, l'exigible en retranche la retenue.
        self.assertEqual(facture.retenue_garantie_mad, Decimal('7500.00'))
        self.assertEqual(facture.reference_commande_client, 'BC-CLIENT-42')
        self.assertIn(PHRASE, facture.conditions_paiement)

    def test_facture_consolidee(self):
        d1, d2 = self._devis(), self._devis()
        r = self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [d1.id, d2.id]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self._assert_entete(self._relire(r.data['id']),
                            '15000.00', '285000.00')

    def test_tranche_temoin_inchangee(self):
        devis = self._devis()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = self._relire(r.data['id'])
        self.assertEqual(Decimal(str(facture.total_ttc)), Decimal('45000.00'))
        self._assert_entete(facture, '2250.00', '42750.00')
