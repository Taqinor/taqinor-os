"""ADOC122 — le mot de passe choisi à l'acceptation d'une invitation portail
passe par la politique (``validate_new_password``).

Constat (C-ADOC-051, sonde #93) : POST
``/api/django/public/portail/invitations/accepter/`` avec
``mot_de_passe='1'`` répondait 200, créait le compte et consommait
l'invitation — quatrième entrée de mot de passe neuf hors politique.

Run :
    python manage.py test apps.portail.tests.test_adoc_invitation_mot_de_passe -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import InvitationPortail
from apps.portail.services import (
    inviter_membre_portail,
    provisionner_compte_portail_client,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

URL = '/api/django/public/portail/invitations/accepter/'


class InvitationMotDePasseTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc122-{n}', defaults={'nom': f'ADOC122 {n}'})
        client = Client.objects.create(
            company=self.co, nom='Client', prenom='ADOC122',
            email=f'adoc122-{n}@example.invalid')
        provisionner_compte_portail_client(self.co, client.id)
        self.email = f'invite-adoc122-{n}@example.invalid'
        self.invitation = inviter_membre_portail(
            self.co, client.id, self.email, 'lecture')
        self.api = APIClient()

    def test_mot_de_passe_faible_refuse(self):
        res = self.api.post(URL, {
            'token': self.invitation.token_invitation, 'mot_de_passe': '1',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        corps = res.json()
        self.assertIn('mot_de_passe', corps)
        self.assertTrue(corps['mot_de_passe'])
        self.assertTrue(all(isinstance(m, str) for m in corps['mot_de_passe']))
        # Rien n'est créé, l'invitation n'est pas consommée.
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.statut,
                         InvitationPortail.Statut.EN_ATTENTE)
        self.assertIsNone(self.invitation.utilisateur_cree_id)
        self.assertFalse(CustomUser.objects.filter(email=self.email).exists())

        # Un mot de passe conforme passe ensuite, sur la MÊME invitation.
        res = self.api.post(URL, {
            'token': self.invitation.token_invitation,
            'mot_de_passe': 'Soleil-Portail-2026!',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(
            res.json()['detail'],
            'Compte créé — vous pouvez maintenant vous connecter.')
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.statut,
                         InvitationPortail.Statut.ACCEPTEE)
        self.assertTrue(CustomUser.objects.filter(email=self.email).exists())

    def test_mot_de_passe_similaire_a_l_email_refuse(self):
        """La règle de similarité reçoit l'utilisateur provisoire."""
        res = self.api.post(URL, {
            'token': self.invitation.token_invitation,
            'mot_de_passe': self.email,
        }, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('mot_de_passe', res.json())
        self.assertFalse(CustomUser.objects.filter(email=self.email).exists())
