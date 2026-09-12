"""NTSRV28 — Fiche de synthèse ticket imprimable (PDF INTERNE).

Critère d'acceptation : le PDF ne contient JAMAIS ``Produit.prix_achat`` ni
aucun champ de marge. Il est rendu par WeasyPrint (pile facture legacy) et
surtout PAS par le moteur ``quote_engine``, réservé aux devis client
(règle #4).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv28 -v 2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import (
    CauseDefaillance, Equipement, PieceConsommee, RemedeDefaillance, Ticket,
    TicketActivity,
)
from apps.stock.models import Produit

User = get_user_model()

#: Prix d'achat volontairement IMPROBABLE : s'il apparaît dans le rendu, ce
#: n'est pas une coïncidence (garde anti-fuite sur le RENDU, pas sur un
#: chiffre nu banal).
PRIX_ACHAT_TEMOIN = '987654.32'


@patch('apps.ventes.utils.pdf._download', return_value=None)
class NTSRV28FicheTicketPdfTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv28', defaults={'nom': 'Sav Co NTSRV28'})
        self.user = User.objects.create_user(
            username='ntsrv28_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Karim')
        self.installation = Installation.objects.create(
            company=self.company, reference='CHT-NTSRV28',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTSRV28', sku='NTSRV28-OND',
            prix_achat=PRIX_ACHAT_TEMOIN, prix_vente=1500)
        self.equipement = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.installation, numero_serie='NTSRV28-SN-1')
        self.cause = CauseDefaillance.objects.create(
            company=self.company, nom='Défaut composant')
        self.remede = RemedeDefaillance.objects.create(
            company=self.company, nom='Remplacement pièce')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV28-1',
            client=self.client_obj, installation=self.installation,
            equipement=self.equipement, cause=self.cause, remede=self.remede,
            description='Onduleur en défaut depuis lundi.',
            statut=Ticket.Statut.RESOLU, cout=4321,
            technicien_responsable=self.user)
        TicketActivity.objects.create(
            company=self.company, ticket=self.ticket,
            kind=TicketActivity.Kind.NOTE, user=self.user,
            body='Diagnostic réalisé sur site.')
        TicketActivity.objects.create(
            company=self.company, ticket=self.ticket,
            kind=TicketActivity.Kind.MODIFICATION, user=self.user,
            field='statut', field_label='Statut',
            old_value='Nouveau', new_value='Résolu')
        PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=2)
        self.intervention = Intervention.objects.create(
            company=self.company, installation=self.installation,
            ticket=self.ticket, type_intervention=list(Intervention.Type)[0],
            technicien=self.user, compte_rendu='Remplacement onduleur.')

        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, pk=None):
        return f'/api/django/sav/tickets/{pk or self.ticket.pk}/fiche-pdf/'

    def _html(self):
        """Rend la fiche en interceptant la conversion PDF → HTML brut."""
        with patch('apps.sav.pdf._html_to_pdf') as mock_pdf:
            mock_pdf.return_value = b'%PDF-fake'
            from apps.sav.pdf import fiche_synthese_ticket_pdf
            fiche_synthese_ticket_pdf(self.ticket)
            return mock_pdf.call_args[0][0]

    # ── Critère d'acceptation : zéro prix d'achat, zéro marge ────────────
    def test_aucun_prix_achat_ni_marge(self, _dl):
        html = self._html()
        self.assertNotIn('prix_achat', html)
        self.assertNotIn(PRIX_ACHAT_TEMOIN, html)
        self.assertNotIn('987 654', html)
        self.assertNotIn('marge', html.lower())

    def test_aucun_cout_interne_du_ticket(self, _dl):
        self.assertNotIn('4321', self._html())

    def test_piece_affichee_sans_prix(self, _dl):
        html = self._html()
        self.assertIn('Onduleur NTSRV28', html)
        self.assertIn('Pièces utilisées', html)

    # ── Contenu ──────────────────────────────────────────────────────────
    def test_historique_complet_present(self, _dl):
        html = self._html()
        self.assertIn('Historique complet', html)
        self.assertIn('Diagnostic réalisé sur site.', html)
        # Une ligne de modification est rendue « ancien → nouveau ».
        self.assertIn('Nouveau', html)
        self.assertIn('Résolu', html)

    def test_cause_et_remede_presents(self, _dl):
        html = self._html()
        self.assertIn('Défaut composant', html)
        self.assertIn('Remplacement pièce', html)

    def test_signature_omise_quand_absente(self, _dl):
        self.assertNotIn('Signature client', self._html())

    def test_signature_rendue_quand_presente(self, _dl):
        self.intervention.signature_client = (
            'data:image/png;base64,NTSRV28FAKESIGNATURE')
        self.intervention.signataire_nom = 'Karim Bennani'
        self.intervention.save(
            update_fields=['signature_client', 'signataire_nom'])
        html = self._html()
        self.assertIn('Signature client', html)
        self.assertIn('Karim Bennani', html)

    def test_document_marque_interne(self, _dl):
        self.assertIn('Document interne', self._html())

    # ── Moteur : WeasyPrint, JAMAIS le quote_engine (règle #4) ───────────
    def test_n_utilise_pas_le_moteur_de_devis(self, _dl):
        import apps.sav.pdf as sav_pdf

        with open(sav_pdf.__file__, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertNotIn('quote_engine', source)

    # ── Endpoint ─────────────────────────────────────────────────────────
    def test_endpoint_renvoie_un_pdf(self, _dl):
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(resp.content[:4], b'%PDF')
        self.assertIn('fiche-ticket-SAV-NTSRV28-1.pdf',
                      resp['Content-Disposition'])

    def test_endpoint_autre_societe_404(self, _dl):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv28-b', defaults={'nom': 'Autre NTSRV28'})
        client_etranger = Client.objects.create(
            company=autre, nom='Étranger', prenom='X')
        etranger = Ticket.objects.create(
            company=autre, reference='SAV-NTSRV28-ETR',
            client=client_etranger)
        resp = self.api.get(self._url(etranger.pk))
        self.assertEqual(resp.status_code, 404)
