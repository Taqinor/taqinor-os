"""
Tests for the seed_catalogue management command (devis-simulator catalogue).

Run:
    docker compose exec django_core python manage.py test apps.stock -v 2
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.stock.models import Produit, MouvementStock


def make_company(slug='test-cat-co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test Catalogue Co'},
    )
    return company


def seed(company):
    out = StringIO()
    call_command('seed_catalogue', company_slug=company.slug, stdout=out)
    return out.getvalue()


class TestSeedCatalogue(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_seeds_full_catalogue(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # 31 solaire + 9 pompage + 16 VEICHI + 11 pompes OSP
        self.assertEqual(qs.count(), 67)
        # Spot-check key items: HT price = simulator TTC / 1.2
        huawei_10t = qs.get(sku='OND-R-HUA-10T')
        self.assertEqual(huawei_10t.nom, 'Onduleur réseau Huawei 10kW Triphasé')
        self.assertEqual(huawei_10t.prix_vente, Decimal('16666.67'))  # 20 000 TTC
        # Réforme TVA : panneau à 10 % — HT dérivé pour préserver 1 400 TTC
        panneau = qs.get(sku='PAN-CS-710')
        self.assertEqual(panneau.prix_vente, Decimal('1272.73'))      # 1 400 TTC @ 10 %
        self.assertEqual(panneau.tva, Decimal('10.00'))
        bat10 = qs.get(sku='BAT-DEY-10')
        self.assertEqual(bat10.prix_vente, Decimal('25000.00'))       # 30 000 TTC
        socles = qs.get(sku='SOC-BET')
        self.assertEqual(socles.prix_vente, Decimal('66.67'))         # 80 TTC
        # Stock available so auto-fill is never blocked
        self.assertTrue(all(p.quantite_stock > 0 for p in qs))
        # Traceability: one entry movement per product
        self.assertEqual(
            MouvementStock.objects.filter(
                company=self.company, reference='SEED-CATALOGUE').count(), 67,
        )

    def test_fiches_and_pompage_seeded(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # Fiches commerciales remplies (marque/description/garantie)
        huawei = qs.get(sku='OND-R-HUA-10T')
        self.assertEqual(huawei.marque, 'Huawei')
        self.assertIn('FusionSolar', huawei.description)
        self.assertIn('10 ans', huawei.garantie)
        panneau = qs.get(sku='PAN-CS-710')
        self.assertIn('30 ans performance', panneau.garantie)
        # Pompage : specs de dimensionnement + prix d'achat laissé vide
        pompe = qs.get(sku='PMP-IMM-5.5T')
        self.assertEqual(str(pompe.pompe_cv), '5.50')
        self.assertEqual(pompe.prix_achat, 0)
        self.assertEqual(pompe.categorie.nom, 'Pompage')
        # Prix existants jamais modifiés par la passe fiches
        self.assertEqual(huawei.prix_vente, Decimal('16666.67'))

    def test_veichi_seeded_with_real_buy_and_sell_prices(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        v75 = qs.get(sku='VEI-SI23-7.5-380')
        self.assertEqual(v75.nom, 'VARIATEUR VEICHI SI23 7.5KW 380V')
        self.assertEqual(v75.prix_vente, Decimal('3333.33'))   # 4 000 TTC public
        self.assertEqual(v75.prix_achat, Decimal('2875.00'))   # 3 450 TTC revendeur
        self.assertEqual(str(v75.pompe_kw), '7.50')
        self.assertEqual(v75.tension_v, 380)
        self.assertEqual(v75.marque, 'VEICHI')
        self.assertEqual(v75.categorie.nom, 'Pompage')
        # L'afficheur n'a pas de kW : il ne peut jamais être pris pour le variateur
        aff = qs.get(sku='VEI-SI22-AFF')
        self.assertIsNone(aff.pompe_kw)
        self.assertEqual(aff.prix_vente, Decimal('350.00'))    # 420 TTC
        self.assertEqual(aff.prix_achat, Decimal('300.00'))    # 360 TTC

    def test_osp_pumps_seeded_with_curves_and_empty_price(self):
        seed(self.company)
        p = Produit.objects.get(company=self.company, sku='PMP-OSP-30-8')
        self.assertEqual(p.prix_vente, Decimal('0'))   # à renseigner par le fondateur
        self.assertEqual(p.prix_achat, Decimal('0'))
        self.assertEqual(str(p.pompe_cv), '10.00')
        self.assertEqual(str(p.pompe_kw), '7.50')
        self.assertEqual(p.tension_v, 380)
        self.assertEqual(p.courbe_pompe['debits_m3h'], [0, 12, 24, 30, 36, 39])
        self.assertEqual(p.courbe_pompe['hmt_m'], [91, 85, 70, 60, 43, 34])

    def test_placeholder_coffrets_archived_prices_intact(self):
        # Un ancien coffret placeholder existant est archivé par le seeder
        # (autorisation fondateur) — jamais supprimé, prix jamais modifié.
        old = Produit.objects.create(
            company=self.company, nom='Variateur pompage solaire 5.5 CV Triphasé (coffret complet)',
            sku='VFD-PMP-5.5T', prix_vente=Decimal('5416.67'), quantite_stock=20,
        )
        seed(self.company)
        old.refresh_from_db()
        self.assertTrue(old.is_archived)
        self.assertEqual(old.prix_vente, Decimal('5416.67'))
        # Et le seeder ne les recrée jamais
        self.assertEqual(
            Produit.objects.filter(
                company=self.company, sku__startswith='VFD-PMP').count(), 1)

    def test_fiches_update_is_idempotent_and_price_safe(self):
        seed(self.company)
        before = dict(Produit.objects.filter(company=self.company)
                      .values_list('sku', 'prix_vente'))
        seed(self.company)
        after = dict(Produit.objects.filter(company=self.company)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(before, after)

    def test_idempotent_second_run_creates_nothing(self):
        seed(self.company)
        count_after_first = Produit.objects.filter(company=self.company).count()
        out = seed(self.company)
        self.assertEqual(
            Produit.objects.filter(company=self.company).count(), count_after_first)
        self.assertIn('0 created, 67 already present', out)

    def test_never_overwrites_existing_product(self):
        # Pre-existing product with the same name but a different price
        existing = Produit.objects.create(
            company=self.company, nom='Structures acier', sku='STR-LEGACY',
            prix_vente=Decimal('375.00'), prix_achat=Decimal('280.00'),
            quantite_stock=10,
        )
        out = seed(self.company)
        existing.refresh_from_db()
        # Untouched, no duplicate created under the catalogue SKU
        self.assertEqual(existing.prix_vente, Decimal('375.00'))
        self.assertFalse(
            Produit.objects.filter(company=self.company, sku='STR-ACIER').exists())
        self.assertEqual(
            Produit.objects.filter(
                company=self.company, nom__iexact='Structures acier').count(), 1)
        self.assertIn('Structures acier', out)

    def test_archived_product_frees_its_name_for_the_catalogue(self):
        # Un produit démo ARCHIVÉ ne bloque plus la création de la version
        # catalogue portant le même nom (l'actif, lui, bloque toujours).
        Produit.objects.create(
            company=self.company, nom='Structures acier', sku='STR-LEGACY2',
            prix_vente=Decimal('375.00'), quantite_stock=5, is_archived=True,
        )
        seed(self.company)
        actifs = Produit.objects.filter(
            company=self.company, nom__iexact='Structures acier',
            is_archived=False)
        self.assertEqual(actifs.count(), 1)
        self.assertEqual(actifs.first().sku, 'STR-ACIER')
        self.assertEqual(actifs.first().prix_vente, Decimal('416.67'))  # 500 TTC

    def test_tva_reform_panels_10_others_20_ttc_preserved(self):
        seed(self.company)
        qs = Produit.objects.filter(company=self.company)
        # TOUS les panneaux à 10 %, TTC strictement préservé
        for p in qs.filter(nom__icontains='panneau'):
            self.assertEqual(p.tva, Decimal('10.00'), p.nom)
            ttc = p.prix_vente * Decimal('1.10')
            self.assertEqual(ttc.quantize(Decimal('1')), Decimal('1400'), p.nom)
        # Tout le reste à 20 % (onduleurs, batteries, structures, pompes…)
        for p in qs.exclude(nom__icontains='panneau'):
            self.assertEqual(p.tva, Decimal('20.00'), p.nom)
        # Idempotent : un second passage ne retouche plus les prix
        before = dict(qs.values_list('sku', 'prix_vente'))
        seed(self.company)
        after = dict(Produit.objects.filter(company=self.company)
                     .values_list('sku', 'prix_vente'))
        self.assertEqual(before, after)

    def test_tva_reform_converts_existing_panel_preserving_ttc(self):
        # Un panneau créé AVANT la réforme (HT à 20 %) est converti :
        # 1 166,67 HT @20 % (1 400 TTC) → 1 272,73 HT @10 % (1 400 TTC)
        p = Produit.objects.create(
            company=self.company, nom='Panneau Maison 550W', sku='PAN-LEGACY',
            prix_vente=Decimal('1166.67'), prix_achat=Decimal('1000.00'),
            quantite_stock=5, tva=Decimal('20.00'),
        )
        seed(self.company)
        p.refresh_from_db()
        self.assertEqual(p.tva, Decimal('10.00'))
        self.assertEqual(p.prix_vente, Decimal('1272.73'))
        self.assertEqual(p.prix_achat, Decimal('1090.91'))  # 1 200 TTC préservé

    def test_scoped_to_target_company_only(self):
        other = make_company(slug='test-cat-other')
        seed(self.company)
        self.assertEqual(Produit.objects.filter(company=other).count(), 0)
