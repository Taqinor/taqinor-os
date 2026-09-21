"""NTASS22 — Assurance homme-clé liée au dossier employé.

Critère d'acceptation : une police homme-clé affiche le nom du dirigeant/
employé couvert résolu à la volée, sans FK réelle vers rh."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, PoliceAssurance
from apps.assurances.selectors import libelle_employe_couvert

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class HommeCleTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p22', 'P22')
        self.user = make_user(self.company, 'assur-p22')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='HK-2026-001',
            type_police=PoliceAssurance.TypePolice.HOMME_CLE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))

    def test_libelle_employe_none_sans_dossier(self):
        # Aucun DossierEmploye rh ne correspond → résolution None (défensif).
        self.assertIsNone(libelle_employe_couvert(self.company, 999999))
        self.assertIsNone(libelle_employe_couvert(self.company, None))

    def test_resolution_via_rh_selectors_quand_dossier_existe(self):
        # Crée un vrai DossierEmploye rh et vérifie la résolution à la volée.
        from apps.rh.models import DossierEmploye
        dossier = DossierEmploye.objects.create(
            company=self.company, nom='Kasri', prenom='Reda', matricule='D001')
        self.police.employe_ref = dossier.id
        self.police.save(update_fields=['employe_ref'])

        libelle = libelle_employe_couvert(self.company, dossier.id)
        self.assertEqual(libelle, 'Reda Kasri')

        api = auth(self.user)
        resp = api.get(
            f'/api/django/assurances/polices/{self.police.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['employe_couvert_libelle'], 'Reda Kasri')
