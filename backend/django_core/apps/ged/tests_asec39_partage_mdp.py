"""ASEC39 — mot de passe de partage GED : jamais en query string, et gel du
partage après N échecs quelle que soit l'IP.

Constat C-ASEC-026 : ``?password=`` était accepté (journalisé par les
proxies) et le seul frein était un throttle PAR IP — un essai réparti sur
plusieurs IP n'était jamais arrêté ; POST répondait 405.
MinIO de la pile de test réel ; aucun mock interne.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, PartageGed
from apps.ged.views import PARTAGE_ECHECS_MAX
from authentication.models import Company

User = get_user_model()
PDF = b'%PDF-1.4\n%asec39\n' + b'P' * 32
MDP = 'bon-mot-de-passe'


class PartageMotDePasseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.co = Company.objects.create(nom='ASEC39', slug='asec39')
        self.admin = User.objects.create_user(
            username='asec39_admin', password='x', role_legacy='admin',
            company=self.co)
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=folder, nom='partage.pdf')
        cle, _meta = services._store_bytes(PDF, mime='application/pdf')
        services.add_version(
            self.doc, file_key=cle, company=self.co, filename='partage.pdf',
            mime='application/pdf', uploaded_by=self.admin)
        self.partage = services.create_partage(
            document=self.doc, company=self.co, created_by=self.admin,
            password=MDP)
        self.url = f'/api/django/ged/public/{self.partage.token}/'

    def tearDown(self):
        cache.clear()

    def _get(self, mdp, ip='10.0.0.1'):
        return APIClient().get(self.url, HTTP_X_PARTAGE_PASSWORD=mdp,
                               REMOTE_ADDR=ip)

    def test_query_string_refusee(self):
        r = APIClient().get(self.url + '?password=' + MDP)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['code'], 'mot_de_passe_en_en_tete')
        self.partage.refresh_from_db()
        self.assertEqual(self.partage.telechargements, 0)

    def test_post_corps_accepte(self):
        r = APIClient().post(self.url, {'password': MDP}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_gel_par_partage_multi_ip(self):
        for i in range(PARTAGE_ECHECS_MAX):
            r = self._get('faux', ip=f'10.1.0.{i + 1}')
            self.assertEqual(r.status_code, 403, r.content)
        self.partage.refresh_from_db()
        self.assertIsNotNone(self.partage.gele_jusqua)
        self.assertGreater(self.partage.gele_jusqua, timezone.now())
        # Le BON mot de passe, depuis une IP neuve : refusé pendant le gel.
        r = self._get(MDP, ip='10.9.9.9')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertIn("Trop d'essais", r.data['detail'])

    def test_degel_apres_periode(self):
        PartageGed.objects.filter(pk=self.partage.pk).update(
            gele_jusqua=timezone.now() - timedelta(minutes=1))
        r = self._get(MDP, ip='10.2.0.1')
        self.assertEqual(r.status_code, 200, r.content)
