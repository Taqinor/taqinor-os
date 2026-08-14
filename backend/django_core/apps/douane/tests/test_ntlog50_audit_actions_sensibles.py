"""NTLOG50 (volet douane) — ``audit.AuditLog`` sur les actions douanières
sensibles réellement construites dans cette app : clôture d'un dossier
export (statut → clôturé) et suppression d'une pièce déjà VALIDÉE.

``BaremeDouanier`` (NTLOG13) et la pièce de dossier IMPORT (NTLOG11) restent
BLOCKED (NTLOG10 — voir ``apps/douane/apps.py``) : hors de ce test, comme le
volet ``apps/transport`` de NTLOG50 (lane concurrente).

Run :
    python manage.py test \
        apps.douane.tests.test_ntlog50_audit_actions_sensibles -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.douane.models import DossierExport, PieceDossierExport
from apps.douane.services import cloturer_dossier_export

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/douane'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog50-co-{n}', defaults={'nom': f'NTLOG50 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntlog50-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class TestAuditClotureDossierExport(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG50-1',
            statut=DossierExport.Statut.LEVE)

    def test_cloture_ecrit_une_entree_audit_avec_ancien_et_nouveau_statut(self):
        cloturer_dossier_export(self.dossier, user=self.user)

        ct = ContentType.objects.get_for_model(DossierExport)
        entry = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.dossier.pk),
            action=AuditLog.Action.STATUS).latest('id')
        self.assertEqual(
            entry.changes, [{'field': 'statut', 'old': 'Levé', 'new': 'Clôturé'}])
        self.assertEqual(entry.user_id, self.user.id)

    def test_cloture_idempotente_pas_de_double_ligne_audit(self):
        cloturer_dossier_export(self.dossier, user=self.user)
        ct = ContentType.objects.get_for_model(DossierExport)
        avant = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.dossier.pk)).count()

        cloturer_dossier_export(self.dossier, user=self.user)
        apres = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.dossier.pk)).count()
        self.assertEqual(avant, apres)

    def test_endpoint_cloturer_ecrit_aussi_l_audit(self):
        api = auth(self.user)
        r = api.post(f'{BASE}/dossiers-export/{self.dossier.id}/cloturer/')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, DossierExport.Statut.CLOTURE)
        ct = ContentType.objects.get_for_model(DossierExport)
        self.assertTrue(AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.dossier.pk),
            action=AuditLog.Action.STATUS).exists())


class TestAuditSuppressionPieceValidee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG50-2')
        self.piece_validee = PieceDossierExport.objects.create(
            company=self.company, dossier=self.dossier,
            type_piece=PieceDossierExport.TypePiece.EUR1,
            statut_piece=PieceDossierExport.StatutPiece.VALIDEE)
        self.piece_manquante = PieceDossierExport.objects.create(
            company=self.company, dossier=self.dossier,
            type_piece=PieceDossierExport.TypePiece.PACKING_LIST,
            statut_piece=PieceDossierExport.StatutPiece.MANQUANTE)

    def test_suppression_piece_validee_ecrit_une_entree_audit(self):
        r = self.api.delete(
            f'{BASE}/dossiers-export-pieces/{self.piece_validee.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT, r.content)

        entry = AuditLog.objects.filter(
            company=self.company, action=AuditLog.Action.DELETE).latest('id')
        self.assertIn('VALIDÉE', entry.detail.upper())
        self.assertEqual(entry.user_id, self.user.id)

    def test_suppression_piece_non_validee_n_ecrit_rien(self):
        avant = AuditLog.objects.filter(company=self.company).count()
        r = self.api.delete(
            f'{BASE}/dossiers-export-pieces/{self.piece_manquante.id}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT, r.content)

        apres = AuditLog.objects.filter(company=self.company).count()
        self.assertEqual(avant, apres)
