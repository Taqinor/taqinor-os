"""APRF20 — ``nb_tentatives`` par sous-requête corrélée : la requête de page
des leads ne joint plus ``crm_leadactivity`` au niveau principal, et la
valeur de chaque lead est inchangée (appel/WhatsApp/e-mail AVEC auteur).

Test-du-test : remettre le ``Count`` joint ⇒ test_sql_sans_jointure échoue ;
oublier le filtre ``user__isnull=False`` ⇒ test_valeurs échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.views import LeadViewSet

User = get_user_model()

HUMAINES = (LeadActivity.Kind.APPEL, LeadActivity.Kind.WHATSAPP,
            LeadActivity.Kind.EMAIL)


class NbTentativesSousRequeteTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF20 Solaire', slug='aprf20-tentatives')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf20-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.attendu = {}
        kinds = (LeadActivity.Kind.NOTE,) + HUMAINES
        for i in range(12):
            lead = Lead.objects.create(
                company=self.company, nom=f'L{i}', stage=stages.CONTACTED)
            n = 0
            if i % 2 == 0:
                for j in range(8):
                    kind = kinds[j % len(kinds)]
                    auteur = self.user if j % 3 else None
                    LeadActivity.objects.create(
                        company=self.company, lead=lead, user=auteur,
                        kind=kind, body=f'a{j}')
                    if kind in HUMAINES and auteur is not None:
                        n += 1
            self.attendu[lead.pk] = n

    def test_sql_sans_jointure(self):
        qs = LeadViewSet._annoter_prochaine_touche(
            Lead.objects.filter(company=self.company), self.company)
        sql = str(qs.query)
        self.assertNotIn('LEFT OUTER JOIN "crm_leadactivity"', sql)
        self.assertIn('crm_leadactivity', sql)  # bien via la sous-requête

    def test_valeurs(self):
        qs = LeadViewSet._annoter_prochaine_touche(
            Lead.objects.filter(company=self.company), self.company)
        obtenu = dict(qs.values_list('pk', 'nb_tentatives'))
        self.assertEqual(obtenu, self.attendu)
        self.assertTrue(any(self.attendu.values()))

    def test_page_api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get('/api/django/crm/leads/?page_size=50')
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data.get('results', resp.data)
        obtenu = {r['id']: r['nb_tentatives'] for r in lignes}
        self.assertEqual(obtenu, self.attendu)
