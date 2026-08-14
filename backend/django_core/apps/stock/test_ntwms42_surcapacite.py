"""NTWMS42 — alertes de sur-stockage par zone (passives, planifiées).

Critère d'acceptation testé : une zone qui franchit 95 % de capacité
déclenche une NOTIFICATION sans aucune action manuelle de l'utilisateur — et
une zone sans capacité déclarée n'est jamais signalée.

Run :
    python manage.py test apps.stock.test_ntwms42_surcapacite -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Produit
from apps.stock.selectors import zones_en_surcapacite
from apps.stock.tasks import alerter_surcapacite_zones_task

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms42Base(TestCase):
    def setUp(self):
        from apps.installations.models import (
            BinAffectation, BinLocation, CategorieStockage,
        )

        self.company = make_company('ntwms42-co', 'NTWMS42 Co')
        self.admin = User.objects.create_user(
            username='ntwms42_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms42_normal', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS42', is_principal=True)
        categorie = CategorieStockage.objects.create(
            company=self.company, nom='Rayonnage 100 NTWMS42', qte_max=100)

        self.pleine = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='F-01-01', zone='F', allee='01', casier='01', ordre=10,
            categorie=categorie)
        self.vide = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='V-01-01', zone='V', allee='01', casier='01', ordre=20,
            categorie=categorie)
        self.sans_capacite = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='N-01-01', zone='N', allee='01', casier='01', ordre=30)

        self.produit = Produit.objects.create(
            company=self.company, nom='Câble NTWMS42', sku='CAB-NTWMS42',
            prix_achat=Decimal('10'), prix_vente=Decimal('15'),
            quantite_stock=500)
        BinAffectation.objects.create(
            company=self.company, bin=self.pleine, produit=self.produit,
            quantite=97)
        BinAffectation.objects.create(
            company=self.company, bin=self.vide, produit=self.produit,
            quantite=20)
        BinAffectation.objects.create(
            company=self.company, bin=self.sans_capacite,
            produit=self.produit, quantite=9999)


class Ntwms42SelecteurTests(Ntwms42Base):
    def test_une_zone_au_dessus_du_seuil_est_alertee(self):
        alertes = zones_en_surcapacite(self.company)
        zones = [a['zone'] for a in alertes]
        self.assertEqual(zones, ['F'])
        self.assertEqual(alertes[0]['taux_pct'], '97')
        self.assertEqual(alertes[0]['seuil_pct'], '95')

    def test_une_zone_sous_le_seuil_nest_pas_alertee(self):
        self.assertNotIn(
            'V', [a['zone'] for a in zones_en_surcapacite(self.company)])

    def test_une_zone_sans_capacite_declaree_nest_jamais_alertee(self):
        self.assertNotIn(
            'N', [a['zone'] for a in zones_en_surcapacite(self.company)])

    def test_le_seuil_est_configurable(self):
        zones = [a['zone'] for a in zones_en_surcapacite(
            self.company, seuil_pct='20')]
        self.assertIn('F', zones)
        self.assertIn('V', zones)


class Ntwms42TacheTests(Ntwms42Base):
    def test_la_tache_notifie_sans_action_manuelle(self):
        from apps.notifications.models import Notification

        resultat = alerter_surcapacite_zones_task()

        self.assertEqual(resultat.get(self.company.id), 1)
        self.assertTrue(Notification.objects.filter(
            company=self.company,
            link__startswith=f'stock-surcapacite-{self.company.id}-',
        ).exists())

    def test_la_tache_ne_notifie_quune_fois_par_jour(self):
        alerter_surcapacite_zones_task()
        second = alerter_surcapacite_zones_task()
        self.assertEqual(second.get(self.company.id), 0)

    def test_la_tache_ne_notifie_pas_une_societe_sans_zone_saturee(self):
        from apps.installations.models import BinAffectation

        BinAffectation.objects.filter(bin=self.pleine).update(quantite=10)
        resultat = alerter_surcapacite_zones_task()
        self.assertEqual(resultat.get(self.company.id), 0)


class Ntwms42EndpointTests(Ntwms42Base):
    URL = '/api/django/stock/entrepot/alertes-surcapacite/'

    def test_endpoint_liste_les_zones_saturees(self):
        res = auth(self.admin).get(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual([z['zone'] for z in res.data['zones']], ['F'])

    def test_endpoint_refuse_un_role_normal(self):
        self.assertEqual(auth(self.normal).get(self.URL).status_code, 403)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)
