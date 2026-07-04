"""Tests XQHS10 — Programme d'audit interne annuel.

Couvre :

* la garde d'indépendance ADVISORY (auditeur == responsable du domaine) ;
* l'instanciation idempotente de l'Audit réel ;
* la relance des audits planifiés en retard ;
* le scoping société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import Audit, AuditPlanifie, GrilleAudit, ProgrammeAudit
from apps.qhse.services import (
    instancier_audit_planifie, relancer_audits_planifies_en_retard,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_grille(company):
    return GrilleAudit.objects.create(company=company, nom='Grille QHSE')


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
