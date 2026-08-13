"""NTMKT28 — Rapport imprimable « Registre de consentement » (export CNDP).

Lecture seule sur ``core.ConsentRecord``/``SuppressionMarketing`` — jamais un
second registre créé. Multi-tenant : aucune fuite inter-sociétés.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, tag
from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import SuppressionMarketing
from core.models import ConsentRecord

User = get_user_model()


class RegistreConsentementExportTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt28', nom='NTMKT28')
        ConsentRecord.objects.create(
            company=self.co, subject_identifier='a@b.ma', purpose='marketing',
            granted=True, source='formulaire site')
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='c@d.ma',
            motif=SuppressionMarketing.Motif.DESINSCRIT)

    def test_export_contient_les_deux_sections(self):
        donnees = mkt_services.registre_consentement_export(self.co)
        self.assertEqual(len(donnees['consentements']), 1)
        self.assertEqual(len(donnees['suppressions']), 1)
        self.assertEqual(donnees['consentements'][0]['subject_identifier'],
                         'a@b.ma')

    def test_filtrable_par_contact(self):
        donnees = mkt_services.registre_consentement_export(
            self.co, contact='a@b')
        self.assertEqual(len(donnees['consentements']), 1)
        donnees_vide = mkt_services.registre_consentement_export(
            self.co, contact='inconnu')
        self.assertEqual(len(donnees_vide['consentements']), 0)

    def test_filtrable_par_periode(self):
        hier = (timezone.now() - datetime.timedelta(days=1)).date()
        demain = (timezone.now() + datetime.timedelta(days=1)).date()
        donnees = mkt_services.registre_consentement_export(
            self.co, date_debut=hier, date_fin=demain)
        self.assertEqual(len(donnees['consentements']), 1)
        donnees_hors_periode = mkt_services.registre_consentement_export(
            self.co, date_debut=hier - datetime.timedelta(days=10),
            date_fin=hier - datetime.timedelta(days=5))
        self.assertEqual(len(donnees_hors_periode['consentements']), 0)

    def test_scoping_societe_aucune_fuite(self):
        autre = Company.objects.create(slug='ntmkt28b', nom='Autre')
        ConsentRecord.objects.create(
            company=autre, subject_identifier='x@y.ma', purpose='marketing')
        donnees = mkt_services.registre_consentement_export(self.co)
        self.assertEqual(len(donnees['consentements']), 1)


@tag('weasyprint')
class RegistreConsentementPdfEndpointTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt28c', nom='NTMKT28c')
        self.user = User.objects.create_user(
            username='ntmkt28_user', password='x', role_legacy='responsable',
            company=self.co)

    def test_endpoint_exige_une_authentification(self):
        res = self.client.get(
            '/api/django/marketing/registre-consentement/export-pdf/')
        self.assertIn(res.status_code, (401, 403))

    def test_endpoint_renvoie_un_pdf(self):
        self.client.force_login(self.user)
        with patch('apps.marketing.services.registre_consentement_pdf',
                   return_value=b'%PDF-1.4 stub'):
            res = self.client.get(
                '/api/django/marketing/registre-consentement/export-pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
