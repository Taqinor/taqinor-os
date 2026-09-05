"""AUD129 — « Consigner une relance (aucun envoi) » envoyait vraiment un email.

Deux moitiés du même écran :

(a) PAY-4 — le backend faisait ``if request.data.get('envoyer_email', True):``
    (l'envoi était le DÉFAUT) alors que la modale annonce littéralement
    « Cette action journalise la relance (aucun envoi). » et que le lot
    (``doConsigner``) poste ``{niveau}`` seul. Un gestionnaire qui « consigne »
    en lot sur 40 clients envoyait 40 mises en demeure.

(b) PAY-19 — la note saisie n'alimentait que ``RelanceLog.note`` : l'email
    était construit avec ``message=(lvl.message if lvl else '')``, donc la
    personnalisation était perdue pour le destinataire.

Après correctif : l'envoi est un OPT-IN explicite (``envoyer_email=true``) et
le corps de l'email utilise ``note or lvl.message``.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import (
    EmailLog, Facture, FollowupLevel, RelanceLog,
)

User = get_user_model()


class TestAud129RelanceConsigner(TestCase):
    """Le chemin « consigner » ne doit RIEN envoyer sans opt-in explicite."""

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='aud129-co', defaults={'nom': 'AUD129 Co'})[0]
        self.user = User.objects.create_user(
            username='aud129_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.niveau = FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel amiable',
            delai_jours=7, message='Message générique du niveau configuré.')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur AUD129',
            email='debiteur.aud129@example.com', telephone='+212600000129')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD129-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('1000.00'),
            date_echeance=date.today() - timedelta(days=30))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        mail.outbox = []

    def _url(self):
        return f'/api/django/ventes/factures/{self.facture.id}/relancer/'

    def test_consigner_sans_envoyer_email_n_envoie_rien(self):
        """(a) Le corps du lot ``{niveau}`` seul ne doit produire AUCUN email."""
        resp = self.api.post(
            self._url(), {'niveau': 1}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # La relance est bien consignée…
        self.assertTrue(
            RelanceLog.objects.filter(facture=self.facture).exists())
        # …mais rien n'est parti.
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EmailLog.objects.filter(
            facture=self.facture,
            direction=EmailLog.Direction.SORTANT).exists())
        self.assertIsNone(resp.data.get('email_log_id'))

    def test_consigner_avec_note_sans_case_n_envoie_rien(self):
        """Le chemin unitaire de la modale (niveau+note+date) reste muet."""
        nxt = (date.today() + timedelta(days=7)).isoformat()
        resp = self.api.post(
            self._url(),
            {'niveau': 1, 'note': 'Appelé — promet de payer vendredi.',
             'prochaine_relance': nxt},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 0)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.prochaine_relance.isoformat(), nxt)

    def test_envoi_explicite_utilise_la_note_saisie(self):
        """(b) Avec la case cochée, le corps porte EXACTEMENT la note saisie."""
        note = 'Bonjour, votre chèque du 12/08 est revenu impayé.'
        resp = self.api.post(
            self._url(),
            {'niveau': 1, 'note': note, 'envoyer_email': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].body
        self.assertIn(note, corps)
        # Le message générique du niveau ne doit PAS remplacer la note.
        self.assertNotIn('Message générique du niveau configuré.', corps)
        self.assertIsNotNone(resp.data.get('email_log_id'))

    def test_envoi_explicite_sans_note_retombe_sur_le_niveau(self):
        """Sans note saisie, le message configuré du niveau reste utilisé."""
        resp = self.api.post(
            self._url(), {'niveau': 1, 'envoyer_email': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            'Message générique du niveau configuré.', mail.outbox[0].body)
