"""WIR99/DC12 — pré-remplissage d'un devis SANS LEAD depuis ``crm.SiteProfile``.

Le docstring de ``crm.SiteProfile`` promettait ce pré-remplissage, mais
``crm.selectors.site_profile_for_client`` n'avait AUCUN appelant : un devis
sans lead n'était jamais pré-rempli. Ce test verrouille le point d'entrée
``GET /ventes/devis/prefill-site/?client=<id>`` — y compris l'isolation
société (un profil d'une autre société n'est jamais renvoyé).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_wir99_site_profile_prefill -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, SiteProfile

User = get_user_model()

URL = '/api/django/ventes/devis/prefill-site/'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WIR99SiteProfilePrefillTests(TestCase):
    def setUp(self):
        self.company = make_company('wir99-co', 'WIR99 Co')
        self.user = User.objects.create_user(
            username='wir99_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Sans', prenom='Lead',
            email='wir99@example.com')

    def test_sans_profil_renvoie_null(self):
        r = self.api.get(URL, {'client': self.client_obj.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['client'], self.client_obj.id)
        self.assertIsNone(r.data['profil'])

    def test_profil_rempli_est_renvoye(self):
        SiteProfile.objects.create(
            company=self.company, client=self.client_obj,
            facture_hiver=Decimal('1200.00'), ete_differente=True,
            facture_ete=Decimal('900.00'),
            conso_mensuelle_kwh=Decimal('850.00'),
            raccordement='triphase', type_installation='agricole',
            pompe_cv=Decimal('7.50'), pompe_hmt_m=Decimal('60.00'),
            pompe_debit_m3h=Decimal('12.00'),
            surface_toiture_m2=Decimal('140.00'))

        r = self.api.get(URL, {'client': self.client_obj.id})
        self.assertEqual(r.status_code, 200)
        profil = r.data['profil']
        self.assertIsNotNone(profil)
        self.assertEqual(profil['facture_hiver'], Decimal('1200.00'))
        self.assertEqual(profil['facture_ete'], Decimal('900.00'))
        self.assertTrue(profil['ete_differente'])
        self.assertEqual(profil['conso_mensuelle_kwh'], Decimal('850.00'))
        self.assertEqual(profil['raccordement'], 'triphase')
        self.assertEqual(profil['type_installation'], 'agricole')
        self.assertEqual(profil['pompe_cv'], Decimal('7.50'))
        self.assertEqual(profil['surface_toiture_m2'], Decimal('140.00'))

    def test_profil_dune_autre_societe_jamais_renvoye(self):
        autre = make_company('wir99-co-2', 'WIR99 Co 2')
        client_autre = Client.objects.create(
            company=autre, nom='Autre', email='wir99b@example.com')
        SiteProfile.objects.create(
            company=autre, client=client_autre,
            facture_hiver=Decimal('5000.00'))

        r = self.api.get(URL, {'client': client_autre.id})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['profil'])

    def test_parametre_client_requis_et_valide(self):
        self.assertEqual(self.api.get(URL).status_code, 400)
        self.assertEqual(
            self.api.get(URL, {'client': 'abc'}).status_code, 400)

    def test_lecture_ouverte_a_tout_role(self):
        """`get_permissions` PRIME sur le `permission_classes` de l'@action :
        sans l'ajout explicite, cette lecture retombait sur IsAdminRole."""
        normal = User.objects.create_user(
            username='wir99_normal', password='x', role_legacy='normal',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(normal)}')
        r = api.get(URL, {'client': self.client_obj.id})
        self.assertEqual(r.status_code, 200)

    def test_prefill_nexpose_aucun_prix_achat(self):
        SiteProfile.objects.create(
            company=self.company, client=self.client_obj,
            facture_hiver=Decimal('1200.00'))
        r = self.api.get(URL, {'client': self.client_obj.id})
        self.assertNotIn('prix_achat', str(r.data))
        self.assertNotIn('marge', str(r.data))
