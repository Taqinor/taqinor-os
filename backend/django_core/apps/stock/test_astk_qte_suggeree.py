"""ASTK207 (C-ASTK-053, MVT-21) — UNE quantité suggérée pour trois lectures.

Reproduction MVT-21 : produit stock 2, seuil 6, quantite_reappro_cible 20, un
BCF ouvert de 5. AVANT : a-reapprovisionner = 13, previsions-reappro = 20
(cible brute), catalogue « ~5 » (seuil × 2 − stock, calcul front). APRÈS :
les trois lisent `quantite_suggeree_nette` → 13.

Run :
    python manage.py test apps.stock.test_astk_qte_suggeree -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    MouvementStock, Produit,
)
from apps.stock.services import quantite_suggeree_nette

User = get_user_model()


class QteSuggereeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='astk207', slug='astk207')
        self.admin = User.objects.create_user(
            username='astk207-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK207')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK207', sku='ASTK207-OND',
            prix_vente=Decimal('3000'), prix_achat=Decimal('1500'),
            quantite_stock=2, seuil_alerte=6, quantite_reappro_cible=20)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK207-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1500'), quantite_recue=0)
        # Une sortie récente : le produit entre dans previsions-reappro.
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=4, quantite_avant=6, quantite_apres=2,
            reference='SORTIE-ASTK207')
        MouvementStock.objects.filter(pk=mvt.pk).update(
            date=timezone.now() - datetime.timedelta(days=10))

    def _reappro(self):
        resp = self.api.get('/api/django/stock/produits/a-reapprovisionner/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return next(i for i in resp.json()
                    if i['produit_id'] == self.produit.id)

    def _previsions(self):
        resp = self.api.get('/api/django/stock/produits/previsions-reappro/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return next(i for i in resp.json()
                    if i['produit_id'] == self.produit.id)

    def _catalogue(self):
        resp = self.api.get(f'/api/django/stock/produits/{self.produit.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_trois_lectures_meme_valeur(self):
        self.assertEqual(self._reappro()['quantite_suggere'], 13)
        self.assertEqual(self._reappro()['quantite_suggeree'], 13)
        self.assertEqual(self._previsions()['quantite_suggeree'], 13)
        self.assertEqual(self._catalogue()['quantite_suggeree'], 13)
        self.assertEqual(
            quantite_suggeree_nette(self.company, self.produit), 13)

    def test_previsions_retranche_disponible_et_en_commande(self):
        item = self._previsions()
        self.assertEqual(item['cible'], 20)
        self.assertEqual(item['disponible'], 2)
        self.assertEqual(item['en_commande'], 5)

    def test_sans_cible_repli_seuil_double(self):
        Produit.objects.filter(pk=self.produit.pk).update(
            quantite_reappro_cible=0)
        self.produit.refresh_from_db()
        # 6 × 2 − 2 − 5 = 5
        self.assertEqual(self._reappro()['quantite_suggere'], 5)
        self.assertEqual(self._catalogue()['quantite_suggeree'], 5)
        self.assertEqual(
            quantite_suggeree_nette(self.company, self.produit), 5)

    def test_jamais_negative(self):
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=40)
        self.assertEqual(self._catalogue()['quantite_suggeree'], 0)

    def test_liste_sans_requete_par_produit(self):
        for n in range(5):
            Produit.objects.create(
                company=self.company, nom=f'P{n}', sku=f'ASTK207-P{n}',
                prix_vente=Decimal('10'), prix_achat=Decimal('5'),
                quantite_stock=1, seuil_alerte=3)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as avec_6:
            self.api.get('/api/django/stock/produits/?page_size=200')
        for n in range(5, 15):
            Produit.objects.create(
                company=self.company, nom=f'P{n}', sku=f'ASTK207-P{n}',
                prix_vente=Decimal('10'), prix_achat=Decimal('5'),
                quantite_stock=1, seuil_alerte=3)
        with CaptureQueriesContext(connection) as avec_16:
            self.api.get('/api/django/stock/produits/?page_size=200')
        # Le champ quantite_suggeree n'ajoute aucune requête PAR produit.
        requetes_profil = [
            q for q in avec_16.captured_queries
            if 'profilsaisonnier' in q['sql'].lower()]
        self.assertLessEqual(len(requetes_profil), 1)
        self.assertGreater(len(avec_6.captured_queries), 0)
