"""Tests XCTR18 — Caution (dépôt de garantie) sur location.

Couvre : cycle caution complet (encaissée → restituée / retenue partielle),
restitution avant retour refusée, retenue → ligne de facture exacte, journal
des transitions.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import CautionLocationLog, OrdreLocation
from apps.crm.models import Client
from apps.stock.models import Produit

User = get_user_model()

BASE = '/api/django/contrats/ordres-location/'


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


def make_produit(company, **kwargs):
    return Produit.objects.create(
        company=company, nom=kwargs.pop('nom', 'Groupe électrogène'),
        prix_vente=Decimal('100'), louable=True,
        tarif_location_jour=Decimal('500'), **kwargs)


def make_client(company, nom='Client X'):
    return Client.objects.create(company=company, nom=nom)


def make_ordre(company, client, produit, **kwargs):
    return services.creer_ordre_location(
        company, client_id=client.id, produit=produit,
        date_reservation=kwargs.pop('date_reservation', date(2026, 7, 1)),
        date_enlevement_prevue=kwargs.pop(
            'date_enlevement_prevue', date(2026, 7, 5)),
        date_retour_prevue=kwargs.pop('date_retour_prevue', date(2026, 7, 9)),
        **kwargs)


class CautionServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr18-svc', 'Svc')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre(self.company, self.client_obj, self.produit)

    def test_encaisser_caution(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        self.ordre.refresh_from_db()
        self.assertEqual(
            self.ordre.caution_statut, OrdreLocation.CautionStatut.ENCAISSEE)
        self.assertEqual(self.ordre.caution_montant, Decimal('2000'))
        self.assertTrue(
            CautionLocationLog.objects.filter(ordre_location=self.ordre).exists())

    def test_encaisser_montant_invalide_refuse(self):
        with self.assertRaises(services.CautionLocationError):
            services.encaisser_caution(self.ordre, montant=0)

    def test_encaisser_deux_fois_refuse(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        with self.assertRaises(services.CautionLocationError):
            services.encaisser_caution(self.ordre, montant=Decimal('1000'))

    def test_restitution_avant_retour_refusee(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        with self.assertRaises(services.CautionLocationError):
            services.restituer_caution(self.ordre)

    def test_restitution_apres_retour_ok(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)
        services.restituer_caution(self.ordre)
        self.ordre.refresh_from_db()
        self.assertEqual(
            self.ordre.caution_statut, OrdreLocation.CautionStatut.RESTITUEE)

    def test_retenue_partielle_avant_retour_refusee(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        with self.assertRaises(services.CautionLocationError):
            services.retenir_caution_partielle(
                self.ordre, montant_retenu=Decimal('500'), motif='Casse')

    def test_retenue_partielle_cree_ligne_facture_exacte(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)

        resultat = services.retenir_caution_partielle(
            self.ordre, montant_retenu=Decimal('600'), motif='Casse capot')

        self.ordre.refresh_from_db()
        self.assertEqual(
            self.ordre.caution_statut,
            OrdreLocation.CautionStatut.RETENUE_PARTIELLE)
        self.assertEqual(self.ordre.caution_retenue, Decimal('600'))

        facture = resultat['facture']
        self.assertEqual(facture.montant_ttc, Decimal('600.00'))

    def test_retenue_superieure_a_caution_refusee(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)
        with self.assertRaises(services.CautionLocationError):
            services.retenir_caution_partielle(
                self.ordre, montant_retenu=Decimal('5000'), motif='Casse')

    def test_retenue_sans_motif_refusee(self):
        services.encaisser_caution(self.ordre, montant=Decimal('2000'))
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)
        with self.assertRaises(services.CautionLocationError):
            services.retenir_caution_partielle(
                self.ordre, montant_retenu=Decimal('100'), motif='')


class CautionApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr18-api', 'Api')
        self.user = make_user(self.company, 'xctr18-api')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre(self.company, self.client_obj, self.produit)

    def test_encaisser_via_api(self):
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.ordre.id}/caution/encaisser/',
            {'montant': '1500'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['caution_statut'], 'encaissee')

    def test_restituer_avant_retour_400(self):
        api = auth(self.user)
        api.post(
            f'{BASE}{self.ordre.id}/caution/encaisser/',
            {'montant': '1500'}, format='json')
        resp = api.post(f'{BASE}{self.ordre.id}/caution/restituer/', {})
        self.assertEqual(resp.status_code, 400)

    def test_retenir_via_api_apres_retour(self):
        api = auth(self.user)
        api.post(
            f'{BASE}{self.ordre.id}/caution/encaisser/',
            {'montant': '1500'}, format='json')
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'enlevee'}, format='json')
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'retournee'}, format='json')
        resp = api.post(
            f'{BASE}{self.ordre.id}/caution/retenir/',
            {'montant_retenu': '300', 'motif': 'Rayures'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('facture_id', resp.data)
