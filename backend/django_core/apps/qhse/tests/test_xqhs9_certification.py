"""Tests XQHS9 — Registre des certifications (ISO / IMANOR NM) + audits.

Couvre :

* le calcul de statut (valide / à renouveler / expiré / suspendu) ;
* la levée de NCR sur constat majeur d'audit, idempotente ;
* un constat non majeur ne lève pas de NCR ;
* le scoping société ;
* WIR275 — l'exposition REST (CRUD + action ``lever-ncr``), jusqu'ici
  totalement orpheline (services testés, aucun endpoint).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import AuditCertification, Certification, NonConformite
from apps.qhse.services import lever_ncr_audit_certification

User = get_user_model()

CERTIFICATIONS = '/api/django/qhse/certifications/'
AUDITS_CERTIF = '/api/django/qhse/audits-certification/'


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


class CertificationApiTests(TestCase):
    """WIR275 — CRUD REST scopé société, jusqu'ici inexistant."""

    def setUp(self):
        self.company = make_company('co-xqhs9-api', 'CoXqhs9Api')
        self.user = make_user(self.company, 'resp-xqhs9-api')
        self.api = auth_client(self.user)

    def test_create_et_statut_calcule_expose(self):
        resp = self.api.post(CERTIFICATIONS, {
            'referentiel': Certification.Referentiel.ISO_9001,
            'organisme': 'IMANOR',
            'date_expiration': str(date.today() - timedelta(days=1)),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('company', resp.data)  # jamais exposée en écriture
        self.assertEqual(resp.data['statut_calcule'], 'expire')
        certif = Certification.objects.get(id=resp.data['id'])
        self.assertEqual(certif.company_id, self.company.id)

    def test_isolation_inter_societes(self):
        autre = make_company('co-xqhs9-api-x', 'Autre')
        Certification.objects.create(company=autre, referentiel='iso_9001')
        data = self.api.get(CERTIFICATIONS).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)


class AuditCertificationApiTests(TestCase):
    """WIR275 — CRUD + action ``lever-ncr`` (``lever_ncr_audit_certification``
    n'avait aucun appelant)."""

    def setUp(self):
        self.company = make_company('co-xqhs9-audit-api', 'CoXqhs9AuditApi')
        self.user = make_user(self.company, 'resp-xqhs9-audit-api')
        self.api = auth_client(self.user)
        self.certif = Certification.objects.create(
            company=self.company, referentiel=Certification.Referentiel.ISO_45001)

    def test_lever_ncr_leve_et_pose_ncr_id(self):
        audit = AuditCertification.objects.create(
            company=self.company, certification=self.certif,
            constat_majeur=True, constats='Non-respect LOTO')
        resp = self.api.post(f'{AUDITS_CERTIF}{audit.id}/lever-ncr/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['ncr_id'])
        self.assertEqual(
            NonConformite.objects.filter(company=self.company).count(), 1)

    def test_certification_hors_societe_refusee(self):
        autre = make_company('co-xqhs9-audit-api-x', 'Autre')
        certif_autre = Certification.objects.create(
            company=autre, referentiel='iso_9001')
        resp = self.api.post(AUDITS_CERTIF, {
            'certification': certif_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
