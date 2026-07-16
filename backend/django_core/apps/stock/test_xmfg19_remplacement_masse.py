"""XMFG19 — Remplacement de masse d'un composant dans toutes les
nomenclatures (kits stock FG66 + kits de pré-assemblage installations FG328).

Couvre :
  - `dry_run` (préview) : liste EXACTE des kits impactés des deux modules,
    quantités avant/après (ratio appliqué), AUCUNE modification ;
  - application : remplacement effectif dans les deux modules, en UNE
    transaction, ratio de quantité appliqué (2 déc. côté stock, entier côté
    installations) ;
  - chaque kit modifié reçoit sa révision XMFG18 ;
  - fusion propre si un kit contient déjà le produit de remplacement
    (jamais de doublon (kit, produit)) ;
  - une ligne d'audit récapitulative est écrite ;
  - les kits d'une AUTRE société sont intouchés ;
  - erreurs : produits identiques / inconnus / ratio invalide → 400 ;
  - garde d'écriture (rôle sans stock_modifier → 403).

Run :
    python manage.py test apps.stock.test_xmfg19_remplacement_masse -v2
"""
from decimal import Decimal

from apps.installations.models import Kit as KitInst
from apps.installations.models import KitComposant as KitComposantInst
from apps.stock.models import KitComposant, KitProduit, Produit
from testkit.base import TenantAPITestCase

URL = '/api/django/stock/kits/remplacer-composant/'


class RemplacementBase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.ancien = Produit.objects.create(
            company=self.company, nom='Panneau 500W', sku='PV500',
            prix_vente=Decimal('550'), prix_achat=Decimal('350'),
            quantite_stock=10)
        self.nouveau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV550',
            prix_vente=Decimal('600'), prix_achat=Decimal('400'),
            quantite_stock=20)
        # Kit stock utilisant l'ancien produit.
        self.kit_stock = KitProduit.objects.create(
            company=self.company, nom='Kit stock A')
        KitComposant.objects.create(
            kit=self.kit_stock, produit=self.ancien, quantite=Decimal('9'))
        # Kit de pré-assemblage (installations) utilisant l'ancien produit.
        self.kit_inst = KitInst.objects.create(
            company=self.company, nom='Coffret pré-câblé')
        KitComposantInst.objects.create(
            kit=self.kit_inst, produit=self.ancien, quantite=3)
        # Kit d'une AUTRE société utilisant le même produit-nom (isolation).
        self.produit_autre = Produit.objects.create(
            company=self.other_company, nom='Panneau 500W', sku='PV500',
            prix_vente=Decimal('550'), prix_achat=Decimal('350'))
        self.kit_autre = KitProduit.objects.create(
            company=self.other_company, nom='Kit autre société')
        KitComposant.objects.create(
            kit=self.kit_autre, produit=self.produit_autre,
            quantite=Decimal('4'))

    def _post(self, body, role='responsable'):
        return self.client_as(role=role).post(URL, body, format='json')


class TestDryRun(RemplacementBase):
    def test_dry_run_lists_both_modules_exactly(self):
        resp = self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['dry_run'])
        self.assertEqual(data['nb_total'], 2)
        self.assertEqual(
            [k['kit_id'] for k in data['kits_stock']], [self.kit_stock.id])
        self.assertEqual(
            [k['kit_id'] for k in data['kits_installations']],
            [self.kit_inst.id])

    def test_dry_run_changes_nothing(self):
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
        })
        c = self.kit_stock.composants.first()
        self.assertEqual(c.produit_id, self.ancien.id)
        ci = self.kit_inst.composants.first()
        self.assertEqual(ci.produit_id, self.ancien.id)
        self.assertEqual(self.kit_stock.revisions.count(), 0)

    def test_dry_run_shows_ratio_applied_quantities(self):
        resp = self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'ratio_quantite': '0.5',
        })
        data = resp.json()
        self.assertEqual(data['kits_stock'][0]['quantite_apres'], '4.50')
        # Installations : entier arrondi (3 × 0.5 = 1.5 → 2 ROUND_HALF_UP).
        self.assertEqual(
            data['kits_installations'][0]['quantite_apres'], '2')


class TestApplication(RemplacementBase):
    def test_apply_replaces_in_both_modules(self):
        resp = self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'dry_run': False,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        c = self.kit_stock.composants.first()
        self.assertEqual(c.produit_id, self.nouveau.id)
        self.assertEqual(c.quantite, Decimal('9'))
        ci = self.kit_inst.composants.first()
        self.assertEqual(ci.produit_id, self.nouveau.id)
        self.assertEqual(ci.quantite, 3)

    def test_apply_with_ratio_scales_quantities(self):
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'ratio_quantite': '1.67',
            'dry_run': False,
        })
        c = self.kit_stock.composants.first()
        self.assertEqual(c.quantite, Decimal('15.03'))  # 9 × 1.67
        ci = self.kit_inst.composants.first()
        self.assertEqual(ci.quantite, 5)  # 3 × 1.67 = 5.01 → 5

    def test_apply_creates_revisions_for_each_modified_kit(self):
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'dry_run': False,
        })
        self.assertEqual(self.kit_stock.revisions.count(), 1)
        self.assertEqual(self.kit_inst.revisions.count(), 1)

    def test_apply_merges_when_kit_already_has_new_product(self):
        KitComposant.objects.create(
            kit=self.kit_stock, produit=self.nouveau,
            quantite=Decimal('2'))
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'dry_run': False,
        })
        composants = list(self.kit_stock.composants.all())
        self.assertEqual(len(composants), 1)
        self.assertEqual(composants[0].produit_id, self.nouveau.id)
        self.assertEqual(composants[0].quantite, Decimal('11'))  # 2 + 9

    def test_apply_writes_audit_line(self):
        from apps.audit.models import AuditLog
        avant = AuditLog.objects.filter(company=self.company).count()
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'dry_run': False,
        })
        logs = AuditLog.objects.filter(
            company=self.company,
            detail__icontains='Remplacement de masse')
        self.assertEqual(logs.count(), 1)
        self.assertGreater(
            AuditLog.objects.filter(company=self.company).count(), avant)

    def test_other_company_kits_untouched(self):
        self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'dry_run': False,
        })
        c = self.kit_autre.composants.first()
        self.assertEqual(c.produit_id, self.produit_autre.id)
        self.assertEqual(self.kit_autre.revisions.count(), 0)


class TestValidationEtGardes(RemplacementBase):
    def test_same_product_400(self):
        resp = self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.ancien.id,
        })
        self.assertEqual(resp.status_code, 400)

    def test_unknown_product_400(self):
        resp = self._post({
            'produit_ancien': 999999,
            'produit_nouveau': self.nouveau.id,
        })
        self.assertEqual(resp.status_code, 400)

    def test_cross_tenant_product_400(self):
        resp = self._post({
            'produit_ancien': self.produit_autre.id,
            'produit_nouveau': self.nouveau.id,
        })
        self.assertEqual(resp.status_code, 400)

    def test_invalid_ratio_400(self):
        resp = self._post({
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
            'ratio_quantite': '-2',
        })
        self.assertEqual(resp.status_code, 400)

    def test_write_guard_normal_role_403(self):
        resp = self.client_as().post(URL, {
            'produit_ancien': self.ancien.id,
            'produit_nouveau': self.nouveau.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)
