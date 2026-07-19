"""WIR97 — Ancrer le référentiel ARC27 (UniteMesure) comme SOURCE via FK.

La FK ``Produit.unite`` existait déjà en MIROIR mais n'était posée que par le
backfill ponctuel : un produit créé/modifié après coup ne la reliait jamais.
Ce test vérifie que ``Produit.save()`` maintient désormais la FK alignée sur le
code MAÎTRE ``unite_stock`` — la rendant EFFECTIVEMENT la source du libellé lu
par ``ProduitSerializer.unite_stock_display`` — sans régression quand aucune
unité de référence ne correspond.
"""
from decimal import Decimal

from django.test import TestCase

from apps.parametres.models import UniteMesure
from apps.stock.models import Produit
from apps.stock.serializers import ProduitSerializer


def _make_company(slug='wir97-co', nom='WIR97 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestWir97UniteFkSource(TestCase):
    def setUp(self):
        self.company = _make_company()
        UniteMesure.seed_defaults(self.company)  # unité, m, kg, …

    def _produit(self, unite_stock='kg', sku='P1'):
        return Produit.objects.create(
            company=self.company, nom=sku, sku=sku,
            prix_vente=Decimal('10'), quantite_stock=1,
            unite_stock=unite_stock)

    def test_creation_auto_links_fk_from_code(self):
        # Un produit créé avec un code présent au référentiel relie sa FK — sans
        # backfill.
        p = self._produit('kg')
        self.assertIsNotNone(p.unite_id)
        self.assertEqual(p.unite.code, 'kg')
        # Le libellé affiché vient DE LA FK (référentiel), pas du code brut.
        data = ProduitSerializer(p).data
        self.assertEqual(data['unite_stock_display'], 'Kilogramme')

    def test_changing_code_relinks_fk(self):
        # Passer le code MAÎTRE d'une unité référencée à une autre re-relie la
        # FK (pas de libellé périmé).
        p = self._produit('kg')
        p.unite_stock = 'm'
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.unite.code, 'm')
        self.assertEqual(ProduitSerializer(p).data['unite_stock_display'], 'Mètre')

    def test_unreferenced_code_leaves_fk_null_and_falls_back(self):
        # Un code sans unité active correspondante → FK nulle, repli sur le code
        # brut (aucune régression).
        p = self._produit('carton', sku='P2')
        self.assertIsNone(p.unite_id)
        self.assertEqual(ProduitSerializer(p).data['unite_stock_display'], 'carton')

    def test_unite_stock_stays_master(self):
        # Le CharField reste MAÎTRE : la FK n'écrase jamais le code saisi.
        p = self._produit('kg')
        self.assertEqual(p.unite_stock, 'kg')

    def test_inactive_referentiel_unit_not_linked(self):
        # Une unité désactivée n'est pas reliée (repli code brut).
        UniteMesure.objects.filter(
            company=self.company, code='kg').update(actif=False)
        p = self._produit('kg', sku='P3')
        self.assertIsNone(p.unite_id)
        self.assertEqual(ProduitSerializer(p).data['unite_stock_display'], 'kg')

    def test_partial_save_of_unite_only_is_not_resynced(self):
        # Le backfill (``save(update_fields=['unite'])``) n'est jamais re-synchro
        # (idempotence préservée).
        p = self._produit('kg')
        # Simule un backfill posant une unité arbitraire sans toucher le code.
        autre = UniteMesure.objects.get(company=self.company, code='m')
        p.unite = autre
        p.save(update_fields=['unite'])
        p.refresh_from_db()
        # La FK posée explicitement est conservée (pas de resync sur ce chemin).
        self.assertEqual(p.unite.code, 'm')
