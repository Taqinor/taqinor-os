"""Tests du rapport PDF d'intervention SAV (N45).

Le rapport est régénéré à la demande, scopé société (404 inter-société), et
n'expose jamais de prix d'achat / marge.
"""
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket

User = get_user_model()


def _company(slug='savpdf-co', nom='SAV PDF Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _user(company, username):
    return User.objects.create_user(
        username=username, password='pw',
        role_legacy='responsable', company=company)


def _ticket(company, client, **kw):
    return Ticket.objects.create(
        company=company, reference='SAV-PDF-0001', client=client,
        type=Ticket.Type.PANNE if hasattr(Ticket.Type, 'PANNE')
        else list(Ticket.Type)[0],
        statut=Ticket.Statut.RESOLU if hasattr(Ticket.Statut, 'RESOLU')
        else list(Ticket.Statut)[0],
        priorite=list(Ticket.Priorite)[0],
        description='Onduleur en défaut.', **kw)


@patch('apps.ventes.utils.pdf._download', return_value=None)
class SavReportEndpointTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _user(self.company, 'savpdf_user')
        self.client_obj = Client.objects.create(
            nom='Bennani', prenom='Karim', telephone='0600000000',
            company=self.company)
        self.installation = Installation.objects.create(
            company=self.company, reference='CH-SAVPDF-1',
            client=self.client_obj)
        self.ticket = _ticket(
            self.company, self.client_obj, installation=self.installation,
            technicien_responsable=self.user)
        Intervention.objects.create(
            company=self.company, installation=self.installation,
            ticket=self.ticket,
            type_intervention=list(Intervention.Type)[0],
            technicien=self.user, compte_rendu='Remplacement onduleur.',
            date_realisee=None)

        self.other_company = _company(slug='savpdf-other', nom='Other')
        self.other_user = _user(self.other_company, 'savpdf_other')
        self.other_client = Client.objects.create(
            nom='X', company=self.other_company)
        self.other_ticket = _ticket(
            self.other_company, self.other_client)
        self.other_ticket.reference = 'SAV-PDF-9999'
        self.other_ticket.save()

        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _url(self, pk):
        return f'/api/django/sav/tickets/{pk}/rapport-pdf/'

    def test_rapport_pdf_ok(self, _dl):
        r = self.api.get(self._url(self.ticket.id))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(len(r.content) > 1000)
        self.assertEqual(r.content[:4], b'%PDF')

    def test_rapport_pdf_foreign_404(self, _dl):
        r = self.api.get(self._url(self.other_ticket.id))
        self.assertEqual(r.status_code, 404)

    @patch('apps.sav.pdf._html_to_pdf')
    def test_no_buy_price_leak(self, mock_pdf, _dl):
        mock_pdf.return_value = b'%PDF-fake'
        from apps.sav.pdf import rapport_intervention_pdf
        rapport_intervention_pdf(self.ticket)
        html = mock_pdf.call_args[0][0]
        # Le rapport ne contient aucune notion de prix d'achat.
        self.assertNotIn('prix_achat', html)
        self.assertNotIn('marge', html.lower())
