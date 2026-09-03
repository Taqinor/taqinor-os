"""Tests AUD139 — le mot de passe temporaire du portail est FORCÉ à changer.

Défaut d'origine : ``provisionner_compte_portail_client`` créait le compte
avec ``must_change_password=True`` et sa docstring garantissait que « le
client DOIT le changer à sa première session » — mais le drapeau était INERTE.
Grep backend : le modèle, les serializers et des tests, aucune permission,
aucun middleware, aucune vue. Le mot de passe temporaire, transmis EN CLAIR
par email, restait donc valide indéfiniment et ouvrait tout l'espace client.

Ces tests étaient ROUGES avant le correctif (200 sur les surfaces portail).

Run :
    python manage.py test apps.portail.tests.test_aud139_mot_de_passe_temporaire -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.permissions import CODE_MOT_DE_PASSE_A_CHANGER
from apps.portail.services import provisionner_compte_portail_client
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

MOT_DE_PASSE_CHOISI = 'Nouveau-MotDePasse-2026!'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD139-{n}',
        email=f'aud139-{company.id}-{n}@example.invalid')


class MotDePasseTemporaireForceTests(TestCase):
    def setUp(self):
        self.company = make_company('aud139-co', 'AUD139 Société')
        self.client_crm = make_client_crm(self.company, 'Alpha')
        self.user, _ = provisionner_compte_portail_client(
            self.company, self.client_crm.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_le_compte_fraichement_provisionne_porte_le_drapeau(self):
        self.assertTrue(self.user.must_change_password)

    def test_les_surfaces_portail_sont_refusees_avec_le_code_dedie(self):
        """ROUGE avant AUD139 : 200."""
        for url in ('/api/django/portail/mes-factures/',
                    '/api/django/portail/mes-devis/',
                    '/api/django/portail/mes-livraisons/'):
            with self.subTest(url=url):
                res = self.api.get(url)
                self.assertEqual(res.status_code, 403)
                self.assertEqual(
                    res.data.get('code'), CODE_MOT_DE_PASSE_A_CHANGER)

    def test_les_endpoints_de_sortie_restent_joignables(self):
        """Sans eux le client ne pourrait JAMAIS quitter cet état."""
        self.assertEqual(self.api.get('/api/django/auth/me/').status_code, 200)

    def test_apres_le_changement_lespace_client_souvre(self):
        res = self.api.post(
            '/api/django/auth/change-password/',
            {'current_password': self._mot_de_passe_temporaire(),
             'new_password': MOT_DE_PASSE_CHOISI},
            format='json')
        self.assertEqual(res.status_code, 200, res.data)

        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)

        api = APIClient()
        api.force_authenticate(user=self.user)
        self.assertEqual(
            api.get('/api/django/portail/mes-factures/').status_code, 200)

    # ── Utilitaire ─────────────────────────────────────────────────────────

    def _mot_de_passe_temporaire(self):
        """Le service ne RENVOIE jamais le mot de passe temporaire (c'est le
        contrat NTPRT2) : on en pose donc un connu directement en base pour
        pouvoir exercer ``/auth/change-password/``, sans toucher au drapeau."""
        connu = 'Temporaire-AUD139-2026!'
        self.user.set_password(connu)
        self.user.save(update_fields=['password'])
        return connu


class MotDePasseTemporaireInterneTests(TestCase):
    """Un compte INTERNE n'est pas concerné par cette garde portail.

    L'enforcement vit dans les gardes ``/api/django/portail/*`` : il ne doit
    pas déborder sur le parcours interne (dont la rotation forcée N96 est
    pilotée par un admin et gérée par ses propres écrans).
    """

    def test_le_drapeau_ninterdit_rien_a_un_interne(self):
        company = make_company('aud139-co-int', 'AUD139 Interne')
        user = CustomUser.objects.create_user(
            username='aud139-interne', password='motdepasse-test-1234',
            company=company, is_superuser=True)
        user.must_change_password = True
        user.save(update_fields=['must_change_password'])

        api = APIClient()
        api.force_authenticate(user=user)
        self.assertEqual(api.get('/api/django/auth/me/').status_code, 200)
