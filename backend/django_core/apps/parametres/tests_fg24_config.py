"""FG24 — export/import de la configuration entre sociétés.

Export = config reproductible uniquement (jamais secrets/données métier).
Import = additif, scopé à la société de l'appelant, modes merge/overwrite."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS
from apps.parametres.models import CompanyProfile, MessageTemplate

User = get_user_model()


def _company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _admin_api(company):
    role = Role.objects.create(
        company=company, nom='Administrateur',
        permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
    u = User.objects.create_user(
        username=f'admin_{company.slug}', password='pw', role_legacy='admin',
        role=role, company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
    return api


class FG24ConfigTest(TestCase):
    def setUp(self):
        self.src = _company('fg24-src', 'Source')
        CompanyProfile.objects.create(
            company=self.src, rib='SECRET-RIB-123',
            quote_validity_days=45, couleur_principale='#abcdef')
        MessageTemplate.objects.create(
            company=self.src, cle='facture', corps_fr='Bonjour {client}')
        Role.objects.create(
            company=self.src, nom='Rôle perso',
            permissions=['crm_voir'], est_systeme=False)
        self.api_src = _admin_api(self.src)

    def test_export_excludes_secrets_and_business_data(self):
        r = self.api_src.get('/api/django/parametres/config-export/')
        self.assertEqual(r.status_code, 200, r.content)
        bundle = r.data
        # Profil : pas de RIB ni de coordonnées (secrets).
        self.assertNotIn('rib', bundle['profile'])
        self.assertIn('quote_validity_days', bundle['profile'])
        # Modèles & rôle perso présents.
        self.assertTrue(any(m['cle'] == 'facture'
                            for m in bundle['message_templates']))
        self.assertTrue(any(r2['nom'] == 'Rôle perso'
                            for r2 in bundle['roles']))

    def test_import_merge_creates_into_target_company(self):
        bundle = self.api_src.get(
            '/api/django/parametres/config-export/').data
        dst = _company('fg24-dst', 'Dest')
        api_dst = _admin_api(dst)
        r = api_dst.post('/api/django/parametres/config-import/', bundle,
                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # Le rôle perso et le modèle ont été créés DANS la société cible.
        self.assertTrue(Role.objects.filter(
            company=dst, nom='Rôle perso').exists())
        self.assertTrue(MessageTemplate.objects.filter(
            company=dst, cle='facture').exists())

    def test_import_merge_does_not_overwrite_existing(self):
        dst = _company('fg24-dst2', 'Dest2')
        MessageTemplate.objects.create(
            company=dst, cle='facture', corps_fr='EXISTANT')
        api_dst = _admin_api(dst)
        bundle = self.api_src.get(
            '/api/django/parametres/config-export/').data
        api_dst.post('/api/django/parametres/config-import/', bundle,
                     format='json')
        # merge n'écrase pas → le corps existant est préservé.
        self.assertEqual(
            MessageTemplate.objects.get(company=dst, cle='facture').corps_fr,
            'EXISTANT')

    def test_import_overwrite_updates_existing(self):
        dst = _company('fg24-dst3', 'Dest3')
        MessageTemplate.objects.create(
            company=dst, cle='facture', corps_fr='EXISTANT')
        api_dst = _admin_api(dst)
        bundle = self.api_src.get(
            '/api/django/parametres/config-export/').data
        api_dst.post(
            '/api/django/parametres/config-import/?mode=overwrite',
            bundle, format='json')
        self.assertEqual(
            MessageTemplate.objects.get(company=dst, cle='facture').corps_fr,
            'Bonjour {client}')

    def test_import_requires_admin(self):
        dst = _company('fg24-dst4', 'Dest4')
        viewer = User.objects.create_user(
            username='fg24_viewer', password='pw', role_legacy='utilisateur',
            company=dst)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        r = api.post('/api/django/parametres/config-import/', {}, format='json')
        self.assertEqual(r.status_code, 403)
