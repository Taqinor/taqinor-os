"""Tests XCTR11 — Campagne de révision tarifaire en masse.

Couvre :
- preview sans écriture (aucun avenant créé) ;
- application idempotente (re-run = 0 nouvel avenant) ;
- rollback list retournée + compensation effective ;
- endpoint admin-only.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client

from apps.contrats import services
from apps.contrats.models import Avenant, Contrat

User = get_user_model()

CAMPAGNE = "/api/django/contrats/contrats/campagne-revision/"
ROLLBACK = "/api/django/contrats/contrats/campagne-revision-rollback/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat(company, montant, *, type_contrat="om"):
    cli = Client.objects.create(company=company, nom="Client SARL")
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant,
        type_contrat=type_contrat, statut=Contrat.Statut.ACTIF,
        client_id=cli.id, date_debut=date(2026, 1, 1))


class CampagneRevisionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("campagne-svc", "CampagneSvc")
        self.admin = make_user(self.co, "campagne-svc-admin")

    def test_preview_aucune_ecriture(self):
        make_contrat(self.co, Decimal("1000"))
        make_contrat(self.co, Decimal("2000"))
        resultat = services.campagne_revision(
            self.co, pct=Decimal("5"), preview=True)
        self.assertTrue(resultat['preview'])
        self.assertEqual(len(resultat['lignes']), 2)
        self.assertEqual(Avenant.objects.filter(company=self.co).count(), 0)
        ligne = next(
            entry for entry in resultat['lignes']
            if entry['ancien_montant'] == Decimal("1000"))
        self.assertEqual(ligne['nouveau_montant'], Decimal("1050.00"))

    def test_application_cree_un_avenant_par_contrat(self):
        c1 = make_contrat(self.co, Decimal("1000"))
        c2 = make_contrat(self.co, Decimal("2000"))
        resultat = services.campagne_revision(
            self.co, pct=Decimal("5"), preview=False, auteur=self.admin)
        self.assertFalse(resultat['preview'])
        self.assertEqual(resultat['avenants_crees'], 2)
        self.assertEqual(len(resultat['rollback_ids']), 2)
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.montant, Decimal("1050.00"))
        self.assertEqual(c2.montant, Decimal("2100.00"))

    def test_application_idempotente_re_run_zero_nouvel_avenant(self):
        make_contrat(self.co, Decimal("1000"))
        date_effet = date(2026, 3, 1)
        r1 = services.campagne_revision(
            self.co, pct=Decimal("5"), date_effet=date_effet, preview=False,
            auteur=self.admin)
        self.assertEqual(r1['avenants_crees'], 1)

        r2 = services.campagne_revision(
            self.co, pct=Decimal("5"), date_effet=date_effet, preview=False,
            auteur=self.admin)
        self.assertEqual(r2['avenants_crees'], 0)
        self.assertEqual(Avenant.objects.filter(company=self.co).count(), 1)

    def test_filtre_type_contrat(self):
        make_contrat(self.co, Decimal("1000"), type_contrat="om")
        make_contrat(self.co, Decimal("500"), type_contrat="vente")
        resultat = services.campagne_revision(
            self.co, filtres={'type_contrat': 'om'}, pct=Decimal("10"),
            preview=True)
        self.assertEqual(len(resultat['lignes']), 1)

    def test_rollback_compense(self):
        c1 = make_contrat(self.co, Decimal("1000"))
        resultat = services.campagne_revision(
            self.co, pct=Decimal("10"), preview=False, auteur=self.admin)
        c1.refresh_from_db()
        self.assertEqual(c1.montant, Decimal("1100.00"))

        compensations = services.rollback_campagne_revision(
            self.co, resultat['rollback_ids'], auteur=self.admin)
        self.assertEqual(len(compensations), 1)
        c1.refresh_from_db()
        self.assertEqual(c1.montant, Decimal("1000.00"))


class CampagneRevisionApiTests(TestCase):
    def setUp(self):
        self.co = make_company("campagne-api", "CampagneApi")
        self.admin = make_user(self.co, "campagne-api-admin")
        self.responsable = make_user(
            self.co, "campagne-api-resp", role="responsable")

    def test_preview_via_api(self):
        make_contrat(self.co, Decimal("1000"))
        api = auth(self.admin)
        res = api.post(CAMPAGNE, {'pct': '5'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data['preview'])
        self.assertEqual(len(res.data['lignes']), 1)

    def test_application_via_api(self):
        make_contrat(self.co, Decimal("1000"))
        api = auth(self.admin)
        res = api.post(
            CAMPAGNE, {'pct': '5', 'preview': False}, format='json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data['avenants_crees'], 1)
        self.assertEqual(len(res.data['rollback_ids']), 1)

    def test_endpoint_admin_only_refuse_responsable(self):
        api = auth(self.responsable)
        res = api.post(CAMPAGNE, {'pct': '5'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_rollback_endpoint(self):
        make_contrat(self.co, Decimal("1000"))
        api = auth(self.admin)
        res = api.post(
            CAMPAGNE, {'pct': '5', 'preview': False}, format='json')
        rollback_ids = res.data['rollback_ids']
        res2 = api.post(
            ROLLBACK, {'avenant_ids': rollback_ids}, format='json')
        self.assertEqual(res2.status_code, 201, res2.content)
        self.assertEqual(res2.data['compensations_creees'], 1)
