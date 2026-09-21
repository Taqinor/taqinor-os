"""Tests du radar de retards PROJ14 — tâches/jalons en retard ou à risque.

Couvre :
  - Sélecteur ``retards_projet`` : tâches en retard / à risque / dans les délais
  - Sélecteur ``retards_projet`` : jalons en retard / à risque / dans les délais
  - Exclusion des tâches terminées et jalons atteints
  - Paramètre ``seuil_jours`` personnalisable
  - Endpoint ``GET /api/django/gestion-projet/projets/<id>/retards/``
  - Isolation multi-société (user B ne voit pas le projet de A → 404)
  - Paramètre ``?seuil_jours=N`` via l'API
  - Accès réservé au palier Administrateur/Responsable (rôle normal → 403)
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Jalon, Projet, Tache

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


TODAY = date.today()
HIER = TODAY - timedelta(days=1)
AVANT_HIER = TODAY - timedelta(days=10)
DANS_3 = TODAY + timedelta(days=3)
DANS_10 = TODAY + timedelta(days=10)


class RetardsSelecteurTachesTests(TestCase):
    """Sélecteur ``retards_projet`` — tâches."""

    def setUp(self):
        self.co = make_company('rtr-ta-co', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-RTR', nom='Projet retards')

    def test_tache_en_retard_fin_passee(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='En retard',
            statut='en_cours', date_fin_prevue=HIER)
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_taches_en_retard'], 1)
        self.assertEqual(result['nb_taches_a_risque'], 0)
        t = result['taches_en_retard'][0]
        self.assertEqual(t['libelle'], 'En retard')
        self.assertEqual(t['retard_jours'], 1)  # aujourd'hui - hier = 1

    def test_tache_en_retard_ancienne(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Vieux retard',
            statut='a_faire', date_fin_prevue=AVANT_HIER)
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_taches_en_retard'], 1)
        t = result['taches_en_retard'][0]
        self.assertEqual(t['retard_jours'], 10)

    def test_tache_a_risque_dans_seuil(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='À risque',
            statut='en_cours', date_fin_prevue=DANS_3)
        result = selectors.retards_projet(self.projet, seuil_jours=7)
        self.assertEqual(result['nb_taches_en_retard'], 0)
        self.assertEqual(result['nb_taches_a_risque'], 1)
        t = result['taches_a_risque'][0]
        self.assertEqual(t['libelle'], 'À risque')
        # retard_jours négatif = encore des jours devant soi
        self.assertEqual(t['retard_jours'], -3)

    def test_tache_dans_les_delais_exclue(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='OK',
            statut='en_cours', date_fin_prevue=DANS_10)
        result = selectors.retards_projet(self.projet, seuil_jours=7)
        self.assertEqual(result['nb_taches_en_retard'], 0)
        self.assertEqual(result['nb_taches_a_risque'], 0)

    def test_tache_terminee_exclue(self):
        # Tâche terminée mais fin passée : NON signalée (terminée = ok).
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Terminée',
            statut='termine', date_fin_prevue=HIER)
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_taches_en_retard'], 0)
        self.assertEqual(result['nb_taches_a_risque'], 0)

    def test_tache_sans_date_fin_exclue(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Sans date',
            statut='en_cours')
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_taches_en_retard'], 0)
        self.assertEqual(result['nb_taches_a_risque'], 0)

    def test_seuil_jours_personnalise(self):
        # Dans 10 jours : dans le seuil=15 mais pas dans le seuil=7.
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Risque large',
            statut='en_cours', date_fin_prevue=DANS_10)
        result_7 = selectors.retards_projet(self.projet, seuil_jours=7)
        result_15 = selectors.retards_projet(self.projet, seuil_jours=15)
        self.assertEqual(result_7['nb_taches_a_risque'], 0)
        self.assertEqual(result_15['nb_taches_a_risque'], 1)

    def test_tache_bloquee_comptee(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Bloquée retard',
            statut='bloque', date_fin_prevue=HIER)
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_taches_en_retard'], 1)

    def test_date_reference_et_seuil_dans_resultat(self):
        result = selectors.retards_projet(self.projet, seuil_jours=5)
        self.assertEqual(result['date_reference'], TODAY.isoformat())
        self.assertEqual(result['seuil_jours'], 5)

    def test_champs_dict_tache(self):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T',
            code_wbs='1', statut='en_cours', avancement_pct=30,
            date_fin_prevue=HIER)
        result = selectors.retards_projet(self.projet)
        t = result['taches_en_retard'][0]
        for champ in ('id', 'libelle', 'code_wbs', 'statut', 'avancement_pct',
                      'date_fin_prevue', 'retard_jours', 'phase', 'parent'):
            self.assertIn(champ, t, f'Champ manquant : {champ}')


class RetardsSelecteurJalonsTests(TestCase):
    """Sélecteur ``retards_projet`` — jalons."""

    def setUp(self):
        self.co = make_company('rtr-jal-co', 'J')
        self.projet = Projet.objects.create(
            company=self.co, code='P-JAL-RTR', nom='Projet jalons retards')

    def test_jalon_en_retard(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Manqué',
            date_prevue=HIER, statut='a_venir')
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_jalons_en_retard'], 1)
        self.assertEqual(result['nb_jalons_a_risque'], 0)
        j = result['jalons_en_retard'][0]
        self.assertEqual(j['libelle'], 'Manqué')
        self.assertEqual(j['retard_jours'], 1)

    def test_jalon_a_risque(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Risqué',
            date_prevue=DANS_3, statut='a_venir')
        result = selectors.retards_projet(self.projet, seuil_jours=7)
        self.assertEqual(result['nb_jalons_en_retard'], 0)
        self.assertEqual(result['nb_jalons_a_risque'], 1)
        j = result['jalons_a_risque'][0]
        self.assertEqual(j['retard_jours'], -3)

    def test_jalon_atteint_exclu(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Atteint',
            date_prevue=HIER, statut='atteint')
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_jalons_en_retard'], 0)

    def test_jalon_manque_en_retard(self):
        # ``statut='manque'`` = raté manuellement ; reste en retard.
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Raté',
            date_prevue=HIER, statut='manque')
        result = selectors.retards_projet(self.projet)
        self.assertEqual(result['nb_jalons_en_retard'], 1)

    def test_jalon_dans_les_delais_exclu(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='OK',
            date_prevue=DANS_10, statut='a_venir')
        result = selectors.retards_projet(self.projet, seuil_jours=7)
        self.assertEqual(result['nb_jalons_en_retard'], 0)
        self.assertEqual(result['nb_jalons_a_risque'], 0)

    def test_champs_dict_jalon(self):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='J',
            date_prevue=HIER, statut='a_venir', facturation_pct='30.00')
        result = selectors.retards_projet(self.projet)
        j = result['jalons_en_retard'][0]
        for champ in ('id', 'libelle', 'statut', 'date_prevue',
                      'retard_jours', 'facturation_pct', 'phase', 'tache'):
            self.assertIn(champ, j, f'Champ manquant : {champ}')


class RetardsApiTests(TestCase):
    """Endpoint ``GET /api/django/gestion-projet/projets/<id>/retards/``."""

    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('rtr-api-a', 'A')
        self.co_b = make_company('rtr-api-b', 'B')
        self.user_a = make_user(self.co_a, 'rtr-api-a')
        self.user_b = make_user(self.co_b, 'rtr-api-b')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-A-RTR', nom='Projet A')
        self.projet_b = Projet.objects.create(
            company=self.co_b, code='P-B-RTR', nom='Projet B')

    def test_retards_projet_vide(self):
        resp = auth(self.user_a).get(f'{self.BASE}{self.projet_a.id}/retards/')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data['nb_taches_en_retard'], 0)
        self.assertEqual(data['nb_taches_a_risque'], 0)
        self.assertEqual(data['nb_jalons_en_retard'], 0)
        self.assertEqual(data['nb_jalons_a_risque'], 0)
        self.assertIn('date_reference', data)
        self.assertIn('seuil_jours', data)

    def test_retards_avec_tache_et_jalon_en_retard(self):
        Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='T retard',
            statut='en_cours', date_fin_prevue=HIER)
        Jalon.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='J retard',
            date_prevue=AVANT_HIER, statut='a_venir')
        resp = auth(self.user_a).get(f'{self.BASE}{self.projet_a.id}/retards/')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data['nb_taches_en_retard'], 1)
        self.assertEqual(data['nb_jalons_en_retard'], 1)

    def test_cross_tenant_404(self):
        # user B ne doit PAS voir le projet de A.
        resp = auth(self.user_b).get(f'{self.BASE}{self.projet_a.id}/retards/')
        self.assertEqual(resp.status_code, 404)

    def test_seuil_jours_param(self):
        # Tâche dans 10 jours : non vue avec seuil=7, vue avec seuil=14.
        Tache.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='T risque large',
            statut='en_cours', date_fin_prevue=DANS_10)
        url = f'{self.BASE}{self.projet_a.id}/retards/?seuil_jours=14'
        resp = auth(self.user_a).get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_taches_a_risque'], 1)
        self.assertEqual(resp.data['seuil_jours'], 14)

        url7 = f'{self.BASE}{self.projet_a.id}/retards/?seuil_jours=7'
        resp7 = auth(self.user_a).get(url7)
        self.assertEqual(resp7.data['nb_taches_a_risque'], 0)

    def test_seuil_jours_invalide_degrade(self):
        # Valeur non-entière → silencieusement remplacée par la valeur défaut.
        resp = auth(self.user_a).get(
            f'{self.BASE}{self.projet_a.id}/retards/?seuil_jours=abc')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('seuil_jours', resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'rtr-normal', role='normal')
        resp = auth(normal).get(f'{self.BASE}{self.projet_a.id}/retards/')
        self.assertEqual(resp.status_code, 403)

    def test_isolation_taches_de_b_non_visibles_par_a(self):
        # Tâche en retard du projet B : user A ne la voit PAS (404 projet).
        Tache.objects.create(
            company=self.co_b, projet=self.projet_b, libelle='T-B',
            statut='en_cours', date_fin_prevue=HIER)
        resp = auth(self.user_a).get(f'{self.BASE}{self.projet_b.id}/retards/')
        self.assertEqual(resp.status_code, 404)
