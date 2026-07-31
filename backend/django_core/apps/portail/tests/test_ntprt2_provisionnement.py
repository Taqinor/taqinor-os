"""Tests NTPRT2 — Provisionnement d'un VRAI compte utilisateur portail client.

Couvre :

* le service crée un ``CustomUser`` ``portee=portail_client`` rattaché au
  client par ``portail_client_id`` (fondation NTPRT1), porteur du rôle système
  « Portail client » (aucune permission interne) ;
* idempotence : deux appels ne créent qu'UN compte, et un compte désactivé
  (accès révoqué) n'est JAMAIS réactivé silencieusement ;
* isolation multi-tenant : un ``client_id`` d'une AUTRE société ne provisionne
  rien (jamais un compte croisé) ;
* le ``token_acces`` historique est CONSERVÉ intact (les liens email existants
  continuent de fonctionner — le token devient un magic-link complémentaire) ;
* l'endpoint ``POST /api/django/portail/comptes-portail/{id}/provisionner-acces/``
  est réservé à l'ADMINISTRATEUR : un Responsable et un compte portail externe
  reçoivent 403, et la réponse ne contient JAMAIS le mot de passe temporaire.

Run :
    python manage.py test apps.portail.tests.test_ntprt2_provisionnement -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import ComptePortailClient
from apps.portail.services import provisionner_compte_portail_client
from apps.roles.models import ROLE_PORTAIL_CLIENT, Role
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par société.

    Deux sociétés qui partageraient un slug généré identique rendraient tout
    test d'isolation croisée vide de sens (il testerait la même société deux
    fois) : chaque appelant passe donc son propre slug.
    """
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email=None):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT2-{n}',
        email=email if email is not None
        else f'ntprt2-{company.id}-{n}@example.invalid')


def make_role(company, nom, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=nom,
        defaults={'permissions': list(permissions), 'est_systeme': True})
    return role


def make_user(company, username, permissions):
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=make_role(company, f'role-{username}',
                                        permissions))
    return user


class ServiceProvisionnementTests(TestCase):
    """Le service de provisionnement lui-même."""

    def setUp(self):
        self.company = make_company('ntprt2-co-a', 'NTPRT2 Société A')

    def test_cree_un_compte_utilisateur_portail_scope(self):
        client = make_client(self.company)
        user, cree = provisionner_compte_portail_client(
            self.company, client.id)

        self.assertTrue(cree)
        self.assertIsNotNone(user)
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_CLIENT)
        self.assertEqual(user.portail_client_id, client.id)
        self.assertEqual(user.company_id, self.company.id)
        self.assertEqual(user.email, client.email)
        # Le compte DOIT changer son mot de passe temporaire (N96).
        self.assertTrue(user.must_change_password)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_le_role_portail_ne_porte_aucune_permission_interne(self):
        client = make_client(self.company)
        user, _ = provisionner_compte_portail_client(self.company, client.id)

        self.assertEqual(user.role.nom, ROLE_PORTAIL_CLIENT)
        self.assertEqual(user.role.permissions, ['portail_client_acces'])
        # Aucun code interne (le préfixe portail_ est un axe séparé).
        self.assertFalse(user.is_admin_role)
        for code in ('crm_voir', 'ventes_voir', 'stock_voir', 'roles_gerer'):
            self.assertFalse(user.has_erp_permission(code), code)

    def test_le_compte_portail_et_son_token_sont_conserves(self):
        client = make_client(self.company)
        compte = ComptePortailClient.objects.create(
            company=self.company, client=client, token_acces='token-ntprt2-1')

        provisionner_compte_portail_client(self.company, client.id)

        compte.refresh_from_db()
        # Le magic-link historique n'est jamais régénéré ni invalidé.
        self.assertEqual(compte.token_acces, 'token-ntprt2-1')
        self.assertEqual(
            ComptePortailClient.objects.filter(
                company=self.company, client=client).count(), 1)

    def test_cree_le_compte_portail_si_absent(self):
        client = make_client(self.company)
        provisionner_compte_portail_client(self.company, client.id)
        compte = ComptePortailClient.objects.get(
            company=self.company, client=client)
        self.assertTrue(compte.token_acces)

    def test_idempotent_un_seul_utilisateur(self):
        client = make_client(self.company)
        premier, cree1 = provisionner_compte_portail_client(
            self.company, client.id)
        second, cree2 = provisionner_compte_portail_client(
            self.company, client.id)

        self.assertTrue(cree1)
        self.assertFalse(cree2)
        self.assertEqual(premier.id, second.id)
        self.assertEqual(
            CustomUser.objects.filter(
                company=self.company,
                portail_client_id=client.id).count(), 1)

    def test_ne_reactive_jamais_un_acces_revoque(self):
        """Re-provisionner ne doit PAS ré-ouvrir un accès explicitement coupé."""
        client = make_client(self.company)
        user, _ = provisionner_compte_portail_client(self.company, client.id)
        user.is_active = False
        user.save(update_fields=['is_active'])
        ancien_hash = user.password

        rendu, cree = provisionner_compte_portail_client(
            self.company, client.id)
        rendu.refresh_from_db()

        self.assertFalse(cree)
        self.assertFalse(rendu.is_active)
        # Ni mot de passe réinitialisé (pas de reprise d'accès déguisée).
        self.assertEqual(rendu.password, ancien_hash)

    def test_username_unique_meme_email_dans_deux_societes(self):
        autre = make_company('ntprt2-co-b', 'NTPRT2 Société B')
        email = 'homonyme-ntprt2@example.invalid'
        c1 = make_client(self.company, email=email)
        c2 = make_client(autre, email=email)

        u1, _ = provisionner_compte_portail_client(self.company, c1.id)
        u2, _ = provisionner_compte_portail_client(autre, c2.id)

        self.assertNotEqual(u1.username, u2.username)
        self.assertNotEqual(u1.id, u2.id)

    def test_client_d_une_autre_societe_ne_provisionne_rien(self):
        autre = make_company('ntprt2-co-c', 'NTPRT2 Société C')
        client_autre = make_client(autre)

        user, cree = provisionner_compte_portail_client(
            self.company, client_autre.id)

        self.assertIsNone(user)
        self.assertFalse(cree)
        self.assertFalse(
            CustomUser.objects.filter(
                portail_client_id=client_autre.id).exists())

    def test_company_ou_client_absent_est_inerte(self):
        self.assertEqual(
            provisionner_compte_portail_client(None, 1), (None, False))
        self.assertEqual(
            provisionner_compte_portail_client(self.company, None),
            (None, False))


class EndpointProvisionnementTests(TestCase):
    """La garde de l'endpoint ``provisionner-acces`` (admin interne SEUL)."""

    def setUp(self):
        self.company = make_company('ntprt2-api-a', 'NTPRT2 API A')
        self.client_crm = make_client(self.company)
        self.compte = ComptePortailClient.objects.create(
            company=self.company, client=self.client_crm,
            token_acces='token-ntprt2-api')
        self.url = ('/api/django/portail/comptes-portail/'
                    f'{self.compte.id}/provisionner-acces/')
        self.api = APIClient()

    def _admin(self):
        return make_user(self.company, 'ntprt2-admin',
                         ['roles_gerer', 'crm_voir'])

    def _responsable(self):
        # Porteur d'un rôle sans ``roles_gerer`` : ``is_responsable`` est vrai
        # (il passerait la garde de CLASSE) mais ``is_admin_role`` est faux.
        return make_user(self.company, 'ntprt2-resp', ['crm_voir',
                                                       'ventes_voir'])

    def test_admin_provisionne_et_le_mot_de_passe_ne_fuite_pas(self):
        self.api.force_authenticate(user=self._admin())
        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['cree'])
        user = CustomUser.objects.get(id=res.data['utilisateur_id'])
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_CLIENT)
        self.assertEqual(user.portail_client_id, self.client_crm.id)
        # Aucun secret dans la réponse.
        corps = str(res.data).lower()
        for interdit in ('password', 'mot_de_passe', 'motdepasse'):
            self.assertNotIn(interdit, corps)

    def test_responsable_non_admin_refuse(self):
        self.api.force_authenticate(user=self._responsable())
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(
            CustomUser.objects.filter(
                portail_client_id=self.client_crm.id).exists())

    def test_anonyme_refuse(self):
        res = APIClient().post(self.url, {}, format='json')
        self.assertIn(res.status_code, (401, 403))

    def test_compte_portail_externe_refuse(self):
        user, _ = provisionner_compte_portail_client(
            self.company, self.client_crm.id)
        self.api.force_authenticate(user=user)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_compte_d_une_autre_societe_ne_voit_pas_la_ressource(self):
        autre = make_company('ntprt2-api-b', 'NTPRT2 API B')
        etranger = make_user(autre, 'ntprt2-admin-b', ['roles_gerer'])
        self.api.force_authenticate(user=etranger)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_idempotent_via_endpoint(self):
        self.api.force_authenticate(user=self._admin())
        premier = self.api.post(self.url, {}, format='json')
        second = self.api.post(self.url, {}, format='json')

        self.assertEqual(premier.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(premier.data['cree'])
        self.assertFalse(second.data['cree'])
        self.assertEqual(
            CustomUser.objects.filter(
                portail_client_id=self.client_crm.id).count(), 1)
