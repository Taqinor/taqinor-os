"""AUD117 — la facture d'un BC naît dans la société DU BON DE COMMANDE.

``creer_facture`` posait ``company = request.user.company`` puis créait la
Facture avec cette valeur, sans jamais la comparer à ``bc.company`` ; et
``_company_qs`` laisse passer TOUS les BC quand ``user.company_id`` est vide et
``user.is_superuser`` est vrai. La règle maison (company forcée côté serveur,
jamais issue de la requête) était bien respectée — mais la valeur venait du
MAUVAIS objet serveur.

Même faille conditionnelle dans ``perform_create`` : la validation cross-tenant
client/devis ERR13 était enveloppée dans ``if company is not None:``, donc
inactive pour ce même profil — exactement celui contre lequel elle protège.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestFactureSocieteDuBonCommande(TestCase):
    def setUp(self):
        self.a = Company.objects.create(
            nom='AUD117 A', slug=f'aud117a-{_nxt()}')
        self.b = Company.objects.create(
            nom='AUD117 B', slug=f'aud117b-{_nxt()}')
        # Superutilisateur SANS société : le profil que `_company_qs` laisse
        # voir tous les tenants.
        self.root = User.objects.create_superuser(
            username=f'aud117root_{_nxt()}', password='x', email='')
        self.root.company = None
        self.root.role_legacy = 'admin'
        self.root.save()
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.root)}')

        self.client_a = Client.objects.create(
            company=self.a, nom='A', prenom='Client',
            telephone='+212600000118')
        self.client_b = Client.objects.create(
            company=self.b, nom='B', prenom='Client',
            telephone='+212600000119')
        self.produit_a = Produit.objects.create(
            company=self.a, nom='Kit', sku=f'AUD117-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=50)
        self.devis_a = Devis.objects.create(
            company=self.a, client=self.client_a,
            reference=f'DEV-AUD117-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis_a, produit=self.produit_a, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        self.bc_a = BonCommande.objects.create(
            company=self.a, reference=f'BC-AUD117-{_nxt()}',
            devis=self.devis_a, client=self.client_a,
            statut=BonCommande.Statut.CONFIRME)

    def test_facture_prend_la_societe_du_bc(self):
        """ROUGE avant le correctif : company NULL (celle du superutilisateur)."""
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc_a.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(bon_commande=self.bc_a)
        self.assertEqual(facture.company_id, self.a.id)

    def test_perform_create_refuse_un_client_d_une_autre_societe(self):
        """ROUGE avant le correctif : la garde ERR13 était désactivée pour ce
        profil (elle vivait dans `if company is not None`)."""
        resp = self.api.post(
            '/api/django/ventes/bons-commande/',
            {'client': self.client_b.id, 'devis': self.devis_a.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('client', resp.data)

    def test_bc_sans_societe_refuse_la_facturation(self):
        bc = BonCommande.objects.create(
            company=None, reference=f'BC-AUD117-{_nxt()}',
            devis=None, client=self.client_a,
            statut=BonCommande.Statut.CONFIRME)
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Facture.objects.filter(bon_commande=bc).exists())
