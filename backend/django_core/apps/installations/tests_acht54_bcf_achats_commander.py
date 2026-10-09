"""ACHT54 (C-ACHT-053) — créer un BCF depuis installations exige
`achats_commander` (`generer-bcf`, `commander-besoin`, `commander-manques`)
et `demandes-achat/<id>/approuver/` exige `approuver_demande_achat`.

Rejoue CTEN-5 : le Technicien approuvait (200) et générait un BCF (200).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht54_bcf_achats_commander"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, Installation, Intervention,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS,
)
from apps.stock.models import BonCommandeFournisseur, Fournisseur

User = get_user_model()
BASE = '/api/django/installations'


class BcfAchatsCommanderTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT54', slug='acht54-co')
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.tech = User.objects.create_user(
            username='tech-acht54', password='x', company=self.company,
            role=role_tech)
        self.admin = User.objects.create_user(
            username='admin-acht54', password='x', company=self.company,
            role=role_admin)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ACHT54')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT54')
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.tech)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-ACHT54', objet='Test',
            created_by=self.tech, statut=DemandeAchat.Statut.SOUMISE,
            fournisseur_suggere=self.fournisseur)
        DemandeAchatLigne.objects.create(
            demande=self.da, designation='Câble', quantite=Decimal('2'),
            prix_estime=Decimal('10'))

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _nb_bcf(self):
        return BonCommandeFournisseur.objects.filter(
            company=self.company).count()

    def test_technicien_refuse_partout(self):
        api = self._api(self.tech)
        avant = self._nb_bcf()
        for url, corps in (
                (f'{BASE}/demandes-achat/{self.da.id}/approuver/', {}),
                (f'{BASE}/demandes-achat/{self.da.id}/generer-bcf/',
                 {'fournisseur': self.fournisseur.id}),
                (f'{BASE}/chantiers/{self.chantier.id}/commander-besoin/',
                 {'fournisseur': self.fournisseur.id}),
                (f'{BASE}/interventions/{self.interv.id}/commander-manques/',
                 {'fournisseur': self.fournisseur.id})):
            r = api.post(url, corps, format='json')
            self.assertEqual(r.status_code, 403, (url, r.data))
        self.assertEqual(self._nb_bcf(), avant)
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.SOUMISE)
        self.assertIsNone(self.da.approuvee_par_id)

    def test_admin_approuve_et_genere(self):
        api = self._api(self.admin)
        r = api.post(f'{BASE}/demandes-achat/{self.da.id}/approuver/', {},
                     format='json')
        self.assertEqual(r.status_code, 200, r.data)
        avant = self._nb_bcf()
        r = api.post(f'{BASE}/demandes-achat/{self.da.id}/generer-bcf/',
                     {'fournisseur': self.fournisseur.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._nb_bcf(), avant + 1)
        for url in (
                f'{BASE}/chantiers/{self.chantier.id}/commander-besoin/',
                f'{BASE}/interventions/{self.interv.id}/commander-manques/'):
            r = api.post(url, {'fournisseur': self.fournisseur.id},
                         format='json')
            self.assertNotEqual(r.status_code, 403, (url, r.data))
