"""ASTK204 / ASTK205 (C-ASTK-052) — la sortie d'un lot et le stock du
produit bougent ENSEMBLE.

Sonde MVT-17 (a) d'origine : ``POST lots-entrepot/<L>/sortir/ {quantite: 4}``
→ 200, lot restant 6, mais ``quantite_stock`` restait 10 et AUCUN
``MouvementStock`` n'était posé ; deux sorties concurrentes relisaient le
même restant (pas de verrou).

Aucun mock : vues, services et ``record_stock_movement`` réels.

Run :
    python manage.py test apps.stock.test_astk_lot_sortie -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import LotEntrepot, MouvementStock, Produit
from apps.stock.services import sortir_lot_entrepot

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class LotSortieTests(TestCase):
    def setUp(self):
        self.co = make_company('astk204-co', 'ASTK204 Co')
        self.resp = User.objects.create_user(
            username='astk204_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.api = auth_client(self.resp)
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie ASTK204', sku='ASTK204-1',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'),
            quantite_stock=10)
        self.lot = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-ASTK204',
            quantite_recue=10, quantite_restante=10,
            reference_reception='REC-ASTK204')

    def test_sortir_lot_cree_un_mouvement(self):
        r = self.api.post(
            f'/api/django/stock/lots-entrepot/{self.lot.id}/sortir/',
            {'quantite': 4}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['quantite_restante'], 6)
        # Persistance relue.
        self.lot.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 6)
        self.assertEqual(self.produit.quantite_stock, 6)
        mouvements = MouvementStock.objects.filter(
            company=self.co, produit=self.produit)
        self.assertEqual(mouvements.count(), 1)
        mvt = mouvements.get()
        self.assertEqual(mvt.type_mouvement,
                         MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mvt.quantite, 4)
        self.assertEqual(mvt.quantite_avant, 10)
        self.assertEqual(mvt.quantite_apres, 6)
        self.assertEqual(mvt.reference, 'LOT-ASTK204')

    def test_double_sortie_refusee_sous_verrou(self):
        """Deux lecteurs du MÊME lot (restant 10 en mémoire) : la seconde
        sortie de 6 relit le lot sous verrou et est refusée."""
        lecteur_1 = LotEntrepot.objects.get(pk=self.lot.pk)
        lecteur_2 = LotEntrepot.objects.get(pk=self.lot.pk)
        sortir_lot_entrepot(company=self.co, lot=lecteur_1, quantite=6)
        with self.assertRaises(ValueError):
            sortir_lot_entrepot(company=self.co, lot=lecteur_2, quantite=6)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 4)

    def test_sortie_refusee_ne_pose_aucun_mouvement(self):
        r = self.api.post(
            f'/api/django/stock/lots-entrepot/{self.lot.id}/sortir/',
            {'quantite': 11}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.lot.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(self.lot.quantite_restante, 10)
        self.assertEqual(self.produit.quantite_stock, 10)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())


class LotExpeditionTests(TestCase):
    """ASTK205 — l'expédition décrémente le lot assigné par le picking."""

    def setUp(self):
        from apps.stock.models_wms import LignePicking
        from apps.stock.services import (
            ajouter_ligne_unite_logistique, creer_expedition_transporteur,
            creer_unite_logistique, creer_vague_depuis_besoins,
            sceller_unite_logistique,
        )

        self.co = make_company('astk205-co', 'ASTK205 Co')
        self.resp = User.objects.create_user(
            username='astk205_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie ASTK205', sku='ASTK205-1',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'),
            quantite_stock=10)
        self.lot_a = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-A-205',
            quantite_recue=6, quantite_restante=6, reference_reception='R-A')
        self.lot_b = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-B-205',
            quantite_recue=4, quantite_restante=4, reference_reception='R-B')
        vague = creer_vague_depuis_besoins(
            company=self.co, user=self.resp,
            besoins=[{'produit_id': self.produit.id, 'quantite': 5}])
        # Ligne de picking déterministe : lot A × 5, déjà prélevée.
        ligne = LignePicking.objects.create(
            company=self.co, vague=vague, produit=self.produit,
            quantite_demandee=5, quantite_prelevee=5, lot=self.lot_a)
        colis = creer_unite_logistique(company=self.co)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=colis, produit=self.produit, quantite=5,
            ligne_picking=ligne)
        sceller_unite_logistique(unite=colis, user=self.resp)
        colis.refresh_from_db()
        self.expedition = creer_expedition_transporteur(
            company=self.co, unite=colis)

    def test_expedition_decremente_le_lot_picke(self):
        from unittest import mock

        from apps.stock.services import generer_etiquette_expedition

        with mock.patch('apps.stock.services_wms._stocker_etiquette',
                        return_value='stock/x/etiquettes/t.pdf'):
            generer_etiquette_expedition(
                expedition=self.expedition, user=self.resp)

        self.produit.refresh_from_db()
        self.lot_a.refresh_from_db()
        self.lot_b.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)
        self.assertEqual(self.lot_a.quantite_restante, 1)
        self.assertEqual(self.lot_b.quantite_restante, 4)
        # Σ lots = stock suivi par lot.
        self.assertEqual(
            self.lot_a.quantite_restante + self.lot_b.quantite_restante,
            self.produit.quantite_stock)


class SortieSansLotTests(TestCase):
    """ERR-ASTK205-SORTIE-SANS-LOT-REGISTRE — une SORTIE manuelle sans lot
    sur un produit suivi par lot reste permise, mais le registre la marque
    « Non affectée à un lot » et l'écart lots/stock est nommé."""

    def setUp(self):
        self.co = make_company('errastk205-co', 'ERR ASTK205 Co')
        self.resp = User.objects.create_user(
            username='errastk205_resp', password='x',
            role_legacy='admin', company=self.co)
        self.api = auth_client(self.resp)
        self.produit = Produit.objects.create(
            company=self.co, nom='Batterie ERR-ASTK205', sku='ERRASTK205-1',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'),
            quantite_stock=10)
        self.lot = LotEntrepot.objects.create(
            company=self.co, produit=self.produit, numero_lot='LOT-E205',
            quantite_recue=10, quantite_restante=10,
            reference_reception='R-E205')
        self.sans_lot = Produit.objects.create(
            company=self.co, nom='Câble ERR-ASTK205', sku='ERRASTK205-2',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=10)

    def _sortie(self, produit, quantite, note=''):
        return self.api.post('/api/django/stock/mouvements/', {
            'produit': produit.id, 'type_mouvement': 'sortie',
            'quantite': quantite, 'note': note}, format='json')

    def test_sortie_manuelle_sans_lot_marquee(self):
        from apps.stock.services_wms import (
            MENTION_SORTIE_SANS_LOT, ecart_lots_non_affecte,
        )
        r = self._sortie(self.produit, 3, note='Casse atelier')
        self.assertEqual(r.status_code, 201, r.content)
        mouvement = MouvementStock.objects.get(pk=r.data['id'])
        self.assertIn(MENTION_SORTIE_SANS_LOT, mouvement.note)
        self.assertIn('Casse atelier', mouvement.note)
        self.produit.refresh_from_db()
        self.lot.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)
        self.assertEqual(self.lot.quantite_restante, 10)
        # Écart nommé : 3 unités sorties sans lot.
        self.assertEqual(ecart_lots_non_affecte(self.co, self.produit), 3)

    def test_sortie_scannee_sans_lot_marquee(self):
        from apps.stock.services import enregistrer_mouvement_scanne
        from apps.stock.services_wms import MENTION_SORTIE_SANS_LOT
        mouvement = enregistrer_mouvement_scanne(
            company=self.co, user=self.resp, produit_id=self.produit.id,
            type_mouvement='sortie', quantite=2)
        mouvement.refresh_from_db()
        self.assertIn(MENTION_SORTIE_SANS_LOT, mouvement.note)

    def test_produit_sans_lot_note_inchangee(self):
        from apps.stock.services_wms import (
            MENTION_SORTIE_SANS_LOT, ecart_lots_non_affecte,
        )
        r = self._sortie(self.sans_lot, 3, note='Chantier')
        self.assertEqual(r.status_code, 201, r.content)
        mouvement = MouvementStock.objects.get(pk=r.data['id'])
        self.assertNotIn(MENTION_SORTIE_SANS_LOT, mouvement.note or '')
        self.assertEqual(ecart_lots_non_affecte(self.co, self.sans_lot), 0)
