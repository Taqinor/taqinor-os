"""AUD220 — une ligne de picking PAR LOT du plan résolu (FEFO/FIFO).

Défaut d'origine : `_casier_pour_ligne` ne retenait que la TÊTE du plan produit
par `resoudre_allocation_picking` — un besoin couvert par DEUX lots FEFO
donnait UNE ligne agrégée portant le premier lot. Le lot enregistré sur la
ligne ne représentait donc pas ce qui serait réellement prélevé, et FEFO était
contourné en pratique (le magasinier n'avait aucune instruction sur le second
lot).

Run :
    python manage.py test apps.stock.test_aud220_picking_multilot -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Categorie, LotEntrepot, Produit
from apps.stock.services import creer_vague_depuis_besoins

User = get_user_model()


def make_company(slug='aud220-co', nom='AUD220 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud220Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud220_admin', password='x', role_legacy='admin',
            company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Batteries AUD220',
            strategie_picking_defaut=Categorie.StrategiePicking.FEFO)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie AUD220', sku='AUD220-1',
            categorie=self.categorie, prix_achat=Decimal('3000'),
            prix_vente=Decimal('4500'), quantite_stock=20)

    def _lot(self, numero, quantite, peremption):
        return LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot=numero,
            date_peremption=peremption, quantite_recue=quantite,
            quantite_restante=quantite)


class TestVagueMultiLot(Aud220Base):
    def test_un_besoin_sur_deux_lots_donne_deux_lignes(self):
        proche = self._lot('LOT-A', 4, datetime.date(2026, 10, 1))
        lointain = self._lot('LOT-B', 10, datetime.date(2027, 4, 1))

        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 6}])

        lignes = list(vague.lignes.order_by('id'))
        # Avant AUD220 : UNE ligne de 6 portant LOT-A.
        self.assertEqual(len(lignes), 2)
        self.assertEqual([li.lot_id for li in lignes],
                         [proche.id, lointain.id])
        self.assertEqual([li.quantite_demandee for li in lignes], [4, 2])
        # La quantité totale demandée reste celle du besoin.
        self.assertEqual(sum(li.quantite_demandee for li in lignes), 6)

    def test_un_seul_lot_suffisant_donne_une_ligne(self):
        lot = self._lot('LOT-A', 10, datetime.date(2026, 10, 1))

        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 6}])

        lignes = list(vague.lignes.all())
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].lot_id, lot.id)
        self.assertEqual(lignes[0].quantite_demandee, 6)

    def test_lots_insuffisants_le_reliquat_reste_demande(self):
        self._lot('LOT-A', 2, datetime.date(2026, 10, 1))

        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 5}])

        lignes = list(vague.lignes.order_by('id'))
        self.assertEqual(len(lignes), 2)
        self.assertIsNone(lignes[1].lot_id)   # reliquat sans lot
        self.assertEqual(sum(li.quantite_demandee for li in lignes), 5)

    def test_produit_sans_lot_garde_une_ligne_unique(self):
        """Comportement historique : sans lot suivi, une ligne libre."""
        libre = Produit.objects.create(
            company=self.company, nom='Câble AUD220', sku='AUD220-2',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=50)

        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': libre.id, 'quantite': 7}])

        lignes = list(vague.lignes.all())
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0].lot_id)
        self.assertEqual(lignes[0].quantite_demandee, 7)
