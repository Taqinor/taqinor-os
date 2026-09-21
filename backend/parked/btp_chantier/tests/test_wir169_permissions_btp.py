"""WIR169 — le module BTP est enfin atteignable par un rôle FIN (Directeur inclus).

Les 7 viewsets BTP déclarent depuis toujours ``read_permission = 'btp_voir'``
et ``write_permission = 'btp_gerer'``, mais ces deux codes n'étaient inscrits
NULLE PART dans ``roles.ALL_PERMISSIONS``. Comme ``DIRECTEUR_PERMISSIONS`` en
dérive, même un Directeur ne les portait pas : ``has_erp_permission`` renvoyait
False et TOUTE la surface BTP répondait 403. Seuls les comptes HÉRITÉS sans
rôle fin passaient (repli ``core.permissions._user_has_or_legacy``) — c'est
pourquoi les tests NTCON existants, qui utilisent ``make_user`` (``role_legacy``
sans Role FK), ne voyaient rien.

Ce module teste donc avec de VRAIS ``Role`` FK :
  * un Directeur lit (200) et écrit les 7 routes du routeur BTP ;
  * un rôle fin SANS les codes BTP reçoit 403 en lecture comme en écriture ;
  * le repli légacy (compte sans Role fin) reste inchangé — aucune régression.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import DIRECTEUR_PERMISSIONS, Role

from .helpers import auth, make_chantier, make_company, make_user

User = get_user_model()

RACINE = '/api/django/btp-chantier/'

#: Les 7 routes enregistrées par ``apps/btp_chantier/urls.py`` (routeur DRF).
ROUTES_BTP = (
    'reserves-chantier/',
    'rfi/',
    'visas/',
    'journal-chantier/',
    'avenants-chantier/',
    'decomptes-generaux/',
    'diffusions-plan/',
)


def _client_pour(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PermissionsBtpRoleFinTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.role_directeur = Role.objects.create(
            company=self.co, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.directeur = User.objects.create_user(
            username='wir169-directeur', password='x',
            company=self.co, role=self.role_directeur)
        # Rôle fin porteur d'écritures AILLEURS (CRM) mais d'aucun code BTP :
        # il ne doit franchir ni la lecture ni l'écriture du module.
        self.role_sans_btp = Role.objects.create(
            company=self.co, nom='Commercial sans BTP',
            permissions=['crm_voir', 'crm_creer', 'ventes_voir'])
        self.sans_btp = User.objects.create_user(
            username='wir169-sans-btp', password='x',
            company=self.co, role=self.role_sans_btp)

    # ── Lecture ────────────────────────────────────────────────────────────
    def test_directeur_lit_les_7_routes(self):
        api = _client_pour(self.directeur)
        for route in ROUTES_BTP:
            with self.subTest(route=route):
                resp = api.get(RACINE + route)
                self.assertEqual(
                    resp.status_code, status.HTTP_200_OK, resp.content)

    def test_role_sans_code_refuse_en_lecture(self):
        api = _client_pour(self.sans_btp)
        for route in ROUTES_BTP:
            with self.subTest(route=route):
                resp = api.get(RACINE + route)
                self.assertEqual(
                    resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)

    # ── Écriture ───────────────────────────────────────────────────────────
    def test_directeur_franchit_la_garde_en_ecriture(self):
        """POST corps vide : 400 (validation), JAMAIS 403 (garde franchie)."""
        api = _client_pour(self.directeur)
        for route in ROUTES_BTP:
            with self.subTest(route=route):
                resp = api.post(RACINE + route, {}, format='json')
                self.assertNotEqual(
                    resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)
                self.assertIn(
                    resp.status_code,
                    (status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED),
                    resp.content)

    def test_directeur_cree_reellement_une_reserve(self):
        """Une écriture COMPLÈTE aboutit (201) — pas seulement la garde."""
        resp = _client_pour(self.directeur).post(
            RACINE + 'reserves-chantier/',
            {
                'chantier': self.chantier.id,
                'lot': 'électricité',
                'localisation_plan': {
                    'document_ged_id': 7, 'x': 0.5, 'y': 0.5,
                },
                'description': 'Prise à reprendre',
                'gravite': 'majeure',
            },
            format='json')
        self.assertEqual(
            resp.status_code, status.HTTP_201_CREATED, resp.content)

        from apps.btp_chantier.models import ReserveChantier
        reserve = ReserveChantier.objects.get(pk=resp.data['id'])
        # Société et créateur posés côté SERVEUR (jamais lus du corps).
        self.assertEqual(reserve.company_id, self.co.id)
        self.assertEqual(reserve.created_by_id, self.directeur.id)

    def test_role_sans_code_refuse_en_ecriture(self):
        api = _client_pour(self.sans_btp)
        for route in ROUTES_BTP:
            with self.subTest(route=route):
                resp = api.post(RACINE + route, {}, format='json')
                self.assertEqual(
                    resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)

    # ── Non-régression du repli légacy ─────────────────────────────────────
    def test_compte_legacy_sans_role_fin_inchange(self):
        """Un compte hérité (``role_legacy``, aucun Role FK) garde son accès."""
        legacy = make_user(self.co, role='responsable')
        self.assertIsNone(legacy.role)
        api = auth(legacy)
        for route in ROUTES_BTP:
            with self.subTest(route=route):
                self.assertEqual(
                    api.get(RACINE + route).status_code, status.HTTP_200_OK)
