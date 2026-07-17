"""NTASS14 — Pièces jointes sinistre (constat, expertise, photos).

Réutilise ``records.Attachment`` (generic FK) : la cible
``assurances.declarationsinistre`` est déclarée dans le manifeste
``apps/assurances/platform.py`` (``record_targets``) — l'union paresseuse
``records.ALLOWED_TARGETS`` la lit sans éditer ``apps/records/models.py``.

Critère d'acceptation : un rapport d'expertise est rattaché à un sinistre et
apparaît dans sa galerie de pièces jointes, téléchargeable."""
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
from apps.records.models import ALLOWED_TARGETS, Attachment
from apps.records.serializers import resolve_target

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class SinistreAttachmentTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p14', 'P14')
        self.user = make_user(self.company, 'assur-p14')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        today = datetime.date.today()
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='MR-2026-014',
            type_police=PoliceAssurance.TypePolice.MULTIRISQUE,
            date_effet=today, date_echeance=today + datetime.timedelta(days=365))
        self.declaration = DeclarationSinistre.objects.create(
            company=self.company, police=self.police, reference='SIN-2026-400',
            date_survenance=today,
            type_sinistre=DeclarationSinistre.TypeSinistre.INCENDIE)

    def test_declarationsinistre_dans_allowed_targets(self):
        self.assertIn(
            ('assurances', 'declarationsinistre'), ALLOWED_TARGETS)

    def test_resolve_target_accepte_le_sinistre(self):
        ct, obj = resolve_target(
            'assurances.declarationsinistre', self.declaration.id, self.company)
        self.assertEqual(obj, self.declaration)

    def test_galerie_pieces_jointes_du_sinistre(self):
        ct = ContentType.objects.get_for_model(DeclarationSinistre)
        Attachment.objects.create(
            company=self.company, content_type=ct,
            object_id=self.declaration.id, uploaded_by=self.user,
            file_key='attachments/expertise.pdf',
            filename='rapport_expertise.pdf', size=1234, mime='application/pdf')

        api = auth(self.user)
        resp = api.get('/api/django/records/attachments/', {
            'model': 'assurances.declarationsinistre',
            'id': self.declaration.id,
        })
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'rapport_expertise.pdf')
