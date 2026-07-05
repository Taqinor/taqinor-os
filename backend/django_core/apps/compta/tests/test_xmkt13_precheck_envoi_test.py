"""XMKT13 — Envoi test + aperçu fusionné + pré-check santé avant envoi.

Couvre : le test part vers les seeds avec la fusion réelle, le pré-check
liste chaque avertissement (image, segment vide), l'absence de lien de
désinscription BLOQUE l'envoi email marketing, un canal SMS n'exige pas ce
lien, tests.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, ListeDiffusion
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


class EnvoiTestTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt13', 'XMKT13')
        self.user = make_user(self.co, 'xmkt13-user')

    def test_envoi_test_fusionne_pour_contact_exemple(self):
        lead = Lead.objects.create(company=self.co, nom='A', prenom='Sara')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='Bonjour {prenom} !')
        resultat = services.envoyer_test_campagne(
            camp, adresses_seed=['seed@x.ma'], lead_id_exemple=lead.id)
        self.assertEqual(resultat['seeds'], ['seed@x.ma'])
        self.assertEqual(resultat['corps_fusionne'], 'Bonjour Sara !')

    def test_envoi_test_ne_modifie_pas_le_statut(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL, corps='Hi')
        services.envoyer_test_campagne(camp, adresses_seed=['seed@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)
        self.assertEqual(camp.nb_envois, 0)


class PrecheckSanteTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt13-b', 'XMKT13-B')
        self.user = make_user(self.co, 'xmkt13-b-user')

    def test_bloque_si_lien_desinscription_absent_email(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='Bonjour, profitez de notre offre !')
        rapport = services.precheck_sante_campagne(camp)
        self.assertTrue(rapport['bloque'])
        self.assertTrue(any('désinscription' in a for a in rapport['avertissements']))

    def test_ne_bloque_pas_si_lien_desinscription_present(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='Offre. Se désinscrire : /desinscription/abc123/')
        rapport = services.precheck_sante_campagne(camp)
        self.assertFalse(rapport['bloque'])

    def test_sms_nexige_pas_le_lien_desinscription(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.SMS,
            corps='Offre spéciale, appelez-nous.')
        rapport = services.precheck_sante_campagne(camp)
        self.assertFalse(rapport['bloque'])

    def test_avertit_segment_vide(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.SMS, corps='Hi')
        rapport = services.precheck_sante_campagne(camp)
        self.assertTrue(
            any('destinataire' in a for a in rapport['avertissements']))

    def test_pas_davertissement_segment_vide_si_liste_ciblee(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.SMS, corps='Hi')
        camp.listes.add(liste)
        rapport = services.precheck_sante_campagne(camp)
        self.assertFalse(
            any('destinataire' in a for a in rapport['avertissements']))

    def test_avertit_image_dans_le_corps(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.SMS,
            corps='Voir https://x.ma/promo.jpg')
        rapport = services.precheck_sante_campagne(camp)
        self.assertTrue(any('Image' in a for a in rapport['avertissements']))


class PrecheckSanteApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt13-api', 'XMKT13 API')
        self.user = make_user(self.co, 'xmkt13-api-user')

    def test_precheck_endpoint(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL, corps='Hi')
        api = auth(self.user)
        resp = api.get(f'/api/django/compta/campagnes/{camp.id}/precheck/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['bloque'])

    def test_envoyer_test_endpoint(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL, corps='Hi')
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/campagnes/{camp.id}/envoyer-test/',
            {'adresses_seed': ['seed@x.ma']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['seeds'], ['seed@x.ma'])
