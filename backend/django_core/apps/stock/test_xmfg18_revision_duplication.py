"""XMFG18 — Révisions de nomenclature + duplication (kits stock FG66).

Couvre :
  - snapshot AUTO : créer un kit avec composants via l'API crée la révision 1 ;
    modifier les composants crée la révision 2 ; re-sauver sans changement de
    composition ne crée PAS de doublon ;
  - `revisions/` liste l'historique (numéro, user, snapshot sans prix) ;
  - `composition-au/?date=` (JJ/MM/AAAA et AAAA-MM-JJ) renvoie la révision en
    vigueur à la date ; 404 avant la première révision ;
  - `dupliquer/` copie en-tête + composants ; facteur d'échelle ×1.67 arrondi
    proprement (2 décimales, ROUND_HALF_UP) ; la copie reçoit sa révision 1 ;
  - isolation multi-tenant (kit d'une autre société → 404).

Run :
    python manage.py test apps.stock.test_xmfg18_revision_duplication -v2
"""
from decimal import Decimal

from apps.stock.models import KitComposant, KitProduit, Produit, RevisionKit
from apps.stock.services import (
    composition_kit_au, dupliquer_kit, snapshot_revision_kit,
)
from testkit.base import TenantAPITestCase

BASE = '/api/django/stock/kits'


class RevisionKitBase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV550',
            prix_vente=Decimal('600'), prix_achat=Decimal('400'),
            quantite_stock=20)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_vente=Decimal('4500'), prix_achat=Decimal('3000'),
            quantite_stock=5)

    def _create_kit_api(self, nom='Kit rev', composants=None):
        payload = {
            'nom': nom,
            'composants': composants if composants is not None else [
                {'produit': self.panneau.id, 'quantite': '9'},
                {'produit': self.onduleur.id, 'quantite': '1'},
            ],
        }
        resp = self.client_as(role='responsable').post(
            f'{BASE}/', payload, format='json')
        assert resp.status_code == 201, resp.content
        return KitProduit.objects.get(id=resp.json()['id'])


class TestSnapshotAuto(RevisionKitBase):
    def test_create_via_api_creates_revision_1(self):
        kit = self._create_kit_api()
        revs = list(kit.revisions.all())
        self.assertEqual(len(revs), 1)
        self.assertEqual(revs[0].numero, 1)
        self.assertEqual(len(revs[0].composition), 2)
        self.assertEqual(revs[0].company_id, self.company.id)

    def test_update_composants_creates_revision_2(self):
        kit = self._create_kit_api()
        resp = self.client_as(role='responsable').patch(
            f'{BASE}/{kit.id}/',
            {'composants': [
                {'produit': self.panneau.id, 'quantite': '12'},
            ]},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(kit.revisions.count(), 2)
        derniere = kit.revisions.order_by('-numero').first()
        self.assertEqual(derniere.numero, 2)
        self.assertEqual(len(derniere.composition), 1)
        self.assertEqual(derniere.composition[0]['quantite'], '12.00')

    def test_unchanged_composition_creates_no_duplicate(self):
        kit = self._create_kit_api()
        _, created = snapshot_revision_kit(kit)
        self.assertFalse(created)
        self.assertEqual(kit.revisions.count(), 1)

    def test_snapshot_contains_no_price(self):
        kit = self._create_kit_api()
        composition = kit.revisions.first().composition
        for ligne in composition:
            self.assertNotIn('prix_achat', ligne)
            self.assertNotIn('prix_vente', ligne)

    def test_revisions_endpoint_lists_history(self):
        kit = self._create_kit_api()
        resp = self.client_as().get(f'{BASE}/{kit.id}/revisions/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['numero'], 1)


class TestCompositionAu(RevisionKitBase):
    def test_composition_au_today_returns_latest(self):
        from django.utils import timezone
        kit = self._create_kit_api()
        aujourd_hui = timezone.localdate()
        resp = self.client_as().get(
            f'{BASE}/{kit.id}/composition-au/'
            f'?date={aujourd_hui.strftime("%d/%m/%Y")}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['numero'], 1)

    def test_composition_au_iso_format_accepted(self):
        from django.utils import timezone
        kit = self._create_kit_api()
        aujourd_hui = timezone.localdate()
        resp = self.client_as().get(
            f'{BASE}/{kit.id}/composition-au/'
            f'?date={aujourd_hui.isoformat()}')
        self.assertEqual(resp.status_code, 200)

    def test_composition_au_before_first_revision_404(self):
        kit = self._create_kit_api()
        resp = self.client_as().get(
            f'{BASE}/{kit.id}/composition-au/?date=01/01/2020')
        self.assertEqual(resp.status_code, 404)

    def test_composition_au_missing_date_400(self):
        kit = self._create_kit_api()
        resp = self.client_as().get(f'{BASE}/{kit.id}/composition-au/')
        self.assertEqual(resp.status_code, 400)

    def test_composition_kit_au_service_picks_correct_revision(self):
        from django.utils import timezone
        kit = self._create_kit_api()
        # Modifie la composition → révision 2 (même jour).
        KitComposant.objects.filter(kit=kit).delete()
        KitComposant.objects.create(
            kit=kit, produit=self.panneau, quantite=Decimal('3'))
        snapshot_revision_kit(kit)
        rev = composition_kit_au(kit, timezone.localdate())
        self.assertEqual(rev.numero, 2)


class TestDuplication(RevisionKitBase):
    def test_dupliquer_copies_header_and_composants(self):
        kit = self._create_kit_api(nom='Kit source')
        resp = self.client_as(role='responsable').post(
            f'{BASE}/{kit.id}/dupliquer/', {}, format='json')
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['nom'], 'Kit source (copie)')
        self.assertIsNone(data['sku'])
        copie = KitProduit.objects.get(id=data['id'])
        self.assertEqual(copie.composants.count(), 2)
        self.assertEqual(copie.company_id, self.company.id)

    def test_dupliquer_facteur_167_arrondit_proprement(self):
        kit = KitProduit.objects.create(company=self.company, nom='Échelle')
        KitComposant.objects.create(
            kit=kit, produit=self.panneau, quantite=Decimal('3'))
        KitComposant.objects.create(
            kit=kit, produit=self.onduleur, quantite=Decimal('1.5'))
        copie = dupliquer_kit(kit, facteur_echelle='1.67')
        quantites = {
            c.produit_id: c.quantite for c in copie.composants.all()}
        # 3 × 1.67 = 5.01 ; 1.5 × 1.67 = 2.505 → 2.51 (ROUND_HALF_UP).
        self.assertEqual(quantites[self.panneau.id], Decimal('5.01'))
        self.assertEqual(quantites[self.onduleur.id], Decimal('2.51'))

    def test_dupliquer_creates_revision_1_for_copy(self):
        kit = self._create_kit_api()
        resp = self.client_as(role='responsable').post(
            f'{BASE}/{kit.id}/dupliquer/', {}, format='json')
        copie = KitProduit.objects.get(id=resp.json()['id'])
        self.assertEqual(copie.revisions.count(), 1)
        self.assertEqual(copie.revisions.first().numero, 1)

    def test_dupliquer_invalid_facteur_400(self):
        kit = self._create_kit_api()
        resp = self.client_as(role='responsable').post(
            f'{BASE}/{kit.id}/dupliquer/',
            {'facteur_echelle': 'abc'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_dupliquer_copies_sous_kits_xmfg17(self):
        sous_kit = KitProduit.objects.create(
            company=self.company, nom='Sous-kit')
        KitComposant.objects.create(
            kit=sous_kit, produit=self.panneau, quantite=Decimal('4'))
        kit = KitProduit.objects.create(company=self.company, nom='Parent')
        KitComposant.objects.create(
            kit=kit, composant_kit=sous_kit, quantite=Decimal('2'))
        copie = dupliquer_kit(kit)
        c = copie.composants.first()
        self.assertEqual(c.composant_kit_id, sous_kit.id)
        self.assertIsNone(c.produit_id)

    def test_cross_tenant_cannot_dupliquer(self):
        kit = self._create_kit_api()
        resp = self.client_as(user=self.other_user).post(
            f'{BASE}/{kit.id}/dupliquer/', {}, format='json')
        self.assertIn(resp.status_code, (403, 404))
        self.assertFalse(
            KitProduit.objects.filter(company=self.other_company).exists())

    def test_revision_isolation_multi_tenant(self):
        kit = self._create_kit_api()
        self.assertFalse(
            RevisionKit.objects.filter(company=self.other_company).exists())
        resp = self.client_as(user=self.other_user).get(
            f'{BASE}/{kit.id}/revisions/')
        self.assertIn(resp.status_code, (403, 404))
