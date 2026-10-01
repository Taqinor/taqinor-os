"""QJR655 — UNE règle de portée société : ``core.mixins.company_qs``.

Sémantique exacte de ``TenantMixin.get_queryset`` (et des 8 copies
``_company_qs`` des vues ventes qu'elle remplace) : un utilisateur rattaché
voit sa société ; un superuser SANS société voit tout (acteur plateforme,
test_aud117) ; tout autre utilisateur sans société ne voit rien.

Run :
    python manage.py test core.tests.test_company_qs -v2
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core.mixins import company_qs

User = get_user_model()

VUES_VENTES = Path(__file__).resolve().parents[2] / 'apps' / 'ventes' / 'views'


class CompanyQsTest(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='QS A', slug='qs-a-655')
        self.b = Company.objects.create(nom='QS B', slug='qs-b-655')
        self.membre_a = User.objects.create_user(
            username='membre-a655', password='x', company=self.a)
        self.membre_b = User.objects.create_user(
            username='membre-b655', password='x', company=self.b)

    def test_utilisateur_sans_societe_ne_voit_rien(self):
        user = User.objects.create_user(username='orphelin655', password='x')
        self.assertFalse(company_qs(User.objects.all(), user).exists())

    def test_superuser_sans_societe_voit_tout(self):
        root = User.objects.create_superuser(
            username='root655', password='x', email='root655@ex.com')
        ids = set(company_qs(User.objects.all(), root)
                  .values_list('id', flat=True))
        self.assertTrue({self.membre_a.id, self.membre_b.id} <= ids)

    def test_a_ne_voit_pas_b(self):
        user = User.objects.create_user(
            username='a655', password='x', company=self.a)
        ids = set(company_qs(User.objects.all(), user)
                  .values_list('id', flat=True))
        self.assertIn(self.membre_a.id, ids)
        self.assertNotIn(self.membre_b.id, ids)


class AucuneCopieDansLesVuesVentes(SimpleTestCase):
    def test_aucun_def_company_qs_sous_ventes_views(self):
        coupables = [p.name for p in sorted(VUES_VENTES.glob('*.py'))
                     if 'def _company_qs' in p.read_text(encoding='utf-8')]
        self.assertEqual(coupables, [])
