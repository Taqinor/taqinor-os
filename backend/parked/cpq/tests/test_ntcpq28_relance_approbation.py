"""NTCPQ28 — Wizard « Escalade d'approbation » côté commercial (demandeur).

``POST cpq/devis/{id}/relancer-approbation/`` : relance MANUELLE de
l'approbateur assigné, throttlée à 1 relance/24h (même marqueur que la
relance automatique NTCPQ33 — cliquer deux fois le même jour n'envoie
qu'une seule notification)."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import services
from apps.cpq.models import EtapeApprobationDevis, RegleApprobationRemise
from apps.notifications.models import Notification
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRelancerApprobation(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.demandeur = UserFactory(company=self.company)
        self.approbateur = UserFactory(company=self.company)
        RegleApprobationRemise.objects.create(
            company=self.company, remise_min_pct=Decimal('0'),
            remise_max_pct=Decimal('100'), nombre_approbateurs=1)
        self.devis = DevisFactory(
            company=self.company, remise_globale=Decimal('30'))
        self.etape = services.lancer_approbation_devis(self.devis)[0]
        self.etape.approbateur = self.approbateur
        self.etape.save(update_fields=['approbateur'])

    def _url(self):
        return f'/api/django/cpq/devis/{self.devis.id}/relancer-approbation/'

    def test_relance_envoie_une_notification(self):
        etape, envoyee = services.relancer_etape_approbation(
            self.devis, user=self.demandeur)
        self.assertTrue(envoyee)
        self.assertTrue(Notification.objects.filter(
            recipient=self.approbateur, event_type='approval_reminder',
        ).exists())
        etape.refresh_from_db()
        self.assertIsNotNone(etape.derniere_relance_le)

    def test_deux_relances_meme_jour_une_seule_notification(self):
        services.relancer_etape_approbation(self.devis, user=self.demandeur)
        etape2, envoyee2 = services.relancer_etape_approbation(
            self.devis, user=self.demandeur)
        self.assertFalse(envoyee2)
        self.assertEqual(Notification.objects.filter(
            recipient=self.approbateur, event_type='approval_reminder',
        ).count(), 1)

    def test_relance_de_nouveau_apres_24h(self):
        services.relancer_etape_approbation(self.devis, user=self.demandeur)
        EtapeApprobationDevis.objects.filter(id=self.etape.id).update(
            derniere_relance_le=timezone.now() - timedelta(hours=25))
        etape3, envoyee3 = services.relancer_etape_approbation(
            self.devis, user=self.demandeur)
        self.assertTrue(envoyee3)

    def test_aucune_etape_en_attente_leve(self):
        self.etape.statut = EtapeApprobationDevis.Statut.APPROUVE
        self.etape.save(update_fields=['statut'])
        with self.assertRaises(ValidationError):
            services.relancer_etape_approbation(self.devis, user=self.demandeur)

    def test_endpoint_accessible_a_tout_role_interne(self):
        resp = auth(self.demandeur).post(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['relance_envoyee'])
        self.assertEqual(resp.data['approbateur'], self.approbateur.username)

    def test_endpoint_isole_les_societes(self):
        autre_company = CompanyFactory()
        autre_user = UserFactory(company=autre_company)
        resp = auth(autre_user).post(self._url())
        self.assertEqual(resp.status_code, 404)
