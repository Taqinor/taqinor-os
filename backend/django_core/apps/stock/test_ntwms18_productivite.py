"""NTWMS18 — suivi de productivité entrepôt (aucun nouveau modèle).

Critère d'acceptation testé : un responsable voit le nombre de lignes traitées
par opérateur ET par type d'opération sur une période donnée.

Toutes les dates sont FIXES et injectées : la suite ne lit jamais l'horloge.

Run :
    python manage.py test apps.stock.test_ntwms18_productivite -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import MouvementStock, Produit
from apps.stock.selectors import productivite_operateur

User = get_user_model()

DEBUT = datetime.date(2026, 3, 1)
FIN = datetime.date(2026, 3, 31)
HORS_PERIODE = datetime.date(2026, 1, 15)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _horodater(mouvement, jour):
    """`date` est `auto_now_add` : on repositionne l'horodatage par UPDATE
    (aware, jamais naïf) pour tester une période sans dépendre de l'horloge."""
    instant = timezone.make_aware(
        datetime.datetime.combine(jour, datetime.time(9, 30)),
        timezone.get_default_timezone())
    MouvementStock.objects.filter(id=mouvement.id).update(date=instant)


class Ntwms18Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms18-co', 'NTWMS18 Co')
        self.autre = make_company('ntwms18-autre', 'NTWMS18 Autre')
        self.admin = User.objects.create_user(
            username='ntwms18_admin', password='x', role_legacy='admin',
            company=self.company)
        self.magasinier = User.objects.create_user(
            username='ntwms18_magasinier', password='x', role_legacy='normal',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS18',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=100)
        self.api = auth(self.admin)

    def _mouvement(self, user, type_mouvement, jour):
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=type_mouvement, quantite=1,
            quantite_avant=100, quantite_apres=101, created_by=user)
        _horodater(mouvement, jour)
        return mouvement


class TestProductiviteOperateur(Ntwms18Base):
    def test_compte_par_operateur_et_par_type(self):
        self._mouvement(self.magasinier, 'entree', datetime.date(2026, 3, 4))
        self._mouvement(self.magasinier, 'entree', datetime.date(2026, 3, 5))
        self._mouvement(self.magasinier, 'sortie', datetime.date(2026, 3, 6))
        self._mouvement(self.admin, 'transfert', datetime.date(2026, 3, 7))

        lignes = productivite_operateur(
            self.company, debut=DEBUT, fin=FIN)

        self.assertEqual(len(lignes), 2)
        # Le plus productif d'abord.
        self.assertEqual(lignes[0]['operateur_id'], self.magasinier.id)
        self.assertEqual(lignes[0]['total'], 3)
        self.assertEqual(lignes[0]['operations']['entree'], 2)
        self.assertEqual(lignes[0]['operations']['sortie'], 1)
        self.assertEqual(lignes[1]['operations']['transfert'], 1)

    def test_hors_periode_exclu(self):
        self._mouvement(self.magasinier, 'entree', HORS_PERIODE)
        self.assertEqual(
            productivite_operateur(self.company, debut=DEBUT, fin=FIN), [])
        # Sans bornes, le même mouvement est bien compté.
        self.assertEqual(
            productivite_operateur(self.company)[0]['total'], 1)

    def test_colisage_scanne_compte_comme_operation(self):
        from apps.stock.models import UniteLogistique, UniteLogistiqueLigne

        unite = UniteLogistique.objects.create(
            company=self.company, sscc='1' * 18)
        ligne = UniteLogistiqueLigne.objects.create(
            company=self.company, unite=unite, produit=self.produit,
            quantite=2, scanne_par=self.magasinier)
        UniteLogistiqueLigne.objects.filter(id=ligne.id).update(
            scanne_le=timezone.make_aware(
                datetime.datetime.combine(
                    datetime.date(2026, 3, 9), datetime.time(11, 0)),
                timezone.get_default_timezone()))

        lignes = productivite_operateur(self.company, debut=DEBUT, fin=FIN)
        self.assertEqual(lignes[0]['operations']['colisage'], 1)

    def test_autre_societe_jamais_comptee(self):
        intrus = User.objects.create_user(
            username='ntwms18_intrus', password='x', role_legacy='normal',
            company=self.autre)
        produit_autre = Produit.objects.create(
            company=self.autre, nom='Autre', sku='AUT-NTWMS18',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        mouvement = MouvementStock.objects.create(
            company=self.autre, produit=produit_autre,
            type_mouvement='entree', quantite=1, quantite_avant=0,
            quantite_apres=1, created_by=intrus)
        _horodater(mouvement, datetime.date(2026, 3, 4))

        self.assertEqual(
            productivite_operateur(self.company, debut=DEBUT, fin=FIN), [])


class TestEndpointProductivite(Ntwms18Base):
    URL = '/api/django/stock/entrepot/productivite/'

    def test_responsable_voit_le_classement(self):
        self._mouvement(self.magasinier, 'entree', datetime.date(2026, 3, 4))
        reponse = self.api.get(
            self.URL, {'debut': DEBUT.isoformat(), 'fin': FIN.isoformat()})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['debut'], DEBUT.isoformat())
        self.assertEqual(len(reponse.data['operateurs']), 1)
        self.assertEqual(reponse.data['operateurs'][0]['total'], 1)

    def test_dates_illisibles_ignorees_sans_500(self):
        reponse = self.api.get(self.URL, {'debut': 'pas-une-date'})
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data['debut'])

    def test_utilisateur_normal_refuse(self):
        reponse = auth(self.magasinier).get(self.URL)
        self.assertEqual(reponse.status_code, 403)
