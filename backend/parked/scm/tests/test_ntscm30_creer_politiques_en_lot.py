"""NTSCM30 — Assistant guidé « Créer une politique de stock » (en lot).

Critère d'acceptation : sélectionner 5 produits et valider crée 5
``PolitiqueStock`` cohérentes en un seul appel, testé côté service."""
from decimal import Decimal

from django.test import TestCase

from apps.scm.models import PolitiqueStock
from apps.scm.services import creer_politiques_en_lot
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class CreerPolitiquesEnLotTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-politiques-lot', 'Supply Politiques Lot')
        self.admin = make_user(self.company, 'scm-politiques-lot-admin', 'admin')
        self.produits = [
            Produit.objects.create(
                company=self.company, nom=f'Produit {i}', prix_vente=100,
                quantite_stock=10)
            for i in range(5)
        ]

    def test_cree_5_politiques_en_un_appel(self):
        politiques = creer_politiques_en_lot(
            self.produits, Decimal('92'), self.company)
        self.assertEqual(len(politiques), 5)
        self.assertEqual(
            PolitiqueStock.objects.filter(company=self.company).count(), 5)
        for politique in politiques:
            self.assertEqual(politique.service_level_pct, Decimal('92'))

    def test_ne_reecrase_pas_un_niveau_deja_personnalise(self):
        # Premier passage : crée avec 92%.
        creer_politiques_en_lot([self.produits[0]], Decimal('92'), self.company)
        politique = PolitiqueStock.objects.get(
            company=self.company, produit=self.produits[0])
        politique.service_level_pct = Decimal('99')
        politique.save(update_fields=['service_level_pct'])

        # Second passage (même produit, niveau différent proposé) : l'override
        # acheteur (99%) n'est jamais écrasé.
        creer_politiques_en_lot([self.produits[0]], Decimal('80'), self.company)
        politique.refresh_from_db()
        self.assertEqual(politique.service_level_pct, Decimal('99'))

    def test_endpoint_creer_en_lot(self):
        resp = auth(self.admin).post(
            '/api/django/scm/politiques-stock/creer-en-lot/',
            {'produit_ids': [p.id for p in self.produits], 'service_level_pct': 90},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_politiques'], 5)

    def test_endpoint_sans_produit_ids_renvoie_400(self):
        resp = auth(self.admin).post(
            '/api/django/scm/politiques-stock/creer-en-lot/',
            {'produit_ids': [], 'service_level_pct': 90}, format='json')
        self.assertEqual(resp.status_code, 400)
