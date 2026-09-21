"""AUD303 — DELETE non gardé sur réserve levée/contestée, visa décidé,
avenant décidé (BTP).

Avant ce fix, ``ReserveChantierViewSet``/``VisaDocumentViewSet``/
``AvenantChantierViewSet`` ne définissaient aucun ``perform_destroy`` — seule
garde : ``write_permission='btp_gerer'`` (un rôle, pas un état). Une réserve
LEVEE/CONTESTEE (signature ``SignatureBtp``), un visa APPROUVE/REFUSE, ou un
avenant APPROUVE/REFUSE (potentiellement facturé — ``facture_id``) pouvaient
disparaître sans trace, zéro AuditLog.

Couvre :
* DELETE refusé (403) sur les 3 modèles dans leurs statuts « décidés » —
  la ligne SURVIT (compte inchangé) ;
* DELETE toujours autorisé sur un statut non verrouillé, ET journalisé
  (``btp_chantier`` désormais dans ``audit.signals.TRACKED_MODELS``) ;
* cross-tenant reste 404 (comportement ``CompanyScopedModelViewSet``
  inchangé, non retesté ici — couvert par les suites NTCON existantes).
"""
from django.test import TestCase
from rest_framework import status

from apps.audit.models import AuditLog
from apps.btp_chantier.models import AvenantChantier, ReserveChantier, VisaDocument

from .helpers import auth, make_chantier, make_company, make_user

RESERVES_BASE = '/api/django/btp-chantier/reserves-chantier/'
VISAS_BASE = '/api/django/btp-chantier/visas/'
AVENANTS_BASE = '/api/django/btp-chantier/avenants-chantier/'


class ReserveDestroyGuardTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    def _make_reserve(self, statut):
        return ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, created_by=self.user,
            description='Prise défectueuse', statut=statut)

    def test_delete_reserve_levee_refused(self):
        reserve = self._make_reserve(ReserveChantier.Statut.LEVEE)
        resp = self.api.delete(f'{RESERVES_BASE}{reserve.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(
            ReserveChantier.objects.filter(pk=reserve.pk).exists())

    def test_delete_reserve_contestee_refused(self):
        reserve = self._make_reserve(ReserveChantier.Statut.CONTESTEE)
        resp = self.api.delete(f'{RESERVES_BASE}{reserve.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(
            ReserveChantier.objects.filter(pk=reserve.pk).exists())

    def test_delete_reserve_ouverte_allowed_and_audited(self):
        reserve = self._make_reserve(ReserveChantier.Statut.OUVERTE)
        reserve_pk = reserve.pk
        resp = self.api.delete(f'{RESERVES_BASE}{reserve.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.data)
        self.assertFalse(
            ReserveChantier.objects.filter(pk=reserve_pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                object_id=str(reserve_pk)).exists())


class VisaDestroyGuardTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    def _make_visa(self, statut):
        return VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, soumis_par=self.user,
            reference='VIS-AUD303-0001', document_ged_id=7, statut=statut)

    def test_delete_visa_approuve_sans_reserve_refused(self):
        visa = self._make_visa(VisaDocument.Statut.APPROUVE_SANS_RESERVE)
        resp = self.api.delete(f'{VISAS_BASE}{visa.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(VisaDocument.objects.filter(pk=visa.pk).exists())

    def test_delete_visa_refuse_refused(self):
        visa = self._make_visa(VisaDocument.Statut.REFUSE)
        resp = self.api.delete(f'{VISAS_BASE}{visa.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(VisaDocument.objects.filter(pk=visa.pk).exists())

    def test_delete_visa_soumis_allowed_and_audited(self):
        visa = self._make_visa(VisaDocument.Statut.SOUMIS)
        visa_pk = visa.pk
        resp = self.api.delete(f'{VISAS_BASE}{visa.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.data)
        self.assertFalse(VisaDocument.objects.filter(pk=visa_pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE, object_id=str(visa_pk)).exists())


class AvenantDestroyGuardTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.api = auth(self.user)

    def _make_avenant(self, statut):
        return AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier,
            reference='AVC-AUD303-0001', description='Test',
            montant_ht='10000.00', statut=statut)

    def test_delete_avenant_approuve_refused(self):
        avenant = self._make_avenant(AvenantChantier.Statut.APPROUVE)
        resp = self.api.delete(f'{AVENANTS_BASE}{avenant.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(AvenantChantier.objects.filter(pk=avenant.pk).exists())

    def test_delete_avenant_refuse_refused(self):
        avenant = self._make_avenant(AvenantChantier.Statut.REFUSE)
        resp = self.api.delete(f'{AVENANTS_BASE}{avenant.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.data)
        self.assertTrue(AvenantChantier.objects.filter(pk=avenant.pk).exists())

    def test_delete_avenant_brouillon_allowed_and_audited(self):
        avenant = self._make_avenant(AvenantChantier.Statut.BROUILLON)
        avenant_pk = avenant.pk
        resp = self.api.delete(f'{AVENANTS_BASE}{avenant.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT, resp.data)
        self.assertFalse(AvenantChantier.objects.filter(pk=avenant_pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE, object_id=str(avenant_pk)).exists())
