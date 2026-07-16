"""XMFG17 — Nomenclature multi-niveaux (sous-kits).

Couvre :
  - ``KitComposant.composant_kit`` (FK→KitProduit) XOR avec ``produit``
    (CheckConstraint DB + validation serveur côté serializer) ;
  - ``exploser_kit`` récursif : un kit contenant un sous-kit s'explose en
    lignes PRODUIT (jamais de ligne sous-kit brute), quantités multipliées à
    chaque niveau, agrégées si un même produit apparaît à plusieurs endroits ;
  - garde anti-cycle (direct ET indirect via une chaîne de sous-kits) —
    erreur claire, jamais de RecursionError ;
  - garde de profondeur raisonnable ;
  - ``structure_kit`` (XMFG5) : le roll-up de coût / la disponibilité
    potentielle traversent les niveaux ;
  - vue ``exploser``/``structure`` : un cycle renvoie 400 avec message clair.

Run :
    python manage.py test apps.stock.test_xmfg17_nomenclature_multiniveau -v2
"""
from decimal import Decimal

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import KitComposant, KitProduit, Produit
from apps.stock.services import (
    KitCycleError, exploser_kit, structure_kit,
)
from testkit.base import TenantAPITestCase


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestKitComposantXor(TenantAPITestCase):
    """La contrainte XOR produit/composant_kit est posée en DB (constraint)
    ET en amont côté serializer (message clair)."""

    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', prix_vente=600,
            prix_achat=400)
        self.kit_parent = KitProduit.objects.create(
            company=self.company, nom='Kit parent')
        self.sous_kit = KitProduit.objects.create(
            company=self.company, nom='Sous-kit')

    def test_db_constraint_rejects_both_null(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            KitComposant.objects.create(
                kit=self.kit_parent, quantite=1)

    def test_db_constraint_rejects_both_set(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            KitComposant.objects.create(
                kit=self.kit_parent, produit=self.produit,
                composant_kit=self.sous_kit, quantite=1)

    def test_composant_kit_is_valid(self):
        c = KitComposant.objects.create(
            kit=self.kit_parent, composant_kit=self.sous_kit, quantite=2)
        self.assertIsNone(c.produit_id)
        self.assertEqual(c.composant_kit_id, self.sous_kit.id)

    def test_api_rejects_both_via_serializer(self):
        payload = {
            'nom': 'Kit invalide',
            'composants': [{
                'produit': self.produit.id,
                'composant_kit': self.sous_kit.id,
                'quantite': 1,
            }],
        }
        resp = self.client_as(role='responsable').post(
            '/api/django/stock/kits/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_api_rejects_self_reference(self):
        kit = KitProduit.objects.create(company=self.company, nom='Self')
        payload = {'composants': [
            {'composant_kit': kit.id, 'quantite': 1}]}
        resp = self.client_as(role='responsable').patch(
            f'/api/django/stock/kits/{kit.id}/', payload,
            format='json')
        self.assertEqual(resp.status_code, 400)


class TestExplosionRecursive(TenantAPITestCase):
    """Un kit contenant un sous-kit s'explose récursivement en lignes
    PRODUIT (jamais de ligne « sous-kit » brute dans exploser_kit)."""

    def setUp(self):
        super().setUp()
        self.vis = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS',
            prix_vente=Decimal('2'), prix_achat=Decimal('1'),
            quantite_stock=1000, tva=Decimal('20'))
        self.rail = Produit.objects.create(
            company=self.company, nom='Rail alu', sku='RAIL',
            prix_vente=Decimal('50'), prix_achat=Decimal('30'),
            quantite_stock=100, tva=Decimal('20'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND',
            prix_vente=Decimal('4500'), prix_achat=Decimal('3000'),
            quantite_stock=5, tva=Decimal('20'))

        # Sous-kit "Fixation" = 4 vis + 1 rail.
        self.sous_kit = KitProduit.objects.create(
            company=self.company, nom='Kit fixation', sku='SKFIX')
        KitComposant.objects.create(
            kit=self.sous_kit, produit=self.vis, quantite=Decimal('4'))
        KitComposant.objects.create(
            kit=self.sous_kit, produit=self.rail, quantite=Decimal('1'))

        # Kit parent = 1 onduleur + 2× sous-kit fixation.
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit résidentiel', sku='KITRES')
        KitComposant.objects.create(
            kit=self.kit, produit=self.onduleur, quantite=Decimal('1'))
        KitComposant.objects.create(
            kit=self.kit, composant_kit=self.sous_kit, quantite=Decimal('2'))

    def test_explosion_never_returns_sous_kit_lines(self):
        lignes = exploser_kit(self.kit, 1)
        for ligne in lignes:
            self.assertIn('produit_id', ligne)
            self.assertNotIn('composant_kit_id', ligne)

    def test_explosion_multiplies_quantities_across_levels(self):
        lignes = exploser_kit(self.kit, 1)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        # 2 sous-kits × 4 vis = 8 ; 2 sous-kits × 1 rail = 2 ; 1 onduleur.
        self.assertEqual(by_sku['VIS']['quantite'], Decimal('8'))
        self.assertEqual(by_sku['RAIL']['quantite'], Decimal('2'))
        self.assertEqual(by_sku['OND']['quantite'], Decimal('1'))

    def test_explosion_scales_with_quantite_kit(self):
        lignes = exploser_kit(self.kit, 3)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        self.assertEqual(by_sku['VIS']['quantite'], Decimal('24'))
        self.assertEqual(by_sku['RAIL']['quantite'], Decimal('6'))
        self.assertEqual(by_sku['OND']['quantite'], Decimal('3'))

    def test_explosion_aggregates_shared_product_across_levels(self):
        # Le kit parent utilise AUSSI directement une vis (même produit que
        # dans le sous-kit) : les deux occurrences doivent être cumulées, pas
        # dupliquées en deux lignes.
        KitComposant.objects.create(
            kit=self.kit, produit=self.vis, quantite=Decimal('1'))
        lignes = exploser_kit(self.kit, 1)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        self.assertEqual(by_sku['VIS']['quantite'], Decimal('9'))  # 8 + 1
        self.assertEqual(
            len([ligne for ligne in lignes if ligne['sku'] == 'VIS']), 1)

    def test_explosion_reads_price_tva_marque_from_leaf_produit(self):
        lignes = exploser_kit(self.kit, 1)
        by_sku = {ligne['sku']: ligne for ligne in lignes}
        self.assertEqual(by_sku['VIS']['tva'], Decimal('20'))
        self.assertEqual(
            by_sku['VIS']['prix_vente_unitaire'], Decimal('2'))

    def test_explosion_never_exposes_purchase_price(self):
        for ligne in exploser_kit(self.kit, 1):
            self.assertNotIn('prix_achat', ligne)

    def test_two_level_and_deeper_three_level(self):
        # Kit racine → sous-kit(fixation) → sous-sous-kit(visserie=vis) :
        # trois niveaux, la quantité doit se composer correctement.
        visserie = KitProduit.objects.create(
            company=self.company, nom='Visserie', sku='SKVIS')
        KitComposant.objects.create(
            kit=visserie, produit=self.vis, quantite=Decimal('10'))

        fixation2 = KitProduit.objects.create(
            company=self.company, nom='Fixation N2', sku='SKFIX2')
        KitComposant.objects.create(
            kit=fixation2, composant_kit=visserie, quantite=Decimal('2'))

        racine = KitProduit.objects.create(
            company=self.company, nom='Racine 3N', sku='RACINE3')
        KitComposant.objects.create(
            kit=racine, composant_kit=fixation2, quantite=Decimal('3'))

        lignes = exploser_kit(racine, 1)
        # 3 × 2 × 10 = 60 vis.
        self.assertEqual(lignes[0]['quantite'], Decimal('60'))


class TestCycleGuard(TenantAPITestCase):
    """Un cycle (direct ou indirect) est détecté et refusé avec un message
    clair — jamais de RecursionError / boucle infinie."""

    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Vis', prix_vente=2, prix_achat=1,
            quantite_stock=100)

    def test_indirect_cycle_raises_kitcycleerror(self):
        a = KitProduit.objects.create(company=self.company, nom='A')
        b = KitProduit.objects.create(company=self.company, nom='B')
        # A contient B, B contient A (cycle indirect à 2 niveaux) — construit
        # en contournant la garde anti-self-reference du serializer (celle-ci
        # ne bloque QUE le cas direct kit == composant_kit) pour simuler un
        # cycle réel formé en deux étapes (comme en base après deux updates
        # successifs par l'UI).
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)

        with self.assertRaises(KitCycleError):
            exploser_kit(a, 1)

    def test_cycle_detected_in_structure_kit_too(self):
        a = KitProduit.objects.create(company=self.company, nom='A2')
        b = KitProduit.objects.create(company=self.company, nom='B2')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        with self.assertRaises(KitCycleError):
            structure_kit(a)

    def test_api_exploser_returns_400_on_cycle(self):
        a = KitProduit.objects.create(company=self.company, nom='A3')
        b = KitProduit.objects.create(company=self.company, nom='B3')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        resp = self.client_as().get(
            f'/api/django/stock/kits/{a.id}/exploser/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.json())

    def test_api_structure_returns_400_on_cycle(self):
        a = KitProduit.objects.create(company=self.company, nom='A4')
        b = KitProduit.objects.create(company=self.company, nom='B4')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        resp = self.client_as().get(
            f'/api/django/stock/kits/{a.id}/structure/')
        self.assertEqual(resp.status_code, 400)

    def test_deep_chain_within_limit_succeeds(self):
        # Chaîne de 5 sous-kits (< MAX_PROFONDEUR_KIT) : ne lève rien.
        kits = [KitProduit.objects.create(
            company=self.company, nom=f'Chain{i}') for i in range(6)]
        for i in range(5):
            KitComposant.objects.create(
                kit=kits[i], composant_kit=kits[i + 1], quantite=1)
        KitComposant.objects.create(
            kit=kits[5], produit=self.produit, quantite=1)
        lignes = exploser_kit(kits[0], 1)
        self.assertEqual(lignes[0]['quantite'], Decimal('1'))

    def test_excessive_depth_raises_value_error(self):
        n = 13  # > MAX_PROFONDEUR_KIT (10)
        kits = [KitProduit.objects.create(
            company=self.company, nom=f'Deep{i}') for i in range(n)]
        for i in range(n - 1):
            KitComposant.objects.create(
                kit=kits[i], composant_kit=kits[i + 1], quantite=1)
        KitComposant.objects.create(
            kit=kits[-1], produit=self.produit, quantite=1)
        with self.assertRaises(ValueError):
            exploser_kit(kits[0], 1)


class TestStructureKitMultiNiveau(TenantAPITestCase):
    """XMFG5 — le roll-up de coût/structure ET la disponibilité potentielle
    traversent les niveaux (composé de la disponibilité du sous-kit)."""

    def setUp(self):
        super().setUp()
        self.vis = Produit.objects.create(
            company=self.company, nom='Vis', sku='VIS2',
            prix_vente=Decimal('2'), prix_achat=Decimal('1'),
            quantite_stock=20)
        self.sous_kit = KitProduit.objects.create(
            company=self.company, nom='Sous-kit visserie', sku='SKV2')
        KitComposant.objects.create(
            kit=self.sous_kit, produit=self.vis, quantite=Decimal('4'))
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit avec sous-kit', sku='KWSK')
        KitComposant.objects.create(
            kit=self.kit, composant_kit=self.sous_kit, quantite=Decimal('1'))

    def test_structure_includes_niveau_and_type(self):
        data = structure_kit(self.kit)
        types = {(ligne['niveau'], ligne['type'])
                 for ligne in data['composants']}
        self.assertIn((0, 'sous_kit'), types)
        self.assertIn((1, 'produit'), types)

    def test_structure_cout_total_roll_up_traverses_levels(self):
        data = structure_kit(self.kit)
        # sous-kit: 4 vis × prix_achat(1) = 4 ; kit parent quantite=1 -> 4.
        self.assertEqual(data['cout_total_roll_up'], Decimal('4.00'))

    def test_structure_disponibilite_potentielle_via_soutkit(self):
        # 20 vis dispo / 4 par sous-kit = 5 sous-kits assemblables ; kit
        # parent consomme 1 sous-kit par unité -> 5 kits assemblables.
        data = structure_kit(self.kit)
        self.assertEqual(data['disponibilite_potentielle'], 5)

    def test_structure_disponibilite_potentielle_limited_by_bottleneck(self):
        self.vis.quantite_stock = 6  # seulement 1 sous-kit possible (4 chacun)
        self.vis.save(update_fields=['quantite_stock'])
        data = structure_kit(self.kit)
        self.assertEqual(data['disponibilite_potentielle'], 1)
