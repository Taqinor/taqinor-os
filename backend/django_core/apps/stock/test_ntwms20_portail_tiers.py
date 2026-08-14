"""NTWMS20 — portail 3PL : visibilité du stock d'un dépositaire.

Critère d'acceptation testé : un client dépositaire consultant son lien voit
UNIQUEMENT ses propres quantités — jamais le reste du catalogue société,
jamais un autre dépositaire, jamais un autre locataire.

Run :
    python manage.py test apps.stock.test_ntwms20_portail_tiers -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, PortailTiersToken, Produit, StockEmplacement,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms20Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms20-co', 'NTWMS20 Co')
        self.autre = make_company('ntwms20-autre', 'NTWMS20 Autre')
        self.admin = User.objects.create_user(
            username='ntwms20_admin', password='x', role_legacy='admin',
            company=self.company)
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS20', is_principal=True)
        self.depot_alpha = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente Alpha',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Client Alpha')
        self.depot_beta = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente Beta',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Client Beta')
        self.produit_alpha = Produit.objects.create(
            company=self.company, nom='Panneau Alpha', sku='PA-NTWMS20',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=50)
        self.produit_beta = Produit.objects.create(
            company=self.company, nom='Panneau Beta', sku='PB-NTWMS20',
            prix_achat=Decimal('800'), prix_vente=Decimal('1100'),
            quantite_stock=50)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit_alpha,
            emplacement=self.depot_alpha, quantite=7)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit_beta,
            emplacement=self.depot_beta, quantite=11)
        self.jeton = PortailTiersToken.objects.create(
            company=self.company, tiers_nom='Client Alpha',
            cree_par=self.admin)
        self.api = auth(self.admin)
        self.public = APIClient()

    def _url(self, token=None):
        return (f'/api/django/stock/public/tiers/'
                f'{token or self.jeton.token}/solde/')


class TestPortailTiersPublic(Ntwms20Base):
    def test_le_depositaire_voit_uniquement_son_stock(self):
        reponse = self.public.get(self._url())

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['tiers_nom'], 'Client Alpha')
        self.assertEqual(reponse.data['total_unites'], 7)
        self.assertEqual(len(reponse.data['lignes']), 1)
        self.assertEqual(reponse.data['lignes'][0]['produit'],
                         'Panneau Alpha')
        # Aucun prix, aucune marge n'est exposé.
        self.assertNotIn('prix_achat', reponse.data['lignes'][0])
        self.assertNotIn('prix_vente', reponse.data['lignes'][0])

    def test_autre_depositaire_jamais_visible(self):
        contenu = str(self.public.get(self._url()).data)
        self.assertNotIn('Panneau Beta', contenu)
        self.assertNotIn('Client Beta', contenu)

    def test_stock_interne_jamais_expose(self):
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit_beta,
            emplacement=self.principal, quantite=40)
        reponse = self.public.get(self._url())
        self.assertEqual(reponse.data['total_unites'], 7)

    def test_jeton_revoque_404(self):
        self.jeton.revoked = True
        self.jeton.save(update_fields=['revoked'])
        self.assertEqual(self.public.get(self._url()).status_code, 404)

    def test_jeton_expire_404(self):
        self.jeton.expires_at = timezone.now() - datetime.timedelta(days=1)
        self.jeton.save(update_fields=['expires_at'])
        self.assertEqual(self.public.get(self._url()).status_code, 404)

    def test_jeton_inconnu_404_sans_fuite(self):
        reponse = self.public.get(self._url(token='inexistant'))
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn('Client Alpha', str(reponse.data))

    def test_reponse_est_noindex(self):
        reponse = self.public.get(self._url())
        self.assertIn('noindex', reponse['X-Robots-Tag'])

    def test_usage_horodate(self):
        self.assertIsNone(self.jeton.last_used_at)
        self.public.get(self._url())
        self.jeton.refresh_from_db()
        self.assertIsNotNone(self.jeton.last_used_at)


class TestAdministrationJetons(Ntwms20Base):
    URL = '/api/django/stock/portails-tiers/'

    def test_admin_cree_un_jeton_genere_serveur(self):
        reponse = self.api.post(self.URL, {'tiers_nom': 'Client Gamma'},
                                format='json')
        self.assertEqual(reponse.status_code, 201)
        self.assertTrue(len(reponse.data['token']) > 20)
        self.assertTrue(reponse.data['lien_public'].endswith('/solde/'))
        self.assertTrue(reponse.data['est_valide'])

    def test_tiers_nom_obligatoire(self):
        reponse = self.api.post(self.URL, {'tiers_nom': '  '}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_utilisateur_non_admin_refuse(self):
        normal = User.objects.create_user(
            username='ntwms20_normal', password='x', role_legacy='normal',
            company=self.company)
        self.assertEqual(auth(normal).get(self.URL).status_code, 403)

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms20_intrus', password='x', role_legacy='admin',
            company=self.autre)
        reponse = auth(intrus).get(self.URL)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)
