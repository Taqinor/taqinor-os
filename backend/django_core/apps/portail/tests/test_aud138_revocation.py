"""Tests AUD138 — « Révoquer » un compte portail révoque VRAIMENT l'accès.

Défaut d'origine : l'écran ERP PATCHait ``ComptePortailClient.actif`` et
annonçait que la révocation « empêche la prochaine connexion ». Or ``actif``
n'était lu QUE par le chemin magic-link tokenisé
(``compta.selectors.compte_portail_par_token``) : le mécanisme d'accès
PRIMAIRE depuis NTPRT2 est le ``CustomUser`` ``portee=portail_client`` + JWT,
dont la garde ``roles.permissions._IsPortalUserOfScope`` ne lisait que
``is_authenticated`` / ``portee`` / ``portail_client_id``. Un client révoqué
après un litige continuait donc de consulter ses devis et ses factures.

Ces tests étaient ROUGES avant le correctif (200 sur les trois surfaces).

Run :
    python manage.py test apps.portail.tests.test_aud138_revocation -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.portail.models import ComptePortailClient
from apps.portail.services import (
    reactiver_acces_client,
    revoquer_acces_client,
)
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    Role,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD138-{n}',
        email=f'aud138-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


class RevocationAccesPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('aud138-co', 'AUD138 Société')
        self.client_crm = make_client_crm(self.company, 'Alpha')
        self.compte = ComptePortailClient.objects.create(
            company=self.company, client=self.client_crm,
            token_acces='aud138-token-alpha')
        self.user = make_portal_user(
            self.company, 'aud138-portail-a', self.client_crm.id)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AUD138-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.api = APIClient()

    # ── Le cœur du défaut : le JWT déjà émis ────────────────────────────────

    def test_revocation_ferme_les_trois_surfaces_avec_le_jwt_deja_emis(self):
        """ROUGE avant AUD138 : 200 sur les trois."""
        self.api.force_authenticate(user=self.user)
        self.assertEqual(
            self.api.get('/api/django/portail/mes-devis/').status_code, 200)

        revoquer_acces_client(self.company, self.client_crm.id)
        self.user.refresh_from_db()

        # ``force_authenticate`` court-circuite l'authentification : c'est donc
        # la GARDE de portée qui doit refuser (et non seulement SimpleJWT).
        self.api.force_authenticate(user=self.user)
        self.assertEqual(
            self.api.get('/api/django/portail/mes-devis/').status_code, 403)
        self.assertEqual(
            self.api.get('/api/django/portail/mes-factures/').status_code, 403)
        res = self.api.post(
            f'/api/django/portail/mes-devis/{self.devis.id}/accepter/',
            {'nom': 'Client Alpha', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_le_jeton_jwt_deja_distribue_ne_passe_plus(self):
        """Le vrai chemin de production : jeton émis AVANT la révocation."""
        jeton = str(AccessToken.for_user(self.user))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {jeton}')
        self.assertEqual(
            api.get('/api/django/portail/mes-devis/').status_code, 200)

        revoquer_acces_client(self.company, self.client_crm.id)

        # SimpleJWT refuse un utilisateur inactif dès l'authentification.
        self.assertEqual(
            api.get('/api/django/portail/mes-devis/').status_code, 401)

    # ── Le service ferme les DEUX portes, symétriquement ────────────────────

    def test_le_service_ferme_le_magic_link_et_le_compte_utilisateur(self):
        compte, nb = revoquer_acces_client(self.company, self.client_crm.id)

        self.assertEqual(nb, 1)
        self.compte.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.compte.actif)
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(compte)

    def test_la_reactivation_est_symetrique_et_explicite(self):
        revoquer_acces_client(self.company, self.client_crm.id)
        reactiver_acces_client(self.company, self.client_crm.id)

        self.compte.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(self.compte.actif)
        self.assertTrue(self.user.is_active)

        self.api.force_authenticate(user=self.user)
        self.assertEqual(
            self.api.get('/api/django/portail/mes-devis/').status_code, 200)

    def test_un_client_dune_autre_societe_nest_jamais_touche(self):
        autre = make_company('aud138-co-b', 'AUD138 Société B')
        client_b = make_client_crm(autre, 'Beta')
        compte_b = ComptePortailClient.objects.create(
            company=autre, client=client_b, token_acces='aud138-token-beta')
        user_b = make_portal_user(autre, 'aud138-portail-b', client_b.id)

        # Même id de client, mais dans une AUTRE société : rien ne bouge.
        revoquer_acces_client(self.company, client_b.id)

        compte_b.refresh_from_db()
        user_b.refresh_from_db()
        self.assertTrue(compte_b.actif)
        self.assertTrue(user_b.is_active)

    # ── L'écran ERP : le PATCH `actif` passe par le service ─────────────────

    def test_le_patch_actif_de_lecran_erp_revoque_reellement(self):
        admin_role, _ = Role.objects.get_or_create(
            company=self.company, nom='AUD138 Admin',
            defaults={'permissions': ['roles_gerer']})
        admin = CustomUser.objects.create_user(
            username='aud138-admin', password='motdepasse-test-1234',
            company=self.company, role=admin_role, is_superuser=True)
        api = APIClient()
        api.force_authenticate(user=admin)

        res = api.patch(
            f'/api/django/portail/comptes-portail/{self.compte.id}/',
            {'actif': False}, format='json')

        self.assertIn(res.status_code, (200, 202))
        self.compte.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.compte.actif)
        # ROUGE avant AUD138 : le compte utilisateur restait actif.
        self.assertFalse(self.user.is_active)
