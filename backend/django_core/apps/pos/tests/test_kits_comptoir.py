"""NTRET28 — Kits/bundles vendus comme un seul article au comptoir.

Réutilise le moteur de kits EXISTANT (``stock.KitProduit``/``KitComposant``/
``services.exploser_kit_par_id``, FG66/DC36) plutôt qu'un second système
dupliqué dans ``apps/pos``. Couvre : ajouter un kit décompose ses composants
en lignes réelles, la validation décrémente CHAQUE composant dans les bonnes
quantités en une transaction, un composant en rupture refuse l'ajout sauf
override admin journalisé, kit introuvable/hors société refusé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import VenteComptoir
from apps.stock.models import Categorie, KitComposant, KitProduit, Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class KitComptoirTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret28', 'NTRET28 Co')
        self.user = make_user(self.co, 'caissier-ntret28')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.mc4 = Produit.objects.create(
            company=self.co, nom='Connecteur MC4', prix_vente=Decimal('20'),
            prix_achat=Decimal('8'), quantite_stock=50, categorie=categorie, tva=20)
        self.presse = Produit.objects.create(
            company=self.co, nom='Presse-étoupe', prix_vente=Decimal('10'),
            prix_achat=Decimal('4'), quantite_stock=5, categorie=categorie, tva=20)
        self.kit = KitProduit.objects.create(company=self.co, nom='Kit MC4')
        KitComposant.objects.create(kit=self.kit, produit=self.mc4, quantite=2)
        KitComposant.objects.create(kit=self.kit, produit=self.presse, quantite=1)
        self.vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-KIT-1', client=self.client_obj,
            created_by=self.user)

    def test_ajouter_kit_decompose_en_lignes_composant(self):
        lignes = services.ajouter_kit_a_vente(
            vente=self.vente, kit_id=self.kit.id, quantite_kit=1, user=self.user)
        self.assertEqual(len(lignes), 2)
        by_produit = {ligne.produit_id: ligne for ligne in lignes}
        self.assertEqual(by_produit[self.mc4.id].quantite, Decimal('2'))
        self.assertEqual(by_produit[self.mc4.id].prix_unitaire_ttc, Decimal('20'))
        self.assertEqual(by_produit[self.presse.id].quantite, Decimal('1'))

    def test_valider_vente_decremente_chaque_composant(self):
        services.ajouter_kit_a_vente(
            vente=self.vente, kit_id=self.kit.id, quantite_kit=1, user=self.user)
        # total = 2×20 + 1×10 = 50
        services.valider_vente(
            vente=self.vente, paiements=[{'mode': 'carte', 'montant': '50'}],
            user=self.user)
        self.mc4.refresh_from_db()
        self.presse.refresh_from_db()
        self.assertEqual(self.mc4.quantite_stock, 48)   # 50 - 2
        self.assertEqual(self.presse.quantite_stock, 4)  # 5 - 1

    def test_quantite_kit_multiplie_les_composants(self):
        services.ajouter_kit_a_vente(
            vente=self.vente, kit_id=self.kit.id, quantite_kit=2, user=self.user)
        lignes = list(self.vente.lignes.all())
        by_produit = {ligne.produit_id: ligne for ligne in lignes}
        self.assertEqual(by_produit[self.mc4.id].quantite, Decimal('4'))
        self.assertEqual(by_produit[self.presse.id].quantite, Decimal('2'))

    def test_composant_en_rupture_refuse_sans_forcer(self):
        # 5 en stock, kit demande 1×presse par unité -> demander 6 kits.
        with self.assertRaises(services.KitPosError):
            services.ajouter_kit_a_vente(
                vente=self.vente, kit_id=self.kit.id, quantite_kit=6, user=self.user)
        self.assertEqual(self.vente.lignes.count(), 0)

    def test_composant_en_rupture_avec_forcer_exige_motif(self):
        with self.assertRaises(services.KitPosError):
            services.ajouter_kit_a_vente(
                vente=self.vente, kit_id=self.kit.id, quantite_kit=6,
                user=self.user, forcer=True, motif_force='')

    def test_composant_en_rupture_forcer_avec_motif_journalise(self):
        services.ajouter_kit_a_vente(
            vente=self.vente, kit_id=self.kit.id, quantite_kit=6,
            user=self.user, forcer=True, motif_force='Client VIP, urgence')
        self.assertEqual(self.vente.lignes.count(), 2)

        from apps.audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(company=self.co)
            .filter(detail__icontains='kit ajouté malgré').exists())

    def test_kit_introuvable_refuse(self):
        with self.assertRaises(services.KitPosError):
            services.ajouter_kit_a_vente(
                vente=self.vente, kit_id=999999, quantite_kit=1, user=self.user)

    def test_kit_dune_autre_societe_introuvable(self):
        co_b = make_company('ntret28-b', 'NTRET28 B')
        kit_b = KitProduit.objects.create(company=co_b, nom='Kit B')
        with self.assertRaises(services.KitPosError):
            services.ajouter_kit_a_vente(
                vente=self.vente, kit_id=kit_b.id, quantite_kit=1, user=self.user)

    def test_vente_deja_validee_refuse_ajout_kit(self):
        services.ajouter_kit_a_vente(
            vente=self.vente, kit_id=self.kit.id, quantite_kit=1, user=self.user)
        services.valider_vente(
            vente=self.vente, paiements=[{'mode': 'carte', 'montant': '50'}],
            user=self.user)
        with self.assertRaises(services.KitPosError):
            services.ajouter_kit_a_vente(
                vente=self.vente, kit_id=self.kit.id, quantite_kit=1, user=self.user)


class KitComptoirViewTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret28-view', 'NTRET28 View Co')
        self.user = make_user(self.co, 'responsable-ntret28')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Accessoires')
        self.mc4 = Produit.objects.create(
            company=self.co, nom='Connecteur MC4', prix_vente=Decimal('20'),
            prix_achat=Decimal('8'), quantite_stock=50, categorie=categorie)
        self.kit = KitProduit.objects.create(company=self.co, nom='Kit MC4')
        KitComposant.objects.create(kit=self.kit, produit=self.mc4, quantite=2)

    def test_endpoint_ajoute_les_lignes_du_kit(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-KIT-API', client=self.client_obj,
            created_by=self.user)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        res = api.post(
            f'/api/django/pos/ventes/{vente.id}/lignes-kit/',
            {'kit': self.kit.id, 'quantite_kit': 1})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(vente.lignes.count(), 1)
