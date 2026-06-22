"""Tests QHSE8 — Photos de contrôle (avant/pendant/après) via ``records.Attachment``.

Couvre :

* le selecteur ``photos_controle_par_phase`` regroupe les pièces jointes d'un
  relevé par phase (avant/pendant/après + autres) et reste scopé société ;
* la cible ``qhse.relevecontrole`` (et ``qhse.nonconformite``) est autorisée
  dans le système générique de pièces jointes (``records.ALLOWED_TARGETS``) ;
* l'endpoint ``GET …/releves/<id>/photos/`` renvoie le regroupement par phase,
  scopé société (404 pour un relevé d'une autre société) et palier
  Administrateur/Responsable (rôle « normal » refusé).
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    PlanInspectionChantier, PlanInspectionModele, PointControleModele,
    ReleveControle,
)
from apps.qhse.selectors import photos_controle_par_phase
from apps.records.models import ALLOWED_TARGETS, Attachment

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


def make_releve(company, **kwargs):
    modele = PlanInspectionModele.objects.create(company=company, nom='ITP')
    point = PointControleModele.objects.create(
        company=company, plan=modele, intitule='P')
    plan = PlanInspectionChantier.objects.create(
        company=company, modele=modele, chantier_id=1)
    return ReleveControle.objects.create(
        company=company, plan_chantier=plan, point=point, **kwargs)


def attach(company, user, releve, phase, name):
    ct = ContentType.objects.get_for_model(ReleveControle)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=releve.id,
        uploaded_by=user, phase=phase,
        file_key=f'attachments/{name}', filename=name,
        size=1, mime='image/png')


class PhotosTargetTests(TestCase):
    def test_qhse_targets_are_allowed(self):
        self.assertIn(('qhse', 'relevecontrole'), ALLOWED_TARGETS)
        self.assertIn(('qhse', 'nonconformite'), ALLOWED_TARGETS)


class PhotosSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse8-sel', 'Sel')
        self.user = make_user(self.co, 'qhse8-sel')
        self.releve = make_releve(self.co)

    def test_groups_by_phase(self):
        attach(self.co, self.user, self.releve, 'avant', 'a.png')
        attach(self.co, self.user, self.releve, 'avant', 'a2.png')
        attach(self.co, self.user, self.releve, 'pendant', 'p.png')
        attach(self.co, self.user, self.releve, 'apres', 'z.png')
        attach(self.co, self.user, self.releve, '', 'autre.png')
        groupes = photos_controle_par_phase(self.releve)
        self.assertEqual(len(groupes['avant']), 2)
        self.assertEqual(len(groupes['pendant']), 1)
        self.assertEqual(len(groupes['apres']), 1)
        self.assertEqual(len(groupes['autres']), 1)

    def test_isolation_between_companies(self):
        other = make_company('qhse8-sel-b', 'B')
        other_user = make_user(other, 'qhse8-sel-b')
        other_releve = make_releve(other)
        attach(other, other_user, other_releve, 'avant', 'b.png')
        # Le relevé de la société courante n'a aucune photo.
        groupes = photos_controle_par_phase(self.releve)
        self.assertEqual(
            sum(len(v) for v in groupes.values()), 0)


class PhotosApiTests(TestCase):
    def setUp(self):
        self.co = make_company('qhse8-api', 'Api')
        self.user = make_user(self.co, 'qhse8-api')
        self.releve = make_releve(self.co)

    def url(self, releve):
        return f'/api/django/qhse/releves/{releve.id}/photos/'

    def test_endpoint_returns_phase_groups(self):
        attach(self.co, self.user, self.releve, 'avant', 'a.png')
        attach(self.co, self.user, self.releve, 'apres', 'z.png')
        resp = auth(self.user).get(self.url(self.releve))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['avant']), 1)
        self.assertEqual(len(resp.data['apres']), 1)
        self.assertEqual(resp.data['avant'][0]['filename'], 'a.png')

    def test_endpoint_isolation_404(self):
        other = make_company('qhse8-api-b', 'B')
        make_user(other, 'qhse8-api-b')
        other_releve = make_releve(other)
        resp = auth(self.user).get(self.url(other_releve))
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'qhse8-normal', role='normal')
        resp = auth(normal).get(self.url(self.releve))
        self.assertEqual(resp.status_code, 403)
