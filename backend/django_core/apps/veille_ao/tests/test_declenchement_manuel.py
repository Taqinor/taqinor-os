"""VAO23 — le bouton lance EXACTEMENT le même job que la nuit.

Le « Done = » de la tâche, point par point :
  * le bouton et le beat appellent la MÊME fonction (test d'identité — pas
    « deux fonctions qui font la même chose », la même) ;
  * la progression est visible (``BackgroundJob``, jamais une file maison) ;
  * un double clic ne lance pas deux collectes concurrentes ;
  * 403 pour un rôle non habilité.
"""
import ast
import pathlib

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import Role
from core.models import BackgroundJob

from apps.veille_ao.views import KIND_COLLECTE

URL = '/api/django/veille_ao/collecter/'
MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Collecte')

    def _api(self, permissions, suffixe):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {suffixe}',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username=f'vao_collecte_{suffixe}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api


class RouteTests(_Base):
    def test_le_chemin_litteral_du_texte_de_tache_est_bien_celui_servi(self):
        self.assertEqual(reverse('veille-ao-collecter'), URL)


class PermissionTests(_Base):
    def test_un_lecteur_seul_ne_peut_pas_declencher_la_collecte(self):
        api = self._api(['veille_ao_voir'], 'lecteur')
        self.assertEqual(api.post(URL).status_code, 403)

    def test_un_role_sans_aucune_permission_veille_est_refuse(self):
        api = self._api(['crm_voir'], 'etranger')
        self.assertEqual(api.post(URL).status_code, 403)

    def test_un_anonyme_est_refuse(self):
        self.assertIn(APIClient().post(URL).status_code, (401, 403))

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_le_gestionnaire_declenche_et_recoit_un_job_suivable(self):
        api = self._api(['veille_ao_voir', 'veille_ao_gerer'], 'gestionnaire')

        reponse = api.post(URL)

        self.assertEqual(reponse.status_code, 202)
        self.assertEqual(reponse.data['kind'], KIND_COLLECTE)
        self.assertFalse(reponse.data['deja_en_cours'])
        # Désarmé : l'écran doit pouvoir le DIRE, pas laisser croire au succès.
        self.assertFalse(reponse.data['collecte_active'])
        self.assertIn('VAO4', reponse.data['motif'])
        self.assertTrue(
            BackgroundJob.objects.filter(
                company=self.company, kind=KIND_COLLECTE).exists())


class DoubleClicTests(_Base):
    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_un_job_deja_en_cours_n_en_lance_pas_un_second(self):
        api = self._api(['veille_ao_voir', 'veille_ao_gerer'], 'double')
        user = CustomUser.objects.get(username='vao_collecte_double')
        job = BackgroundJob.objects.create(
            company=self.company, user=user, kind=KIND_COLLECTE,
            statut=BackgroundJob.STATUT_RUNNING)

        reponse = api.post(URL)

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['deja_en_cours'])
        self.assertEqual(reponse.data['job_id'], job.pk)
        self.assertEqual(
            BackgroundJob.objects.filter(
                company=self.company, kind=KIND_COLLECTE).count(), 1)

    @override_settings(VEILLE_AO_COLLECTE_ACTIVE=False)
    def test_le_verrou_est_par_SOCIETE_jamais_global(self):
        """Une collecte chez A ne doit pas bloquer le bouton chez B."""
        autre = Company.objects.create(nom='Autre société')
        autre_user = CustomUser.objects.create_user(
            username='autre_dir', password='x', company=autre)
        BackgroundJob.objects.create(
            company=autre, user=autre_user, kind=KIND_COLLECTE,
            statut=BackgroundJob.STATUT_RUNNING)

        api = self._api(['veille_ao_voir', 'veille_ao_gerer'], 'isole')
        reponse = api.post(URL)

        self.assertEqual(reponse.status_code, 202)
        self.assertFalse(reponse.data['deja_en_cours'])


class UneSeuleMecaniqueTests(SimpleTestCase):
    """Le test d'IDENTITÉ : le bouton soumet LA tâche du beat, pas une jumelle.

    Une garde mécanique, pas une garde de revue : elle lit le code source du
    bouton et vérifie que la tâche soumise est bien
    ``tasks.collecte_quotidienne`` — celle-là même que
    ``erp_agentique/celery.py`` planifie à 06:00.
    """

    def test_le_bouton_soumet_litteralement_la_tache_planifiee(self):
        source = (MODULE_DIR / 'views.py').read_text(encoding='utf-8')
        arbre = ast.parse(source)
        soumissions = [
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == 'submit'
        ]
        self.assertEqual(len(soumissions), 1,
                         'un seul point de soumission, jamais deux chemins')
        taches = [a.id for a in soumissions[0].args
                  if isinstance(a, ast.Name)]
        self.assertIn('collecte_quotidienne', taches)

    def test_la_tache_soumise_est_bien_celle_du_beat(self):
        from erp_agentique.celery import app

        from apps.veille_ao.tasks import collecte_quotidienne

        planifiees = {e.get('task') for e in app.conf.beat_schedule.values()}
        self.assertIn(collecte_quotidienne.name, planifiees)

    def test_aucun_second_chemin_de_collecte_dans_les_vues(self):
        """``views.py`` n'appelle JAMAIS le service de collecte en direct."""
        source = (MODULE_DIR / 'views.py').read_text(encoding='utf-8')
        for interdit in ('collecter(', 'collecter_toutes_les_sources('):
            self.assertNotIn(
                interdit, source,
                'la collecte passe par le job de fond, jamais en synchrone '
                'dans une requête HTTP')
