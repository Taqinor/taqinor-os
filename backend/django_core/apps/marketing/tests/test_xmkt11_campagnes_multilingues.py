"""XMKT11 — Campagnes multilingues FR/AR/Darija avec variantes par contact.

Couvre : un contact AR/darija reçoit sa variante (dir=rtl pour l'arabe),
absence de variante = fallback FR, l'éditeur permet les 2-3 variantes.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne
from apps.crm.models import Lead

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


class CampagnesMultilinguesTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt11', 'XMKT11')
        self.camp = Campagne.objects.create(
            company=self.co, nom='Multi', canal=Campagne.Canal.EMAIL,
            objet='Bonjour {prenom}', corps='Corps FR',
            variantes_langue={
                'ar': {'objet': 'مرحبا', 'corps': 'محتوى بالعربية'},
                'darija': {'objet': 'Salam {prenom}', 'corps': 'Corps darija'},
            })

    def test_variante_fr_par_defaut(self):
        objet, corps = services.variante_pour_langue(self.camp, 'fr')
        self.assertEqual(objet, 'Bonjour {prenom}')
        self.assertEqual(corps, 'Corps FR')

    def test_variante_ar_utilisee(self):
        objet, corps = services.variante_pour_langue(self.camp, 'ar')
        self.assertEqual(objet, 'مرحبا')
        self.assertEqual(corps, 'محتوى بالعربية')

    def test_variante_darija_utilisee(self):
        objet, corps = services.variante_pour_langue(self.camp, 'darija')
        self.assertEqual(corps, 'Corps darija')

    def test_langue_absente_fallback_fr(self):
        objet, corps = services.variante_pour_langue(self.camp, 'es')
        self.assertEqual(objet, 'Bonjour {prenom}')

    def test_rendu_pour_lead_darija(self):
        lead = Lead.objects.create(
            company=self.co, nom='Client', prenom='Yassine',
            langue_preferee=Lead.LanguePreferee.DARIJA)
        rendu = services.rendre_pour_lead(self.camp, self.co, lead.id)
        self.assertEqual(rendu['langue'], 'darija')
        self.assertFalse(rendu['rtl'])
        self.assertEqual(rendu['corps'], 'Corps darija')

    def test_rendu_pour_lead_ar_rtl(self):
        lead = Lead.objects.create(
            company=self.co, nom='Client', prenom='Amine',
            langue_preferee='ar')
        rendu = services.rendre_pour_lead(self.camp, self.co, lead.id)
        self.assertEqual(rendu['langue'], 'ar')
        self.assertTrue(rendu['rtl'])

    def test_rendu_pour_lead_sans_langue_fallback_fr(self):
        lead = Lead.objects.create(company=self.co, nom='Client')
        rendu = services.rendre_pour_lead(self.camp, self.co, lead.id)
        self.assertEqual(rendu['langue'], 'fr')
        self.assertFalse(rendu['rtl'])

    def test_endpoint_rendu_lead(self):
        lead = Lead.objects.create(
            company=self.co, nom='Client', prenom='Sara',
            langue_preferee='ar')
        user = make_user(self.co, 'xmkt11-user')
        resp = auth(user).get(
            f'/api/django/compta/campagnes/{self.camp.id}/rendu-lead/'
            f'?lead_id={lead.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['langue'], 'ar')
