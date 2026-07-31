"""WIR92 — string-FK optionnel `Praticien.employe_id` vers `rh.DossierEmploye`.

Suit le pattern `agriculture.PointageAgricole.employe_id` /
`flotte.Conducteur.employe_id` : `IntegerField(null=True)`, résolu
paresseusement via `apps.rh.selectors` (jamais un import du modèle rh dans
`apps.sante`). Couvre : praticien lié affiche son libellé RH résolu, praticien
non lié garde un comportement inchangé, migration additive (le modèle se crée
et se récupère sans erreur), isolation tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.sante.models import Praticien
from apps.sante.selectors import libelle_rh_praticien

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_dossier_employe(company, matricule='EMP1', poste=''):
    """Créé via `apps.rh.models` (dépendance de test uniquement — l'app
    `sante`, elle, ne l'importe JAMAIS — voir `selectors.libelle_rh_praticien`
    qui passe TOUJOURS par `apps.rh.selectors`)."""
    from apps.rh.models import DossierEmploye
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Bennani', prenom='Yassine',
        poste=poste)


class PraticienEmployeIdSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('sante-emp-1', 'Clinique EMP1')

    def test_praticien_sans_lien_renvoie_none(self):
        """Un praticien SANS `employe_id` garde un comportement inchangé :
        aucune tentative de résolution RH, pas d'erreur."""
        praticien = Praticien.objects.create(company=self.co, nom='Dr. Alami')
        self.assertIsNone(praticien.employe_id)
        self.assertIsNone(libelle_rh_praticien(self.co, praticien.employe_id))

    def test_praticien_lie_affiche_libelle_rh_resolu(self):
        dossier = make_dossier_employe(self.co, matricule='EMP42', poste='Infirmier')
        praticien = Praticien.objects.create(
            company=self.co, nom='Dr. Bennani', employe_id=dossier.id)

        libelle = libelle_rh_praticien(self.co, praticien.employe_id)
        self.assertIsNotNone(libelle)
        self.assertIn('Bennani', libelle)
        self.assertIn('Yassine', libelle)
        self.assertIn('Infirmier', libelle)

    def test_employe_id_dossier_introuvable_renvoie_none(self):
        """Un `employe_id` pointant vers un dossier inexistant ne lève
        jamais — dégrade proprement vers `None`."""
        praticien = Praticien.objects.create(
            company=self.co, nom='Dr. Cherkaoui', employe_id=999999)
        self.assertIsNone(libelle_rh_praticien(self.co, praticien.employe_id))

    def test_migration_additive_praticien_sans_employe_id(self):
        """Critère d'acceptation : migration additive — un praticien créé
        sans `employe_id` se crée et se récupère toujours sans erreur."""
        obj = Praticien.objects.create(company=self.co, nom='Dr. Idrissi')
        self.assertTrue(Praticien.objects.filter(pk=obj.pk).exists())
        self.assertIsNone(obj.employe_id)


class PraticienEmployeIdApiTests(TestCase):
    BASE = '/api/django/sante/praticiens/'

    def setUp(self):
        self.co = make_company('sante-emp-2', 'Clinique EMP2')
        self.user = make_user(self.co, 'sante-emp-2-user')

    def test_serializer_expose_libelle_rh_pour_praticien_lie(self):
        dossier = make_dossier_employe(self.co, matricule='EMP7', poste='Kiné')
        praticien = Praticien.objects.create(
            company=self.co, nom='Dr. Fassi', employe_id=dossier.id)

        api = auth(self.user)
        resp = api.get(f'{self.BASE}{praticien.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['employe_id'], dossier.id)
        self.assertIsNotNone(resp.data['libelle_rh'])
        self.assertIn('Bennani', resp.data['libelle_rh'])

    def test_serializer_libelle_rh_none_sans_lien(self):
        praticien = Praticien.objects.create(company=self.co, nom='Dr. Saidi')

        api = auth(self.user)
        resp = api.get(f'{self.BASE}{praticien.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['employe_id'])
        self.assertIsNone(resp.data['libelle_rh'])
