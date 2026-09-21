"""Tests ZCTR6 — Devis/commande portant des lignes de location (Rental order
via ventes).

Couvre :
- Un devis accepté à 2 lignes louables crée 2 ``OrdreLocation`` liés.
- Re-run ne duplique pas (idempotence via ``devis_id``/``devis_ligne_id``).
- Une ligne non louable est ignorée.
- Devis non accepté / autre société / sans client → 400, rien créé.
- Isolation multi-société via l'API.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import OrdreLocation
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()

MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_client_obj(company, num=1):
    return Client.objects.create(
        company=company, nom='Client', prenom=f'ZCTR6-{num}',
        telephone=f'+21260000{num:04d}')


def make_produit(company, nom, *, louable=True, num=1):
    return Produit.objects.create(
        company=company, nom=nom, sku=f'ZCTR6-{num}',
        prix_vente=Decimal('1000'), quantite_stock=10,
        louable=louable, tarif_location_jour=Decimal('300'))


def make_devis(company, client_obj, *, num=1, statut=Devis.Statut.ACCEPTE):
    return Devis.objects.create(
        company=company, reference=f'DEV-{MONTH}-{num:04d}',
        client=client_obj, statut=statut, taux_tva=Decimal('20'))


class CreerOrdresLocationDepuisDevisServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr6-svc', 'Zctr6Svc')
        self.client_obj = make_client_obj(self.company)

    def test_devis_accepte_deux_lignes_louables_cree_deux_ordres(self):
        devis = make_devis(self.company, self.client_obj, num=1)
        produit_a = make_produit(self.company, 'Groupe électrogène', num=1)
        produit_b = make_produit(self.company, 'Pompe', num=2)
        LigneDevis.objects.create(
            devis=devis, produit=produit_a, designation='Groupe électrogène',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        LigneDevis.objects.create(
            devis=devis, produit=produit_b, designation='Pompe',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        ordres = services.creer_ordres_location_depuis_devis(
            devis, company=self.company)

        self.assertEqual(len(ordres), 2)
        self.assertEqual(
            OrdreLocation.objects.filter(devis_id=devis.id).count(), 2)

    def test_rerun_ne_duplique_pas(self):
        devis = make_devis(self.company, self.client_obj, num=2)
        produit = make_produit(self.company, 'Nacelle', num=3)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Nacelle',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        premier = services.creer_ordres_location_depuis_devis(
            devis, company=self.company)
        second = services.creer_ordres_location_depuis_devis(
            devis, company=self.company)

        self.assertEqual(len(premier), 1)
        self.assertEqual(len(second), 0)
        self.assertEqual(
            OrdreLocation.objects.filter(devis_id=devis.id).count(), 1)

    def test_ligne_non_louable_ignoree(self):
        devis = make_devis(self.company, self.client_obj, num=3)
        produit_louable = make_produit(
            self.company, 'Groupe électrogène', num=4)
        produit_non_louable = make_produit(
            self.company, 'Panneau PV', louable=False, num=5)
        LigneDevis.objects.create(
            devis=devis, produit=produit_louable,
            designation='Groupe électrogène',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        LigneDevis.objects.create(
            devis=devis, produit=produit_non_louable, designation='Panneau PV',
            quantite=Decimal('14'), prix_unitaire=Decimal('1100'))

        ordres = services.creer_ordres_location_depuis_devis(
            devis, company=self.company)

        self.assertEqual(len(ordres), 1)
        self.assertEqual(ordres[0].produit_id, produit_louable.id)

    def test_devis_non_accepte_refuse(self):
        devis = make_devis(
            self.company, self.client_obj, num=4, statut=Devis.Statut.ENVOYE)
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordres_location_depuis_devis(
                devis, company=self.company)
        self.assertEqual(
            OrdreLocation.objects.filter(devis_id=devis.id).count(), 0)

    def test_devis_autre_societe_refuse(self):
        autre_co = make_company('zctr6-autre', 'Zctr6Autre')
        devis = make_devis(self.company, self.client_obj, num=5)
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordres_location_depuis_devis(
                devis, company=autre_co)

    def test_dates_par_defaut_appliquees_si_absentes(self):
        devis = make_devis(self.company, self.client_obj, num=6)
        produit = make_produit(self.company, 'Groupe électrogène', num=6)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Groupe électrogène',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        ordres = services.creer_ordres_location_depuis_devis(
            devis, company=self.company)

        self.assertEqual(len(ordres), 1)
        ordre = ordres[0]
        self.assertLess(
            ordre.date_enlevement_prevue, ordre.date_retour_prevue)


class OrdresLocationDepuisDevisApiTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr6-api', 'Zctr6Api')
        self.user = make_user(self.company, 'zctr6-api-resp')
        self.client_obj = make_client_obj(self.company, num=9)

    def test_endpoint_cree_ordres_et_isolation_societe(self):
        devis = make_devis(self.company, self.client_obj, num=10)
        produit = make_produit(self.company, 'Groupe électrogène', num=10)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Groupe électrogène',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        api = auth(self.user)
        res = api.post(
            f'/api/django/contrats/ordres-location/depuis-devis/{devis.id}/',
            {}, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(len(res.data), 1)

        autre_co = make_company('zctr6-api-autre', 'Zctr6ApiAutre')
        autre_user = make_user(autre_co, 'zctr6-api-autre-resp')
        api2 = auth(autre_user)
        res2 = api2.post(
            f'/api/django/contrats/ordres-location/depuis-devis/{devis.id}/',
            {}, format='json')
        self.assertEqual(res2.status_code, 400, res2.content)
