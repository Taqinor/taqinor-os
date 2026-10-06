"""ASTK39 — règle d'écart d'inventaire « stock à la saisie » (décision
fondateur ASTK37, 06/10/2026).

Constat C-ASTK-007 (sonde MVT-8) : ``generer_comptages_tournants`` figeait
``quantite_theorique`` au stock de la GÉNÉRATION. Une sortie de 20 entre la
génération (stock 100) et le comptage physique (80) donnait un écart de −20
appliqué au stock live 80 : stock final 60 au lieu de 80.

Règle tranchée : écart = compté − stock AU MOMENT où le compté est saisi.
Le théorique est donc re-snapshoté serveur à la saisie du compté.

Run :
    python manage.py test apps.stock.test_astk_ecart_inventaire_regle -v 2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import InventaireSession, MouvementStock, Produit
from apps.stock.services import (
    assurer_plans_comptage_tournant, generer_comptages_tournants,
    record_stock_movement,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
AUJOURD_HUI = datetime.date(2026, 10, 6)
BASE = '/api/django/stock/inventaire-sessions'


class EcartInventaireRegleTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk39-co-{n}', nom=f'ASTK39 Co {n}')
        self.admin = User.objects.create_user(
            username=f'astk39-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku=f'ASTK39-{n}',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=100)
        assurer_plans_comptage_tournant(self.company)
        generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        self.session = InventaireSession.objects.get(
            company=self.company, lignes__produit=self.produit)
        ligne = self.session.lignes.get(produit=self.produit)
        # Pré-remplissage à la génération : 100 / 100.
        self.assertEqual(
            (ligne.quantite_theorique, ligne.quantite_comptee), (100, 100))

    def _mouvement(self, type_mouvement, delta):
        p = Produit.objects.get(pk=self.produit.pk)
        record_stock_movement(
            company=self.company, produit=p, type_mouvement=type_mouvement,
            quantite=abs(delta), quantite_avant=p.quantite_stock,
            quantite_apres=p.quantite_stock + delta,
            reference='MVT-ASTK39', note='mouvement intermédiaire',
            created_by=self.admin)

    def _saisir(self, comptee):
        r = self.api.patch(
            f'{BASE}/{self.session.id}/',
            {'lignes': [{'produit': self.produit.id,
                         'quantite_comptee': comptee}]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r

    def _valider(self):
        r = self.api.post(f'{BASE}/{self.session.id}/valider/')
        self.assertEqual(r.status_code, 200, r.content)

    def test_sortie_entre_generation_et_saisie(self):
        """MVT-8 : génération 100, sortie 20 (live 80), compté 80 saisi."""
        self._mouvement(MouvementStock.TypeMouvement.SORTIE, -20)
        r = self._saisir(80)
        self.assertEqual(r.data['lignes'][0]['quantite_theorique'], 80)
        self._valider()
        self.produit.refresh_from_db()
        # Avant ASTK39 : 60 (théorique figé à la génération).
        self.assertEqual(self.produit.quantite_stock, 80)

    def test_mouvement_apres_saisie_conserve(self):
        """Le delta (AUD206/ASTK38) préserve un mouvement postérieur à la
        saisie : compté 95 sur stock 100, puis entrée +10 → 105."""
        self._saisir(95)
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, +10)
        self._valider()
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 105)

    def test_ligne_renvoyee_sans_resaisie_garde_son_snapshot(self):
        self._saisir(95)          # théorique 100
        self._mouvement(MouvementStock.TypeMouvement.SORTIE, -5)
        r = self._saisir(95)      # même compté : pas une nouvelle saisie
        self.assertEqual(r.data['lignes'][0]['quantite_theorique'], 100)

    def test_theorique_du_corps_ignore(self):
        r = self.api.patch(
            f'{BASE}/{self.session.id}/',
            {'lignes': [{'produit': self.produit.id, 'quantite_theorique': 7,
                         'quantite_comptee': 90}]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['lignes'][0]['quantite_theorique'], 100)

    def test_produit_autre_societe_refuse(self):
        autre = Company.objects.create(
            slug=f'astk39-autre-{next(_seq)}', nom='Autre')
        etranger = Produit.objects.create(
            company=autre, nom='X', sku=f'ASTK39-X-{next(_seq)}',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=50)
        r = self.api.patch(
            f'{BASE}/{self.session.id}/',
            {'lignes': [{'produit': etranger.id, 'quantite_comptee': 1}]},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
