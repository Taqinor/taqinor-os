"""ALEA31 — le serveur est la SEULE table de l'accueil mobile.

``/auth/me/`` rend ``mobile_home_route_suggeree`` = ``default_mobile_home_route``
(fonction pure) ; le frontend la suit au premier atterrissage mobile puis la
persiste via ``POST /auth/mobile-home-route/`` — dont la liste blanche accepte
désormais les accueils d'équipe (NTMOB25/26). Se reconnecter relit la même
route dans ``mobile_home_route``.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import Role
from authentication.models import Company, CustomUser


def _utilisateur(company, username, role_nom):
    role = Role.objects.create(company=company, nom=role_nom, permissions=[])
    return CustomUser.objects.create_user(
        username=username, password='pw', company=company,
        role=role, role_legacy=CustomUser.ROLE_NORMAL)


ATTENDU = {
    'Commercial terrain': '/visites',
    'Commercial responsable': '/mobile/equipe-commerciale',
    'Technicien responsable': '/mobile/equipe-terrain',
}


class MobileHomeServeurTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEA31 Co', slug='alea31-co')

    def test_me_rend_route_suggeree_par_role(self):
        for i, (role_nom, route) in enumerate(ATTENDU.items()):
            with self.subTest(role=role_nom):
                user = _utilisateur(self.company, f'alea31-{i}', role_nom)
                self.assertIsNone(user.mobile_home_route)
                client = APIClient()
                client.force_authenticate(user)
                res = client.get('/api/django/auth/me/')
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.data['mobile_home_route_suggeree'], route)
                # Rien n'est décidé tant que le frontend ne l'a pas persistée.
                self.assertIsNone(res.data['mobile_home_route'])

    def test_routes_equipe_acceptees(self):
        for i, (role_nom, route) in enumerate(ATTENDU.items()):
            with self.subTest(role=role_nom):
                user = _utilisateur(self.company, f'alea31-p{i}', role_nom)
                client = APIClient()
                client.force_authenticate(user)
                suggeree = client.get('/api/django/auth/me/').data[
                    'mobile_home_route_suggeree']
                res = client.post(
                    '/api/django/auth/mobile-home-route/',
                    {'route': suggeree}, format='json')
                self.assertEqual(res.status_code, 200, res.data)
                # Persistance : la reconnexion relit la MÊME route.
                relu = APIClient()
                relu.force_authenticate(CustomUser.objects.get(pk=user.pk))
                self.assertEqual(
                    relu.get('/api/django/auth/me/').data['mobile_home_route'],
                    route)

    def test_cle_absente_de_la_liste_equipe(self):
        """La clé ne s'ajoute QU'À ``/auth/me/`` : la liste d'équipe n'expose
        rien de plus qu'avant."""
        from authentication.serializers import UserSerializer
        self.assertNotIn('mobile_home_route_suggeree', UserSerializer.Meta.fields)
