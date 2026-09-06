"""AUD119 (FG51) — la preuve de livraison arrive enfin jusqu'à l'API.

Le backend capturait ``signataire``/``note_pv``/``pv`` depuis le premier jour,
mais aucun écran ne les envoyait : ``pv_livraison`` restait toujours vide,
``has_proof_of_delivery`` toujours faux, et l'avertissement « vous facturez
sans BL signé » était permanent — donc sans valeur.

Ce test verrouille la moitié SERVEUR du contrat que l'écran honore désormais
(dialogue « Livrer » → corps multipart) : le côté écran est verrouillé par
``frontend/src/pages/ventes/BonCommandeListPreuveLivraison.test.jsx``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestPreuveLivraisonBonCommande(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD119 Co', slug=f'aud119-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud119_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD119', prenom='Client',
            telephone='+212600000119')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD119-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)
        self.devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD119-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD119-{_nxt()}',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _url(self):
        return (f'/api/django/ventes/bons-commande/{self.bc.id}'
                f'/marquer-livre/')

    def test_signataire_multipart_leve_has_proof_of_delivery(self):
        """ROUGE avant le correctif : l'écran envoyait un corps VIDE."""
        resp = self.api.post(
            self._url(),
            {'signataire': 'M. Alaoui', 'note_pv': 'Réception sans réserve'},
            format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.LIVRE)
        self.assertTrue(self.bc.has_proof_of_delivery)
        self.assertEqual(self.bc.pv_livraison['signataire'], 'M. Alaoui')
        self.assertEqual(
            self.bc.pv_livraison['note'], 'Réception sans réserve')
        self.assertIn('signed_at', self.bc.pv_livraison)

    def test_sans_preuve_le_bc_se_livre_comme_avant(self):
        resp = self.api.post(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.LIVRE)
        self.assertFalse(self.bc.has_proof_of_delivery)

    def test_avertissement_de_facturation_disparait_avec_la_preuve(self):
        """L'avertissement FG51 n'est plus permanent : il répond enfin à un
        chemin produit réel."""
        self.api.post(self._url(), {'signataire': 'M. Alaoui'},
                      format='multipart')
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('warnings', resp.data)
