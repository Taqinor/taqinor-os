"""Tests XPAI21 — Distribution des bulletins : notification + accusé de lecture.

Couvre : valider un bulletin notifie (best-effort) l'employé lié via
``apps.notifications``, la première consultation du coffre-fort (détail ou
PDF) pose ``lu_le`` (jamais réécrit ensuite), et un profil sans utilisateur
lié ne casse rien (no-op silencieux).
"""
from unittest import mock
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults, generer_bulletin, marquer_bulletin_lu, valider_bulletin,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def auth_client(user):
    client = APIClient()
    token = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


class NotifierBulletinDisponibleTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai21-notif')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_validation_notifie_employe_lie(self):
        user = User.objects.create_user(
            username='sal21', password='x', company=self.co)
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='N1', nom='Sal', prenom='A', user=user)
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        bulletin = generer_bulletin(profil, self.periode)
        with mock.patch(
                'apps.notifications.services.notify') as mock_notify:
            valider_bulletin(bulletin)
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertEqual(args[0], user)
        self.assertEqual(args[1], 'paie_bulletin_disponible')

    def test_validation_sans_utilisateur_lie_ne_leve_pas(self):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='N2', nom='Sal', prenom='B')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        bulletin = generer_bulletin(profil, self.periode)
        # Ne doit lever aucune exception (no-op silencieux).
        valider_bulletin(bulletin)


class MarquerBulletinLuTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai21-lu')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.user = User.objects.create_user(
            username='sal21b', password='x', company=self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='L1', nom='Sal', prenom='C',
            user=self.user)
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('7000'), affilie_cnss=True, affilie_amo=True)

    def test_service_pose_lu_le_une_seule_fois(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        self.assertIsNone(bulletin.lu_le)
        marquer_bulletin_lu(bulletin)
        premiere = bulletin.lu_le
        self.assertIsNotNone(premiere)
        marquer_bulletin_lu(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.lu_le, premiere)

    def test_consultation_detail_pose_lu_le(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        client = auth_client(self.user)
        resp = client.get(f'/api/django/paie/mes-bulletins/{bulletin.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()['lu_le'])

    def test_pdf_pose_lu_le(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        client = auth_client(self.user)
        client.get(f'/api/django/paie/mes-bulletins/{bulletin.id}/pdf/')
        bulletin.refresh_from_db()
        self.assertIsNotNone(bulletin.lu_le)

    def test_lu_le_jamais_reecrit_apres_premiere_consultation(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        client = auth_client(self.user)
        client.get(f'/api/django/paie/mes-bulletins/{bulletin.id}/')
        bulletin.refresh_from_db()
        premiere = bulletin.lu_le
        client.get(f'/api/django/paie/mes-bulletins/{bulletin.id}/')
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.lu_le, premiere)

    def test_lu_le_absent_avant_toute_consultation(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        self.assertIsNone(bulletin.lu_le)
