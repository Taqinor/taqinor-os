"""ADOC115 — un membre d'équipe portail révoqué n'est jamais ressuscité.

Constat (C-ADOC-044, sondes #84/#92) :
* basculer « Actif » off puis on (``_basculer_acces_portail_client``)
  réactivait TOUS les comptes portail du client — y compris un membre dont
  l'invitation avait été révoquée par l'admin (is_active=True, rôle
  « ecriture ») ;
* ``role_portail_client`` retombait sur ``ECRITURE`` pour un compte dont
  l'invitation n'était pas acceptée ;
* DELETE du compte portail (204) supprimait en cascade les invitations : le
  membre, sans invitation, devenait « admin » (``est_admin_portail_client``).

Run :
    python manage.py test apps.portail.tests.test_adoc_equipe_revocation -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.portail.models import ComptePortailClient, InvitationPortail
from apps.portail.services import (
    accepter_invitation_portail,
    est_admin_portail_client,
    inviter_membre_portail,
    provisionner_compte_portail_client,
    revoquer_invitation_portail,
    role_portail_client,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

RACINE = '/api/django/portail/comptes-portail/'


class EquipeRevocationTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc115-{n}', defaults={'nom': f'ADOC115 {n}'})
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client', prenom='ADOC115',
            email=f'adoc115-{n}@example.invalid')
        self.admin, _ = provisionner_compte_portail_client(
            self.co, self.client_crm.id)
        self.admin.must_change_password = False
        self.admin.save(update_fields=['must_change_password'])
        self.compte = ComptePortailClient.objects.get(
            company=self.co, client_id=self.client_crm.id)

        # Membre « lecture » invité, accepté, puis RÉVOQUÉ par l'admin.
        invitation = inviter_membre_portail(
            self.co, self.client_crm.id, f'revoque-{n}@example.invalid',
            'lecture')
        self.revoque = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-revoque-1234')
        revoquer_invitation_portail(self.co, invitation.id)
        self.invitation_revoquee = invitation

        # Membre « ecriture » toujours en règle.
        invitation_ok = inviter_membre_portail(
            self.co, self.client_crm.id, f'actif-{n}@example.invalid',
            'ecriture')
        self.membre_ok = accepter_invitation_portail(
            invitation_ok.token_invitation, 'motdepasse-actif-12345')

        self.resp = CustomUser.objects.create_user(
            username=f'adoc115-resp-{n}', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

    def _basculer(self, actif):
        res = self.api.patch(
            f'{RACINE}{self.compte.id}/', {'actif': actif}, format='json')
        self.assertEqual(res.status_code, 200, res.content)

    def test_reactivation_ne_ressuscite_pas_un_membre_revoque(self):
        self.revoque.refresh_from_db()
        self.assertFalse(self.revoque.is_active)

        self._basculer(False)
        self._basculer(True)

        self.revoque.refresh_from_db()
        self.admin.refresh_from_db()
        self.membre_ok.refresh_from_db()
        self.assertFalse(self.revoque.is_active)
        self.assertEqual(role_portail_client(self.revoque),
                         InvitationPortail.Role.LECTURE)
        # L'admin et le membre non révoqué sont bien réactivés.
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.membre_ok.is_active)
        self.invitation_revoquee.refresh_from_db()
        self.assertEqual(self.invitation_revoquee.statut,
                         InvitationPortail.Statut.REVOQUEE)

        # Le membre révoqué ne passe plus l'authentification JWT.
        membre_api = APIClient()
        membre_api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.revoque)}')
        res = membre_api.get('/api/django/portail/mon-equipe/')
        self.assertIn(res.status_code, (401, 403), res.content)

    def test_role_invitation_revoquee_vaut_lecture(self):
        # Même une invitation « ecriture » révoquée ne rend jamais ECRITURE.
        invitation = inviter_membre_portail(
            self.co, self.client_crm.id, 'ex-ecrivain@example.invalid',
            'ecriture')
        ex = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-exmembre-123')
        revoquer_invitation_portail(self.co, invitation.id)
        self.assertEqual(role_portail_client(ex),
                         InvitationPortail.Role.LECTURE)
        self.assertFalse(est_admin_portail_client(ex))
        # L'admin (aucune invitation) garde ECRITURE.
        self.assertEqual(role_portail_client(self.admin),
                         InvitationPortail.Role.ECRITURE)

    def test_delete_compte_portail_refuse(self):
        nb_invitations = InvitationPortail.objects.filter(
            compte_portail_client=self.compte).count()
        self.assertFalse(est_admin_portail_client(self.revoque))

        res = self.api.delete(f'{RACINE}{self.compte.id}/')

        self.assertEqual(res.status_code, 405, res.content)
        self.assertTrue(ComptePortailClient.objects.filter(
            pk=self.compte.id).exists())
        self.assertEqual(InvitationPortail.objects.filter(
            compte_portail_client=self.compte).count(), nb_invitations)
        self.assertFalse(est_admin_portail_client(self.revoque))
