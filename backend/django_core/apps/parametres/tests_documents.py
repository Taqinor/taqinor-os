"""D2/N60/N67/N26/N59 — tests des modèles de documents éditables.

Couvre : scoping société (get-or-create par société), surcharges non vides
seulement (``as_doc_texts``), versionnement N67, endpoints GET/UPDATE avec
``company`` posée côté serveur, et l'audit des changements (N55)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import SettingsAuditLog
from apps.parametres.models_documents import DocumentTemplates

User = get_user_model()

GET_URL = '/api/django/parametres/document-templates/'
PUT_URL = '/api/django/parametres/document-templates/update/'


def _company(slug='doc-co', nom='Doc Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class DocumentTemplatesModelTest(TestCase):
    def test_get_creates_one_per_company(self):
        c1, c2 = _company('c1', 'C1'), _company('c2', 'C2')
        a = DocumentTemplates.get(company=c1)
        b = DocumentTemplates.get(company=c1)
        d = DocumentTemplates.get(company=c2)
        self.assertEqual(a.pk, b.pk)            # singleton par société
        self.assertNotEqual(a.pk, d.pk)         # isolé par société
        self.assertEqual(a.version, 1)

    def test_as_doc_texts_empty_by_default(self):
        tpl = DocumentTemplates.get(company=_company())
        # Rien d'édité → aucune surcharge → le moteur applique ses littéraux.
        self.assertEqual(tpl.as_doc_texts(), {})

    def test_as_doc_texts_only_non_empty_overrides(self):
        tpl = DocumentTemplates.get(company=_company())
        tpl.cgv_titre = 'MES CGV'
        tpl.garantie_titre = ''             # vide → ignoré
        tpl.cgv_bullets = []                # liste vide → ignorée
        tpl.bpa_titre = 'Accord'
        tpl.save()
        out = tpl.as_doc_texts()
        self.assertEqual(out, {'cgv_titre': 'MES CGV', 'bpa_titre': 'Accord'})

    def test_as_doc_texts_includes_bullets_list_when_set(self):
        tpl = DocumentTemplates.get(company=_company())
        tpl.cgv_bullets = ['Une', 'Deux']
        tpl.save()
        self.assertEqual(tpl.as_doc_texts()['cgv_bullets'], ['Une', 'Deux'])


class DocumentTemplatesApiTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='doc_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)

    def test_get_returns_defaults_blank(self):
        r = self.api.get(GET_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cgv_titre'], '')
        self.assertEqual(r.data['version'], 1)
        # company jamais exposée
        self.assertNotIn('company', r.data)

    def test_update_persists_and_bumps_version(self):
        r = self.api.patch(
            PUT_URL, {'cgv_titre': 'Conditions maison'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cgv_titre'], 'Conditions maison')
        self.assertEqual(r.data['version'], 2)   # N67 — incrément
        tpl = DocumentTemplates.get(company=self.company)
        self.assertEqual(tpl.cgv_titre, 'Conditions maison')

    def test_update_no_change_keeps_version(self):
        self.api.patch(PUT_URL, {'cgv_titre': 'X'}, format='json')
        # Re-soumettre la même valeur ne doit pas ré-incrémenter.
        r = self.api.patch(PUT_URL, {'cgv_titre': 'X'}, format='json')
        self.assertEqual(r.data['version'], 2)

    def test_update_writes_audit_log(self):
        self.api.patch(PUT_URL, {'bpa_titre': 'Accord'}, format='json')
        logs = SettingsAuditLog.objects.filter(
            company=self.company, section='documents', field='bpa_titre')
        self.assertEqual(logs.count(), 1)

    def test_company_forced_server_side(self):
        # Tenter d'injecter une autre company est ignoré (champ non exposé).
        other = _company('other', 'Other')
        r = self.api.patch(
            PUT_URL, {'cgv_titre': 'A', 'company': other.id}, format='json')
        self.assertEqual(r.status_code, 200)
        tpl = DocumentTemplates.get(company=self.company)
        self.assertEqual(tpl.cgv_titre, 'A')
        # La société de l'utilisateur reste la cible.
        self.assertEqual(tpl.company_id, self.company.id)

    def test_cgv_bullets_must_be_list(self):
        r = self.api.patch(
            PUT_URL, {'cgv_bullets': 'pas-une-liste'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_cgv_bullets_list_persists(self):
        r = self.api.patch(
            PUT_URL, {'cgv_bullets': ['Puce A', 'Puce B']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['cgv_bullets'], ['Puce A', 'Puce B'])

    def test_non_admin_cannot_update(self):
        limited = User.objects.create_user(
            username='doc_limited', password='x',
            role_legacy='commercial', company=self.company)
        api = _auth(limited)
        r = api.patch(PUT_URL, {'cgv_titre': 'Z'}, format='json')
        self.assertIn(r.status_code, (401, 403))
