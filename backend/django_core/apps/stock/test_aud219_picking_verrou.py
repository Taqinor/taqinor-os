"""AUD219 — `prelever_ligne_picking` ne perd plus un prélèvement concurrent.

Défaut d'origine : la vue chargeait la `LignePicking` AVANT d'entrer en
transaction, et le service incrémentait `quantite_prelevee` sur CETTE copie
mémoire, sans verrou ni expression `F()`. Deux scanners sur la même ligne
lisaient donc le même `quantite_prelevee` et le second écrasait le premier —
lost update : de la marchandise prélevée physiquement n'était jamais comptée.

Le test reproduit exactement cela sans concurrence réelle : deux copies
Python distinctes de la même ligne (ce que deux requêtes HTTP obtiennent), la
seconde étant STALE au moment de son prélèvement.

Run :
    python manage.py test apps.stock.test_aud219_picking_verrou -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Produit, VaguePicking
from apps.stock.models_wms import LignePicking
from apps.stock.services import (
    creer_vague_depuis_besoins, lancer_vague, prelever_ligne_picking,
)

User = get_user_model()


def make_company(slug='aud219-co', nom='AUD219 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud219Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud219_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD219', sku='AUD219-1',
            prix_achat=Decimal('900'), prix_vente=Decimal('1400'),
            quantite_stock=100)
        self.vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 10}])
        lancer_vague(self.vague)
        self.ligne = self.vague.lignes.first()

    def _copie(self):
        """Ce que voit une seconde requête HTTP : sa propre copie mémoire."""
        return LignePicking.objects.get(pk=self.ligne.pk)


class TestPrelevementConcurrent(Aud219Base):
    def test_deux_scans_simultanes_s_additionnent(self):
        scanner_a = self._copie()
        scanner_b = self._copie()   # lue AVANT le prélèvement de A : stale

        prelever_ligne_picking(ligne=scanner_a, quantite=4, user=self.admin)
        prelever_ligne_picking(ligne=scanner_b, quantite=3, user=self.admin)

        self.ligne.refresh_from_db()
        # 4 + 3 = 7. Avant AUD219 : 3 (le prélèvement de A était écrasé).
        self.assertEqual(self.ligne.quantite_prelevee, 7)

    def test_le_second_scan_ne_peut_pas_depasser_le_reste(self):
        scanner_a = self._copie()
        scanner_b = self._copie()

        prelever_ligne_picking(ligne=scanner_a, quantite=8, user=self.admin)
        with self.assertRaises(ValueError):
            # Reste réel : 2 — la copie stale en croyait 10 disponibles.
            prelever_ligne_picking(
                ligne=scanner_b, quantite=5, user=self.admin)

        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.quantite_prelevee, 8)

    def test_cloture_automatique_quand_tout_est_servi(self):
        prelever_ligne_picking(
            ligne=self._copie(), quantite=6, user=self.admin)
        prelever_ligne_picking(
            ligne=self._copie(), quantite=4, user=self.admin)

        self.vague.refresh_from_db()
        self.assertEqual(self.vague.statut, VaguePicking.Statut.TERMINEE)

    def test_quantite_invalide_refusee(self):
        for invalide in (0, -1, 'abc', None):
            with self.assertRaises(ValueError):
                prelever_ligne_picking(
                    ligne=self._copie(), quantite=invalide, user=self.admin)
