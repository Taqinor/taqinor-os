"""Tests QHSE40 — IndicateurESG + export reporting.

Couvre :
* CRUD scopé société (``company`` posée côté serveur) ;
* ``atteinte_cible`` dérivé selon la tendance souhaitée ;
* FK ``bilan_carbone`` validé même-société ;
* sélecteur / action ``export`` (groupé par pilier, filtre année) ;
* filtres, rôle, isolation société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import BilanCarbone, IndicateurESG
from apps.qhse.selectors import export_esg

User = get_user_model()

ESG_URL = '/api/django/qhse/indicateurs-esg/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_esg(company, code='E1', pilier='environnement', valeur=None,
             cible=None, annee=2026, tendance='neutre'):
    return IndicateurESG.objects.create(
        company=company, code=code, libelle='Indicateur', pilier=pilier,
        valeur=valeur, cible=cible, annee=annee,
        tendance_souhaitee=tendance)


class IndicateurESGModelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-esg', 'CoEsg')

    def test_atteinte_cible_hausse(self):
        ind = make_esg(
            self.company, valeur=Decimal('80'), cible=Decimal('70'),
            tendance='hausse_favorable')
        self.assertTrue(ind.atteinte_cible)

    def test_atteinte_cible_baisse(self):
        ind = make_esg(
            self.company, valeur=Decimal('5'), cible=Decimal('10'),
            tendance='baisse_favorable')
        self.assertTrue(ind.atteinte_cible)

    def test_atteinte_cible_none_si_manquant(self):
        ind = make_esg(self.company, valeur=None, cible=Decimal('10'))
        self.assertIsNone(ind.atteinte_cible)


class ExportEsgSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-esg-exp', 'CoEsgExp')

    def test_export_groupe_par_pilier(self):
        make_esg(self.company, code='E1', pilier='environnement',
                 valeur=Decimal('80'), cible=Decimal('70'),
                 tendance='hausse_favorable')
        make_esg(self.company, code='S1', pilier='social',
                 valeur=Decimal('1'), cible=Decimal('5'),
                 tendance='hausse_favorable')  # non atteinte
        make_esg(self.company, code='G1', pilier='gouvernance')
        export = export_esg(self.company)
        self.assertEqual(export['total'], 3)
        self.assertEqual(export['piliers']['environnement']['nb'], 1)
        self.assertEqual(
            export['piliers']['environnement']['cibles_atteintes'], 1)
        self.assertEqual(
            export['piliers']['social']['cibles_atteintes'], 0)

    def test_export_filtre_annee(self):
        make_esg(self.company, code='E1', annee=2025)
        make_esg(self.company, code='E2', annee=2026)
        export = export_esg(self.company, annee=2026)
        self.assertEqual(export['total'], 1)
        self.assertEqual(export['lignes'][0]['code'], 'E2')

    def test_export_scope_societe(self):
        other = make_company('co-esg-exp-2', 'CoEsgExp2')
        make_esg(self.company, code='E1')
        make_esg(other, code='E1')
        export = export_esg(self.company)
        self.assertEqual(export['total'], 1)


class IndicateurESGApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-esg-api', 'CoEsgApi')
        self.other_company = make_company('co-esg-api-2', 'CoEsgApi2')
        self.user = make_user(self.company, 'esg-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'esg-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_company_serveur(self):
        resp = self.client_api.post(
            ESG_URL,
            {'code': 'E1', 'libelle': 'Émissions', 'pilier': 'environnement',
             'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ind = IndicateurESG.objects.get(id=resp.data['id'])
        self.assertEqual(ind.company, self.company)

    def test_atteinte_cible_exposee(self):
        ind = make_esg(
            self.company, valeur=Decimal('80'), cible=Decimal('70'),
            tendance='hausse_favorable')
        resp = self.client_api.get(f'{ESG_URL}{ind.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['atteinte_cible'])

    def test_bilan_carbone_meme_societe(self):
        autre_bilan = BilanCarbone.objects.create(
            company=self.other_company, libelle='B', annee=2026)
        resp = self.client_api.post(
            ESG_URL,
            {'code': 'E1', 'libelle': 'X', 'bilan_carbone': autre_bilan.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_export_action(self):
        make_esg(self.company, code='E1', pilier='environnement')
        resp = self.client_api.get(f'{ESG_URL}export/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        self.assertIn('environnement', resp.data['piliers'])

    def test_filtre_pilier(self):
        make_esg(self.company, code='E1', pilier='environnement')
        make_esg(self.company, code='S1', pilier='social')
        resp = self.client_api.get(ESG_URL, {'pilier': 'social'})
        piliers = [r['pilier'] for r in rows(resp)]
        self.assertEqual(piliers, ['social'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'esg-normal', role='normal')
        resp = auth_client(normal).get(ESG_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        ind = make_esg(self.company)
        resp = self.other_client.get(f'{ESG_URL}{ind.id}/')
        self.assertEqual(resp.status_code, 404)
