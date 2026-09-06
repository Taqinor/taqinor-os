"""AUD609 — supprimer un prix contractuel laisse enfin une trace.

Un ``PrixContractuel`` est un accord tarifaire NÉGOCIÉ client×produit : il
prime sur toute liste de prix. Sa suppression n'était journalisée NULLE PART —
ni par la vue (aucun `destroy()` gardé) ni par le mécanisme générique d'audit.
Effacer un prix négocié fait pourtant remonter le client au tarif catalogue :
« qui l'a retiré, et quand » est exactement ce qui manquait.

Le journal générique n'écrit QUE pendant une requête HTTP (voir
``apps.audit.recorder``) : le test passe donc par l'API, jamais par l'ORM.

Run :
    python manage.py test apps.cpq.tests.test_aud609_audit_prix_contractuel -v2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.audit.signals import TRACKED_MODELS
from apps.cpq.models import PrixContractuel
from authentication.models import CustomUser
from testkit.factories import (
    ClientFactory, CompanyFactory, ProduitFactory, UserFactory,
)

URL = '/api/django/cpq/prix-contractuels/'


class TestPrixContractuelSuivi(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            username='aud609_cpq', company=self.company,
            role_legacy=CustomUser.ROLE_ADMIN)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.prix = PrixContractuel.objects.create(
            company=self.company, client=ClientFactory(company=self.company),
            produit=ProduitFactory(company=self.company),
            prix_ht=Decimal('1234.00'))

    def _traces(self):
        return AuditLog.objects.filter(
            company=self.company,
            action=AuditLog.Action.DELETE,
            content_type__model='prixcontractuel')

    def test_le_modele_est_declare_suivi(self):
        self.assertIn(('cpq', 'PrixContractuel'), TRACKED_MODELS)

    def test_la_suppression_par_l_api_est_journalisee(self):
        reponse = self.api.delete(f'{URL}{self.prix.pk}/')
        self.assertEqual(reponse.status_code, 204, reponse.data)
        self.assertTrue(
            self._traces().exists(),
            "La suppression d'un prix négocié ne laisse aucune trace : le "
            'client remonte au tarif catalogue sans que rien ne le dise.')

    def test_la_trace_porte_l_auteur(self):
        self.api.delete(f'{URL}{self.prix.pk}/')
        ligne = self._traces().first()
        self.assertIsNotNone(ligne)
        self.assertEqual(ligne.user_id, self.user.pk)
