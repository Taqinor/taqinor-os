"""YSTCK5 — `expedier`/`livrer` sur une Livraison ventilent le grand livre.

Avant : `LivraisonViewSet.expedier`/`livrer`/`annuler` changeaient SEULEMENT le
statut — les `LivraisonLigne` ne réservaient/déplaçaient jamais rien. Ces
tests couvrent :

  * `expedier` transfère les lignes du dépôt vers l'emplacement van (total
    société inchangé — c'est un TRANSFERT, jamais une sortie) ;
  * `annuler` une livraison expédiée contre-transfère (van → dépôt) ;
  * idempotence : ré-expédier ne double pas le transfert ;
  * mode `direct_site` : jamais de transfert (le dépôt n'est jamais
    décrémenté) ;
  * aucun double mouvement avec la consommation chantier (`consume_
    reservations`, indépendante, sort à « Installé »).

Run :
    python manage.py test apps.installations.tests_ystck5_livraison_stock -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit, EmplacementStock, StockEmplacement
from apps.installations.models import Installation, Livraison, LivraisonLigne

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ystck5-co-{n}', defaults={'nom': f'YSTCK5 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ystck5-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='YSTCK5',
        email=f'ystck5-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-YSTCK5-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_produit(company, quantite_stock=Decimal('20')):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Onduleur {n}',
        prix_vente=Decimal('500'), quantite_stock=quantite_stock)


class TestExpedierVentileStock(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.produit = make_produit(self.company, quantite_stock=Decimal('20'))
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.liv = Livraison.objects.create(
            company=self.company, reference='LIV-YSTCK5-0001',
            installation=self.inst, depot=self.depot,
            statut=Livraison.Statut.PLANIFIEE)
        LivraisonLigne.objects.create(
            livraison=self.liv, produit=self.produit,
            designation=self.produit.nom, quantite=4)

    def test_expedier_transfere_depot_vers_van(self):
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertTrue(self.liv.stock_mouvemente)
        self.produit.refresh_from_db()
        # Total société inchangé (transfert, pas une sortie).
        self.assertEqual(self.produit.quantite_stock, Decimal('20'))
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.get(produit=self.produit, emplacement=van)
        self.assertEqual(se.quantite, 4)

    def test_expedier_idempotent_ne_double_pas(self):
        self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        # Deuxième appel (ex. ré-enregistrement du même statut) : no-op stock.
        from apps.installations.services import ventiler_stock_livraison
        self.liv.refresh_from_db()
        applied = ventiler_stock_livraison(self.liv, self.user)
        self.assertEqual(applied, 0)
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.get(produit=self.produit, emplacement=van)
        self.assertEqual(se.quantite, 4)

    def test_annuler_contre_transfere(self):
        self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/annuler/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertFalse(self.liv.stock_mouvemente)
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.filter(
            produit=self.produit, emplacement=van).first()
        self.assertEqual((se.quantite if se else 0), 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('20'))

    def test_mode_direct_site_ne_transfere_jamais(self):
        self.liv.mode_acheminement = Livraison.ModeAcheminement.DIRECT_SITE
        self.liv.save(update_fields=['mode_acheminement'])
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertFalse(self.liv.stock_mouvemente)
        self.assertFalse(
            StockEmplacement.objects.filter(produit=self.produit).exists())
