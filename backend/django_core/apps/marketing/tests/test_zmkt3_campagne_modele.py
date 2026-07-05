"""ZMKT3 — Enregistrer une campagne comme modèle réutilisable (étoile).

Couvre : étoiler une campagne la sort du flux d'envoi, « créer depuis
modèle » produit un brouillon indépendant copiant le contenu, les modèles
sont listables, migration additive, tests (clone n'altère pas le modèle,
multi-tenant).
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, ListeDiffusion


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CampagneModeleTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt3', 'ZMKT3')

    def test_modele_exclu_du_pipeline_kanban(self):
        Campagne.objects.create(
            company=self.co, nom='Modèle', canal=Campagne.Canal.EMAIL,
            est_modele=True)
        kanban = services.campagnes_par_statut(self.co)
        self.assertEqual(len(kanban[Campagne.Statut.BROUILLON]), 0)

    def test_creer_depuis_modele_clone_contenu(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        modele = Campagne.objects.create(
            company=self.co, nom='Bienvenue', canal=Campagne.Canal.EMAIL,
            objet='Sujet', corps='Corps', est_modele=True)
        modele.listes.add(liste)
        clone = services.creer_depuis_modele(modele)
        self.assertEqual(clone.objet, 'Sujet')
        self.assertEqual(clone.corps, 'Corps')
        self.assertFalse(clone.est_modele)
        self.assertIn(liste, clone.listes.all())

    def test_clone_naltere_pas_le_modele(self):
        modele = Campagne.objects.create(
            company=self.co, nom='M2', canal=Campagne.Canal.EMAIL,
            objet='Original', est_modele=True)
        services.creer_depuis_modele(modele)
        modele.refresh_from_db()
        self.assertEqual(modele.objet, 'Original')
        self.assertTrue(modele.est_modele)

    def test_clone_est_independant(self):
        modele = Campagne.objects.create(
            company=self.co, nom='M3', canal=Campagne.Canal.EMAIL,
            objet='X', est_modele=True)
        clone = services.creer_depuis_modele(modele)
        clone.objet = 'Modifié'
        clone.save(update_fields=['objet'])
        modele.refresh_from_db()
        self.assertEqual(modele.objet, 'X')

    def test_endpoint_creer_depuis_modele(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        modele = Campagne.objects.create(
            company=self.co, nom='M4', canal=Campagne.Canal.EMAIL,
            objet='Y', est_modele=True)
        user = User.objects.create_user(
            username='zmkt3-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.post(
            f'/api/django/compta/campagnes/{modele.id}/creer-depuis-modele/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.json()['est_modele'])

    def test_endpoint_modeles_liste(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        Campagne.objects.create(
            company=self.co, nom='M5', canal=Campagne.Canal.EMAIL,
            est_modele=True)
        Campagne.objects.create(
            company=self.co, nom='Normale', canal=Campagne.Canal.EMAIL)
        user = User.objects.create_user(
            username='zmkt3-user2', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/compta/campagnes/modeles/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt3-b', 'ZMKT3-B')
        Campagne.objects.create(
            company=self.co, nom='Mine', canal=Campagne.Canal.EMAIL,
            est_modele=True)
        self.assertEqual(
            Campagne.objects.filter(company=other, est_modele=True).count(), 0)
