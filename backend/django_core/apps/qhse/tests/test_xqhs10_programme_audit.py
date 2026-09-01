"""Tests XQHS10 — Programme d'audit interne annuel.

Couvre :

* la garde d'indépendance ADVISORY (auditeur == responsable du domaine) ;
* l'instanciation idempotente de l'Audit réel ;
* la relance des audits planifiés en retard ;
* le scoping société ;
* WIR275 — l'exposition REST (CRUD + action ``instancier``,
  ``independance_ok`` exposé en lecture seule, ADVISORY jamais bloquant).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import Audit, AuditPlanifie, GrilleAudit, ProgrammeAudit
from apps.qhse.services import (
    instancier_audit_planifie, relancer_audits_planifies_en_retard,
)

User = get_user_model()

PROGRAMMES = '/api/django/qhse/programmes-audit/'
AUDITS_PLANIFIES = '/api/django/qhse/audits-planifies/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_grille(company):
    return GrilleAudit.objects.create(company=company, nom='Grille QHSE')


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class IndependanceOkTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs10-indep', 'CoXqhs10Indep')
        self.grille = make_grille(self.company)
        self.programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2026)

    def test_auditeur_different_responsable_ok(self):
        auditeur = make_user(self.company, 'auditeur-xqhs10')
        responsable = make_user(self.company, 'resp-xqhs10')
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            auditeur=auditeur, responsable_domaine=responsable)
        self.assertTrue(ap.independance_ok())

    def test_auditeur_egal_responsable_avertit(self):
        user = make_user(self.company, 'meme-xqhs10')
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Sécurité', grille=self.grille,
            auditeur=user, responsable_domaine=user)
        self.assertFalse(ap.independance_ok())

    def test_sans_responsable_ok_par_defaut(self):
        auditeur = make_user(self.company, 'auditeur2-xqhs10')
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Env', grille=self.grille, auditeur=auditeur)
        self.assertTrue(ap.independance_ok())


class InstancierAuditPlanifieTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs10-inst', 'CoXqhs10Inst')
        self.grille = make_grille(self.company)
        self.programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2026)

    def test_instancie_audit_reel(self):
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            date_cible=date(2026, 9, 1))
        audit = instancier_audit_planifie(ap)
        self.assertIsInstance(audit, Audit)
        ap.refresh_from_db()
        self.assertEqual(ap.audit_id, audit.id)
        self.assertEqual(ap.statut, AuditPlanifie.Statut.REALISE)

    def test_instanciation_idempotente(self):
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille)
        audit1 = instancier_audit_planifie(ap)
        ap.refresh_from_db()
        audit2 = instancier_audit_planifie(ap)
        self.assertEqual(audit1.id, audit2.id)
        self.assertEqual(Audit.objects.filter(company=self.company).count(), 1)


class RelancerAuditsPlanifiesEnRetardTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs10-relance', 'CoXqhs10Relance')
        self.grille = make_grille(self.company)
        self.programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2026)

    def test_relance_audit_en_retard(self):
        auditeur = make_user(self.company, 'auditeur-relance')
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            date_cible=date.today() - timedelta(days=5), auditeur=auditeur)
        relances = relancer_audits_planifies_en_retard(company=self.company)
        self.assertEqual(len(relances), 1)
        ap.refresh_from_db()
        self.assertEqual(ap.statut, AuditPlanifie.Statut.EN_RETARD)

    def test_pas_de_relance_avant_echeance(self):
        AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            date_cible=date.today() + timedelta(days=5))
        relances = relancer_audits_planifies_en_retard(company=self.company)
        self.assertEqual(len(relances), 0)

    def test_realise_non_relance(self):
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            date_cible=date.today() - timedelta(days=5))
        instancier_audit_planifie(ap)
        relances = relancer_audits_planifies_en_retard(company=self.company)
        self.assertEqual(len(relances), 0)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs10-relance-autre', 'CoXqhs10RelanceAutre')
        AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille,
            date_cible=date.today() - timedelta(days=5))
        relances = relancer_audits_planifies_en_retard(company=autre)
        self.assertEqual(len(relances), 0)


class ProgrammeAuditUniqueTests(TestCase):
    def test_unique_par_annee_et_societe(self):
        company = make_company('co-xqhs10-uniq', 'CoXqhs10Uniq')
        ProgrammeAudit.objects.create(company=company, annee=2026)
        with self.assertRaises(Exception):
            ProgrammeAudit.objects.create(company=company, annee=2026)


class ProgrammeAuditApiTests(TestCase):
    """WIR275 — CRUD REST scopé société, jusqu'ici inexistant."""

    def setUp(self):
        self.company = make_company('co-xqhs10-prog-api', 'CoXqhs10ProgApi')
        self.user = make_user(self.company, 'resp-xqhs10-prog-api')
        self.api = auth_client(self.user)

    def test_create_pose_company(self):
        resp = self.api.post(PROGRAMMES, {'annee': 2027}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        programme = ProgrammeAudit.objects.get(id=resp.data['id'])
        self.assertEqual(programme.company_id, self.company.id)

    def test_isolation_inter_societes(self):
        autre = make_company('co-xqhs10-prog-api-x', 'Autre')
        ProgrammeAudit.objects.create(company=autre, annee=2027)
        data = self.api.get(PROGRAMMES).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)


class AuditPlanifieApiTests(TestCase):
    """WIR275 — CRUD + action ``instancier`` (``instancier_audit_planifie``
    n'avait aucun appelant) + ``independance_ok`` exposé ADVISORY."""

    def setUp(self):
        self.company = make_company('co-xqhs10-ap-api', 'CoXqhs10ApApi')
        self.user = make_user(self.company, 'resp-xqhs10-ap-api')
        self.api = auth_client(self.user)
        self.grille = make_grille(self.company)
        self.programme = ProgrammeAudit.objects.create(
            company=self.company, annee=2026)

    def test_independance_ok_false_n_empeche_jamais_la_creation(self):
        resp = self.api.post(AUDITS_PLANIFIES, {
            'programme': self.programme.id,
            'processus_domaine': 'Sécurité',
            'grille': self.grille.id,
            'auditeur': self.user.id,
            'responsable_domaine': self.user.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['independance_ok'])

    def test_instancier_action(self):
        ap = AuditPlanifie.objects.create(
            company=self.company, programme=self.programme,
            processus_domaine='Qualité', grille=self.grille)
        resp = self.api.post(f'{AUDITS_PLANIFIES}{ap.id}/instancier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['audit'])
        ap.refresh_from_db()
        self.assertEqual(ap.statut, AuditPlanifie.Statut.REALISE)

    def test_programme_hors_societe_refuse(self):
        autre = make_company('co-xqhs10-ap-api-x', 'Autre')
        programme_autre = ProgrammeAudit.objects.create(
            company=autre, annee=2026)
        resp = self.api.post(AUDITS_PLANIFIES, {
            'programme': programme_autre.id,
            'processus_domaine': 'Qualité',
            'grille': self.grille.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
