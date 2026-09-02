"""Tests AUD141 — le jeton d'accès portail quitte l'écran et l'export CSV.

Défaut d'origine : ``ComptePortailClient.token_acces`` (CharField unique, en
clair, sans expiration ni rotation) était exposé en lecture par
``ComptePortailClientSerializer``, affiché en toutes lettres dans une colonne
de l'écran ERP ET publié dans son export CSV. Or ce jeton authentifie à lui
seul le relevé de compte, son PDF, la contestation de facture et les vues
publiques contrats : un export envoyé par email ou déposé sur un partage
donnait un accès permanent aux relevés financiers de tous les clients de la
société.

Ces tests étaient ROUGES avant le correctif (jeton complet dans la liste ; pas
d'action de régénération).

Note d'honnêteté sur le libellé « → 401 » de la tâche : la surface tokenisée
de ce dépôt répond volontairement 404 sur un jeton inconnu (aucune fuite
d'existence, ``compta.views._portail_not_found``). Le test affirme donc le
comportement RÉEL — l'ancien jeton n'ouvre plus rien.

Run :
    python manage.py test apps.portail.tests.test_aud141_jeton_acces -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta.selectors import compte_portail_par_token
from apps.crm.models import Client
from apps.portail.models import ComptePortailClient
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

RACINE = '/api/django/portail/comptes-portail/'
RACINE_TOKENISEE = '/api/django/compta/portail/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD141-{n}',
        email=f'aud141-{company.id}-{n}@example.invalid')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class JetonAccesPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('aud141-co', 'AUD141 Société')
        self.client_crm = make_client_crm(self.co, 'Alpha')
        self.compte = ComptePortailClient.objects.create(
            company=self.co, client=self.client_crm,
            token_acces='aud141-jeton-secret-complet-0001')
        self.admin = CustomUser.objects.create_user(
            username='aud141-admin', password='motdepasse-test-1234',
            company=self.co, role_legacy='admin', is_superuser=True)
        self.api = auth(self.admin)

    # ── Le jeton ne sort plus de la liste ni de l'export ────────────────────

    def test_la_liste_ne_porte_plus_le_jeton_complet(self):
        """ROUGE avant AUD141 : `token_acces` en clair dans chaque ligne."""
        res = self.api.get(RACINE)
        self.assertEqual(res.status_code, 200, res.content)
        corps = res.content.decode('utf-8', 'replace')
        self.assertNotIn(self.compte.token_acces, corps)
        self.assertNotIn('token_acces', corps)

    def test_la_liste_porte_un_apercu_non_reutilisable(self):
        res = self.api.get(RACINE)
        ligne = (res.data.get('results') or res.data)[0]
        apercu = ligne['token_apercu']
        self.assertTrue(apercu.endswith(self.compte.token_acces[-4:]))
        self.assertNotIn(self.compte.token_acces, apercu)
        # L'export CSV du DataTable est construit sur les mêmes valeurs de
        # ligne : ce qui n'est pas dans le payload ne peut pas y finir.
        self.assertIsNone(compte_portail_par_token(apercu))

    def test_le_detail_non_plus(self):
        res = self.api.get(f'{RACINE}{self.compte.id}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertNotIn(
            self.compte.token_acces, res.content.decode('utf-8', 'replace'))

    # ── Le lien complet se DEMANDE, et c'est journalisé ─────────────────────

    def test_laction_lien_acces_revele_le_lien_a_ladministrateur(self):
        with self.assertLogs('portail.acces', level='INFO') as journal:
            res = self.api.post(f'{RACINE}{self.compte.id}/lien-acces/',
                                {}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['token_acces'], self.compte.token_acces)
        self.assertIn(self.compte.token_acces, res.data['lien'])
        # Journalisé — mais JAMAIS le jeton lui-même.
        trace = '\n'.join(journal.output)
        self.assertIn('lien-acces', trace)
        self.assertNotIn(self.compte.token_acces, trace)

    def test_lien_acces_refuse_a_un_simple_responsable(self):
        responsable = CustomUser.objects.create_user(
            username='aud141-responsable', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        res = auth(responsable).post(
            f'{RACINE}{self.compte.id}/lien-acces/', {}, format='json')
        self.assertEqual(res.status_code, 403, res.content)

    # ── La régénération invalide l'ancien lien ──────────────────────────────

    def test_regenerer_invalide_lancien_jeton(self):
        """ROUGE avant AUD141 : aucune action de régénération n'existait."""
        ancien = self.compte.token_acces
        self.assertIsNotNone(compte_portail_par_token(ancien))

        res = self.api.post(f'{RACINE}{self.compte.id}/regenerer-jeton/',
                            {}, format='json')

        self.assertEqual(res.status_code, 200, res.content)
        self.compte.refresh_from_db()
        self.assertNotEqual(self.compte.token_acces, ancien)
        # L'ancien lien n'ouvre plus rien.
        self.assertIsNone(compte_portail_par_token(ancien))
        self.assertIsNotNone(
            compte_portail_par_token(self.compte.token_acces))
        # La réponse ne renvoie que l'aperçu du NOUVEAU jeton.
        self.assertNotIn('token_acces', res.data)
        self.assertTrue(res.data['token_apercu'])

    def test_lancienne_surface_tokenisee_repond_404_apres_rotation(self):
        ancien = self.compte.token_acces
        self.api.post(f'{RACINE}{self.compte.id}/regenerer-jeton/',
                      {}, format='json')

        public = APIClient()
        res = public.get(f'{RACINE_TOKENISEE}{ancien}/mon-releve/')
        self.assertEqual(res.status_code, 404, res.content)

    def test_regenerer_refuse_a_un_simple_responsable(self):
        responsable = CustomUser.objects.create_user(
            username='aud141-responsable-2', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        res = auth(responsable).post(
            f'{RACINE}{self.compte.id}/regenerer-jeton/', {}, format='json')
        self.assertEqual(res.status_code, 403, res.content)
        self.compte.refresh_from_db()
        self.assertEqual(
            self.compte.token_acces, 'aud141-jeton-secret-complet-0001')

    def test_isolation_societe_sur_les_deux_actions(self):
        autre = make_company('aud141-co-b', 'AUD141 Société B')
        client_b = make_client_crm(autre, 'Beta')
        compte_b = ComptePortailClient.objects.create(
            company=autre, client=client_b, token_acces='aud141-jeton-b')

        for chemin in ('lien-acces', 'regenerer-jeton'):
            with self.subTest(chemin=chemin):
                res = self.api.post(f'{RACINE}{compte_b.id}/{chemin}/',
                                    {}, format='json')
                self.assertEqual(res.status_code, 404, res.content)
        compte_b.refresh_from_db()
        self.assertEqual(compte_b.token_acces, 'aud141-jeton-b')
