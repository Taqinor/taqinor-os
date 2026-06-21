"""Tests pour les FG54–FG65 (stock feature gaps).

FG54 — réapprovisionnement auto (endpoint + service)
FG55 — PDF facture fournisseur (smoke test)
FG56 — facturer une réception
FG57 — rapport rotation / dead-stock
FG58 — comparaison prix fournisseurs
FG59 — scorecard performance fournisseur
FG60 — filtres mouvements + export xlsx
FG61 — numéros de série à la réception
FG62 — seuils min/max par emplacement + suggestions
FG63 — session d'inventaire draft
FG64 — rapport expiry
FG65 — prévisions de demande

Run:
    python manage.py test apps.stock.tests_fg -v 2
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Produit, Categorie, Fournisseur, MouvementStock,
    PrixFournisseur,
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
    ReceptionFournisseur, LigneReceptionFournisseur,
    FactureFournisseur, LigneFactureFournisseur,
    EmplacementStock, StockEmplacement,
    InventaireSession, LigneInventaire,
)

User = get_user_model()


def make_company(slug='fg-test-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'FG Test Co'})
    return company


def make_admin(company, username='admin_fg'):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'company': company, 'role_legacy': 'admin'})
    return user


def make_produit(company, nom='Produit Test', prix_vente=Decimal('100'),
                 prix_achat=Decimal('60'), quantite=10, seuil=5):
    return Produit.objects.create(
        company=company, nom=nom,
        prix_vente=prix_vente, prix_achat=prix_achat,
        quantite_stock=quantite, seuil_alerte=seuil)


def make_fournisseur(company, nom='Fournisseur Test'):
    return Fournisseur.objects.get_or_create(
        company=company, nom=nom)[0]


def make_bcf(company, fournisseur, admin, statut=BonCommandeFournisseur.Statut.ENVOYE):
    bc = BonCommandeFournisseur.objects.create(
        company=company, reference='BCF-TEST-001',
        fournisseur=fournisseur, statut=statut, created_by=admin)
    return bc


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


# ── FG60 — Filtres mouvements + xlsx export ───────────────────────────────────

class TestFG60MouvementsFilter(TestCase):
    def setUp(self):
        self.company = make_company('fg60-co')
        self.admin = make_admin(self.company, 'admin_fg60')
        self.client = auth_client(self.admin)
        self.produit = make_produit(self.company)
        # Créer quelques mouvements
        MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement='entree', quantite=5,
            quantite_avant=10, quantite_apres=15,
            reference='TEST-ENTREE', created_by=self.admin)
        MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement='sortie', quantite=3,
            quantite_avant=15, quantite_apres=12,
            reference='TEST-SORTIE', created_by=self.admin)

    def test_filter_by_type_mouvement(self):
        r = self.client.get('/api/django/stock/mouvements/?type_mouvement=entree')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data)
        self.assertTrue(
            all(m['type_mouvement'] == 'entree' for m in results),
            f"Un mouvement non-entree dans: {results}"
        )

    def test_filter_by_produit(self):
        r = self.client.get(
            f'/api/django/stock/mouvements/?produit={self.produit.id}')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data)
        self.assertTrue(len(results) >= 2)

    def test_filter_by_date_range(self):
        r = self.client.get(
            '/api/django/stock/mouvements/?date_min=2020-01-01&date_max=2099-12-31')
        self.assertEqual(r.status_code, 200)

    def test_export_xlsx_returns_file(self):
        r = self.client.post('/api/django/stock/mouvements/export-xlsx/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])

    def test_company_scoping_cross_tenant(self):
        """Les mouvements d'une autre société ne doivent pas être visibles."""
        company2 = make_company('fg60-other')
        admin2 = make_admin(company2, 'admin_fg60_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/mouvements/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data)
        ids = [m['id'] for m in results]
        # Les mouvements de company1 ne doivent pas apparaître
        own_ids = list(
            MouvementStock.objects.filter(company=self.company)
            .values_list('id', flat=True))
        for oid in own_ids:
            self.assertNotIn(oid, ids)


# ── FG54 — Réapprovisionnement auto ──────────────────────────────────────────

class TestFG54Reappro(TestCase):
    def setUp(self):
        self.company = make_company('fg54-co')
        self.admin = make_admin(self.company, 'admin_fg54')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company)
        # Produit sous seuil
        self.produit_bas = make_produit(
            self.company, nom='Panneau 550W', prix_vente=Decimal('1200'),
            prix_achat=Decimal('900'), quantite=2, seuil=5)
        # Produit avec prix fournisseur
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit_bas,
            fournisseur=self.fournisseur, prix_achat=Decimal('850'))
        # Produit OK (stock > seuil)
        self.produit_ok = make_produit(
            self.company, nom='Onduleur 5kW', prix_vente=Decimal('15000'),
            prix_achat=Decimal('12000'), quantite=10, seuil=3)

    def test_produits_a_reapprovisionner_endpoint(self):
        r = self.client.get('/api/django/stock/produits/a-reapprovisionner/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        noms = [d['nom'] for d in data]
        self.assertIn('Panneau 550W', noms)
        self.assertNotIn('Onduleur 5kW', noms)

    def test_quantite_reappro_cible_field(self):
        """FG54 SCHEMA — quantite_reappro_cible optionnel sur Produit."""
        self.produit_bas.quantite_reappro_cible = 20
        self.produit_bas.save()
        from apps.stock.services import produits_a_reapprovisionner
        besoins = produits_a_reapprovisionner(self.company)
        item = next(b for b in besoins if b['produit_id'] == self.produit_bas.id)
        self.assertEqual(item['quantite_suggere'], 20)

    def test_quantite_suggere_default_seuil_x2(self):
        """Sans quantite_reappro_cible, suggère seuil × 2."""
        from apps.stock.services import produits_a_reapprovisionner
        besoins = produits_a_reapprovisionner(self.company)
        item = next(b for b in besoins if b['produit_id'] == self.produit_bas.id)
        self.assertEqual(item['quantite_suggere'], self.produit_bas.seuil_alerte * 2)

    def test_generer_bcf_reappro_creates_bcf(self):
        r = self.client.post(
            '/api/django/stock/produits/generer-bcf-reappro/',
            {'fournisseur_id': self.fournisseur.id}, format='json')
        self.assertEqual(r.status_code, 201)
        data = r.json()
        self.assertIn('bon_commande_id', data)
        self.assertEqual(data['nb_lignes'], 1)
        bon = BonCommandeFournisseur.objects.get(pk=data['bon_commande_id'])
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_generer_bcf_reappro_uses_create_with_reference(self):
        """Référence numérotée sans trou (préfixe BCF)."""
        r = self.client.post(
            '/api/django/stock/produits/generer-bcf-reappro/',
            {'fournisseur_id': self.fournisseur.id}, format='json')
        self.assertEqual(r.status_code, 201)
        ref = r.json()['reference']
        self.assertTrue(ref.startswith('BCF'), f"Référence incorrecte: {ref}")

    def test_cross_company_isolation(self):
        company2 = make_company('fg54-other')
        admin2 = make_admin(company2, 'admin_fg54_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/produits/a-reapprovisionner/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])


# ── FG57 — Rotation / dead-stock ─────────────────────────────────────────────

class TestFG57Rotation(TestCase):
    def setUp(self):
        self.company = make_company('fg57-co')
        self.admin = make_admin(self.company, 'admin_fg57')
        self.client = auth_client(self.admin)
        self.produit = make_produit(
            self.company, nom='Batterie Test', quantite=5, seuil=2)

    def test_rotation_endpoint_returns_list(self):
        r = self.client.get('/api/django/stock/produits/rotation/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)

    def test_immobile_product_no_sortie(self):
        r = self.client.get('/api/django/stock/produits/rotation/?jours=180')
        data = r.json()
        item = next((d for d in data if d['produit_id'] == self.produit.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item['bucket'], 'immobile')
        self.assertIsNone(item['jours_sans_mouvement'])

    def test_valeur_stock_present(self):
        r = self.client.get('/api/django/stock/produits/rotation/')
        data = r.json()
        item = next((d for d in data if d['produit_id'] == self.produit.id), None)
        # valeur = quantite_stock × prix_achat (INTERNE)
        self.assertIn('valeur_stock', item)

    def test_cross_company_not_shown(self):
        company2 = make_company('fg57-other')
        admin2 = make_admin(company2, 'admin_fg57_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/produits/rotation/')
        data = r.json()
        ids = [d['produit_id'] for d in data]
        self.assertNotIn(self.produit.id, ids)


# ── FG56 — Facturer une réception ────────────────────────────────────────────

class TestFG56FacturerReception(TestCase):
    def setUp(self):
        self.company = make_company('fg56-co')
        self.admin = make_admin(self.company, 'admin_fg56')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company)
        self.produit = make_produit(self.company, quantite=0, seuil=0)
        # Crée BCF + réception confirmée
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-FG56-001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            created_by=self.admin)
        self.ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit,
            quantite=10, prix_achat_unitaire=Decimal('100'),
            quantite_recue=10)
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-FG56-001',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            created_by=self.admin)
        self.ligne_rec = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_bcf,
            produit=self.produit, quantite=10)

    def test_facturer_creates_facture(self):
        r = self.client.post(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/facturer/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.json())
        data = r.json()
        self.assertIn('reference', data)
        self.assertTrue(data['reference'].startswith('FF'))

    def test_facturer_computes_ht_tva_ttc(self):
        r = self.client.post(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/facturer/',
            {}, format='json')
        self.assertEqual(r.status_code, 201)
        data = r.json()
        # 10 × 100 = 1000 HT, TVA 20% = 200, TTC = 1200
        self.assertEqual(Decimal(data['montant_ht']), Decimal('1000.00'))
        self.assertEqual(Decimal(data['montant_tva']), Decimal('200.00'))
        self.assertEqual(Decimal(data['montant_ttc']), Decimal('1200.00'))

    def test_facturer_twice_rejected(self):
        self.client.post(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/facturer/',
            {}, format='json')
        r = self.client.post(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/facturer/',
            {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('déjà', r.json()['detail'].lower())

    def test_facturer_non_confirme_rejected(self):
        reception2 = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-FG56-002',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.admin)
        r = self.client.post(
            f'/api/django/stock/receptions-fournisseur/{reception2.id}/facturer/',
            {}, format='json')
        self.assertEqual(r.status_code, 400)


# ── FG55 — PDF facture fournisseur ────────────────────────────────────────────

class TestFG55FacturePDF(TestCase):
    def setUp(self):
        self.company = make_company('fg55-co')
        self.admin = make_admin(self.company, 'admin_fg55')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company)
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-FG55-001',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'),
            statut=FactureFournisseur.Statut.A_PAYER,
            created_by=self.admin)

    def test_pdf_endpoint_returns_pdf(self):
        r = self.client.get(
            f'/api/django/stock/factures-fournisseur/{self.facture.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_pdf_not_accessible_non_admin(self):
        """PDF facture fournisseur : réservé aux utilisateurs responsable/admin.
        Un utilisateur 'normal' doit recevoir 403."""
        user_normal = User.objects.create_user(
            username='normal_fg55', password='x',
            company=self.company, role_legacy='normal')
        client2 = auth_client(user_normal)
        r = client2.get(
            f'/api/django/stock/factures-fournisseur/{self.facture.id}/pdf/')
        self.assertIn(r.status_code, [403, 404])


# ── FG58 — Comparaison prix fournisseurs ──────────────────────────────────────

class TestFG58CompararePrixFournisseurs(TestCase):
    def setUp(self):
        self.company = make_company('fg58-co')
        self.admin = make_admin(self.company, 'admin_fg58')
        self.client = auth_client(self.admin)
        self.produit = make_produit(self.company, nom='Produit FG58')
        self.f1 = make_fournisseur(self.company, 'Fournisseur A')
        self.f2 = make_fournisseur(self.company, 'Fournisseur B')
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f1, prix_achat=Decimal('1200'))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f2, prix_achat=Decimal('1150'))

    def test_comparer_fournisseurs_endpoint(self):
        r = self.client.get(
            f'/api/django/stock/produits/{self.produit.id}/comparer-fournisseurs/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 2)
        # Trié du moins cher au plus cher
        self.assertLessEqual(
            Decimal(data[0]['prix_achat']), Decimal(data[1]['prix_achat']))
        self.assertEqual(Decimal(data[0]['prix_achat']), Decimal('1150'))

    def test_cross_company_isolation(self):
        company2 = make_company('fg58-other')
        admin2 = make_admin(company2, 'admin_fg58_b')
        produit2 = make_produit(company2, nom='Produit Autre Co')
        client2 = auth_client(admin2)
        r = client2.get(
            f'/api/django/stock/produits/{produit2.id}/comparer-fournisseurs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])  # aucun prix pour cette co


# ── FG59 — Scorecard performance fournisseur ─────────────────────────────────

class TestFG59PerformanceFournisseur(TestCase):
    def setUp(self):
        self.company = make_company('fg59-co')
        self.admin = make_admin(self.company, 'admin_fg59')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company, 'Fournisseur Perf')
        self.produit = make_produit(self.company, quantite=0, seuil=0)

    def test_performance_endpoint_returns_data(self):
        r = self.client.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/performance/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('fill_rate_pct', data)
        self.assertIn('avg_lead_time_days', data)
        self.assertIn('nb_bons', data)
        self.assertIn('total_achats_ht', data)

    def test_performance_no_data(self):
        r = self.client.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/performance/')
        data = r.json()
        self.assertEqual(data['nb_bons'], 0)
        self.assertIsNone(data['fill_rate_pct'])
        self.assertIsNone(data['avg_lead_time_days'])

    def test_cross_company_isolation(self):
        company2 = make_company('fg59-other')
        admin2 = make_admin(company2, 'admin_fg59_b')
        fournisseur2 = make_fournisseur(company2, 'Fournisseur Autre Co')
        client2 = auth_client(admin2)
        r = client2.get(
            f'/api/django/stock/fournisseurs/{fournisseur2.id}/performance/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['nb_bons'], 0)


# ── FG61 — Numéros de série à la réception ───────────────────────────────────

class TestFG61SerialNumbers(TestCase):
    def setUp(self):
        self.company = make_company('fg61-co')
        self.admin = make_admin(self.company, 'admin_fg61')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company)
        self.produit = make_produit(self.company, quantite=0, seuil=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-FG61-001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            created_by=self.admin)
        self.ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit,
            quantite=3, prix_achat_unitaire=Decimal('1500'),
            quantite_recue=0)
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-FG61-001',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.admin)

    def test_numeros_serie_field_exists_on_ligne_reception(self):
        """FG61 SCHEMA — numeros_serie JSON sur LigneReceptionFournisseur."""
        ligne = LigneReceptionFournisseur.objects.create(
            reception=self.reception,
            ligne_commande=self.ligne_bcf,
            produit=self.produit,
            quantite=3,
            numeros_serie=['SN001', 'SN002', 'SN003'])
        ligne.refresh_from_db()
        self.assertEqual(ligne.numeros_serie, ['SN001', 'SN002', 'SN003'])

    def test_numeros_serie_nullable(self):
        ligne = LigneReceptionFournisseur.objects.create(
            reception=self.reception,
            ligne_commande=self.ligne_bcf,
            produit=self.produit,
            quantite=1,
            numeros_serie=None)
        ligne.refresh_from_db()
        self.assertIsNone(ligne.numeros_serie)


# ── FG62 — Seuils min/max par emplacement ────────────────────────────────────

class TestFG62EmplacementMinMax(TestCase):
    def setUp(self):
        self.company = make_company('fg62-co')
        self.admin = make_admin(self.company, 'admin_fg62')
        self.client = auth_client(self.admin)
        self.produit = make_produit(self.company, quantite=20, seuil=3)
        # Créer un emplacement principal + une camionnette
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.van = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette', is_principal=False)
        # Stock de 2 dans la camionnette (< seuil_min=5)
        self.se = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.van, quantite=2,
            seuil_min=5, seuil_max=10)

    def test_seuil_min_max_fields(self):
        """FG62 SCHEMA — seuil_min/max sur StockEmplacement."""
        self.se.refresh_from_db()
        self.assertEqual(self.se.seuil_min, 5)
        self.assertEqual(self.se.seuil_max, 10)

    def test_suggestions_reappro_emplacement_endpoint(self):
        r = self.client.get('/api/django/stock/emplacements/suggestions-reappro/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(len(data) >= 1)
        item = next((d for d in data if d['emplacement_id'] == self.van.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item['produit_id'], self.produit.id)
        # Quantité suggérée = seuil_min - quantité actuelle = 5 - 2 = 3
        self.assertEqual(item['qte_suggere_transfert'], 3)

    def test_suggestions_reappro_cross_company(self):
        company2 = make_company('fg62-other')
        admin2 = make_admin(company2, 'admin_fg62_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/emplacements/suggestions-reappro/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # Aucune suggestion pour cette autre société
        ids = [d['produit_id'] for d in data]
        self.assertNotIn(self.produit.id, ids)


# ── FG64 — Expiry tracking ────────────────────────────────────────────────────

class TestFG64ExpiryTracking(TestCase):
    def setUp(self):
        import datetime
        from django.utils import timezone
        self.company = make_company('fg64-co')
        self.admin = make_admin(self.company, 'admin_fg64')
        self.client = auth_client(self.admin)
        self.fournisseur = make_fournisseur(self.company)
        self.produit = make_produit(
            self.company, nom='Batterie Expiry', quantite=5, seuil=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-FG64-001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            created_by=self.admin)
        self.ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit,
            quantite=5, prix_achat_unitaire=Decimal('500'), quantite_recue=5)
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-FG64-001',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            created_by=self.admin)
        # Ligne avec date de péremption dans 30 jours
        self.today = timezone.now().date()
        self.ligne_rec = LigneReceptionFournisseur.objects.create(
            reception=self.reception,
            ligne_commande=self.ligne_bcf,
            produit=self.produit,
            quantite=5,
            date_peremption=self.today + datetime.timedelta(days=30),
            numero_lot='LOT-001')

    def test_date_peremption_field_on_ligne(self):
        """FG64 SCHEMA — date_peremption sur LigneReceptionFournisseur."""
        self.ligne_rec.refresh_from_db()
        self.assertIsNotNone(self.ligne_rec.date_peremption)
        self.assertEqual(self.ligne_rec.numero_lot, 'LOT-001')

    def test_expirant_bientot_endpoint(self):
        r = self.client.get(
            '/api/django/stock/produits/expirant-bientot/?jours=90')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # Doit trouver la batterie qui expire dans 30 jours
        ids = [d['produit_id'] for d in data]
        self.assertIn(self.produit.id, ids)

    def test_expirant_bientot_excludes_far_future(self):
        """Produits expirant après la fenêtre ne doivent pas apparaître."""
        import datetime
        self.ligne_rec.date_peremption = self.today + datetime.timedelta(days=200)
        self.ligne_rec.save()
        r = self.client.get(
            '/api/django/stock/produits/expirant-bientot/?jours=90')
        data = r.json()
        ids = [d['produit_id'] for d in data]
        self.assertNotIn(self.produit.id, ids)


# ── FG63 — Session d'inventaire ───────────────────────────────────────────────

class TestFG63InventaireSession(TestCase):
    def setUp(self):
        self.company = make_company('fg63-co')
        self.admin = make_admin(self.company, 'admin_fg63')
        self.client = auth_client(self.admin)
        self.produit = make_produit(
            self.company, nom='Produit Inventaire', quantite=10, seuil=0)

    def test_create_session(self):
        r = self.client.post('/api/django/stock/inventaire-sessions/', {
            'motif': 'Inventaire annuel',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.json())
        data = r.json()
        self.assertTrue(data['reference'].startswith('INV'))
        self.assertEqual(data['statut'], 'brouillon')

    def test_valider_session_ajuste_stock(self):
        # Crée session
        r = self.client.post('/api/django/stock/inventaire-sessions/', {
            'motif': 'Test FG63',
        }, format='json')
        session_id = r.json()['id']
        # Ajoute une ligne (théorique = 10, comptée = 7)
        session = InventaireSession.objects.get(pk=session_id)
        LigneInventaire.objects.create(
            session=session,
            produit=self.produit,
            quantite_theorique=10,
            quantite_comptee=7)
        # Valide
        r2 = self.client.post(
            f'/api/django/stock/inventaire-sessions/{session_id}/valider/')
        self.assertEqual(r2.status_code, 200)
        data = r2.json()
        self.assertEqual(data['ajustes'], 1)
        self.assertEqual(data['inchanges'], 0)
        # Stock ajusté
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)

    def test_valider_session_inchange(self):
        r = self.client.post('/api/django/stock/inventaire-sessions/', {}, format='json')
        session_id = r.json()['id']
        session = InventaireSession.objects.get(pk=session_id)
        LigneInventaire.objects.create(
            session=session, produit=self.produit,
            quantite_theorique=10, quantite_comptee=10)
        r2 = self.client.post(
            f'/api/django/stock/inventaire-sessions/{session_id}/valider/')
        data = r2.json()
        self.assertEqual(data['ajustes'], 0)
        self.assertEqual(data['inchanges'], 1)

    def test_valider_already_validated_rejected(self):
        r = self.client.post('/api/django/stock/inventaire-sessions/', {}, format='json')
        session_id = r.json()['id']
        self.client.post(
            f'/api/django/stock/inventaire-sessions/{session_id}/valider/')
        r2 = self.client.post(
            f'/api/django/stock/inventaire-sessions/{session_id}/valider/')
        self.assertEqual(r2.status_code, 400)

    def test_cross_company_isolation(self):
        company2 = make_company('fg63-other')
        admin2 = make_admin(company2, 'admin_fg63_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/inventaire-sessions/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data)
        self.assertEqual(len(results), 0)


# ── FG65 — Prévisions de demande ─────────────────────────────────────────────

class TestFG65Previsions(TestCase):
    def setUp(self):
        self.company = make_company('fg65-co')
        self.admin = make_admin(self.company, 'admin_fg65')
        self.client = auth_client(self.admin)
        self.produit = make_produit(
            self.company, nom='Onduleur FG65', quantite=20, seuil=3)
        # Créer des sorties pour simuler la consommation
        for _ in range(4):
            MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement='sortie', quantite=2,
                quantite_avant=20, quantite_apres=18,
                created_by=self.admin)

    def test_previsions_endpoint(self):
        r = self.client.get('/api/django/stock/produits/previsions-reappro/?nb_mois=6')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        item = next((d for d in data if d['produit_id'] == self.produit.id), None)
        self.assertIsNotNone(item)
        self.assertIn('consommation_mensuelle_moy', item)
        self.assertIn('quantite_suggeree', item)
        self.assertGreater(item['total_sorties'], 0)

    def test_previsions_cross_company_isolation(self):
        company2 = make_company('fg65-other')
        admin2 = make_admin(company2, 'admin_fg65_b')
        client2 = auth_client(admin2)
        r = client2.get('/api/django/stock/produits/previsions-reappro/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        ids = [d['produit_id'] for d in data]
        self.assertNotIn(self.produit.id, ids)
