"""NTRET12 — tests d'intégration : bridge ORM (services.py), API REST, et
intégration caisse réelle (apps.pos.services.promotions_applicables) contre
une vraie ``VenteComptoir`` + de vraies ``ReglexPromotion``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services as pos_services
from apps.pos.models import LigneVenteComptoir, VenteComptoir
from apps.promotions import services as promo_services
from apps.promotions.models import ReglexPromotion
from apps.stock.models import Categorie, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PromotionsServicesBridgeTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret12', 'NTRET12 Co')
        self.user = make_user(self.co, 'ntret12-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.categorie = Categorie.objects.create(company=self.co, nom='Câbles')
        self.produit = Produit.objects.create(
            company=self.co, nom='Câble 6mm²', prix_vente=Decimal('100'),
            prix_achat=Decimal('60'), quantite_stock=50, categorie=self.categorie)

    def _vente_avec_lignes(self, quantite=3, prix='100'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-PROMO-1', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=quantite, prix_unitaire_ttc=Decimal(prix))
        return vente

    def test_evaluer_panier_via_real_lignevente_comptoir(self):
        """Le pont ORM lit de VRAIES LigneVenteComptoir (pos) sans jamais
        importer apps.pos.models — duck-typing sur produit/quantite/prix."""
        vente = self._vente_avec_lignes(quantite=3, prix='100')
        ReglexPromotion.objects.create(
            company=self.co, nom='3 pour 2 câbles', type_regle='n_pour_m',
            categorie=self.categorie, n_achete=3, m_paye=2)

        remises = promo_services.evaluer_panier(self.co, vente.lignes.all())
        self.assertEqual(len(remises), 1)
        self.assertEqual(remises[0].montant, Decimal('100.00'))

    def test_no_rule_no_discount(self):
        vente = self._vente_avec_lignes()
        self.assertEqual(promo_services.evaluer_panier(self.co, vente.lignes.all()), [])

    def test_inactive_rule_ignored(self):
        vente = self._vente_avec_lignes(quantite=3)
        ReglexPromotion.objects.create(
            company=self.co, nom='Désactivée', type_regle='n_pour_m',
            categorie=self.categorie, n_achete=3, m_paye=2, actif=False)
        self.assertEqual(promo_services.evaluer_panier(self.co, vente.lignes.all()), [])

    def test_isolation_multi_tenant(self):
        co_b = make_company('ntret12-b', 'B')
        vente = self._vente_avec_lignes(quantite=3)
        # Règle créée pour une AUTRE société : jamais appliquée ici.
        ReglexPromotion.objects.create(
            company=co_b, nom='Règle société B', type_regle='n_pour_m',
            categorie=self.categorie, n_achete=3, m_paye=2)
        self.assertEqual(promo_services.evaluer_panier(self.co, vente.lignes.all()), [])


class PosIntegrationTests(TestCase):
    """Intégration caisse (apps.pos.services) — le SEUL point où apps/pos
    appelle apps/promotions (import fonction-local)."""

    def setUp(self):
        self.co = make_company('ntret12-pos', 'NTRET12 POS Co')
        self.user = make_user(self.co, 'ntret12-pos-user')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        self.categorie = Categorie.objects.create(company=self.co, nom='Onduleurs')
        self.produit = Produit.objects.create(
            company=self.co, nom='Onduleur 3kW', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=10, categorie=self.categorie)

    def test_promotions_applicables_reflects_active_rule(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-POS-PROMO', client=self.client_obj,
            created_by=self.user)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation=self.produit.nom,
            quantite=1, prix_unitaire_ttc=Decimal('1000'))
        ReglexPromotion.objects.create(
            company=self.co, nom='Remise onduleurs', type_regle='remise_pourcentage_produit',
            categorie=self.categorie, remise_pct=Decimal('10'))

        remises = pos_services.promotions_applicables(vente)
        self.assertEqual(len(remises), 1)
        self.assertEqual(remises[0].montant, Decimal('100.00'))
        self.assertEqual(pos_services.total_remises_promotions(vente), Decimal('100.00'))

    def test_promotions_applicables_never_raises_on_error(self):
        """Best-effort : même un panier vide (aucune ligne) ne lève jamais."""
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-POS-EMPTY', client=self.client_obj,
            created_by=self.user)
        self.assertEqual(pos_services.promotions_applicables(vente), [])
        self.assertEqual(pos_services.total_remises_promotions(vente), Decimal('0'))


class ReglexPromotionApiTests(TestCase):
    BASE = '/api/django/promotions/regles/'

    def setUp(self):
        self.co_a = make_company('ntret12-api-a', 'A')
        self.co_b = make_company('ntret12-api-b', 'B')
        self.admin_a = make_user(self.co_a, 'ntret12-api-a-admin', role='admin')
        self.viewer_a = make_user(self.co_a, 'ntret12-api-a-viewer', role='utilisateur')
        self.admin_b = make_user(self.co_b, 'ntret12-api-b-admin', role='admin')

    def test_admin_creates_rule_company_forced_server_side(self):
        api = auth(self.admin_a)
        resp = api.post(self.BASE, {
            'nom': 'Remise été', 'type_regle': 'remise_montant_panier',
            'remise_montant': '20',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        regle = ReglexPromotion.objects.get(id=resp.data['id'])
        self.assertEqual(regle.company_id, self.co_a.id)

    def test_viewer_can_list_but_not_create(self):
        api = auth(self.viewer_a)
        list_resp = api.get(self.BASE)
        self.assertEqual(list_resp.status_code, 200)
        create_resp = api.post(self.BASE, {
            'nom': 'x', 'type_regle': 'remise_montant_panier', 'remise_montant': '5',
        }, format='json')
        self.assertEqual(create_resp.status_code, 403)

    def test_company_isolation(self):
        api_a = auth(self.admin_a)
        resp = api_a.post(self.BASE, {
            'nom': 'Règle A', 'type_regle': 'remise_montant_panier',
            'remise_montant': '10',
        }, format='json')
        regle_id = resp.data['id']

        api_b = auth(self.admin_b)
        detail = api_b.get(f'{self.BASE}{regle_id}/')
        self.assertEqual(detail.status_code, 404)

    def test_n_pour_m_requires_n_greater_than_m(self):
        api = auth(self.admin_a)
        resp = api.post(self.BASE, {
            'nom': 'Invalide', 'type_regle': 'n_pour_m', 'n_achete': 2, 'm_paye': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_simuler_action(self):
        api = auth(self.admin_a)
        api.post(self.BASE, {
            'nom': 'Remise simu', 'type_regle': 'remise_montant_panier',
            'remise_montant': '30',
        }, format='json')
        resp = api.post(f'{self.BASE}simuler/', {
            'lignes': [
                {'produit_id': 1, 'categorie_id': None, 'quantite': '1',
                 'prix_unitaire_ttc': '100'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_remise'], '30.00')
