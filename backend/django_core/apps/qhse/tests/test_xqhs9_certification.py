"""Tests XQHS9 — Registre des certifications (ISO / IMANOR NM) + audits.

Couvre :

* le calcul de statut (valide / à renouveler / expiré / suspendu) ;
* la levée de NCR sur constat majeur d'audit, idempotente ;
* un constat non majeur ne lève pas de NCR ;
* le scoping société.
"""
from datetime import date, timedelta

from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import AuditCertification, Certification, NonConformite
from apps.qhse.services import lever_ncr_audit_certification


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class StatutCalculeTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs9-statut', 'CoXqhs9Statut')

    def test_valide_loin_de_l_echeance(self):
        certif = Certification.objects.create(
            company=self.company, referentiel=Certification.Referentiel.ISO_9001,
            date_expiration=date.today() + timedelta(days=365))
        self.assertEqual(certif.statut_calcule(), Certification.Statut.VALIDE)

    def test_a_renouveler_dans_prealerte(self):
        certif = Certification.objects.create(
            company=self.company, date_expiration=date.today() + timedelta(days=10),
            prealerte_jours=60)
        self.assertEqual(
            certif.statut_calcule(), Certification.Statut.A_RENOUVELER)

    def test_expire_apres_echeance(self):
        certif = Certification.objects.create(
            company=self.company, date_expiration=date.today() - timedelta(days=1))
        self.assertEqual(certif.statut_calcule(), Certification.Statut.EXPIRE)

    def test_suspendu_reste_suspendu(self):
        certif = Certification.objects.create(
            company=self.company, statut=Certification.Statut.SUSPENDU,
            date_expiration=date.today() + timedelta(days=365))
        self.assertEqual(certif.statut_calcule(), Certification.Statut.SUSPENDU)


class LeverNcrAuditCertificationTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs9-ncr', 'CoXqhs9Ncr')
        self.certif = Certification.objects.create(
            company=self.company, referentiel=Certification.Referentiel.ISO_45001)

    def test_constat_majeur_leve_ncr(self):
        audit = AuditCertification.objects.create(
            company=self.company, certification=self.certif,
            constat_majeur=True, constats='Non-respect procédure LOTO')
        ncr = lever_ncr_audit_certification(audit)
        self.assertIsNotNone(ncr)
        self.assertEqual(ncr.gravite, NonConformite.Gravite.MAJEURE)
        audit.refresh_from_db()
        self.assertEqual(audit.ncr_id, ncr.id)

    def test_constat_non_majeur_ne_leve_pas_ncr(self):
        audit = AuditCertification.objects.create(
            company=self.company, certification=self.certif,
            constat_majeur=False)
        ncr = lever_ncr_audit_certification(audit)
        self.assertIsNone(ncr)
        audit.refresh_from_db()
        self.assertIsNone(audit.ncr_id)

    def test_idempotent(self):
        audit = AuditCertification.objects.create(
            company=self.company, certification=self.certif,
            constat_majeur=True)
        ncr1 = lever_ncr_audit_certification(audit)
        audit.refresh_from_db()
        ncr2 = lever_ncr_audit_certification(audit)
        self.assertEqual(ncr1.id, ncr2.id)
        self.assertEqual(
            NonConformite.objects.filter(company=self.company).count(), 1)


class IsolationSocieteTests(TestCase):
    def test_certification_isolee_par_societe(self):
        c1 = make_company('co-xqhs9-iso-a', 'CoXqhs9IsoA')
        c2 = make_company('co-xqhs9-iso-b', 'CoXqhs9IsoB')
        Certification.objects.create(company=c1, referentiel='iso_9001')
        self.assertEqual(
            Certification.objects.filter(company=c2).count(), 0)
