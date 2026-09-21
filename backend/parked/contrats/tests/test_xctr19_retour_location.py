"""Tests XCTR19 — Retour de location : retards, frais automatiques, inspection.

Couvre : détection de retard, frais calculés au bon nombre de jours à la
clôture, inspection avec dommage → ligne de facture + ticket SAV, inspection
sans dommage → rien de plus.
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
        company=company, nom=kwargs.pop('nom', 'Nacelle'),
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


class DetectionRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr19-detect', 'Detect')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre(self.company, self.client_obj, self.produit)

    def test_pas_en_retard_si_reservee(self):
        self.assertFalse(
            self.ordre.est_en_retard(today=date(2026, 7, 20)))

    def test_en_retard_si_enlevee_et_date_depassee(self):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        self.assertTrue(self.ordre.est_en_retard(today=date(2026, 7, 12)))
        self.assertEqual(self.ordre.jours_de_retard(today=date(2026, 7, 12)), 3)

    def test_pas_en_retard_avant_echeance(self):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        self.assertFalse(self.ordre.est_en_retard(today=date(2026, 7, 8)))

    def test_selector_ordres_en_retard(self):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        from apps.contrats import selectors

        en_retard = selectors.ordres_location_en_retard(
            self.company, today=date(2026, 7, 15))
        self.assertIn(self.ordre, list(en_retard))

        pas_encore = selectors.ordres_location_en_retard(
            self.company, today=date(2026, 7, 8))
        self.assertNotIn(self.ordre, list(pas_encore))


class ClotureFraisRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr19-cloture', 'Cloture')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        # Dates RELATIVES à aujourd'hui : la transition « retournée » pose
        # date_retour_reelle = aujourd'hui — avec l'ancienne date absolue
        # (2026-07-09), le test « sans retard » devenait faux dès le
        # lendemain de son écriture (bombe à retardement calendaire).
        from django.utils import timezone
        aujourdhui = timezone.now().date()
        delta = __import__('datetime').timedelta
        self.ordre = make_ordre(
            self.company, self.client_obj, self.produit,
            date_reservation=aujourdhui - delta(days=4),
            date_enlevement_prevue=aujourdhui - delta(days=2),
            date_retour_prevue=aujourdhui + delta(days=2),
            frais_retard_jour=Decimal('100'))

    def _retourner_avec_retard(self, jours_retard):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        self.ordre.date_retour_reelle = (
            self.ordre.date_retour_prevue
            + __import__('datetime').timedelta(days=jours_retard))
        self.ordre.statut = OrdreLocation.Statut.RETOURNEE
        self.ordre.save(update_fields=['date_retour_reelle', 'statut'])

    def test_cloture_sans_retard_aucun_frais(self):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)
        services.cloturer_ordre_location(self.ordre)
        self.ordre.refresh_from_db()
        self.assertIsNone(self.ordre.frais_retard_montant)
        self.assertEqual(self.ordre.statut, OrdreLocation.Statut.CLOTUREE)

    def test_cloture_avec_retard_facture_montant_exact(self):
        self._retourner_avec_retard(3)
        services.cloturer_ordre_location(self.ordre)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.frais_retard_montant, Decimal('300'))
        self.assertIsNotNone(self.ordre.frais_retard_facture_id)
        self.assertEqual(self.ordre.statut, OrdreLocation.Statut.CLOTUREE)

    def test_cloture_avant_retour_refusee(self):
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        with self.assertRaises(services.RetourLocationError):
            services.cloturer_ordre_location(self.ordre)


class InspectionRetourTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr19-inspect', 'Inspect')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre(self.company, self.client_obj, self.produit)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.ENLEVEE)
        services.changer_statut_ordre_location(
            self.ordre, OrdreLocation.Statut.RETOURNEE)

    def test_inspection_sans_dommage_ne_facture_rien(self):
        resultat = services.inspecter_retour(
            self.ordre, checklist={'pneus': 'ok'}, releve_compteur='1234h')
        self.assertIsNone(resultat['facture'])
        self.assertIsNone(resultat['ticket_id'])
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.inspection_checklist, {'pneus': 'ok'})
        self.assertIsNone(self.ordre.inspection_facture_id)
        self.assertIsNone(self.ordre.inspection_ticket_sav_id)

    def test_inspection_avec_dommage_facture_et_ticket(self):
        resultat = services.inspecter_retour(
            self.ordre, checklist={'moteur': 'endommage'},
            dommages_montant=Decimal('1200'),
            motif_dommages='Fuite hydraulique')
        self.assertIsNotNone(resultat['facture'])
        self.assertIsNotNone(resultat['ticket_id'])
        self.ordre.refresh_from_db()
        self.assertEqual(
            self.ordre.inspection_dommages_montant, Decimal('1200'))
        self.assertIsNotNone(self.ordre.inspection_facture_id)
        self.assertIsNotNone(self.ordre.inspection_ticket_sav_id)


class RetourLocationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xctr19-api', 'Api')
        self.user = make_user(self.company, 'xctr19-api')
        self.client_obj = make_client(self.company)
        self.produit = make_produit(self.company)
        self.ordre = make_ordre(
            self.company, self.client_obj, self.produit,
            frais_retard_jour=Decimal('50'))

    def test_en_retard_endpoint(self):
        api = auth(self.user)
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'enlevee'}, format='json')
        resp = api.get(f'{BASE}en-retard/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_cloturer_endpoint(self):
        api = auth(self.user)
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'enlevee'}, format='json')
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'retournee'}, format='json')
        resp = api.post(f'{BASE}{self.ordre.id}/cloturer/', {})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'cloturee')

    def test_inspecter_endpoint_avec_dommage(self):
        api = auth(self.user)
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'enlevee'}, format='json')
        api.post(
            f'{BASE}{self.ordre.id}/changer-statut/',
            {'statut': 'retournee'}, format='json')
        resp = api.post(
            f'{BASE}{self.ordre.id}/inspecter/',
            {'checklist': {'carrosserie': 'endommage'},
             'dommages_montant': '400', 'motif_dommages': 'Choc'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['ticket_id'])
