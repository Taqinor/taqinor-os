"""ENF2 — les 6 GET 500 de la checklist/des étapes chantier (fuzz api du 07/10).

Cause : plusieurs étapes modèles ORPHELINES (sans template) partageant une clé
— l'unicité est (company, template, cle) et NULL ≠ NULL, donc la base les
accepte — puis ``ensure_default_template`` les rattachait au « Défaut » par un
``update()`` en bloc : violation d'unicité, et CHAQUE lecture (liste des
modèles, des étapes, checklist et étapes d'un chantier) répondait 500.

Et les lignes de comptage / de prélèvement, générées serveur, refusaient un
POST direct par un 500 NOT NULL : la création directe est désormais 405.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.installations.models import (
    ChecklistEtapeModele, ChecklistTemplate, Installation,
)
from apps.installations.services import ensure_default_template

User = get_user_model()
BASE = '/api/django/installations'


class ChecklistOrphelinesTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ENF2 Chk', slug='enf2-chk')
        self.admin = User.objects.create_user(
            username='enf2_chk', password='x', role_legacy='admin',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        # Le « Défaut » existe déjà avec ses étapes système…
        ensure_default_template(self.co)
        # …puis trois orphelines : deux de même clé, une qui reprend une clé
        # système du « Défaut ».
        for libelle in ('A', 'B'):
            ChecklistEtapeModele.objects.create(
                company=self.co, template=None, cle='etude_site',
                libelle=libelle, ordre=50)
        ChecklistEtapeModele.objects.create(
            company=self.co, template=None, cle='materiel_recu',
            libelle='Doublon système', ordre=51)
        self.chantier = Installation.objects.create(
            company=self.co, reference='CHT-ENF2-1')

    def test_rattachement_saute_les_cles_deja_portees(self):
        defaut = ensure_default_template(self.co)
        cles = list(defaut.etapes.values_list('cle', flat=True))
        self.assertEqual(len(cles), len(set(cles)))
        self.assertEqual(cles.count('etude_site'), 1)
        # Les doublons restent orphelins — jamais supprimés.
        self.assertEqual(ChecklistEtapeModele.objects.filter(
            company=self.co, template__isnull=True).count(), 2)

    def test_lectures_ne_tombent_plus_en_500(self):
        for url in (f'{BASE}/checklist-templates/',
                    f'{BASE}/checklist-etapes/',
                    f'{BASE}/chantiers/{self.chantier.pk}/checklist/',
                    f'{BASE}/chantiers/{self.chantier.pk}/etapes/'):
            with self.subTest(url=url):
                response = self.api.get(url)
                self.assertEqual(response.status_code, 200, response.content)

    def test_checklist_chantier_sans_doublon_de_cle(self):
        response = self.api.get(f'{BASE}/chantiers/{self.chantier.pk}/checklist/')
        cles = [it['cle'] for it in response.json()['items']]
        self.assertEqual(len(cles), len(set(cles)))
        self.assertTrue(ChecklistTemplate.objects.filter(
            company=self.co, protege=True).exists())


class LignesGenereesServeurTests(TestCase):
    def setUp(self):
        co = Company.objects.create(nom='ENF2 Lignes', slug='enf2-lignes')
        admin = User.objects.create_user(
            username='enf2_lignes', password='x', role_legacy='admin',
            company=co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')

    def test_creation_directe_refusee_405(self):
        for url, corps in (
                (f'{BASE}/comptage-lignes/',
                 {'produit': None, 'designation': '', 'quantite_comptee': 0,
                  'compte': False}),
                (f'{BASE}/pick-list-lignes/',
                 {'produit': None, 'designation': '', 'bin': None,
                  'quantite_demandee': 0, 'quantite_prelevee': 0,
                  'preleve': False})):
            with self.subTest(url=url):
                response = self.api.post(url, corps, format='json')
                self.assertEqual(response.status_code, 405, response.content)
                self.assertEqual(self.api.get(url).status_code, 200)
