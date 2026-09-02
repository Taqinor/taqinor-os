"""AUD218 — un lot d'entrepôt est UNIQUE par (société, produit, numéro de lot).

Défaut d'origine : `services.alimenter_lot_entrepot` fait un
``get_or_create(company, produit, numero_lot)`` alors que ``LotEntrepot.Meta``
ne portait que deux Index NON uniques. Deux confirmations de réception
concurrentes du même lot créaient donc deux `LotEntrepot` distincts (course
documentée de `get_or_create`) : la traçabilité du lot se scindait en silence
et FEFO/rappels/blocages qualité ne voyaient chacun qu'une moitié du lot.

Run :
    python manage.py test apps.stock.test_aud218_lot_entrepot_unique -v 2
"""
import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.stock.models import LotEntrepot, Produit
from apps.stock.services import alimenter_lot_entrepot


def make_company(slug='aud218-co', nom='AUD218 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestLotEntrepotUnique(TestCase):
    def setUp(self):
        self.company = make_company()
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie AUD218', sku='AUD218-1',
            prix_achat=Decimal('3000'), prix_vente=Decimal('4500'),
            quantite_stock=0)

    def _alimenter(self, quantite, reference, peremption=None):
        return alimenter_lot_entrepot(
            company=self.company, produit=self.produit, numero_lot='LOT-A',
            date_peremption=peremption, quantite=quantite,
            reference_reception=reference)

    def test_contrainte_declaree_sur_le_modele(self):
        noms = {c.name for c in LotEntrepot._meta.constraints}
        self.assertIn('lotentrepot_unique_company_produit_lot', noms)

    def test_doublon_refuse_en_base(self):
        self._alimenter(10, 'REC-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LotEntrepot.objects.create(
                    company=self.company, produit=self.produit,
                    numero_lot='LOT-A', quantite_recue=5,
                    quantite_restante=5, reference_reception='REC-2')

    def test_deux_receptions_du_meme_lot_s_additionnent(self):
        self._alimenter(10, 'REC-1')
        self._alimenter(4, 'REC-2')

        lots = LotEntrepot.objects.filter(
            company=self.company, produit=self.produit, numero_lot='LOT-A')
        self.assertEqual(lots.count(), 1)
        lot = lots.get()
        self.assertEqual(lot.quantite_recue, 14)
        self.assertEqual(lot.quantite_restante, 14)

    def test_peremption_completee_a_la_seconde_reception(self):
        self._alimenter(10, 'REC-1')
        self._alimenter(4, 'REC-2', peremption=datetime.date(2027, 6, 30))

        lot = LotEntrepot.objects.get(
            company=self.company, produit=self.produit, numero_lot='LOT-A')
        self.assertEqual(lot.date_peremption, datetime.date(2027, 6, 30))

    def test_lots_distincts_restent_distincts(self):
        self._alimenter(10, 'REC-1')
        alimenter_lot_entrepot(
            company=self.company, produit=self.produit, numero_lot='LOT-B',
            date_peremption=None, quantite=7, reference_reception='REC-2')

        self.assertEqual(
            LotEntrepot.objects.filter(produit=self.produit).count(), 2)
