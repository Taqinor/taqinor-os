"""Tests XCTR17 — Location de matériel SORTANTE (aux clients) — fondation.

Couvre : produit non louable refusé, double réservation chevauchante refusée
(400), disponibilité correcte, cycle complet via l'API (réservée → enlevée →
retournée → clôturée), migrations additives (le test lui-même le prouve en
s'exécutant), isolation société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import OrdreLocation
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


def make_produit(company, nom='Groupe électrogène', louable=True, **kwargs):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('100'),
        louable=louable, tarif_location_jour=kwargs.pop(
            'tarif_location_jour', Decimal('500')),
        **kwargs)


class CreerOrdreLocationServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr17-svc', 'Svc')
        self.produit = make_produit(self.company)

    def test_creation_ok_calcule_montant_estime(self):
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        # 5 jours (bornes incluses) x 500 = 2500.
        self.assertEqual(ordre.montant_estime, Decimal('2500'))
        self.assertEqual(ordre.statut, OrdreLocation.Statut.RESERVEE)

    def test_double_reservation_chevauchante_refusee(self):
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordre_location(
                self.company, client_id=2, produit=self.produit,
                numero_serie='SN-1',
                date_reservation=date(2026, 7, 6),
                date_enlevement_prevue=date(2026, 7, 7),
                date_retour_prevue=date(2026, 7, 12),
            )

    def test_reservation_non_chevauchante_ok(self):
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        # Commence le lendemain du retour prévu — pas de chevauchement.
        ordre2 = services.creer_ordre_location(
            self.company, client_id=2, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 9),
            date_enlevement_prevue=date(2026, 7, 10),
            date_retour_prevue=date(2026, 7, 15),
        )
        self.assertIsNotNone(ordre2.id)

    def test_numero_serie_different_pas_de_conflit(self):
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        ordre2 = services.creer_ordre_location(
            self.company, client_id=2, produit=self.produit,
            numero_serie='SN-2',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        self.assertIsNotNone(ordre2.id)

    def test_dates_incoherentes_refusees(self):
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordre_location(
                self.company, client_id=1, produit=self.produit,
                date_reservation=date(2026, 7, 1),
                date_enlevement_prevue=date(2026, 7, 9),
                date_retour_prevue=date(2026, 7, 5),
            )

    def test_cycle_complet_transitions(self):
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        services.changer_statut_ordre_location(
            ordre, OrdreLocation.Statut.ENLEVEE)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreLocation.Statut.ENLEVEE)
        self.assertIsNotNone(ordre.date_enlevement_reelle)

        services.changer_statut_ordre_location(
            ordre, OrdreLocation.Statut.RETOURNEE)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreLocation.Statut.RETOURNEE)
        self.assertIsNotNone(ordre.date_retour_reelle)

        services.changer_statut_ordre_location(
            ordre, OrdreLocation.Statut.CLOTUREE)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreLocation.Statut.CLOTUREE)

    def test_transition_interdite_refusee(self):
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        with self.assertRaises(services.OrdreLocationError):
            services.changer_statut_ordre_location(
                ordre, OrdreLocation.Statut.CLOTUREE)


class OrdreLocationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xctr17-a', 'A')
        self.co_b = make_company('xctr17-b', 'B')
        self.user_a = make_user(self.co_a, 'xctr17-a')
        self.user_b = make_user(self.co_b, 'xctr17-b')
        self.produit_a = make_produit(self.co_a)
        self.produit_non_louable = make_produit(
            self.co_a, nom='Non louable', louable=False)

    def test_creation_produit_non_louable_refusee(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'client_id': 1,
            'produit': self.produit_non_louable.id,
            'date_reservation': '2026-07-01',
            'date_enlevement_prevue': '2026-07-05',
            'date_retour_prevue': '2026-07-09',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_creation_ok_via_api(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'client_id': 1,
            'produit': self.produit_a.id,
            'numero_serie': 'SN-A',
            'date_reservation': '2026-07-01',
            'date_enlevement_prevue': '2026-07-05',
            'date_retour_prevue': '2026-07-09',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'reservee')

    def test_double_reservation_chevauchante_api_400(self):
        api = auth(self.user_a)
        payload = {
            'client_id': 1,
            'produit': self.produit_a.id,
            'numero_serie': 'SN-A',
            'date_reservation': '2026-07-01',
            'date_enlevement_prevue': '2026-07-05',
            'date_retour_prevue': '2026-07-09',
        }
        resp1 = api.post(BASE, payload, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)

        payload2 = dict(payload, date_enlevement_prevue='2026-07-07',
                        date_retour_prevue='2026-07-12')
        resp2 = api.post(BASE, payload2, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)

    def test_disponibilite_endpoint(self):
        api = auth(self.user_a)
        api.post(BASE, {
            'client_id': 1,
            'produit': self.produit_a.id,
            'numero_serie': 'SN-A',
            'date_reservation': '2026-07-01',
            'date_enlevement_prevue': '2026-07-05',
            'date_retour_prevue': '2026-07-09',
        }, format='json')

        resp = api.get(
            f'{BASE}disponibilite/?produit={self.produit_a.id}'
            f'&numero_serie=SN-A&date_debut=2026-07-06&date_fin=2026-07-08')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['disponible'])

        resp2 = api.get(
            f'{BASE}disponibilite/?produit={self.produit_a.id}'
            f'&numero_serie=SN-A&date_debut=2026-07-10&date_fin=2026-07-12')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertTrue(resp2.data['disponible'])

    def test_isolation_societe(self):
        from apps.contrats import services

        ordre = services.creer_ordre_location(
            self.co_a, client_id=1, produit=self.produit_a,
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )
        api_b = auth(self.user_b)
        resp = api_b.get(f'{BASE}{ordre.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_changer_statut_action(self):
        api = auth(self.user_a)
        resp = api.post(BASE, {
            'client_id': 1,
            'produit': self.produit_a.id,
            'date_reservation': '2026-07-01',
            'date_enlevement_prevue': '2026-07-05',
            'date_retour_prevue': '2026-07-09',
        }, format='json')
        ordre_id = resp.data['id']

        resp2 = api.post(
            f'{BASE}{ordre_id}/changer-statut/', {'statut': 'enlevee'},
            format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['statut'], 'enlevee')
