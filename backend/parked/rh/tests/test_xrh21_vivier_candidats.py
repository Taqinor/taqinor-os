"""Tests XRH21 — Vivier de candidats (talent pool).

Couvre :
* un rejeté mis au vivier ressort par tag (recherche ``?q=``/``?tag=``,
  company-scopée) ;
* le rattachement crée une candidature « reçu » sur la nouvelle ouverture
  avec le CV et le lien vers l'originale ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Candidature, OuverturePoste

User = get_user_model()

CANDIDATURES = '/api/django/rh/candidatures/'


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


class VivierCandidatsTests(TestCase):
    def setUp(self):
        self.co = make_company('viv-a', 'A')
        self.rh = make_user(self.co, 'viv-rh')
        self.ouverture1 = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose 2026')
        self.ouverture2 = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose 2027')
        cv = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 fake cv', content_type='application/pdf')
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture1, nom='Yassir Fahmi',
            email='yassir@example.com', etape=Candidature.Etape.REJETE,
            cv_fichier=cv)

    def test_mettre_au_vivier_avec_tags(self):
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.id}/mettre-au-vivier/',
            {'tags_vivier': 'senior,electricite'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['vivier'])
        self.assertEqual(resp.data['tags_vivier'], 'senior,electricite')

    def test_ressort_par_tag(self):
        self.cand.vivier = True
        self.cand.tags_vivier = 'senior,electricite'
        self.cand.save(update_fields=['vivier', 'tags_vivier'])

        resp = auth(self.rh).get(f'{CANDIDATURES}vivier/', {'tag': 'senior'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], self.cand.id)

        resp = auth(self.rh).get(f'{CANDIDATURES}vivier/', {'tag': 'absent'})
        self.assertEqual(len(resp.data), 0)

    def test_ressort_par_recherche_q(self):
        self.cand.vivier = True
        self.cand.save(update_fields=['vivier'])
        resp = auth(self.rh).get(f'{CANDIDATURES}vivier/', {'q': 'Yassir'})
        self.assertEqual(len(resp.data), 1)

    def test_vivier_liste_ne_montre_que_les_marques(self):
        autre = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture1, nom='Non vivier')
        resp = auth(self.rh).get(f'{CANDIDATURES}vivier/')
        ids = {row['id'] for row in resp.data}
        self.assertNotIn(autre.id, ids)

    def test_rattacher_cree_candidature_recu_avec_cv_et_lien(self):
        self.cand.vivier = True
        self.cand.save(update_fields=['vivier'])

        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.id}/rattacher/',
            {'ouverture': self.ouverture2.id})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['etape'], 'recu')
        self.assertEqual(resp.data['vivier_origine'], self.cand.id)
        self.assertTrue(resp.data['cv_fichier'])

        nouvelle = Candidature.objects.get(pk=resp.data['id'])
        self.assertEqual(nouvelle.ouverture_id, self.ouverture2.id)
        self.assertEqual(nouvelle.vivier_origine_id, self.cand.id)

    def test_rattacher_ouverture_autre_societe_404(self):
        co_b = make_company('viv-b', 'B')
        ouverture_b = OuverturePoste.objects.create(
            company=co_b, intitule='Poste B')
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.id}/rattacher/',
            {'ouverture': ouverture_b.id})
        self.assertEqual(resp.status_code, 404)

    def test_isolation_societe(self):
        co_b = make_company('viv-c', 'B')
        rh_b = make_user(co_b, 'viv-rh-b')
        self.cand.vivier = True
        self.cand.tags_vivier = 'senior'
        self.cand.save(update_fields=['vivier', 'tags_vivier'])
        resp = auth(rh_b).get(f'{CANDIDATURES}vivier/', {'tag': 'senior'})
        self.assertEqual(len(resp.data), 0)
