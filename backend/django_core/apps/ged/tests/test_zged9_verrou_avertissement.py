"""ZGED9 — Verrouillage/déverrouillage manuel d'un document (« en cours
d'édition »).

Couvre :
  * verrouiller affiche l'avertissement à tous ;
  * seul le poseur ou un gestionnaire déverrouille ;
  * le forçage est tracé ;
  * la lecture reste possible pendant le verrou ;
  * gardes GED23/24 respectées (implicitement — ce verrou n'y touche pas).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentActivity, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZGed9Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged9-a', 'Zged9 A')
        self.admin_a = make_user(self.co_a, 'zged9-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'zged9-autre-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')


class ServiceTests(ZGed9Base):
    def test_verrouiller_pose_le_verrou(self):
        doc = services.verrouiller_avertissement(
            self.doc, self.autre_a, motif='Édition en cours')
        self.assertEqual(doc.verrou_avertissement_par_id, self.autre_a.pk)
        self.assertIsNotNone(doc.verrou_avertissement_le)
        self.assertEqual(doc.verrou_avertissement_motif, 'Édition en cours')
        self.assertTrue(doc.est_verrouille_avertissement)

    def test_verrouiller_par_un_autre_leve_permission_error(self):
        services.verrouiller_avertissement(self.doc, self.autre_a)
        with self.assertRaises(PermissionError):
            services.verrouiller_avertissement(self.doc, self.admin_a)

    def test_poseur_peut_deverrouiller(self):
        services.verrouiller_avertissement(self.doc, self.autre_a)
        doc = services.deverrouiller_avertissement(self.doc, self.autre_a)
        self.assertFalse(doc.est_verrouille_avertissement)

    def test_gestionnaire_peut_forcer_deverrouillage_trace(self):
        self.doc.refresh_from_db()
        services.verrouiller_avertissement(self.doc, self.autre_a)
        self.doc.refresh_from_db()
        doc = services.deverrouiller_avertissement(self.doc, self.admin_a)
        self.assertFalse(doc.est_verrouille_avertissement)
        force_event = DocumentActivity.objects.filter(
            document=doc, type_evenement='verrou_avertissement_force').first()
        self.assertIsNotNone(force_event)

    def test_tiers_non_gestionnaire_ne_peut_pas_deverrouiller(self):
        tiers = make_user(self.co_a, 'zged9-tiers-a', 'normal')
        services.verrouiller_avertissement(self.doc, self.autre_a)
        with self.assertRaises(PermissionError):
            services.deverrouiller_avertissement(self.doc, tiers)

    def test_deverrouiller_deja_libre_idempotent(self):
        doc = services.deverrouiller_avertissement(self.doc, self.admin_a)
        self.assertFalse(doc.est_verrouille_avertissement)


class ViewTests(ZGed9Base):
    def test_verrouiller_affiche_avertissement_a_tous(self):
        api = auth(self.autre_a)
        resp = api.post(
            f'/api/django/ged/documents/{self.doc.pk}/verrouiller/',
            {'motif': 'Édition'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['est_verrouille_avertissement'])
        self.assertEqual(resp.data['verrou_avertissement_par_nom'], 'zged9-autre-a')
        # Lecture par un autre utilisateur reste possible pendant le verrou.
        api_admin = auth(self.admin_a)
        resp_get = api_admin.get(f'/api/django/ged/documents/{self.doc.pk}/')
        self.assertEqual(resp_get.status_code, 200)
        self.assertTrue(resp_get.data['est_verrouille_avertissement'])

    def test_verrouille_par_autre_conflit_409(self):
        api_autre = auth(self.autre_a)
        api_autre.post(f'/api/django/ged/documents/{self.doc.pk}/verrouiller/')
        api_admin = auth(self.admin_a)
        resp = api_admin.post(
            f'/api/django/ged/documents/{self.doc.pk}/verrouiller/')
        self.assertEqual(resp.status_code, 409)

    def test_deverrouiller_par_tiers_403(self):
        tiers = make_user(self.co_a, 'zged9-tiers-a2', 'normal')
        api_autre = auth(self.autre_a)
        api_autre.post(f'/api/django/ged/documents/{self.doc.pk}/verrouiller/')
        api_tiers = auth(tiers)
        resp = api_tiers.post(
            f'/api/django/ged/documents/{self.doc.pk}/deverrouiller/')
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe(self):
        co_b = make_company('zged9-b', 'Zged9 B')
        admin_b = make_user(co_b, 'zged9-admin-b', 'admin')
        api_b = auth(admin_b)
        resp = api_b.post(
            f'/api/django/ged/documents/{self.doc.pk}/verrouiller/')
        self.assertEqual(resp.status_code, 404)
