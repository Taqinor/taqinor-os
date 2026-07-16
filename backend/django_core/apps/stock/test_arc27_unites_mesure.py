"""ARC27 — Référentiel des unités de mesure (parametres.UniteMesure).

Vérifie :
  - le master seedé (unité, m, m², kg, h, jeu…) ;
  - le backfill des codes DISTINCTS de Produit.unite_stock en unités du
    référentiel + la FK miroir posée, idempotent ;
  - unite_stock reste MAÎTRE (miroir seulement) ;
  - le serializer produit expose le LIBELLÉ du référentiel quand présent
    (unite_stock_display), sinon le code brut (comportement historique) ;
  - le référentiel est borné à la société.

Run:
    docker compose exec django_core python manage.py test \
        apps.stock.test_arc27_unites_mesure -v 2
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.parametres.models import UNITES_MESURE_DEFAUT, UniteMesure
from apps.stock.models import Produit
from apps.stock.serializers import ProduitSerializer


def _make_company(slug='arc27-co', nom='ARC27 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestArc27UniteMesureSeed(TestCase):
    def setUp(self):
        self.company = _make_company()

    def test_seed_creates_usual_units(self):
        crees = UniteMesure.seed_defaults(self.company)
        self.assertEqual(crees, len(UNITES_MESURE_DEFAUT))
        codes = set(
            UniteMesure.objects.filter(company=self.company)
            .values_list('code', flat=True))
        for expected in ('unité', 'm', 'm²', 'kg', 'h', 'jeu'):
            self.assertIn(expected, codes)

    def test_seed_is_idempotent(self):
        self.assertEqual(
            UniteMesure.seed_defaults(self.company), len(UNITES_MESURE_DEFAUT))
        self.assertEqual(UniteMesure.seed_defaults(self.company), 0)

    def test_libelle_pour_code(self):
        UniteMesure.seed_defaults(self.company)
        self.assertEqual(
            UniteMesure.libelle_pour_code(self.company, 'm'), 'Mètre')
        # Code absent → None (l'appelant affichera le code brut).
        self.assertIsNone(
            UniteMesure.libelle_pour_code(self.company, 'inconnu'))


class TestArc27Backfill(TestCase):
    def setUp(self):
        self.company = _make_company(slug='arc27-bf', nom='ARC27 BF')
        self.p_unite = self._produit('P1', 'unité')
        self.p_metre = self._produit('P2', 'm')
        self.p_metre2 = self._produit('P3', 'm')

    def _produit(self, sku, unite_stock):
        return Produit.objects.create(
            company=self.company, nom=sku, sku=sku,
            prix_vente=Decimal('100'), quantite_stock=1,
            unite_stock=unite_stock)

    def test_backfill_creates_distinct_units_and_links(self):
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        # Deux codes distincts ('unité', 'm') → deux unités.
        self.assertEqual(
            UniteMesure.objects.filter(company=self.company).count(), 2)
        self.p_metre.refresh_from_db()
        self.p_metre2.refresh_from_db()
        self.p_unite.refresh_from_db()
        # Les deux produits « m » partagent la MÊME unité miroir.
        self.assertIsNotNone(self.p_metre.unite_id)
        self.assertEqual(self.p_metre.unite_id, self.p_metre2.unite_id)
        self.assertNotEqual(self.p_metre.unite_id, self.p_unite.unite_id)
        self.assertEqual(self.p_metre.unite.code, 'm')

    def test_unite_stock_stays_master(self):
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        self.p_metre.refresh_from_db()
        # Le CharField reste INCHANGÉ (miroir seulement).
        self.assertEqual(self.p_metre.unite_stock, 'm')

    def test_backfill_is_idempotent(self):
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        avant = UniteMesure.objects.filter(company=self.company).count()
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        apres = UniteMesure.objects.filter(company=self.company).count()
        self.assertEqual(avant, apres)


class TestArc27SerializerDisplay(TestCase):
    def setUp(self):
        self.company = _make_company(slug='arc27-ser', nom='ARC27 Ser')

    def _produit(self, unite_stock='m'):
        return Produit.objects.create(
            company=self.company, nom='Câble', sku='CBL',
            prix_vente=Decimal('10'), quantite_stock=1,
            unite_stock=unite_stock)

    def test_display_uses_referentiel_label_when_present(self):
        UniteMesure.seed_defaults(self.company)
        p = self._produit('m')
        data = ProduitSerializer(p).data
        # Le référentiel a un libellé pour 'm' → 'Mètre' est affiché.
        self.assertEqual(data['unite_stock_display'], 'Mètre')

    def test_display_falls_back_to_raw_code_without_referentiel(self):
        # Aucun référentiel seedé → le code brut est renvoyé (historique).
        p = self._produit('carton')
        data = ProduitSerializer(p).data
        self.assertEqual(data['unite_stock_display'], 'carton')

    def test_display_uses_linked_mirror_label(self):
        UniteMesure.seed_defaults(self.company)
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        p = self._produit('kg')
        call_command('backfill_unites_mesure',
                     company_slug=self.company.slug)
        p.refresh_from_db()
        data = ProduitSerializer(p).data
        self.assertEqual(data['unite_stock_display'], 'Kilogramme')

    def test_referentiel_is_company_scoped(self):
        other = _make_company(slug='arc27-other', nom='Autre')
        UniteMesure.seed_defaults(self.company)
        self.assertIsNone(UniteMesure.libelle_pour_code(other, 'm'))
        self.assertEqual(
            UniteMesure.objects.filter(company=other).count(), 0)
