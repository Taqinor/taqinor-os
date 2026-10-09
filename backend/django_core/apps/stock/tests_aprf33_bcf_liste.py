"""APRF33 — la liste des BCF garde un nombre de requêtes plat (acomptes et
annonces de livraison préchargés), pour un rôle qui voit les montants d'achat
comme pour un rôle qui ne les voit pas, avec des données inchangées."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, AnnonceLivraisonFournisseur, BonCommandeFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from authentication.models import Company

User = get_user_model()
BCF = '/api/django/stock/bons-commande-fournisseur/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BcfListeRequetesPlatesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='APRF33', slug='aprf33-co')
        base = ['stock_voir', 'stock_modifier']
        self.role_voit = Role.objects.create(
            company=self.company, nom='voit',
            permissions=base + ['prix_achat_voir'])
        self.role_aveugle = Role.objects.create(
            company=self.company, nom='aveugle', permissions=base)
        self.u_voit = User.objects.create_user(
            username='aprf33-a', password='x', company=self.company,
            role=self.role_voit, role_legacy='responsable')
        self.u_aveugle = User.objects.create_user(
            username='aprf33-b', password='x', company=self.company,
            role=self.role_aveugle, role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four APRF33')
        self.produit = Produit.objects.create(
            company=self.company, nom='P', sku='APRF33-1',
            prix_vente=Decimal('100'), prix_achat=Decimal('70'),
            quantite_stock=0)
        self.n = 0

    def _bcf(self, count):
        for _ in range(count):
            self.n += 1
            bcf = BonCommandeFournisseur.objects.create(
                company=self.company, reference=f'BCF-APRF33-{self.n}',
                fournisseur=self.fournisseur)
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bcf, produit=self.produit, quantite=2,
                prix_achat_unitaire=Decimal('70'))
            for k in range(2):
                AcompteFournisseur.objects.create(
                    company=self.company, bon_commande=bcf,
                    montant=Decimal('10') + k,
                    date_versement=date(2026, 1, 1 + k))
                AnnonceLivraisonFournisseur.objects.create(
                    company=self.company, bon_commande_fournisseur=bcf,
                    date_expedition=date(2026, 2, 1 + k),
                    transporteur=f'T{k}',
                    lignes=[{'produit_id': self.produit.id,
                             'produit_nom': 'P', 'quantite': 1}])

    def _mesure(self, user):
        with CaptureQueriesContext(connection) as ctx:
            resp = _api(user).get(BCF + '?page_size=50')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        return len(ctx.captured_queries), data.get('results', data)

    def test_requetes_plates_deux_roles(self):
        self._bcf(2)
        petit = {u: self._mesure(u) for u in (self.u_voit, self.u_aveugle)}
        self._bcf(10)
        for user in (self.u_voit, self.u_aveugle):
            n2, _ = petit[user]
            n12, rows = self._mesure(user)
            self.assertEqual(
                n2, n12, f'N+1 sur la liste BCF ({user.username})')
            self.assertEqual(len(rows), 12)

    def test_donnees_et_ordre_inchanges(self):
        self._bcf(1)
        _, rows = self._mesure(self.u_voit)
        row = rows[0]
        # acomptes : tri du Meta (-date_versement) ; annonces : -date_expedition.
        self.assertEqual(
            [Decimal(a['montant']) for a in row['acomptes']],
            [Decimal('11'), Decimal('10')])
        self.assertEqual(
            [a['transporteur'] for a in row['livraisons_annoncees']],
            ['T1', 'T0'])
        self.assertTrue(all(
            a['bon_commande_reference'] == row['reference']
            for a in row['livraisons_annoncees']))
        _, rows = self._mesure(self.u_aveugle)
        self.assertNotIn('acomptes', rows[0])
        self.assertEqual(len(rows[0]['livraisons_annoncees']), 2)
