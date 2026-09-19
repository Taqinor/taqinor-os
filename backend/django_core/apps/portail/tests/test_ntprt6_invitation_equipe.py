"""Tests NTPRT6 — Invitation & gestion de l'équipe du portail client.

Couvre :

* ``services.inviter_membre_portail`` crée une ``InvitationPortail`` (token,
  expiration, rôle) rattachée à un ``ComptePortailClient`` existant de la
  société appelante — jamais pour un ``client_id`` sans compte provisionné ;
* ``services.accepter_invitation_portail`` crée un 2ᵉ ``CustomUser``
  ``portee=portail_client`` lié au MÊME ``client_id`` que l'admin, avec le
  mot de passe choisi par l'invité (pas de mot de passe temporaire) ; refuse
  un token inconnu/expiré/déjà accepté/révoqué ;
* le rôle ``lecture`` empêche RÉELLEMENT d'accepter un devis et d'ouvrir un
  ticket SAV (critère d'acceptation NTPRT6) — le rôle ``ecriture`` et l'admin
  (compte sans invitation) gardent le comportement d'aujourd'hui ;
* seul l'admin (compte SANS invitation) peut inviter/révoquer — un membre
  d'équipe, même ``ecriture``, ne gère jamais l'équipe lui-même ;
* isolation multi-tenant : rien ne fuit d'une société à l'autre.

Run :
    python manage.py test apps.portail.tests.test_ntprt6_invitation_equipe -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from testkit.time import frozen

from apps.crm.models import Client
from apps.portail.models import InvitationPortail
from apps.portail.services import (
    accepter_invitation_portail,
    est_admin_portail_client,
    inviter_membre_portail,
    peut_ecrire_portail_client,
    provisionner_compte_portail_client,
    role_portail_client,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, email=None):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT6-{n}',
        email=email if email is not None
        else f'ntprt6-{company.id}-{n}@example.invalid')


def make_admin_et_compte(company):
    """Provisionne le compte ADMIN (premier compte, NTPRT2) d'un client.

    AUD139 bloque tout endpoint portail tant que ``must_change_password``
    n'est pas retombé à ``False`` — on simule ici un admin qui a DÉJÀ changé
    son mot de passe temporaire (l'onboarding lui-même n'est pas l'objet de
    ces tests), sinon toute requête de l'admin recevrait un 403
    ``mot_de_passe_a_changer`` sans rapport avec NTPRT6.
    """
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


class ServiceInvitationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt6-co-a', 'NTPRT6 Société A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)

    def test_inviter_cree_une_invitation_avec_token_et_expiration(self):
        # Horloge GELÉE (check_test_determinism) : l'expiration se juge
        # contre l'instant de création, pas contre un now() vivant.
        ancre = timezone.make_aware(timezone.datetime(2026, 9, 15, 12, 0, 0))
        with frozen(ancre):
            invitation = inviter_membre_portail(
                self.company, self.client_crm.id, 'collegue@example.invalid',
                'lecture')

        self.assertIsNotNone(invitation)
        self.assertTrue(invitation.token_invitation)
        self.assertEqual(invitation.role, InvitationPortail.Role.LECTURE)
        self.assertEqual(invitation.statut, InvitationPortail.Statut.EN_ATTENTE)
        self.assertGreater(invitation.expire_le, ancre)

    def test_inviter_role_invalide_retombe_sur_lecture(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'x@example.invalid',
            'super-admin')
        self.assertEqual(invitation.role, InvitationPortail.Role.LECTURE)

    def test_inviter_sans_compte_portail_provisionne_echoue(self):
        client_sans_compte = make_client_crm(self.company)
        invitation = inviter_membre_portail(
            self.company, client_sans_compte.id, 'x@example.invalid',
            'ecriture')
        self.assertIsNone(invitation)

    def test_inviter_client_d_une_autre_societe_echoue(self):
        autre = make_company('ntprt6-co-b', 'NTPRT6 Société B')
        client_autre, _ = make_admin_et_compte(autre)
        invitation = inviter_membre_portail(
            self.company, client_autre.id, 'x@example.invalid', 'ecriture')
        self.assertIsNone(invitation)


class ServiceAcceptationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt6-acc-a', 'NTPRT6 Acceptation A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)
        self.invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'invite@example.invalid',
            'ecriture')

    def test_accepter_cree_un_2e_compte_lie_au_meme_client(self):
        user = accepter_invitation_portail(
            self.invitation.token_invitation, 'motdepasse-invite-1234')

        self.assertIsNotNone(user)
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_CLIENT)
        self.assertEqual(user.portail_client_id, self.client_crm.id)
        self.assertNotEqual(user.id, self.admin.id)
        # L'invité choisit SON mot de passe : pas de changement forcé.
        self.assertFalse(user.must_change_password)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.statut, InvitationPortail.Statut.ACCEPTEE)
        self.assertEqual(self.invitation.utilisateur_cree_id, user.id)
        self.assertIsNotNone(self.invitation.date_acceptation)

    def test_accepter_token_inconnu_echoue(self):
        self.assertIsNone(
            accepter_invitation_portail('token-inexistant', 'x' * 12))

    def test_accepter_deux_fois_ne_cree_pas_un_2e_compte(self):
        premier = accepter_invitation_portail(
            self.invitation.token_invitation, 'motdepasse-invite-1234')
        second = accepter_invitation_portail(
            self.invitation.token_invitation, 'autre-mot-de-passe-1234')
        self.assertIsNotNone(premier)
        self.assertIsNone(second)
        self.assertEqual(
            CustomUser.objects.filter(
                portail_client_id=self.client_crm.id).count(), 2)  # admin + invité

    def test_accepter_invitation_expiree_echoue(self):
        self.invitation.expire_le = timezone.now() - timezone.timedelta(days=1)
        self.invitation.save(update_fields=['expire_le'])
        self.assertIsNone(accepter_invitation_portail(
            self.invitation.token_invitation, 'x' * 12))

    def test_accepter_invitation_revoquee_echoue(self):
        self.invitation.statut = InvitationPortail.Statut.REVOQUEE
        self.invitation.save(update_fields=['statut'])
        self.assertIsNone(accepter_invitation_portail(
            self.invitation.token_invitation, 'x' * 12))


class RolePortailClientTests(TestCase):
    """Le critère d'acceptation NTPRT6 : lecture seule = ni devis, ni ticket."""

    def setUp(self):
        self.company = make_company('ntprt6-role-a', 'NTPRT6 Rôle A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)

    def test_admin_est_toujours_ecriture(self):
        self.assertEqual(
            role_portail_client(self.admin), InvitationPortail.Role.ECRITURE)
        self.assertTrue(peut_ecrire_portail_client(self.admin))
        self.assertTrue(est_admin_portail_client(self.admin))

    def test_membre_lecture_ne_peut_pas_ecrire(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'lecteur@example.invalid',
            'lecture')
        membre = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-lecteur-1234')

        self.assertEqual(
            role_portail_client(membre), InvitationPortail.Role.LECTURE)
        self.assertFalse(peut_ecrire_portail_client(membre))
        self.assertFalse(est_admin_portail_client(membre))

    def test_membre_ecriture_peut_ecrire_mais_nest_pas_admin(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'ecrivain@example.invalid',
            'ecriture')
        membre = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-ecrivain-1234')

        self.assertTrue(peut_ecrire_portail_client(membre))
        self.assertFalse(est_admin_portail_client(membre))


class EndpointDevisEtTicketGatingTests(TestCase):
    """Le rôle lecture bloque RÉELLEMENT les endpoints d'écriture du portail."""

    def setUp(self):
        self.company = make_company('ntprt6-gate-a', 'NTPRT6 Gate A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-NTPRT6-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'lecteur2@example.invalid',
            'lecture')
        self.lecteur = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-lecteur2-1234')
        self.api = APIClient()

    def test_lecture_refuse_l_acceptation_de_devis(self):
        self.api.force_authenticate(user=self.lecteur)
        res = self.api.post(
            f'/api/django/portail/mes-devis/{self.devis.id}/accepter/',
            {'nom': 'Lecteur', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 403)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_admin_accepte_toujours_le_devis(self):
        self.api.force_authenticate(user=self.admin)
        res = self.api.post(
            f'/api/django/portail/mes-devis/{self.devis.id}/accepter/',
            {'nom': 'Admin', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

    def test_lecture_refuse_l_ouverture_de_ticket(self):
        self.api.force_authenticate(user=self.lecteur)
        res = self.api.post(
            '/api/django/portail/mes-demandes-sav/',
            {'sujet': 'Onduleur en défaut'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_admin_ouvre_toujours_un_ticket(self):
        self.api.force_authenticate(user=self.admin)
        res = self.api.post(
            '/api/django/portail/mes-demandes-sav/',
            {'sujet': 'Onduleur en défaut'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)


class MonEquipeEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt6-eq-a', 'NTPRT6 Équipe A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)
        self.api = APIClient()

    def test_admin_invite_un_collegue(self):
        self.api.force_authenticate(user=self.admin)
        res = self.api.post('/api/django/portail/mon-equipe/', {
            'email': 'nouveau@example.invalid', 'role': 'ecriture',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(
            InvitationPortail.objects.filter(
                company=self.company, email='nouveau@example.invalid',
            ).exists())

    def test_membre_ne_peut_pas_inviter(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'membre@example.invalid',
            'ecriture')
        membre = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-membre-1234')
        self.api.force_authenticate(user=membre)
        res = self.api.post('/api/django/portail/mon-equipe/', {
            'email': 'x@example.invalid', 'role': 'lecture',
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_membre_peut_consulter_le_roster(self):
        inviter_membre_portail(
            self.company, self.client_crm.id, 'visible@example.invalid',
            'lecture')
        self.api.force_authenticate(user=self.admin)
        res = self.api.get('/api/django/portail/mon-equipe/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['count'] if 'count' in res.data
                         else len(res.data['results']), 1)

    def test_admin_revoque_ferme_l_acces_du_compte_deja_accepte(self):
        invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'revoque@example.invalid',
            'ecriture')
        membre = accepter_invitation_portail(
            invitation.token_invitation, 'motdepasse-revoque-1234')
        self.api.force_authenticate(user=self.admin)
        res = self.api.post(
            f'/api/django/portail/mon-equipe/{invitation.id}/revoquer/',
            {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        membre.refresh_from_db()
        self.assertFalse(membre.is_active)
        invitation.refresh_from_db()
        self.assertEqual(invitation.statut, InvitationPortail.Statut.REVOQUEE)

    def test_isolation_societe_sur_le_roster(self):
        autre = make_company('ntprt6-eq-b', 'NTPRT6 Équipe B')
        client_autre, admin_autre = make_admin_et_compte(autre)
        inviter_membre_portail(
            autre, client_autre.id, 'etranger@example.invalid', 'lecture')

        self.api.force_authenticate(user=self.admin)
        res = self.api.get('/api/django/portail/mon-equipe/')
        self.assertEqual(res.status_code, 200)
        results = res.data.get('results', res.data)
        self.assertEqual(len(results), 0)


class PublicAcceptationEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt6-pub-a', 'NTPRT6 Public A')
        self.client_crm, self.admin = make_admin_et_compte(self.company)
        self.invitation = inviter_membre_portail(
            self.company, self.client_crm.id, 'public@example.invalid',
            'lecture')
        self.api = APIClient()

    def test_accepter_via_endpoint_public(self):
        res = self.api.post('/api/django/public/portail/invitations/accepter/', {
            'token': self.invitation.token_invitation,
            'mot_de_passe': 'motdepasse-public-1234',
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(
            CustomUser.objects.filter(email='public@example.invalid').exists())

    def test_token_absent_refuse(self):
        res = self.api.post('/api/django/public/portail/invitations/accepter/', {
            'mot_de_passe': 'x' * 12,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_token_invalide_refuse(self):
        res = self.api.post('/api/django/public/portail/invitations/accepter/', {
            'token': 'invalide', 'mot_de_passe': 'x' * 12,
        }, format='json')
        self.assertEqual(res.status_code, 400)
