"""Tests NTPRT4 — Provisionnement d'un VRAI compte utilisateur portail
partenaire.

Même mécanique que NTPRT2 (portail client), pour ``crm.Partenaire``
(apporteurs/sous-revendeurs/installateurs — modèle vivant dans ``apps.crm``
depuis ODX13). SOLMVP16 — le service portail le lit désormais via le
sélecteur ``apps.crm.selectors.partenaire_pour_certification`` (jamais un
import de ``apps.crm.models`` — frontière cross-app CLAUDE.md) ; ce test
crée directement l'objet ``crm.Partenaire`` pour les besoins de la fixture.

Couvre :

* le service crée un ``CustomUser`` ``portee=portail_partenaire`` rattaché au
  partenaire par ``portail_partenaire_id`` (fondation NTPRT1), porteur du rôle
  système « Portail partenaire » (aucune permission interne) ;
* idempotence : deux appels ne créent qu'UN compte, et un compte désactivé
  (accès révoqué) n'est JAMAIS réactivé silencieusement ;
* isolation multi-tenant : un ``partenaire_id`` d'une AUTRE société ne
  provisionne rien (jamais un compte croisé) ;
* le ``token_acces`` historique du partenaire est CONSERVÉ intact ;
* l'endpoint ``POST /api/django/compta/partenaires/{id}/provisionner-acces/``
  est réservé à l'ADMINISTRATEUR : un Responsable et un compte portail externe
  reçoivent 403, et la réponse ne contient JAMAIS le mot de passe temporaire.

Run :
    python manage.py test apps.portail.tests.test_ntprt4_provisionnement_partenaire -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Partenaire
from apps.portail.services import provisionner_compte_partenaire
from apps.roles.models import ROLE_PORTAIL_PARTENAIRE, Role
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par société (sinon un
    test d'isolation croisée re-teste la même société deux fois)."""
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_partenaire(company, email=None, token=None):
    n = next(_seq)
    return Partenaire.objects.create(
        company=company, nom=f'Partenaire NTPRT4-{n}',
        email=email if email is not None
        else f'ntprt4-{company.id}-{n}@example.invalid',
        token_acces=token or f'tok-ntprt4-{company.id}-{n}')


def make_role(company, nom, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=nom,
        defaults={'permissions': list(permissions), 'est_systeme': True})
    return role


def make_user(company, username, permissions):
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=make_role(company, f'role-{username}',
                                        permissions))


class ServiceProvisionnementPartenaireTests(TestCase):
    """Le service de provisionnement lui-même."""

    def setUp(self):
        self.company = make_company('ntprt4-co-a', 'NTPRT4 Société A')

    def test_cree_un_compte_utilisateur_portail_scope(self):
        partenaire = make_partenaire(self.company)
        user, cree = provisionner_compte_partenaire(
            self.company, partenaire.id)

        self.assertTrue(cree)
        self.assertIsNotNone(user)
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_PARTENAIRE)
        self.assertEqual(user.portail_partenaire_id, partenaire.id)
        self.assertEqual(user.company_id, self.company.id)
        self.assertEqual(user.email, partenaire.email)
        # Le compte DOIT changer son mot de passe temporaire (N96).
        self.assertTrue(user.must_change_password)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_le_role_portail_ne_porte_aucune_permission_interne(self):
        partenaire = make_partenaire(self.company)
        user, _ = provisionner_compte_partenaire(self.company, partenaire.id)

        self.assertEqual(user.role.nom, ROLE_PORTAIL_PARTENAIRE)
        self.assertEqual(user.role.permissions, ['portail_partenaire_acces'])
        self.assertFalse(user.is_admin_role)
        for code in ('crm_voir', 'ventes_voir', 'stock_voir', 'roles_gerer'):
            self.assertFalse(user.has_erp_permission(code), code)

    def test_le_token_acces_du_partenaire_est_conserve(self):
        partenaire = make_partenaire(self.company, token='token-ntprt4-1')
        provisionner_compte_partenaire(self.company, partenaire.id)

        partenaire.refresh_from_db()
        # Le lien tokenisé historique n'est jamais régénéré ni invalidé.
        self.assertEqual(partenaire.token_acces, 'token-ntprt4-1')

    def test_idempotent_un_seul_utilisateur(self):
        partenaire = make_partenaire(self.company)
        premier, cree1 = provisionner_compte_partenaire(
            self.company, partenaire.id)
        second, cree2 = provisionner_compte_partenaire(
            self.company, partenaire.id)

        self.assertTrue(cree1)
        self.assertFalse(cree2)
        self.assertEqual(premier.id, second.id)
        self.assertEqual(
            CustomUser.objects.filter(
                company=self.company,
                portail_partenaire_id=partenaire.id).count(), 1)

    def test_ne_reactive_jamais_un_acces_revoque(self):
        """Re-provisionner ne doit PAS ré-ouvrir un accès explicitement coupé."""
        partenaire = make_partenaire(self.company)
        user, _ = provisionner_compte_partenaire(self.company, partenaire.id)
        user.is_active = False
        user.save(update_fields=['is_active'])
        ancien_hash = user.password

        rendu, cree = provisionner_compte_partenaire(
            self.company, partenaire.id)
        rendu.refresh_from_db()

        self.assertFalse(cree)
        self.assertFalse(rendu.is_active)
        self.assertEqual(rendu.password, ancien_hash)

    def test_username_unique_meme_email_dans_deux_societes(self):
        autre = make_company('ntprt4-co-b', 'NTPRT4 Société B')
        email = 'homonyme-ntprt4@example.invalid'
        p1 = make_partenaire(self.company, email=email)
        p2 = make_partenaire(autre, email=email)

        u1, _ = provisionner_compte_partenaire(self.company, p1.id)
        u2, _ = provisionner_compte_partenaire(autre, p2.id)

        self.assertNotEqual(u1.username, u2.username)
        self.assertNotEqual(u1.id, u2.id)

    def test_partenaire_d_une_autre_societe_ne_provisionne_rien(self):
        autre = make_company('ntprt4-co-c', 'NTPRT4 Société C')
        partenaire_autre = make_partenaire(autre)

        user, cree = provisionner_compte_partenaire(
            self.company, partenaire_autre.id)

        self.assertIsNone(user)
        self.assertFalse(cree)
        self.assertFalse(
            CustomUser.objects.filter(
                portail_partenaire_id=partenaire_autre.id).exists())

    def test_company_ou_partenaire_absent_est_inerte(self):
        self.assertEqual(
            provisionner_compte_partenaire(None, 1), (None, False))
        self.assertEqual(
            provisionner_compte_partenaire(self.company, None),
            (None, False))


class EndpointProvisionnementPartenaireTests(TestCase):
    """La garde de l'endpoint ``provisionner-acces`` (admin interne SEUL)."""

    def setUp(self):
        self.company = make_company('ntprt4-api-a', 'NTPRT4 API A')
        self.partenaire = make_partenaire(self.company)
        self.url = ('/api/django/compta/partenaires/'
                    f'{self.partenaire.id}/provisionner-acces/')
        self.api = APIClient()

    def _admin(self):
        return make_user(self.company, 'ntprt4-admin',
                         ['roles_gerer', 'crm_voir'])

    def _responsable(self):
        # Porteur d'un rôle sans ``roles_gerer`` : ``is_responsable`` est vrai
        # (il passerait la garde de CLASSE ``IsResponsableOrAdmin``) mais
        # ``is_admin_role`` est faux.
        return make_user(
            self.company, 'ntprt4-resp', ['crm_voir', 'ventes_voir'])

    def test_admin_provisionne_et_le_mot_de_passe_ne_fuite_pas(self):
        self.api.force_authenticate(user=self._admin())
        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['cree'])
        user = CustomUser.objects.get(id=res.data['utilisateur_id'])
        self.assertEqual(user.portee, CustomUser.PORTEE_PORTAIL_PARTENAIRE)
        self.assertEqual(user.portail_partenaire_id, self.partenaire.id)
        corps = str(res.data).lower()
        for interdit in ('password', 'mot_de_passe', 'motdepasse'):
            self.assertNotIn(interdit, corps)

    def test_responsable_non_admin_refuse(self):
        self.api.force_authenticate(user=self._responsable())
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(
            CustomUser.objects.filter(
                portail_partenaire_id=self.partenaire.id).exists())

    def test_anonyme_refuse(self):
        res = APIClient().post(self.url, {}, format='json')
        self.assertIn(res.status_code, (401, 403))

    def test_compte_portail_externe_refuse(self):
        user, _ = provisionner_compte_partenaire(
            self.company, self.partenaire.id)
        self.api.force_authenticate(user=user)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_compte_d_une_autre_societe_ne_voit_pas_la_ressource(self):
        autre = make_company('ntprt4-api-b', 'NTPRT4 API B')
        etranger = make_user(autre, 'ntprt4-admin-b', ['roles_gerer'])
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
                portail_partenaire_id=self.partenaire.id).count(), 1)
