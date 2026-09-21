"""AUD152 — ``position_credit_pdf`` (NTCRD25) est réellement réservé
Direction/Finance, comme son propre docstring l'annonce.

Défaut d'origine : le décorateur portait ``@permission_classes(
[IsAuthenticated])`` — identique à ``ping``/``fiche_credit_client``/
``exposition_credit`` — alors que ``IsDirecteurOrAdmin`` existe et est DÉJÀ
utilisée dans le MÊME fichier pour restreindre exactement ce type de
document (``importer_limites``, ``LimiteCreditViewSet.get_permissions``,
NTCRD35). Un Commercial pouvait télécharger la position crédit consolidée de
tout le portefeuille — encours, limites, retards.

Le rendu PDF réel n'est pas en cause ici (couvert par ``services.py`` /
``test_ntcrd25_position_pdf.py``, qui teste le HTML sous-jacent) : le moteur
est mocké pour isoler la garde de permission.

Run :
    python manage.py test apps.credit.tests.test_aud152_position_pdf_permission -v2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


def make_company(slug='aud152-co', nom='AUD152 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Aud152PositionPdfPermissionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='aud152@example.com')
        self.url = (
            f'/api/django/credit/clients/{self.client_obj.id}/position-pdf/')

        self.admin = User.objects.create_user(
            username='aud152_admin', password='x', role_legacy='admin',
            company=self.company)
        role_com = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.commercial = User.objects.create_user(
            username='aud152_com', password='x', role_legacy='normal',
            company=self.company, role=role_com)
        role_dir = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=['crm_voir', 'ventes_voir'])
        self.directeur = User.objects.create_user(
            username='aud152_dir', password='x', role_legacy='normal',
            company=self.company, role=role_dir)

    # ROUGE avant correctif : IsAuthenticated seul laissait passer TOUT rôle
    # authentifié de la société, Commercial compris.
    @patch('apps.credit.services.generer_pdf_position_credit',
           return_value=b'%PDF-1.4 stub aud152')
    def test_un_commercial_est_refuse(self, m_pdf):
        r = auth(self.commercial).get(self.url)
        self.assertEqual(r.status_code, 403)
        m_pdf.assert_not_called()

    @patch('apps.credit.services.generer_pdf_position_credit',
           return_value=b'%PDF-1.4 stub aud152')
    def test_un_directeur_est_autorise(self, m_pdf):
        r = auth(self.directeur).get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    @patch('apps.credit.services.generer_pdf_position_credit',
           return_value=b'%PDF-1.4 stub aud152')
    def test_un_admin_est_autorise(self, m_pdf):
        r = auth(self.admin).get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_anonyme_refuse(self):
        r = APIClient().get(self.url)
        self.assertIn(r.status_code, (401, 403))
