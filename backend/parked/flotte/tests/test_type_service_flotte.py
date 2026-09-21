"""Tests ZCTR10 — Référentiel des types de service/entretien flotte.

Couvre :
- Le référentiel ``ReferentielFlotte.Domaine.TYPE_SERVICE`` (CRUD via l'API
  ``/referentiels/?domaine=type_service``, additif, pas de régression sur les
  autres domaines).
- FK nullable ``OrdreReparation.type_service`` : validation same-company +
  domaine (jamais un domaine hardcodé), API + modèle.
- Le rapport XFLT7 (``analyse_couts_report``) gagne ``group_by='type_service'``
  et regroupe correctement, un OR non typé tombant sous 'non_categorise'.
- Le ledger XFLT3 (``ledger_vehicule``) remonte le type sur chaque ligne de
  réparation.
- Le seeder ``seed_referentiels_flotte`` crée les 8 types standard,
  idempotent.
"""
import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.management.commands.seed_referentiels_flotte import (
    seed_referentiels_flotte_for_company,
)
from apps.flotte.models import (
    ActifFlotte, OrdreReparation, ReferentielFlotte, Vehicule,
)
from apps.flotte.selectors import analyse_couts_report, ledger_vehicule

User = get_user_model()

URL_REF = '/api/django/flotte/referentiels/'
URL_OR = '/api/django/flotte/ordres-reparation/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def make_vehicule(company, immat='ZCTR10', km=0):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie='diesel',
        kilometrage=km)


def make_type_service(company, code='vidange', libelle='Vidange'):
    return ReferentielFlotte.objects.create(
        company=company, domaine=ReferentielFlotte.Domaine.TYPE_SERVICE,
        code=code, libelle=libelle)


class TypeServiceModelTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr10-model', 'ZCTR10 Model')
        self.veh = make_vehicule(self.co)
        self.actif = ActifFlotte.objects.create(company=self.co, vehicule=self.veh)

    def test_type_service_meme_societe_ok(self):
        type_service = make_type_service(self.co)
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif, type_service=type_service,
            date_ouverture=datetime.date.today())
        ordre.full_clean()  # ne lève pas.

    def test_type_service_autre_societe_rejete(self):
        autre = make_company('zctr10-model-b', 'ZCTR10 Model B')
        type_service_b = make_type_service(autre)
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif, type_service=type_service_b,
            date_ouverture=datetime.date.today())
        with self.assertRaises(ValidationError):
            ordre.full_clean()

    def test_type_service_mauvais_domaine_rejete(self):
        """Un référentiel d'un AUTRE domaine (ex. énergie) n'est pas un type
        de service valide — jamais un domaine hardcodé, toujours le référentiel."""
        mauvais_domaine = ReferentielFlotte.objects.create(
            company=self.co, domaine=ReferentielFlotte.Domaine.ENERGIE,
            code='diesel', libelle='Diesel')
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif, type_service=mauvais_domaine,
            date_ouverture=datetime.date.today())
        with self.assertRaises(ValidationError):
            ordre.full_clean()

    def test_sans_type_service_ok(self):
        """Absence de type = "non catégorisé", aucune régression."""
        ordre = OrdreReparation(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date.today())
        ordre.full_clean()


class TypeServiceApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('zctr10-api-a', 'ZCTR10 Api A')
        self.co_b = make_company('zctr10-api-b', 'ZCTR10 Api B')
        self.admin_a = make_user(self.co_a, 'zctr10-admin-a', 'admin')
        self.veh = make_vehicule(self.co_a)
        self.actif = ActifFlotte.objects.create(company=self.co_a, vehicule=self.veh)

    def test_crud_type_service_via_referentiel(self):
        resp = auth(self.admin_a).post(URL_REF, {
            'domaine': 'type_service', 'code': 'freins', 'libelle': 'Freins',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['domaine_display'], 'Type de service / entretien')

    def test_filter_referentiels_by_type_service(self):
        make_type_service(self.co_a, 'vidange', 'Vidange')
        ReferentielFlotte.objects.create(
            company=self.co_a, domaine=ReferentielFlotte.Domaine.ENERGIE,
            code='diesel', libelle='Diesel')
        resp = auth(self.admin_a).get(f'{URL_REF}?domaine=type_service')
        self.assertEqual([r['code'] for r in rows(resp)], ['vidange'])

    def test_create_or_avec_type_service(self):
        type_service = make_type_service(self.co_a)
        resp = auth(self.admin_a).post(URL_OR, {
            'actif_flotte': self.actif.id,
            'type_service': type_service.id,
            'date_ouverture': '2026-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_service_libelle'], 'Vidange')

    def test_create_or_type_service_autre_societe_refuse(self):
        type_service_b = make_type_service(self.co_b)
        resp = auth(self.admin_a).post(URL_OR, {
            'actif_flotte': self.actif.id,
            'type_service': type_service_b.id,
            'date_ouverture': '2026-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_or_type_service_mauvais_domaine_refuse(self):
        mauvais = ReferentielFlotte.objects.create(
            company=self.co_a, domaine=ReferentielFlotte.Domaine.ENERGIE,
            code='diesel', libelle='Diesel')
        resp = auth(self.admin_a).post(URL_OR, {
            'actif_flotte': self.actif.id,
            'type_service': mauvais.id,
            'date_ouverture': '2026-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_or_sans_type_service_non_categorise(self):
        resp = auth(self.admin_a).post(URL_OR, {
            'actif_flotte': self.actif.id,
            'date_ouverture': '2026-06-10',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['type_service_libelle'])

    def test_filtre_ordres_par_type_service(self):
        type_service = make_type_service(self.co_a)
        OrdreReparation.objects.create(
            company=self.co_a, actif_flotte=self.actif, type_service=type_service,
            date_ouverture=datetime.date.today())
        OrdreReparation.objects.create(
            company=self.co_a, actif_flotte=self.actif,
            date_ouverture=datetime.date.today())
        resp = auth(self.admin_a).get(f'{URL_OR}?type_service={type_service.id}')
        self.assertEqual(len(rows(resp)), 1)


class RapportCoutsTypeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr10-rapport', 'ZCTR10 Rapport')
        self.veh = make_vehicule(self.co, 'RAP', km=1000)
        self.actif = ActifFlotte.objects.create(company=self.co, vehicule=self.veh)
        self.vidange = make_type_service(self.co, 'vidange', 'Vidange')
        self.freins = make_type_service(self.co, 'freins', 'Freins')

    def test_group_by_type_service(self):
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif, type_service=self.vidange,
            date_ouverture=datetime.date(2026, 6, 1), cout_main_oeuvre=100)
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif, type_service=self.freins,
            date_ouverture=datetime.date(2026, 6, 2), cout_main_oeuvre=200)
        # Un OR NON catégorisé.
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date(2026, 6, 3), cout_main_oeuvre=50)

        result = analyse_couts_report(self.co, group_by='type_service')
        totaux = {p['cle']: p['total'] for p in result['pivot']}
        self.assertEqual(totaux['Vidange'], 100.0)
        self.assertEqual(totaux['Freins'], 200.0)
        self.assertEqual(totaux['non_categorise'], 50.0)

    def test_ledger_remonte_le_type_service(self):
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif, type_service=self.vidange,
            date_ouverture=datetime.date(2026, 6, 1), cout_main_oeuvre=100)
        ledger = ledger_vehicule(self.co, self.veh.id)
        lignes_reparation = [
            ligne for ligne in ledger['lignes'] if ligne['source'] == 'reparation']
        self.assertEqual(len(lignes_reparation), 1)
        self.assertEqual(
            lignes_reparation[0]['type_service_libelle'], 'Vidange')

    def test_ledger_type_service_none_si_non_categorise(self):
        OrdreReparation.objects.create(
            company=self.co, actif_flotte=self.actif,
            date_ouverture=datetime.date(2026, 6, 1), cout_main_oeuvre=50)
        ledger = ledger_vehicule(self.co, self.veh.id)
        lignes_reparation = [
            ligne for ligne in ledger['lignes'] if ligne['source'] == 'reparation']
        self.assertIsNone(lignes_reparation[0]['type_service_libelle'])
        self.assertIsNone(lignes_reparation[0]['type_service_id'])


class SeedTypeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('zctr10-seed', 'ZCTR10 Seed')

    def test_seed_creates_8_types_service(self):
        seed_referentiels_flotte_for_company(self.co)
        qs = ReferentielFlotte.objects.filter(
            company=self.co, domaine=ReferentielFlotte.Domaine.TYPE_SERVICE)
        self.assertEqual(qs.count(), 8)
        self.assertTrue(qs.filter(code='vidange').exists())
        self.assertTrue(qs.filter(code='controle_technique').exists())

    def test_seed_idempotent(self):
        out = StringIO()
        call_command(
            'seed_referentiels_flotte', company='zctr10-seed', stdout=out)
        before = ReferentielFlotte.objects.filter(
            company=self.co,
            domaine=ReferentielFlotte.Domaine.TYPE_SERVICE).count()
        call_command(
            'seed_referentiels_flotte', company='zctr10-seed', stdout=out)
        after = ReferentielFlotte.objects.filter(
            company=self.co,
            domaine=ReferentielFlotte.Domaine.TYPE_SERVICE).count()
        self.assertEqual(before, after)
        self.assertEqual(after, 8)
