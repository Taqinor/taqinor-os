"""Tests d'intégrité d'inventaire (ERR10, ERR23, ERR24, ERR54, ERR93-95).

Couvre :
  - ERR10 — validation des quantités de MouvementStock (positives, garde
    plancher SORTIE, pas d'augmentation silencieuse via négatif) ;
  - ERR23 — perform_create atomique + verrou de ligne produit ;
  - ERR54 — besoin matériel : quantité Decimal fractionnaire arrondie au
    supérieur (2,5 → 3) ;
  - ERR93 — StockEmplacement : company dans la contrainte + quantité non
    négative ;
  - ERR94 — ventilation par emplacement : principal jamais négatif ;
  - ERR95 — ProduitSerializer : allowlist explicite, prix_achat gardé par
    permission.

Run :
    python manage.py test apps.stock.test_integrity -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import (
    Produit, EmplacementStock, StockEmplacement, MouvementStock,
)
from apps.stock.serializers import ProduitSerializer
from apps.stock.services import (
    ensure_emplacements, stock_breakdown, stock_breakdown_map,
    compute_besoin_materiel,
)
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='integ-co', nom='Integ Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, sku, stock=0, prix_achat='100', prix_vente='150'):
    return Produit.objects.create(
        company=company, nom=f'Produit {sku}', sku=sku,
        prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
        quantite_stock=stock)


# ── ERR10 / ERR23 — MouvementStock : validation + garde plancher ─────────────

class TestMouvementValidation(TestCase):
    def setUp(self):
        self.company = make_company(slug='mv-co', nom='Mv Co')
        self.resp = User.objects.create_user(
            username='mv_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.produit = make_produit(self.company, 'MV-1', stock=10)
        self.api = auth(self.resp)

    def _post(self, **body):
        return self.api.post('/api/django/stock/mouvements/', body,
                             format='json')

    def test_entree_positive_increments(self):
        r = self._post(produit=self.produit.id, type_mouvement='entree',
                       quantite=5)
        self.assertEqual(r.status_code, 201, r.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)

    def test_sortie_positive_decrements(self):
        r = self._post(produit=self.produit.id, type_mouvement='sortie',
                       quantite=4)
        self.assertEqual(r.status_code, 201, r.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 6)

    def test_zero_quantite_rejected(self):
        r = self._post(produit=self.produit.id, type_mouvement='entree',
                       quantite=0)
        self.assertEqual(r.status_code, 400)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)  # inchangé

    def test_negative_sortie_does_not_increase_stock(self):
        # Une SORTIE négative augmenterait silencieusement le stock — refusée.
        r = self._post(produit=self.produit.id, type_mouvement='sortie',
                       quantite=-5)
        self.assertEqual(r.status_code, 400)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())

    def test_negative_entree_rejected(self):
        r = self._post(produit=self.produit.id, type_mouvement='entree',
                       quantite=-3)
        self.assertEqual(r.status_code, 400)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)

    def test_sortie_below_zero_floored_with_french_message(self):
        # ERR10 — une SORTIE ne peut jamais descendre le stock sous 0.
        r = self._post(produit=self.produit.id, type_mouvement='sortie',
                       quantite=99)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Stock insuffisant', str(r.data))
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)  # inchangé
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())

    def test_perform_create_audit_columns_consistent(self):
        # ERR23 — quantite_avant/quantite_apres cohérents et persistés.
        self._post(produit=self.produit.id, type_mouvement='entree',
                   quantite=2)
        mv = MouvementStock.objects.get(produit=self.produit)
        self.assertEqual(mv.quantite_avant, 10)
        self.assertEqual(mv.quantite_apres, 12)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 12)


# ── ERR54 — besoin matériel : quantité fractionnaire arrondie au supérieur ───

class TestBesoinCeil(TestCase):
    def setUp(self):
        self.company = make_company(slug='ceil-co', nom='Ceil Co')

    def _chantier(self, produit, qte):
        cl = Client.objects.create(
            company=self.company, nom='Cl', prenom='I',
            email='ceil@example.com', telephone='+212600000010')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-8001', client=cl,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(qte), prix_unitaire=produit.prix_vente)
        return Installation.objects.create(
            company=self.company, reference=f'CH-{MONTH}-8001',
            client=cl, devis=devis)

    def test_fractional_quantity_rounds_up(self):
        # 2,5 unités requises → besoin de 3 (jamais 2 par troncature).
        produit = make_produit(self.company, 'CEIL-1', stock=0)
        inst = self._chantier(produit, '2.5')
        besoins = compute_besoin_materiel(inst)
        self.assertEqual(besoins[0]['requis'], 3)
        self.assertEqual(besoins[0]['manque'], 3)

    def test_integer_quantity_unchanged(self):
        produit = make_produit(self.company, 'CEIL-2', stock=0)
        inst = self._chantier(produit, '4')
        besoins = compute_besoin_materiel(inst)
        self.assertEqual(besoins[0]['requis'], 4)


# ── ERR93 — StockEmplacement : contrainte company + quantité non négative ────

class TestStockEmplacementConstraints(TestCase):
    def setUp(self):
        self.company = make_company(slug='se-co', nom='SE Co')
        self.produit = make_produit(self.company, 'SE-1', stock=10)
        ensure_emplacements(self.company)
        self.camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')

    def test_company_in_unique_together(self):
        self.assertIn(
            ('company', 'produit', 'emplacement'),
            StockEmplacement._meta.unique_together)

    def test_negative_quantite_rejected_by_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockEmplacement.objects.create(
                    company=self.company, produit=self.produit,
                    emplacement=self.camionnette, quantite=-1)

    def test_zero_and_positive_quantite_allowed(self):
        se = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.camionnette, quantite=0)
        self.assertEqual(se.quantite, 0)


# ── ERR94 — ventilation : principal jamais négatif ───────────────────────────

class TestBreakdownNonNegative(TestCase):
    def setUp(self):
        self.company = make_company(slug='bd-co', nom='Bd Co')
        # total 5, mais 8 alloués hors principal → principal serait −3
        self.produit = make_produit(self.company, 'BD-1', stock=5)
        ensure_emplacements(self.company)
        self.camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.camionnette, quantite=8)

    def test_stock_breakdown_principal_clamped_at_zero(self):
        rows = {b['emplacement_nom']: b['quantite']
                for b in stock_breakdown(self.produit)}
        self.assertEqual(rows['Dépôt principal'], 0)  # jamais −3
        self.assertEqual(rows['Camionnette'], 8)

    def test_stock_breakdown_map_principal_clamped_at_zero(self):
        m = stock_breakdown_map(self.company)
        rows = {b['emplacement_nom']: b['quantite']
                for b in m[self.produit.id]}
        self.assertEqual(rows['Dépôt principal'], 0)
        self.assertEqual(rows['Camionnette'], 8)


# ── ERR95 — ProduitSerializer : allowlist explicite + prix_achat gardé ───────

class _FakeRequest:
    def __init__(self, user):
        self.user = user


class TestProduitSerializerAllowlist(TestCase):
    def setUp(self):
        self.company = make_company(slug='ser-co', nom='Ser Co')
        self.produit = make_produit(
            self.company, 'SER-1', stock=3, prix_achat='77', prix_vente='150')
        # Compte légacy (sans rôle fin) : voit les prix d'achat (historique).
        self.legacy = User.objects.create_user(
            username='ser_legacy', password='x', role_legacy='responsable',
            company=self.company)
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commerciale',
            permissions=['stock_voir'])  # pas de prix_achat_voir
        self.restricted = User.objects.create_user(
            username='ser_restricted', password='x',
            company=self.company, role=role)

    def _serialize(self, user):
        return ProduitSerializer(
            self.produit, context={'request': _FakeRequest(user)}).data

    def test_uses_explicit_allowlist_not_all(self):
        self.assertNotEqual(ProduitSerializer.Meta.fields, '__all__')
        self.assertIsInstance(ProduitSerializer.Meta.fields, list)

    def test_prix_achat_present_for_authorized_user(self):
        data = self._serialize(self.legacy)
        self.assertIn('prix_achat', data)
        self.assertEqual(Decimal(data['prix_achat']), Decimal('77'))

    def test_prix_achat_absent_for_unauthorized_user(self):
        data = self._serialize(self.restricted)
        self.assertNotIn('prix_achat', data)

    def test_present_fields_unchanged(self):
        # Les champs métier exposés restent disponibles et corrects.
        data = self._serialize(self.legacy)
        for key in ('id', 'nom', 'sku', 'prix_vente', 'quantite_stock',
                    'seuil_alerte', 'categorie', 'fournisseur',
                    'quantite_disponible', 'stock_par_emplacement',
                    'is_low_stock', 'date_creation'):
            self.assertIn(key, data, key)
        self.assertEqual(data['nom'], self.produit.nom)
        self.assertEqual(Decimal(data['prix_vente']), Decimal('150'))
        self.assertEqual(data['quantite_stock'], 3)
