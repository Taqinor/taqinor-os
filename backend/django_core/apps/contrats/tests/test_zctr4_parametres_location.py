"""Tests ZCTR4 — Réglages de location : durée minimale, temps de sécurité
(padding) & frais de retard par défaut.

Couvre :
- Deux locations séparées de moins que le padding sont refusées.
- Une location plus courte que le minimum est refusée (message FR).
- Le frais de retard par défaut s'applique quand l'ordre ne le précise pas.
- Valeurs neutres (pas de ``ParametresLocation``, ou tout à 0/NULL) =
  comportement XCTR17/19 inchangé.
- API singleton ``GET``/``PATCH /parametres-location/courant/``.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import ParametresLocation
from apps.stock.models import Produit

User = get_user_model()

COURANT = '/api/django/contrats/parametres-location/courant/'


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


class DureeMinimaleTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr4-dur', 'Zctr4Dur')
        self.produit = make_produit(self.company)
        ParametresLocation.objects.create(
            company=self.company, duree_minimale_jours=5)

    def test_duree_inferieure_au_minimum_refusee(self):
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordre_location(
                self.company, client_id=1, produit=self.produit,
                numero_serie='SN-1',
                date_reservation=date(2026, 7, 1),
                date_enlevement_prevue=date(2026, 7, 5),
                date_retour_prevue=date(2026, 7, 7),  # 3 jours < 5
            )

    def test_duree_egale_au_minimum_acceptee(self):
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 9),  # 5 jours = minimum
        )
        self.assertIsNotNone(ordre.id)

    def test_sans_parametres_aucune_duree_minimale(self):
        autre_co = make_company('zctr4-dur-sans', 'Zctr4DurSans')
        produit = make_produit(autre_co)
        ordre = services.creer_ordre_location(
            autre_co, client_id=1, produit=produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 5),
            date_retour_prevue=date(2026, 7, 5),  # 1 jour, aucun minimum
        )
        self.assertIsNotNone(ordre.id)


class PaddingDisponibiliteTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr4-pad', 'Zctr4Pad')
        self.produit = make_produit(self.company)

    def test_deux_locations_separees_de_moins_que_le_padding_refusees(self):
        ParametresLocation.objects.create(
            company=self.company, temps_securite_heures=48)  # 2 jours
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 1),
            date_retour_prevue=date(2026, 7, 5),
        )
        # Démarre le lendemain du retour (7/6) — séparées d'1 jour < padding 2j.
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordre_location(
                self.company, client_id=2, produit=self.produit,
                numero_serie='SN-1',
                date_reservation=date(2026, 7, 6),
                date_enlevement_prevue=date(2026, 7, 6),
                date_retour_prevue=date(2026, 7, 10),
            )

    def test_deux_locations_separees_de_plus_que_le_padding_acceptees(self):
        ParametresLocation.objects.create(
            company=self.company, temps_securite_heures=24)  # 1 jour
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 1),
            date_retour_prevue=date(2026, 7, 5),
        )
        # 7/8 est séparé de 2 jours pleins du retour (7/5) > padding 1j.
        ordre2 = services.creer_ordre_location(
            self.company, client_id=2, produit=self.produit,
            numero_serie='SN-1',
            date_reservation=date(2026, 7, 8),
            date_enlevement_prevue=date(2026, 7, 8),
            date_retour_prevue=date(2026, 7, 12),
        )
        self.assertIsNotNone(ordre2.id)

    def test_sans_parametres_comportement_xctr17_strict_inchange(self):
        # Contigu (retour == enlèvement suivant) sans ParametresLocation créé
        # doit être refusé (chevauchement strict XCTR17, jour partagé).
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-2',
            date_reservation=date(2026, 8, 1),
            date_enlevement_prevue=date(2026, 8, 1),
            date_retour_prevue=date(2026, 8, 5),
        )
        with self.assertRaises(services.OrdreLocationError):
            services.creer_ordre_location(
                self.company, client_id=2, produit=self.produit,
                numero_serie='SN-2',
                date_reservation=date(2026, 8, 5),
                date_enlevement_prevue=date(2026, 8, 5),
                date_retour_prevue=date(2026, 8, 9),
            )
        # Le lendemain (pas de chevauchement, padding 0) est accepté.
        ordre = services.creer_ordre_location(
            self.company, client_id=2, produit=self.produit,
            numero_serie='SN-2',
            date_reservation=date(2026, 8, 6),
            date_enlevement_prevue=date(2026, 8, 6),
            date_retour_prevue=date(2026, 8, 9),
        )
        self.assertIsNotNone(ordre.id)

    def test_padding_zero_comportement_inchange(self):
        ParametresLocation.objects.create(
            company=self.company, temps_securite_heures=0)
        services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-3',
            date_reservation=date(2026, 9, 1),
            date_enlevement_prevue=date(2026, 9, 1),
            date_retour_prevue=date(2026, 9, 5),
        )
        # Le lendemain (pas de chevauchement) est accepté avec padding=0.
        ordre = services.creer_ordre_location(
            self.company, client_id=2, produit=self.produit,
            numero_serie='SN-3',
            date_reservation=date(2026, 9, 6),
            date_enlevement_prevue=date(2026, 9, 6),
            date_retour_prevue=date(2026, 9, 9),
        )
        self.assertIsNotNone(ordre.id)


class FraisRetardDefautTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr4-frais', 'Zctr4Frais')
        self.produit = make_produit(self.company)

    def test_frais_retard_defaut_applique_si_non_saisi(self):
        ParametresLocation.objects.create(
            company=self.company, frais_retard_jour_defaut=Decimal('150'))
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-4',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 1),
            date_retour_prevue=date(2026, 7, 5),
        )
        self.assertEqual(ordre.frais_retard_jour, Decimal('150'))

    def test_frais_retard_saisi_prevaut_sur_le_defaut(self):
        ParametresLocation.objects.create(
            company=self.company, frais_retard_jour_defaut=Decimal('150'))
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-5',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 1),
            date_retour_prevue=date(2026, 7, 5),
            frais_retard_jour=Decimal('300'),
        )
        self.assertEqual(ordre.frais_retard_jour, Decimal('300'))

    def test_sans_parametres_aucun_frais_par_defaut(self):
        ordre = services.creer_ordre_location(
            self.company, client_id=1, produit=self.produit,
            numero_serie='SN-6',
            date_reservation=date(2026, 7, 1),
            date_enlevement_prevue=date(2026, 7, 1),
            date_retour_prevue=date(2026, 7, 5),
        )
        self.assertIsNone(ordre.frais_retard_jour)


class ParametresLocationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr4-api', 'Zctr4Api')
        self.user = make_user(self.company, 'zctr4-api-resp')

    def test_get_courant_cree_a_la_volee(self):
        api = auth(self.user)
        res = api.get(COURANT)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(
            ParametresLocation.objects.filter(company=self.company).count(),
            1)

    def test_patch_courant_met_a_jour_et_company_posee_serveur(self):
        api = auth(self.user)
        res = api.patch(
            COURANT,
            {'duree_minimale_jours': 3, 'temps_securite_heures': 12,
             'company': 999},
            format='json')
        self.assertEqual(res.status_code, 200, res.content)
        parametres = ParametresLocation.objects.get(company=self.company)
        self.assertEqual(parametres.duree_minimale_jours, 3)
        self.assertEqual(parametres.temps_securite_heures, 12)
        self.assertEqual(parametres.company_id, self.company.id)  # pas 999

    def test_isolation_multi_societe(self):
        autre_co = make_company('zctr4-api-autre', 'Zctr4ApiAutre')
        ParametresLocation.objects.create(
            company=autre_co, duree_minimale_jours=99)
        api = auth(self.user)
        res = api.get(COURANT)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertNotEqual(res.data.get('duree_minimale_jours'), 99)
