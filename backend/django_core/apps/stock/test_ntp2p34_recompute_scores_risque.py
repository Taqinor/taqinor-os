"""
NTP2P34 / ACEL41 — le recalcul quotidien du score de risque fournisseur est
RETIRÉ du planning.

``score_risque_fournisseur`` (NTP2P8) est un calcul PUR sans cache stocké :
le badge ``fournisseurs/<id>/score-risque/`` le calcule à chaque appel. La
tâche ``stock.recompute_scores_risque`` jetait son résultat (no-op par
construction) ; ACEL41 la supprime avec son entrée du ``beat_schedule`` et sa
route, et ce module prouve que le badge rend toujours son score.

Run :
    python manage.py test \
        apps.stock.test_ntp2p34_recompute_scores_risque -v2
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import Fournisseur

User = get_user_model()

TACHE = 'stock.recompute_scores_risque'


class RecomputeScoresRisqueTaskTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ntp2p34-co', slug='ntp2p34-co')
        self.user = User.objects.create_user(
            username='ntp2p34-user', password='x', company=self.company,
            role_legacy='responsable')

    def test_plus_planifiee_et_badge_toujours_calcule(self):
        from erp_agentique.celery import app

        app.loader.import_default_modules()
        taches_planifiees = {
            entree['task'] for entree in app.conf.beat_schedule.values()}
        self.assertNotIn(TACHE, taches_planifiees)
        self.assertNotIn(TACHE, app.tasks)
        self.assertNotIn(TACHE, settings.CELERY_TASK_ROUTES)

        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four A')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get(
            f'/api/django/stock/fournisseurs/{fournisseur.pk}/score-risque/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('score', resp.data)
        self.assertIn('facteurs', resp.data)
