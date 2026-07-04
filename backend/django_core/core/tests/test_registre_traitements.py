"""Tests XPLT23 — registre CNDP + exécution DSR transverse (loi 09-08).

Couvre :
  * une demande d'accès exporte les données CRM réelles ;
  * un effacement anonymise le lead (activités conservées) ;
  * l'effacement employé est refusé avec motif légal ;
  * le registre CNDP s'exporte en CSV ;
  * le seed est rejouable sans doublon ;
  * isolation multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest, RegistreTraitement
from core.views import RegistreTraitementViewSet

User = get_user_model()


class DsrCrmProviderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.other = Company.objects.create(nom='Autre')

    def _lead(self, company, **kw):
        from apps.crm.models import Lead
        defaults = dict(nom='Dupont', email='jean@example.com',
                        telephone='0612345678')
        defaults.update(kw)
        return Lead.objects.create(company=company, **defaults)

    def test_access_exports_real_crm_data(self):
        self._lead(self.company)
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='jean@example.com',
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(req)
        self.assertEqual(req.statut, DataSubjectRequest.STATUT_TRAITEE)
        crm_data = req.resultat.get('crm', {})
        self.assertTrue(crm_data.get('leads'))
        self.assertEqual(crm_data['leads'][0]['email'], 'jean@example.com')

    def test_erasure_anonymises_lead_keeping_activities(self):
        lead = self._lead(self.company)
        from apps.crm.models import LeadActivity
        LeadActivity.objects.create(
            company=self.company, lead=lead,
            kind=LeadActivity.Kind.NOTE, body='Appel')
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='jean@example.com',
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(req)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Anonymisé')
        self.assertIsNone(lead.email)
        # Activité conservée.
        self.assertEqual(
            LeadActivity.objects.filter(lead=lead).count(), 1)

    def test_tenant_isolation_on_export(self):
        self._lead(self.other, email='jean@example.com')
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='jean@example.com',
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(req)
        # ACME n'a pas ce lead → aucune fuite depuis « Autre ».
        self.assertEqual(req.resultat.get('crm', {}).get('leads'), [])


class DsrRhProviderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def _dossier(self):
        from apps.rh.models import DossierEmploye
        return DossierEmploye.objects.create(
            company=self.company, matricule='E001', nom='Alami',
            prenom='Sara', email='sara@example.com')

    def test_rh_export(self):
        self._dossier()
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='sara@example.com',
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(req)
        rh_data = req.resultat.get('rh', {})
        self.assertTrue(rh_data.get('dossiers_employes'))

    def test_rh_erasure_refused_with_motif(self):
        self._dossier()
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='sara@example.com',
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(req)
        rh_result = req.resultat.get('rh', {})
        self.assertTrue(rh_result.get('refuse'))
        self.assertIn('refus', rh_result.get('motif', '').lower())
        # Le dossier n'est PAS effacé.
        from apps.rh.models import DossierEmploye
        self.assertEqual(DossierEmploye.objects.count(), 1)


class RectificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')

    def test_rectification_is_manual_no_erase(self):
        from apps.crm.models import Lead
        Lead.objects.create(
            company=self.company, nom='Dupont', email='j@example.com')
        req = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='j@example.com',
            kind=DataSubjectRequest.KIND_RECTIFICATION)
        dsr.traiter_demande(req)
        self.assertTrue(req.resultat.get('rectification'))
        # Données NON modifiées (workflow manuel).
        self.assertEqual(
            Lead.objects.get(email='j@example.com').nom, 'Dupont')


class RegistreCndpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.admin = User.objects.create_user(
            username='rt_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.user = User.objects.create_user(
            username='rt_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_seed_idempotent(self):
        call_command('seed_registre_traitements', company=self.company.pk)
        n1 = RegistreTraitement.objects.filter(company=self.company).count()
        self.assertGreater(n1, 0)
        call_command('seed_registre_traitements', company=self.company.pk)
        n2 = RegistreTraitement.objects.filter(company=self.company).count()
        self.assertEqual(n1, n2)

    def test_seed_preserves_recepisse(self):
        call_command('seed_registre_traitements', company=self.company.pk)
        rt = RegistreTraitement.objects.filter(company=self.company).first()
        rt.numero_recepisse = 'CNDP-2026-001'
        rt.save(update_fields=['numero_recepisse'])
        call_command('seed_registre_traitements', company=self.company.pk)
        rt.refresh_from_db()
        self.assertEqual(rt.numero_recepisse, 'CNDP-2026-001')

    def test_csv_export(self):
        call_command('seed_registre_traitements', company=self.company.pk)
        req = self.factory.get('/registre-traitements/export-csv/')
        force_authenticate(req, user=self.admin)
        resp = RegistreTraitementViewSet.as_view(
            {'get': 'export_csv'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', resp['Content-Type'])
        body = resp.content.decode('utf-8')
        self.assertIn('leads_clients', body)

    def test_write_requires_admin(self):
        req = self.factory.post(
            '/registre-traitements/',
            {'code': 'x', 'finalite': 'y'}, format='json')
        force_authenticate(req, user=self.user)
        resp = RegistreTraitementViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_imposes_company(self):
        req = self.factory.post(
            '/registre-traitements/',
            {'code': 'z', 'finalite': 'test'}, format='json')
        force_authenticate(req, user=self.admin)
        resp = RegistreTraitementViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        rt = RegistreTraitement.objects.get(pk=resp.data['id'])
        self.assertEqual(rt.company, self.company)
