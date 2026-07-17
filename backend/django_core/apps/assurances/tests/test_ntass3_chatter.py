"""NTASS3 — chatter police (adossé à ``records.Activity``, ARC8).

Critère d'acceptation : renouveler une police change ``date_echeance`` et une
entrée chatter auto apparaît avec l'ancienne et la nouvelle date."""
import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import Assureur, PoliceAssurance
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


class PoliceChatterTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p3', 'P3')
        self.user = make_user(self.company, 'assur-p3')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        self.today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-010',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=self.today,
            date_echeance=self.today + datetime.timedelta(days=365))

    def test_creation_loggee(self):
        # Créée via l'API pour déclencher perform_create.
        api = auth(self.user)
        payload = {
            'assureur': self.assureur.id,
            'numero_police': 'DEC-2026-011',
            'type_police': PoliceAssurance.TypePolice.DECENNALE,
            'date_effet': self.today.isoformat(),
            'date_echeance': (
                self.today + datetime.timedelta(days=365)).isoformat(),
        }
        resp = api.post(
            '/api/django/assurances/polices/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        police = PoliceAssurance.objects.get(id=resp.data['id'])
        self.assertEqual(
            activites(police).filter(kind=Activity.Kind.CREATION).count(), 1)

    def test_renouvellement_change_date_echeance_loggue_le_chatter(self):
        api = auth(self.user)
        ancienne_echeance = self.police.date_echeance
        nouvelle_echeance = ancienne_echeance + datetime.timedelta(days=365)
        resp = api.patch(
            f'/api/django/assurances/polices/{self.police.id}/',
            {'date_echeance': nouvelle_echeance.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        entree = activites(self.police).get(field='date_echeance')
        self.assertEqual(entree.old_value, str(ancienne_echeance))
        self.assertEqual(entree.new_value, str(nouvelle_echeance))

        resp = api.get(
            f'/api/django/assurances/polices/{self.police.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(
            e['field'] == 'date_echeance' for e in resp.data))

    def test_noter_ajoute_une_note_manuelle(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/assurances/polices/{self.police.id}/noter/',
            {'body': 'Appel assureur pour confirmation renouvellement.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            activites(self.police).filter(kind=Activity.Kind.NOTE).count(), 1)
