"""NTRET31 — Écran client (customer-facing display) : snapshot best-effort
du panier en cours de la session, PATCH par le poste caisse, GET en polling
léger par l'écran client. Lecture seule côté écran client — aucune action.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.pos import services

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_session_caisse(company, user):
    compta_services.seed_plan_comptable(company)
    compta_services.seed_journaux(company)
    compte_caisse = CompteTresorerie.objects.create(
        company=company, type_compte=CompteTresorerie.Type.CAISSE,
        libelle='Caisse comptoir',
        compte_comptable=compta_services.get_compte(company, '5161'))
    caisse_comptable = compta_services.creer_caisse(
        company, compte_caisse, libelle='Caisse POS', solde_initial=Decimal('0'))
    return services.ouvrir_session(
        company=company, caisse_comptable=caisse_comptable,
        caissier=user, fond_ouverture=Decimal('0'), user=user)


class PanierCourantTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret31', 'NTRET31 Co')
        self.caissier = make_user(self.co, 'caissier-ntret31', role='normal')
        self.session = make_session_caisse(self.co, self.caissier)

    def test_get_sans_panier_pousse_renvoie_none(self):
        api = auth(self.caissier)
        res = api.get(f'/api/django/pos/sessions/{self.session.id}/panier-courant/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['panier'])

    def test_patch_par_un_caissier_normal_puis_get_reflete_le_panier(self):
        """Un caissier de rôle 'normal' (pas responsable/admin) peut pousser
        le panier — même palier que la vente elle-même, contrairement au
        reste du ViewSet (IsResponsableOrAdmin)."""
        api = auth(self.caissier)
        panier = {'lignes': [{'nom': 'Câble', 'quantite': 2, 'prix_ttc': 50}], 'total': 100}
        res_patch = api.patch(
            f'/api/django/pos/sessions/{self.session.id}/panier-courant/',
            {'panier': panier}, format='json')
        self.assertEqual(res_patch.status_code, 200, res_patch.data)
        self.assertEqual(res_patch.data['panier'], panier)

        res_get = api.get(f'/api/django/pos/sessions/{self.session.id}/panier-courant/')
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data['panier'], panier)
        self.assertIsNotNone(res_get.data['updated_at'])

    def test_isolation_multi_tenant(self):
        co_b = make_company('ntret31-b', 'NTRET31 B')
        caissier_b = make_user(co_b, 'caissier-ntret31-b', role='normal')
        api_b = auth(caissier_b)
        res = api_b.get(f'/api/django/pos/sessions/{self.session.id}/panier-courant/')
        self.assertEqual(res.status_code, 404)

    def test_requiert_authentification(self):
        api = APIClient()
        res = api.get(f'/api/django/pos/sessions/{self.session.id}/panier-courant/')
        self.assertEqual(res.status_code, 401)
