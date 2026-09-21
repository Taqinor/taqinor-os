"""Tests XCTR20 — Location longue durée : facturation récurrente +
prolongation/écourtage.

Couvre : 3 cycles simulés = 3 factures sans doublon (garde XCTR5 réutilisée),
prolongation conflictuelle refusée, écourtage → avoir exact.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import CycleFacturationLog
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
        tarif_location_jour=Decimal('100'), **kwargs)


def make_client(company, nom='Client X'):
    return Client.objects.create(company=company, nom=nom)


def make_ordre_recurrent(company, client, produit, **kwargs):
    ordre = services.creer_ordre_location(
        company, client_id=client.id, produit=produit,
        date_reservation=kwargs.pop('date_reservation', date(2026, 1, 1)),
        date_enlevement_prevue=kwargs.pop(
            'date_enlevement_prevue', date(2026, 1, 5)),
        date_retour_prevue=kwargs.pop('date_retour_prevue', date(2027, 1, 5)),
        **kwargs)
    ordre.facturation_recurrente_active = True
    ordre.save(update_fields=['facturation_recurrente_active'])
    return ordre


class FacturationRecurrenteTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr20-fact', 'Fact')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre_recurrent(
            self.company, self.client_obj, self.produit)

    def test_trois_cycles_trois_factures_sans_doublon(self):
        f1 = services.facturer_ordre_location_recurrent(
            self.ordre, periode='2026-01')
        f2 = services.facturer_ordre_location_recurrent(
            self.ordre, periode='2026-02')
        f3 = services.facturer_ordre_location_recurrent(
            self.ordre, periode='2026-03')

        self.assertNotEqual(f1.id, f2.id)
        self.assertNotEqual(f2.id, f3.id)
        logs = CycleFacturationLog.objects.filter(
            source_type=CycleFacturationLog.SourceType.ORDRE_LOCATION,
            source_id=self.ordre.id, statut=CycleFacturationLog.Statut.GENERE)
        self.assertEqual(logs.count(), 3)

    def test_meme_periode_refuse_doublon(self):
        services.facturer_ordre_location_recurrent(
            self.ordre, periode='2026-01')
        with self.assertRaises(services.RejeuError):
            services.facturer_ordre_location_recurrent(
                self.ordre, periode='2026-01')

    def test_facturation_non_active_refusee(self):
        self.ordre.facturation_recurrente_active = False
        self.ordre.save(update_fields=['facturation_recurrente_active'])
        with self.assertRaises(services.RetourLocationError):
            services.facturer_ordre_location_recurrent(self.ordre)

    def test_sans_tarif_refusee(self):
        self.ordre.tarif_jour = None
        self.ordre.save(update_fields=['tarif_jour'])
        with self.assertRaises(services.RetourLocationError):
            services.facturer_ordre_location_recurrent(self.ordre)


class ProlongationEcourtageTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr20-prol', 'Prol')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),
        )

    def test_prolongation_ok_recalcule_montant(self):
        services.prolonger_ordre_location(
            self.ordre, nouvelle_date_retour=date(2026, 7, 14))
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.date_retour_prevue, date(2026, 7, 14))
        # 5 -> 14 juillet = 10 jours (bornes incluses) x 100.
        self.assertEqual(self.ordre.montant_estime, Decimal('1000'))

    def test_prolongation_conflictuelle_refusee(self):
        # Un second ordre réserve le créneau juste après le retour initial.
        services.creer_ordre_location(
            self.company, client_id=self.client_obj.id, produit=self.produit,
            numero_serie='',
            date_reservation=date(2026, 7, 9),
            date_enlevement_prevue=date(2026, 7, 10),
            date_retour_prevue=date(2026, 7, 15),
        )
        with self.assertRaises(services.OrdreLocationError):
            services.prolonger_ordre_location(
                self.ordre, nouvelle_date_retour=date(2026, 7, 12))

    def test_prolongation_date_anterieure_refusee(self):
        with self.assertRaises(services.OrdreLocationError):
            services.prolonger_ordre_location(
                self.ordre, nouvelle_date_retour=date(2026, 7, 8))

    def test_ecourtage_sans_facture_prealable_recalcule_seulement(self):
        resultat = services.ecourter_ordre_location(
            self.ordre, nouvelle_date_retour=date(2026, 7, 7))
        self.assertIsNone(resultat['avoir'])
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.date_retour_prevue, date(2026, 7, 7))
        # 5 -> 7 juillet = 3 jours x 100.
        self.assertEqual(self.ordre.montant_estime, Decimal('300'))

    def test_ecourtage_avec_facture_genere_avoir_exact(self):
        self.ordre.facturation_recurrente_active = True
        self.ordre.save(update_fields=['facturation_recurrente_active'])
        services.facturer_ordre_location_recurrent(
            self.ordre, periode='2026-07')

        resultat = services.ecourter_ordre_location(
            self.ordre, nouvelle_date_retour=date(2026, 7, 7))
        avoir = resultat['avoir']
        self.assertIsNotNone(avoir)
        # Delta = 2 jours x 100 = 200 TTC.
        self.assertEqual(avoir.montant_ttc, Decimal('200.00'))

    def test_ecourtage_date_posterieure_refusee(self):
        with self.assertRaises(services.OrdreLocationError):
            services.ecourter_ordre_location(
                self.ordre, nouvelle_date_retour=date(2026, 7, 12))


class LocationRecurrenteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr20-api', 'Api')
        self.user = make_user(self.company, 'xctr20-api')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre_recurrent(
            self.company, self.client_obj, self.produit)

    def test_facturer_cycle_endpoint(self):
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.ordre.id}/facturer-cycle/',
            {'periode': '2026-05'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('facture_id', resp.data)

    def test_prolonger_endpoint(self):
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.ordre.id}/prolonger/',
            {'nouvelle_date_retour': '2027-02-05'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_ecourter_endpoint(self):
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{self.ordre.id}/ecourter/',
            {'nouvelle_date_retour': '2026-06-01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
