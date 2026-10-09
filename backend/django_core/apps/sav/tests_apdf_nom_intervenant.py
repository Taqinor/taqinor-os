"""APDF42 — le rapport d'intervention SAV imprime le nom d'intervenant
(lignes d'intervention et signature « Le technicien »), jamais le username.

Run :
    python manage.py test apps.sav.tests_apdf_nom_intervenant -v2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket

User = get_user_model()
LOGIN = 'x4.tech@outlook.com'


@patch('apps.ventes.utils.pdf._download', return_value=None)
class NomIntervenantSavTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='apdf42-co', defaults={'nom': 'APDF42 Co'})
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'nom': 'Solaire APDF42 SARL'})
        self.tech = User.objects.create_user(
            username=LOGIN, email=LOGIN, password='x', role_legacy='admin',
            company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='APDF42')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-APDF42', client=client)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-APDF42-1', client=client,
            installation=inst, type=Ticket.Type.CORRECTIF,
            created_by=self.tech, technicien_responsable=self.tech)
        Intervention.objects.create(
            company=self.company, installation=inst, ticket=self.ticket,
            type_intervention=list(Intervention.Type)[0],
            technicien=self.tech, compte_rendu='Pose.')

    def _html(self):
        with patch('apps.sav.pdf._html_to_pdf') as mock_pdf:
            mock_pdf.return_value = b'%PDF-fake'
            from apps.sav.pdf import rapport_intervention_pdf
            rapport_intervention_pdf(self.ticket)
            return mock_pdf.call_args[0][0]

    def test_rapport_sans_username(self, _dl):
        html = self._html()
        self.assertNotIn(LOGIN, html)
        self.assertNotIn('outlook.com', html)

    def test_signature_nom(self, _dl):
        html = self._html()
        self.assertIn('Le technicien', html)
        self.assertIn('Solaire APDF42 SARL', html)
