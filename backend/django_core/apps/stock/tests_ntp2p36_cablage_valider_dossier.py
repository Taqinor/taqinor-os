"""NTP2P36 — câblage du code fin ``valider_dossier_fournisseur`` sur
``valider-dossier`` (NTP2P7).

Avant ce module, l'action était gardée UNIQUEMENT par le palier grossier
hérité (``IsResponsableOrAdmin``) : tout compte Responsable/Admin décidait un
dossier d'onboarding fournisseur, même sans porter le geste fin catalogué par
NTP2P36. Ce test prouve, comme NTCON26/NTUX31/NTP2P36(installations) : un
rôle FIN sans le code reçoit 403 sur ``valider-dossier`` (403 explicite,
message FR) ; le même rôle une fois le code ajouté franchit la garde ; un
compte HÉRITÉ (``role_legacy``, palier admin) garde son accès via le repli
légacy de ``core.permissions._user_has_or_legacy`` — aucune régression sur les
tests NTP2P7 existants.

Run :
    python manage.py test apps.stock.tests_ntp2p36_cablage_valider_dossier -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import DossierOnboardingFournisseur, Fournisseur
from apps.stock.permissions import PERM_VALIDER_DOSSIER_FOURNISSEUR

User = get_user_model()
_seq = itertools.count(1)
STOCK = '/api/django/stock'


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntp2p36-stk-co-{n}', defaults={'nom': f'NTP2P36 Co {n}'})
    return company


def make_user(company, role='admin'):
    return User.objects.create_user(
        username=f'ntp2p36-stk-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_role_user(company, codes, username=None):
    role = Role.objects.create(
        company=company, nom=f'Rôle {username or next(_seq)}',
        permissions=list(codes))
    return User.objects.create_user(
        username=username or f'ntp2p36-stk-role-{next(_seq)}', password='x',
        company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ValiderDossierCodeFinTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport NTP2P36')
        self.dossier = DossierOnboardingFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur)

    def test_refuse_sans_le_code_fin(self):
        """Rôle FIN portant SEULEMENT le palier module (pas le geste)."""
        appro = make_role_user(
            self.company, ['stock_voir', 'stock_gerer'],
            'ntp2p36-stk-sans-code')
        # Rejet (`valider: False`) : n'exige pas un dossier complet, isole la
        # garde de permission testée ici de la garde de complétude (NTP2P7).
        resp = auth(appro).post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/', {'valider': False, 'motif_rejet': 'incomplet'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        self.dossier.refresh_from_db()
        self.assertEqual(
            self.dossier.statut, DossierOnboardingFournisseur.Statut.EN_ATTENTE)

    def test_franchit_la_garde_avec_le_code_fin(self):
        appro = make_role_user(
            self.company,
            ['stock_voir', 'stock_gerer', PERM_VALIDER_DOSSIER_FOURNISSEUR],
            'ntp2p36-stk-avec-code')
        resp = auth(appro).post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/', {'valider': False, 'motif_rejet': 'incomplet'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.dossier.refresh_from_db()
        self.assertEqual(
            self.dossier.statut, DossierOnboardingFournisseur.Statut.REJETE)

    def test_compte_legacy_admin_garde_son_acces(self):
        """Non-régression : un compte hérité (palier admin) n'a rien perdu."""
        appro = make_user(self.company, role='admin')
        resp = auth(appro).post(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/'
            'valider-dossier/', {'valider': False, 'motif_rejet': 'incomplet'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

    def test_lecture_reste_ouverte_sans_code_fin(self):
        """``retrieve`` n'est PAS concernée — reste IsAnyRole."""
        appro = make_role_user(
            self.company, ['stock_voir'], 'ntp2p36-stk-lecture')
        resp = auth(appro).get(
            f'{STOCK}/dossiers-onboarding-fournisseur/{self.dossier.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
