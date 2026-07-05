"""ZGED14 — Renouvellement/rappel d'échéance des demandes de signature en
attente (relance émetteur).

Couvre :
  * une demande proche de l'expiration notifie son émetteur une seule fois
    (idempotence anti-doublon) ;
  * la prolongation repousse l'échéance et réarme la notification ;
  * une demande signée/annulée ne notifie pas ;
  * scoping société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    Cabinet, Document, DemandeSignatureDocument, Folder, SIGNATURE_EN_ATTENTE,
    SIGNATURE_SIGNE,
)
from apps.notifications.models import Notification

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZGed14Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged14-a', 'Zged14 A')
        self.admin_a = make_user(self.co_a, 'zged14-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')

    def _make_demande(self, **overrides):
        defaults = dict(
            company=self.co_a, document=self.doc,
            signataire_nom='Client A', signataire_email='a@example.com',
            statut=SIGNATURE_EN_ATTENTE,
            expires_at=timezone.now() + timedelta(days=1),
            created_by=self.admin_a,
        )
        defaults.update(overrides)
        return DemandeSignatureDocument.objects.create(**defaults)


class ServiceTests(ZGed14Base):
    def test_notifie_emetteur_demande_proche_expiration(self):
        demande = self._make_demande()
        count = services.notifier_emetteur_expiration_proche(
            self.co_a, seuil_jours=3)
        self.assertEqual(count, 1)
        demande.refresh_from_db()
        self.assertIsNotNone(demande.emetteur_notifie_expiration_le)
        self.assertTrue(
            Notification.objects.filter(recipient=self.admin_a).exists())

    def test_idempotent_ne_notifie_pas_deux_fois(self):
        self._make_demande()
        services.notifier_emetteur_expiration_proche(self.co_a, seuil_jours=3)
        count2 = services.notifier_emetteur_expiration_proche(
            self.co_a, seuil_jours=3)
        self.assertEqual(count2, 0)

    def test_demande_signee_ne_notifie_pas(self):
        self._make_demande(statut=SIGNATURE_SIGNE)
        count = services.notifier_emetteur_expiration_proche(
            self.co_a, seuil_jours=3)
        self.assertEqual(count, 0)

    def test_demande_hors_fenetre_ne_notifie_pas(self):
        self._make_demande(expires_at=timezone.now() + timedelta(days=30))
        count = services.notifier_emetteur_expiration_proche(
            self.co_a, seuil_jours=3)
        self.assertEqual(count, 0)

    def test_prolonger_reame_la_notification(self):
        demande = self._make_demande()
        services.notifier_emetteur_expiration_proche(self.co_a, seuil_jours=3)
        demande.refresh_from_db()
        self.assertIsNotNone(demande.emetteur_notifie_expiration_le)

        nouvelle_echeance = timezone.now() + timedelta(days=10)
        demande = services.prolonger_demande_signature(
            demande, expires_at=nouvelle_echeance, user=self.admin_a)
        self.assertEqual(demande.expires_at, nouvelle_echeance)
        self.assertIsNone(demande.emetteur_notifie_expiration_le)


class ViewTests(ZGed14Base):
    def test_prolonger_endpoint(self):
        demande = self._make_demande()
        api = auth(self.admin_a)
        nouvelle = (timezone.now() + timedelta(days=15)).isoformat()
        resp = api.post(
            f'/api/django/ged/demandes-signature/{demande.pk}/prolonger/',
            {'expires_at': nouvelle}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['emetteur_notifie_expiration_le'])

    def test_prolonger_sans_date_400(self):
        demande = self._make_demande()
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/ged/demandes-signature/{demande.pk}/prolonger/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        demande = self._make_demande()
        co_b = make_company('zged14-b', 'Zged14 B')
        admin_b = make_user(co_b, 'zged14-admin-b', 'admin')
        api_b = auth(admin_b)
        resp = api_b.post(
            f'/api/django/ged/demandes-signature/{demande.pk}/prolonger/',
            {'expires_at': timezone.now().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 404)
