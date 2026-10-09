"""ERR-ASTK39 — comptage cyclique : le théorique est re-snapshoté À LA SAISIE.

Constat (vérifie ASTK, 09/10) : ``ajouter-ligne`` figeait ``quantite_theorique``
au stock du moment ; une SORTIE survenue entre l'ajout et la saisie du compté
était alors re-comptée dans l'écart posté par ``terminer`` (stock 120 → sortie
20 → 100, compté 100, terminer → AJUSTEMENT −20 → stock 80, faux).

Règle D-ASTK « stock à la saisie » : à la saisie de ``quantite_comptee``, le
théorique = stock live (``stock.services.theorique_a_la_saisie``).

Run :
    python manage.py test apps.installations.tests.test_astk39_comptage_cyclique_snapshot -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import ComptageLigne, SessionComptage
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import record_stock_movement
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


class ComptageCycliqueSnapshotSaisieTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk39-co-{n}', nom=f'ASTK39 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk39-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5 kW', sku=f'ASTK39-{n}',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=100)
        self.session = SessionComptage.objects.create(
            company=self.company, reference=f'CYC-ASTK39-{n}',
            statut=SessionComptage.Statut.EN_COURS, created_by=self.user)

    def _sortie(self, qte):
        p = Produit.objects.get(pk=self.produit.pk)
        record_stock_movement(
            company=self.company, produit=p,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=qte, quantite_avant=p.quantite_stock,
            quantite_apres=p.quantite_stock - qte,
            reference='SOR-ASTK39', note='Sortie entre ajout et saisie',
            created_by=self.user)

    def _scenario(self, compte):
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/ajouter-ligne/',
            {'produit': self.produit.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['quantite_theorique'], 100)
        ligne_id = r.data['id']
        # Sortie légitime APRÈS l'ajout de la ligne, AVANT la saisie.
        self._sortie(20)
        r = self.api.patch(
            f'{BASE}/comptage-lignes/{ligne_id}/',
            {'quantite_comptee': compte, 'compte': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/')
        self.assertEqual(r.status_code, 200, r.content)
        return ComptageLigne.objects.get(pk=ligne_id)

    def _ajustements(self):
        return MouvementStock.objects.filter(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)

    def test_sortie_entre_ajout_et_saisie_non_recomptee(self):
        ligne = self._scenario(compte=80)
        self.assertEqual(ligne.quantite_theorique, 80)
        self.produit.refresh_from_db()
        # Avant le correctif : 80 + (80 − 100) = 60 (sortie comptée 2 fois).
        self.assertEqual(self.produit.quantite_stock, 80)
        self.assertFalse(self._ajustements().exists())

    def test_ecart_reel_poste_depuis_le_stock_a_la_saisie(self):
        ligne = self._scenario(compte=77)
        self.assertEqual(ligne.quantite_theorique, 80)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 77)
        mvt = self._ajustements().get()
        self.assertEqual(mvt.quantite, 3)
        self.assertEqual(mvt.quantite_avant, 80)
        self.assertEqual(mvt.quantite_apres, 77)

    def test_theorique_non_modifiable_par_le_client(self):
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/ajouter-ligne/',
            {'produit': self.produit.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.api.patch(
            f'{BASE}/comptage-lignes/{r.data["id"]}/',
            {'quantite_comptee': 90, 'quantite_theorique': 5},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['quantite_theorique'], 100)
