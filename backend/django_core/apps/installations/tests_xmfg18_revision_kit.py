"""XMFG18 — Révisions de nomenclature + duplication (kits de pré-assemblage
FG328, côté installations).

Couvre :
  - snapshot AUTO : ajouter / modifier / supprimer un composant via l'API
    crée une révision numérotée (composition JSON, user serveur) ;
  - l'ordre d'assemblage FIGE le numéro de révision en vigueur à sa création
    (`revision_kit_numero`) — un changement de BOM ultérieur ne le change pas,
    un NOUVEL ordre porte le nouveau numéro ;
  - `composition-au/?date=` renvoie la révision en vigueur à la date ;
  - `dupliquer/` copie en-tête + composants, facteur d'échelle ×1.67 arrondi
    proprement à l'entier (ROUND_HALF_UP, jamais 0) ; la copie reçoit sa
    révision n°1 ;
  - isolation multi-tenant.

Run :
    python manage.py test apps.installations.tests_xmfg18_revision_kit -v2
"""
from apps.installations.models import Kit, KitComposant, OrdreAssemblage
from apps.installations.services import (
    dupliquer_kit, snapshot_revision_kit,
)
from apps.stock.models import Produit
from testkit.base import TenantAPITestCase

BASE = '/api/django/installations'


class KitRevisionBase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Disjoncteur DC', prix_vente=250,
            prix_achat=150, quantite_stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret DC pré-câblé')


class TestSnapshotAutoInstallations(KitRevisionBase):
    def test_add_composant_via_api_creates_revision(self):
        resp = self.client_as(role='responsable').post(
            f'{BASE}/kit-composants/',
            {'kit': self.kit.id, 'produit': self.produit.id, 'quantite': 2},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(self.kit.revisions.count(), 1)
        rev = self.kit.revisions.first()
        self.assertEqual(rev.numero, 1)
        self.assertEqual(rev.composition[0]['produit_id'], self.produit.id)
        self.assertEqual(rev.composition[0]['quantite'], 2)

    def test_update_composant_creates_next_revision(self):
        c = KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(self.kit)
        resp = self.client_as(role='responsable').patch(
            f'{BASE}/kit-composants/{c.id}/', {'quantite': 5},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.kit.revisions.count(), 2)
        self.assertEqual(
            self.kit.revisions.order_by('-numero').first().numero, 2)

    def test_delete_composant_creates_next_revision(self):
        c = KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(self.kit)
        resp = self.client_as(role='responsable').delete(
            f'{BASE}/kit-composants/{c.id}/')
        self.assertEqual(resp.status_code, 204, resp.content)
        derniere = self.kit.revisions.order_by('-numero').first()
        self.assertEqual(derniere.numero, 2)
        self.assertEqual(derniere.composition, [])

    def test_unchanged_composition_no_duplicate(self):
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(self.kit)
        _, created = snapshot_revision_kit(self.kit)
        self.assertFalse(created)
        self.assertEqual(self.kit.revisions.count(), 1)

    def test_revisions_endpoint(self):
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(self.kit)
        resp = self.client_as().get(f'{BASE}/kits/{self.kit.id}/revisions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)


class TestOrdreFigeSaRevision(KitRevisionBase):
    def _create_ordre(self):
        resp = self.client_as(role='responsable').post(
            f'{BASE}/ordres-assemblage/',
            {'kit': self.kit.id, 'quantite': 1}, format='json')
        assert resp.status_code == 201, resp.content
        return OrdreAssemblage.objects.get(id=resp.json()['id'])

    def test_ordre_records_revision_numero(self):
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        ordre = self._create_ordre()
        # Aucune révision n'existait : l'ordre en crée une (n°1) et la fige.
        self.assertEqual(ordre.revision_kit_numero, 1)
        self.assertEqual(self.kit.revisions.count(), 1)

    def test_old_ordre_keeps_revision_new_ordre_gets_new_one(self):
        composant = KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        premier = self._create_ordre()
        self.assertEqual(premier.revision_kit_numero, 1)

        # La BOM change → révision 2 ; le premier ordre reste figé à 1.
        composant.quantite = 7
        composant.save(update_fields=['quantite'])
        snapshot_revision_kit(self.kit)

        second = self._create_ordre()
        premier.refresh_from_db()
        self.assertEqual(premier.revision_kit_numero, 1)
        self.assertEqual(second.revision_kit_numero, 2)


class TestCompositionAuInstallations(KitRevisionBase):
    def test_composition_au_returns_revision(self):
        from django.utils import timezone
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(self.kit)
        aujourd_hui = timezone.localdate()
        resp = self.client_as().get(
            f'{BASE}/kits/{self.kit.id}/composition-au/'
            f'?date={aujourd_hui.strftime("%d/%m/%Y")}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['numero'], 1)

    def test_composition_au_before_any_revision_404(self):
        resp = self.client_as().get(
            f'{BASE}/kits/{self.kit.id}/composition-au/?date=01/01/2020')
        self.assertEqual(resp.status_code, 404)

    def test_composition_au_bad_date_400(self):
        resp = self.client_as().get(
            f'{BASE}/kits/{self.kit.id}/composition-au/?date=nimporte')
        self.assertEqual(resp.status_code, 400)


class TestDuplicationInstallations(KitRevisionBase):
    def test_dupliquer_scales_and_rounds_to_int(self):
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=3)
        autre = Produit.objects.create(
            company=self.company, nom='Câble 6mm²', prix_vente=15,
            prix_achat=8, quantite_stock=500)
        KitComposant.objects.create(
            kit=self.kit, produit=autre, quantite=1)
        copie = dupliquer_kit(self.kit, facteur_echelle='1.67')
        quantites = {
            c.produit_id: c.quantite for c in copie.composants.all()}
        # 3 × 1.67 = 5.01 → 5 ; 1 × 1.67 = 1.67 → 2 (ROUND_HALF_UP).
        self.assertEqual(quantites[self.produit.id], 5)
        self.assertEqual(quantites[autre.id], 2)
        self.assertEqual(copie.nom, 'Coffret DC pré-câblé (copie)')
        self.assertIsNone(copie.reference_interne)
        self.assertEqual(copie.revisions.count(), 1)

    def test_dupliquer_via_api(self):
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=4)
        resp = self.client_as(role='responsable').post(
            f'{BASE}/kits/{self.kit.id}/dupliquer/',
            {'facteur_echelle': '2'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        copie = Kit.objects.get(id=resp.json()['id'])
        self.assertEqual(copie.composants.first().quantite, 8)
        self.assertEqual(copie.company_id, self.company.id)

    def test_dupliquer_invalid_facteur_400(self):
        resp = self.client_as(role='responsable').post(
            f'{BASE}/kits/{self.kit.id}/dupliquer/',
            {'facteur_echelle': '-1'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_cannot_dupliquer(self):
        resp = self.client_as(user=self.other_user).post(
            f'{BASE}/kits/{self.kit.id}/dupliquer/', {}, format='json')
        self.assertIn(resp.status_code, (403, 404))
        self.assertFalse(
            Kit.objects.filter(company=self.other_company).exists())
