"""NTCPQ46 — Audit trail des changements de prix contractuel.

Toute modification de ``PrixContractuel.prix_ht`` est consignée dans
``audit.AuditLog`` existant (ancienne valeur, nouvelle valeur, auteur,
société) — réutilise l'infrastructure d'audit générique déjà en prod, pas de
nouveau modèle."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.cpq.models import PrixContractuel
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, ClientFactory, ProduitFactory, UserFactory


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestAuditPrixContractuel(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.auteur = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.client_obj = ClientFactory(company=self.company)
        self.produit = ProduitFactory(company=self.company)
        self.prix = PrixContractuel.objects.create(
            company=self.company, client=self.client_obj,
            produit=self.produit, prix_ht=Decimal('900.00'),
            created_by=self.auteur)

    def _url(self):
        return f'/api/django/cpq/prix-contractuels/{self.prix.id}/'

    def test_modification_prix_cree_une_entree_audit(self):
        resp = auth(self.auteur).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ct = ContentType.objects.get_for_model(PrixContractuel)
        log = AuditLog.objects.get(
            company=self.company, content_type=ct,
            object_id=str(self.prix.id), action=AuditLog.Action.UPDATE)
        self.assertIn('900.00', log.detail)
        self.assertIn('950.00', log.detail)
        self.assertEqual(log.user_id, self.auteur.id)

    def test_deux_modifications_creent_deux_entrees_distinctes(self):
        auth(self.auteur).patch(
            self._url(), {'prix_ht': '950.00'}, format='json')
        auth(self.auteur).patch(
            self._url(), {'prix_ht': '999.00'}, format='json')
        ct = ContentType.objects.get_for_model(PrixContractuel)
        logs = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.prix.id), action=AuditLog.Action.UPDATE)
        self.assertEqual(logs.count(), 2)

    def test_modification_dun_autre_champ_ne_cree_pas_dentree_prix(self):
        resp = auth(self.auteur).patch(
            self._url(), {'motif': 'Renégociation annuelle'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ct = ContentType.objects.get_for_model(PrixContractuel)
        self.assertFalse(AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.prix.id),
            action=AuditLog.Action.UPDATE).exists())
