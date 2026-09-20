"""NTP2P36 — câblage du code fin ``approuver_demande_achat`` sur
``approuver-etape`` (NTP2P2).

Avant ce module, l'action était gardée UNIQUEMENT par le palier grossier
hérité (``IsResponsableOrAdmin``) : tout compte Responsable/Admin décidait une
étape du plan d'approbation d'achat, même sans porter le geste fin catalogué
par NTP2P36. Ce test prouve, comme NTCON26/NTUX31 : un rôle FIN sans le code
reçoit 403 sur ``approuver-etape`` (403 explicite, message FR) ; le même rôle
une fois le code ajouté franchit la garde ; un compte HÉRITÉ (``role_legacy``,
palier Directeur/Responsable/Admin) garde son accès via le repli légacy de
``core.permissions._user_has_or_legacy`` — aucune régression sur les tests
NTP2P2 existants.

Run :
    python manage.py test apps.installations.tests_ntp2p36_cablage_approuver_etape -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, RegleApprobationAchat,
)
from apps.installations.permissions import PERM_APPROUVER_DEMANDE_ACHAT
from apps.roles.models import Role

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntp2p36-co-{n}', defaults={'nom': f'NTP2P36 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p36-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_role_user(company, codes, username=None):
    role = Role.objects.create(
        company=company, nom=f'Rôle {username or next(_seq)}',
        permissions=list(codes))
    return User.objects.create_user(
        username=username or f'ntp2p36-role-{next(_seq)}', password='x',
        company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ApprouverEtapeCodeFinTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Au-delà de 20 000 MAD',
            montant_min=20000, nombre_approbateurs=1,
            niveau_approbation=(
                RegleApprobationAchat.NiveauApprobation.DIRECTION))

    def _soumettre(self, montant=50000):
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-NTP2P36-{next(_seq):04d}',
            objet='Réquisition de test', created_by=self.demandeur)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=1,
            prix_estime=montant)
        resp = auth(self.demandeur).post(
            f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        return da

    def test_refuse_sans_le_code_fin(self):
        """Rôle FIN portant SEULEMENT le palier module (pas le geste)."""
        da = self._soumettre()
        appro = make_role_user(
            self.company, ['installation_voir', 'installation_gerer'],
            'ntp2p36-sans-code')
        resp = auth(appro).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)

    def test_franchit_la_garde_avec_le_code_fin(self):
        da = self._soumettre()
        appro = make_role_user(
            self.company,
            ['installation_voir', 'installation_gerer',
             PERM_APPROUVER_DEMANDE_ACHAT],
            'ntp2p36-avec-code')
        resp = auth(appro).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_compte_legacy_directeur_garde_son_acces(self):
        """Non-régression : un compte hérité (palier admin) n'a rien perdu."""
        da = self._soumettre()
        appro = make_user(self.company, role='admin')
        resp = auth(appro).post(
            f'{BASE}/demandes-achat/{da.pk}/approuver-etape/', {},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

    def test_lecture_des_etapes_reste_ouverte_sans_code_fin(self):
        """`etapes-approbation` (GET) n'est PAS concernée — reste IsAnyRole."""
        da = self._soumettre()
        appro = make_role_user(
            self.company, ['installation_voir'], 'ntp2p36-lecture')
        resp = auth(appro).get(
            f'{BASE}/demandes-achat/{da.pk}/etapes-approbation/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
