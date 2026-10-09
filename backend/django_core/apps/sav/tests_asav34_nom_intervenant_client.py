"""ASAV34 — sorties client SAV : nom d'intervenant, jamais l'identifiant.

Le fil client du portail (``selectors.fil_client_du_ticket``) et la fiche de
synthèse PDF (``pdf.fiche_synthese_ticket_pdf`` : « Technicien », colonne
« Auteur », lignes d'intervention) affichent ``parametres.selectors.
nom_intervenant`` — nom complet, sinon la raison sociale — et jamais le
username ni une adresse e-mail interne.

Run :
    python manage.py test apps.sav.tests_asav34_nom_intervenant_client -v2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav import selectors
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()

TECH_LOGIN = 'vspub.tech@outlook.com'
ANON_LOGIN = 'asav34.sansnom@outlook.com'


@patch('apps.ventes.utils.pdf._download', return_value=None)
class NomIntervenantClientTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav34-co', defaults={'nom': 'ASAV34 Co'})
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'nom': 'Solaire ASAV34 SARL'})
        self.tech = User.objects.create_user(
            username=TECH_LOGIN, email=TECH_LOGIN, password='x',
            first_name='Karim', last_name='Tazi',
            role_legacy='admin', company=self.company)
        self.anonyme = User.objects.create_user(
            username=ANON_LOGIN, email=ANON_LOGIN, password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Portail', prenom='Client')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-ASAV34',
            client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV34-1',
            client=self.client_obj, installation=self.installation,
            type=Ticket.Type.CORRECTIF, created_by=self.tech,
            technicien_responsable=self.tech)
        TicketActivity.objects.create(
            company=self.company, ticket=self.ticket,
            kind=TicketActivity.Kind.NOTE, user=self.tech,
            body='Passage prévu jeudi.', visible_client=True)
        TicketActivity.objects.create(
            company=self.company, ticket=self.ticket,
            kind=TicketActivity.Kind.NOTE, user=self.anonyme,
            body='Pièce commandée.', visible_client=True)
        Intervention.objects.create(
            company=self.company, installation=self.installation,
            ticket=self.ticket, type_intervention=list(Intervention.Type)[0],
            technicien=self.tech, compte_rendu='Diagnostic.')

    def _html(self):
        with patch('apps.sav.pdf._html_to_pdf') as mock_pdf:
            mock_pdf.return_value = b'%PDF-fake'
            from apps.sav.pdf import fiche_synthese_ticket_pdf
            fiche_synthese_ticket_pdf(self.ticket)
            return mock_pdf.call_args[0][0]

    def test_fil_portail_nom(self, _dl):
        fil = selectors.fil_client_du_ticket(
            self.company, self.client_obj.id, self.ticket.id)
        auteurs = [e['auteur'] for e in fil]
        self.assertEqual(auteurs, ['Karim Tazi', 'Solaire ASAV34 SARL'])
        for auteur in auteurs:
            self.assertNotIn('@', auteur)

    def test_fiche_sans_username(self, _dl):
        html = self._html()
        self.assertNotIn(TECH_LOGIN, html)
        self.assertNotIn(ANON_LOGIN, html)
        self.assertNotIn('outlook.com', html)
        self.assertIn('Karim Tazi', html)
        self.assertIn('Solaire ASAV34 SARL', html)
