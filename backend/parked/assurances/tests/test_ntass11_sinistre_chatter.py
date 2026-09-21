"""NTASS11 — chatter sinistre (adossé à ``records.Activity``, ARC8).

Critère d'acceptation : passer un sinistre de ``declare`` à ``en_expertise``
logge automatiquement l'entrée avec date et auteur."""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    Assureur, DeclarationSinistre, PoliceAssurance,
)
from apps.records.models import Activity

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


def activites(obj):
    """Entrées de chatter records.Activity ciblant ``obj``."""
    ct = ContentType.objects.get_for_model(obj.__class__)
    return Activity.objects.filter(content_type=ct, object_id=obj.pk)


class SinistreChatterTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p11', 'P11')
        self.user = make_user(self.company, 'assur-p11')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-011',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-100',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE,
            statut=DeclarationSinistre.Statut.DECLARE)

    def test_passage_en_expertise_loggue_auteur_et_date(self):
        api = auth(self.user)
        resp = api.patch(
            f'/api/django/assurances/declarations-sinistre/{self.declaration.id}/',
            {'statut': DeclarationSinistre.Statut.EN_EXPERTISE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        entree = activites(self.declaration).get(field='statut')
        self.assertEqual(entree.old_value, DeclarationSinistre.Statut.DECLARE)
        self.assertEqual(
            entree.new_value, DeclarationSinistre.Statut.EN_EXPERTISE)
        self.assertEqual(entree.created_by, self.user)
        self.assertIsNotNone(entree.created_at)

    def test_noter_et_historique(self):
        api = auth(self.user)
        # Créée via l'API pour déclencher perform_create → entrée « creation ».
        resp = api.post(
            '/api/django/assurances/declarations-sinistre/',
            {
                'police': self.police.id,
                'date_survenance': datetime.date.today().isoformat(),
                'type_sinistre': DeclarationSinistre.TypeSinistre.VOL,
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        declaration_id = resp.data['id']

        resp = api.post(
            '/api/django/assurances/declarations-sinistre/'
            f'{declaration_id}/noter/',
            {'body': 'Expert mandaté, RDV la semaine prochaine.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = api.get(
            '/api/django/assurances/declarations-sinistre/'
            f'{declaration_id}/historique/')
        self.assertEqual(resp.status_code, 200)
        kinds = [e['kind'] for e in resp.data]
        self.assertIn(Activity.Kind.CREATION, kinds)
        self.assertIn(Activity.Kind.NOTE, kinds)
