"""AUD716 — ``salaire_base`` est gaté ``salaires_voir``, dans les deux sens.

ÉTAT AVANT LE FIX. ``ProfilPaieSerializer.Meta.fields`` incluait
``salaire_base`` en écriture normale (absent de ``read_only_fields``), et
``ProfilPaieViewSet`` n'était gardé que par ``paie_voir`` (lecture) /
``paie_gerer`` (écriture) — jamais ``salaires_voir``. La MÊME donnée est
pourtant strictement gatée ``salaires_voir`` partout ailleurs
(``rh.RemunerationViewSet``, ``rh.GrilleSalarialeViewSet``), et jusque dans la
MÊME classe : l'action ``synchroniser_salaire_action`` exige explicitement
``salaires_voir`` « au-delà de paie_gerer… donnée sensible ». Contradiction
interne, exploitable en configuration par défaut — le rôle Responsable livré
porte ``paie_voir``/``paie_gerer`` mais PAS ``salaires_voir``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import ProfilPaie
from apps.rh.models import DossierEmploye
from apps.roles.models import Role

User = get_user_model()

BASE = '/api/django/paie/profils/'


class SalaireBasePermissionTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud716', nom='AUD716')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='SB1', nom='Salaire', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12345.00'))

    def _client(self, permissions, username):
        role = Role.objects.create(
            company=self.co, nom=f'Role {username}', permissions=permissions)
        user = User.objects.create_user(
            username=username, password='x', company=self.co, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _ligne(self, resp):
        donnees = resp.data
        if isinstance(donnees, dict) and 'results' in donnees:
            donnees = donnees['results']
        return donnees[0] if isinstance(donnees, list) else donnees

    # ── Le constat : le rôle Responsable livré par défaut ──────────────────

    def test_paie_voir_sans_salaires_voir_ne_voit_plus_le_salaire(self):
        """Configuration par DÉFAUT du rôle Responsable livré."""
        api = self._client(['paie_voir', 'paie_gerer'], 'resp716')
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = self._ligne(resp)
        # La clé reste présente (forme de réponse stable) mais MASQUÉE.
        self.assertIn('salaire_base', ligne)
        self.assertIsNone(ligne['salaire_base'])
        # Le reste du profil demeure accessible au gestionnaire de paie.
        self.assertIn('affilie_cnss', ligne)
        self.assertEqual(ligne['id'], self.profil.id)

    def test_salaires_voir_voit_le_salaire(self):
        api = self._client(
            ['paie_voir', 'paie_gerer', 'salaires_voir'], 'dir716')
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ligne(resp)['salaire_base'], '12345.00')

    def test_detail_aussi_masque(self):
        api = self._client(['paie_voir', 'paie_gerer'], 'resp716b')
        resp = api.get(f'{BASE}{self.profil.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['salaire_base'])

    # ── Dans les DEUX sens : l'écriture aussi ──────────────────────────────

    def test_ecriture_du_salaire_refusee_sans_salaires_voir(self):
        api = self._client(['paie_voir', 'paie_gerer'], 'resp716c')
        resp = api.patch(f'{BASE}{self.profil.id}/',
                         {'salaire_base': '99999.00'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.profil.refresh_from_db()
        self.assertEqual(self.profil.salaire_base, Decimal('12345.00'))

    def test_ecriture_du_salaire_autorisee_avec_salaires_voir(self):
        api = self._client(
            ['paie_voir', 'paie_gerer', 'salaires_voir'], 'dir716b')
        resp = api.patch(f'{BASE}{self.profil.id}/',
                         {'salaire_base': '13000.00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profil.refresh_from_db()
        self.assertEqual(self.profil.salaire_base, Decimal('13000.00'))

    def test_autres_champs_restent_modifiables_sans_salaires_voir(self):
        """Non-régression : seul le SALAIRE est gaté, pas tout le profil."""
        api = self._client(['paie_voir', 'paie_gerer'], 'resp716d')
        resp = api.patch(f'{BASE}{self.profil.id}/',
                         {'affilie_cimr': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profil.refresh_from_db()
        self.assertTrue(self.profil.affilie_cimr)

    def test_compte_legate_sans_role_fin_inchange(self):
        """Repli assumé : un compte hérité garde son comportement historique."""
        user = User.objects.create_user(
            username='legacy716', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._ligne(resp)['salaire_base'], '12345.00')
