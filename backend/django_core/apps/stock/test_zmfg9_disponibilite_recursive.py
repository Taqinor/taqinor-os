"""ZMFG9 — Disponibilité multi-niveaux du kit (stock partagé + goulots).

Couvre :
  - sur un kit à 2 niveaux dont un composant est PARTAGÉ entre le niveau
    racine et un sous-kit, le nombre assemblable respecte le stock partagé
    (le besoin est agrégé — jamais compté deux fois) ;
  - les composants limitants (goulots) sont listés ;
  - un cycle de nomenclature est refusé (KitCycleError → 400 côté API) ;
  - déduction des réservations actives du disponible ;
  - endpoint `disponibilite/` (fiche kit) + liste `?avec_disponibilite=1` ;
  - isolation multi-tenant.

Run :
    python manage.py test apps.stock.test_zmfg9_disponibilite_recursive -v2
"""
from decimal import Decimal

from apps.stock.models import KitComposant, KitProduit, Produit
from apps.stock.selectors import disponibilite_potentielle_recursive
from apps.stock.services import KitCycleError
from testkit.base import TenantAPITestCase


class DispoBase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.vis = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS',
            prix_vente=Decimal('2'), prix_achat=Decimal('1'),
            quantite_stock=20)
        self.rail = Produit.objects.create(
            company=self.company, nom='Rail alu', sku='RAIL',
            prix_vente=Decimal('50'), prix_achat=Decimal('30'),
            quantite_stock=100)

        # Sous-kit « fixation » : 4 vis + 1 rail.
        self.sous_kit = KitProduit.objects.create(
            company=self.company, nom='Kit fixation', sku='SKFIX')
        KitComposant.objects.create(
            kit=self.sous_kit, produit=self.vis, quantite=Decimal('4'))
        KitComposant.objects.create(
            kit=self.sous_kit, produit=self.rail, quantite=Decimal('1'))

        # Kit racine : 1 sous-kit fixation + 6 vis DIRECTES (composant
        # partagé entre les deux niveaux).
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit racine', sku='KRAC')
        KitComposant.objects.create(
            kit=self.kit, composant_kit=self.sous_kit, quantite=Decimal('1'))
        KitComposant.objects.create(
            kit=self.kit, produit=self.vis, quantite=Decimal('6'))


class TestStockPartage(DispoBase):
    def test_shared_component_not_counted_twice(self):
        # Besoin agrégé en vis par kit : 4 (sous-kit) + 6 (directes) = 10.
        # Stock 20 vis → 2 kits, PAS min(20/4, 20/6) = 3 (double comptage).
        data = disponibilite_potentielle_recursive(self.kit, self.company)
        self.assertEqual(data['kits_assemblables'], 2)
        vis = next(
            c for c in data['composants'] if c['produit_id'] == self.vis.id)
        self.assertEqual(Decimal(vis['besoin_par_kit']), Decimal('10'))
        self.assertEqual(vis['kits_possibles'], 2)

    def test_goulots_list_the_limiting_components(self):
        data = disponibilite_potentielle_recursive(self.kit, self.company)
        self.assertEqual(
            [g['produit_id'] for g in data['goulots']], [self.vis.id])

    def test_multiple_tied_goulots_all_listed(self):
        # Rail réduit à 2 → rail (2/1=2) ET vis (20/10=2) limitent ensemble.
        self.rail.quantite_stock = 2
        self.rail.save(update_fields=['quantite_stock'])
        data = disponibilite_potentielle_recursive(self.kit, self.company)
        self.assertEqual(data['kits_assemblables'], 2)
        self.assertEqual(
            sorted(g['sku'] for g in data['goulots']), ['RAIL', 'VIS'])

    def test_missing_component_gives_zero(self):
        self.vis.quantite_stock = 0
        self.vis.save(update_fields=['quantite_stock'])
        data = disponibilite_potentielle_recursive(self.kit, self.company)
        self.assertEqual(data['kits_assemblables'], 0)
        self.assertIn(
            self.vis.id, [g['produit_id'] for g in data['goulots']])

    def test_kit_without_components_zero_no_goulots(self):
        vide = KitProduit.objects.create(company=self.company, nom='Vide')
        data = disponibilite_potentielle_recursive(vide, self.company)
        self.assertEqual(data['kits_assemblables'], 0)
        self.assertEqual(data['goulots'], [])

    def test_reservations_deducted_from_available(self):
        # 8 vis réservées pour un chantier → dispo 12 → 12/10 = 1 kit.
        from apps.installations.models import Installation, StockReservation
        chantier = Installation.objects.create(
            company=self.company, reference='CH-ZMFG9-0001')
        StockReservation.objects.create(
            company=self.company, installation=chantier,
            produit=self.vis, quantite=8, active=True, consomme=False)
        data = disponibilite_potentielle_recursive(self.kit, self.company)
        self.assertEqual(data['kits_assemblables'], 1)

    def test_cycle_refused_with_clear_error(self):
        a = KitProduit.objects.create(company=self.company, nom='CycleA')
        b = KitProduit.objects.create(company=self.company, nom='CycleB')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        with self.assertRaises(KitCycleError):
            disponibilite_potentielle_recursive(a, self.company)


class TestEndpointDisponibilite(DispoBase):
    def test_fiche_kit_disponibilite(self):
        resp = self.client_as().get(
            f'/api/django/stock/kits/{self.kit.id}/disponibilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['kits_assemblables'], 2)
        self.assertEqual(
            [g['sku'] for g in data['goulots']], ['VIS'])

    def test_cycle_returns_400(self):
        a = KitProduit.objects.create(company=self.company, nom='CycleA2')
        b = KitProduit.objects.create(company=self.company, nom='CycleB2')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        resp = self.client_as().get(
            f'/api/django/stock/kits/{a.id}/disponibilite/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.json())

    def test_liste_avec_disponibilite(self):
        resp = self.client_as().get(
            '/api/django/stock/kits/?avec_disponibilite=1')
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        rows = rows.get('results', rows)
        racine = next(r for r in rows if r['id'] == self.kit.id)
        self.assertEqual(
            racine['disponibilite_potentielle']['kits_assemblables'], 2)
        self.assertEqual(
            [g['sku'] for g in racine['disponibilite_potentielle']['goulots']],
            ['VIS'])

    def test_liste_sans_flag_ne_calcule_pas(self):
        resp = self.client_as().get('/api/django/stock/kits/')
        rows = resp.json()
        rows = rows.get('results', rows)
        racine = next(r for r in rows if r['id'] == self.kit.id)
        self.assertIsNone(racine['disponibilite_potentielle'])

    def test_cyclic_kit_does_not_break_list(self):
        a = KitProduit.objects.create(company=self.company, nom='CycleA3')
        b = KitProduit.objects.create(company=self.company, nom='CycleB3')
        KitComposant.objects.create(kit=a, composant_kit=b, quantite=1)
        KitComposant.objects.create(kit=b, composant_kit=a, quantite=1)
        resp = self.client_as().get(
            '/api/django/stock/kits/?avec_disponibilite=1')
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        rows = rows.get('results', rows)
        cyc = next(r for r in rows if r['id'] == a.id)
        self.assertIsNone(cyc['disponibilite_potentielle'])

    def test_cross_tenant_404(self):
        resp = self.client_as(user=self.other_user).get(
            f'/api/django/stock/kits/{self.kit.id}/disponibilite/')
        self.assertIn(resp.status_code, (403, 404))
