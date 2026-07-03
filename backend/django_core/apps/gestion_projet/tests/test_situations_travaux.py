"""Tests des situations de travaux — décomptes progressifs BTP (XPRJ4).

Couvre : le décompte n°N reprend le cumul antérieur du n°N-1, montants
période = cumulé − antérieur, la facture n'est générée qu'une seule fois
(idempotent), la retenue de garantie est déduite, numérotation incrémentale
PAR PROJET (jamais count()+1).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import services
from apps.gestion_projet.models import Projet, SituationTravaux
from apps.ventes.models import Facture

User = get_user_model()


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


class SituationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-situ-svc', 'S')
        self.client_crm = Client.objects.create(company=self.co, nom='Client BTP')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SIT', nom='S', client_id=self.client_crm.id)
        self.user = make_user(self.co, 'situ-svc')

    def test_numerotation_incrementale(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        self.assertEqual(s1.numero, 1)
        self.assertEqual(s2.numero, 2)

    def test_numerotation_ignore_trous(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        s2.delete()
        s3 = services.creer_situation(self.projet, periode=date(2026, 3, 1))
        self.assertEqual(s1.numero, 1)
        self.assertEqual(s3.numero, 2)

    def test_montant_periode_situation_1_egale_cumule(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        ligne = services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        self.assertEqual(ligne.montant_cumule, Decimal('30000.00'))
        self.assertEqual(ligne.montant_cumule_anterieur, Decimal('0'))
        self.assertEqual(ligne.montant_periode, Decimal('30000.00'))

    def test_situation_2_reprend_cumul_anterieur(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        ligne2 = services.ajouter_ligne_situation(
            s2, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('70'))
        self.assertEqual(ligne2.montant_cumule, Decimal('70000.00'))
        self.assertEqual(ligne2.montant_cumule_anterieur, Decimal('30000.00'))
        self.assertEqual(ligne2.montant_periode, Decimal('40000.00'))

    def test_nouveau_lot_sans_precedent_anterieur_zero(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s2 = services.creer_situation(self.projet, periode=date(2026, 2, 1))
        ligne_nouveau_lot = services.ajouter_ligne_situation(
            s2, libelle='Électricité', montant_marche_ht=Decimal('50000'),
            avancement_cumule_pct=Decimal('20'))
        self.assertEqual(
            ligne_nouveau_lot.montant_cumule_anterieur, Decimal('0'))
        self.assertEqual(ligne_nouveau_lot.montant_periode, Decimal('10000.00'))

    def test_valider_genere_facture_une_seule_fois(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        self.assertEqual(s1.statut, SituationTravaux.Statut.FACTUREE)
        self.assertIsNotNone(s1.facture_id)
        with self.assertRaises(services.SituationTravauxError):
            services.valider_situation(s1, user=self.user)
        self.assertEqual(
            Facture.objects.filter(company=self.co).count(), 1)

    def test_retenue_garantie_deduite(self):
        s1 = services.creer_situation(
            self.projet, periode=date(2026, 1, 1),
            retenue_garantie_pct=Decimal('10'))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        facture = Facture.objects.get(id=s1.facture_id)
        # 30000 HT, RG 10% => 3000 déduits => 27000 HT net.
        self.assertEqual(facture.montant_ht, Decimal('27000.00'))

    def test_valider_sans_ligne_refuse(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        with self.assertRaises(services.SituationTravauxError):
            services.valider_situation(s1, user=self.user)

    def test_ajouter_ligne_sur_situation_facturee_refuse(self):
        s1 = services.creer_situation(self.projet, periode=date(2026, 1, 1))
        services.ajouter_ligne_situation(
            s1, libelle='Terrassement', montant_marche_ht=Decimal('100000'),
            avancement_cumule_pct=Decimal('30'))
        s1 = services.valider_situation(s1, user=self.user)
        with self.assertRaises(services.SituationTravauxError):
            services.ajouter_ligne_situation(
                s1, libelle='Autre', montant_marche_ht=Decimal('1000'),
                avancement_cumule_pct=Decimal('10'))


class SituationApiTests(TestCase):
    BASE = '/api/django/gestion-projet/situations/'

    def setUp(self):
        self.co = make_company('gp-situ-api', 'A')
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client API BTP')
        self.user = make_user(self.co, 'situ-api')
        self.projet = Projet.objects.create(
            company=self.co, code='P-SITA', nom='A',
            client_id=self.client_crm.id)

    def test_creation_pose_numero(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['numero'], 1)

    def test_workflow_ligne_puis_validation(self):
        api = auth(self.user)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        situation_id = resp.data['id']

        resp = api.post(
            f'{self.BASE}{situation_id}/ajouter-ligne/', {
                'libelle': 'Terrassement',
                'montant_marche_ht': '100000',
                'avancement_cumule_pct': '30',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_periode'], '30000.00')

        resp = api.post(f'{self.BASE}{situation_id}/valider/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'facturee')
        self.assertIsNotNone(resp.data['facture_id'])

    def test_isolation_tenant(self):
        co_b = make_company('gp-situ-b', 'B')
        user_b = make_user(co_b, 'situ-b')
        api_owner = auth(self.user)
        resp = api_owner.post(self.BASE, {
            'projet': self.projet.id, 'periode': '2026-01-01',
        }, format='json')
        situation_id = resp.data['id']
        api_b = auth(user_b)
        resp = api_b.post(f'{self.BASE}{situation_id}/valider/')
        self.assertEqual(resp.status_code, 404)
