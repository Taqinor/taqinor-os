"""ODY10 — badges vivants du Menu d'accueil, dérivés du KPI fédéré ARC40.

Le contrat : au plus UN badge par app, DÉRIVÉ des tuiles que
``reports/kpi-federes/`` collecte déjà (aucune requête supplémentaire, aucune
ré-agrégation à la main, aucun nouveau modèle ni migration), ``?vue=badges``
pour une charge utile légère, et un cloisonnement société ABSOLU : la société A
ne voit jamais les compteurs de B.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ModuleToggle

from apps.reporting.reports import (
    _badges_depuis_tuiles, _cle_app_depuis_provider, _valeur_de_badge,
)

User = get_user_model()

URL = '/api/django/reporting/reports/kpi-federes/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BadgeDerivationTests(TestCase):
    """Fonctions pures de dérivation — aucune base, aucun réseau."""

    def test_cle_app_depuis_provider(self):
        self.assertEqual(
            _cle_app_depuis_provider('apps.rh.selectors.kpi_x'), 'rh')
        self.assertEqual(
            _cle_app_depuis_provider('apps.gestion_projet.selectors.kpi_y'),
            'gestion_projet')
        # Formes hors convention : pas de badge, jamais une clé inventée.
        self.assertIsNone(_cle_app_depuis_provider('crm_sales_report'))
        self.assertIsNone(_cle_app_depuis_provider('core.platform.x'))
        self.assertIsNone(_cle_app_depuis_provider(''))

    def test_valeur_de_badge_ne_garde_que_les_compteurs_positifs(self):
        self.assertEqual(_valeur_de_badge(3), 3)
        self.assertEqual(_valeur_de_badge(2.5), 2.5)
        # Un « 0 » n'est pas une information sur une grille d'accueil.
        self.assertIsNone(_valeur_de_badge(0))
        self.assertIsNone(_valeur_de_badge(-1))
        # Une valeur textuelle n'est pas un compteur.
        self.assertIsNone(_valeur_de_badge('Idée A'))
        self.assertIsNone(_valeur_de_badge(None))
        # bool est un int en Python : True ne doit PAS devenir un badge « 1 ».
        self.assertIsNone(_valeur_de_badge(True))

    def test_un_seul_badge_par_app_le_premier_compteur_positif(self):
        tuiles = [
            {'id': 'rh_a', 'label': 'A', 'valeur': 0,
             'provider': 'apps.rh.selectors.k'},
            {'id': 'rh_b', 'label': 'B', 'valeur': 4, 'unite': 'employés',
             'provider': 'apps.rh.selectors.k'},
            {'id': 'rh_c', 'label': 'C', 'valeur': 9,
             'provider': 'apps.rh.selectors.k'},
            {'id': 'compta_a', 'label': 'D', 'valeur': 2,
             'provider': 'apps.compta.selectors.k'},
        ]
        badges = _badges_depuis_tuiles(tuiles)
        self.assertEqual([b['app'] for b in badges], ['rh', 'compta'])
        # La tuile à 0 est sautée, la SUIVANTE positive devient le badge.
        self.assertEqual(badges[0]['valeur'], 4)
        self.assertEqual(badges[0]['tuile'], 'rh_b')
        self.assertEqual(badges[0]['unite'], 'employés')

    def test_app_sans_compteur_positif_na_pas_de_badge(self):
        tuiles = [
            {'id': 'x', 'label': 'X', 'valeur': 0,
             'provider': 'apps.qhse.selectors.k'},
            {'id': 'y', 'label': 'Y', 'valeur': 'texte',
             'provider': 'apps.qhse.selectors.k'},
        ]
        self.assertEqual(_badges_depuis_tuiles(tuiles), [])


class BadgeEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ody10-a', defaults={'nom': 'ODY10 A'})[0]
        self.other = Company.objects.create(slug='ody10-b', nom='ODY10 B')
        self.user = User.objects.create_user(
            username='ody10_user', password='x', role_legacy='responsable',
            company=self.company)
        self.autre_user = User.objects.create_user(
            username='ody10_autre', password='x', role_legacy='responsable',
            company=self.other)
        self.api = auth(self.user)

    def _seed_projets(self, company, en_cours):
        from apps.gestion_projet.models import Projet
        for i in range(en_cours):
            Projet.objects.create(
                company=company, code=f'ODY10-{company.slug}-{i}',
                nom=f'Projet {i}', statut=Projet.Statut.EN_COURS)

    def _seed_compta(self, company):
        from apps.compta.models import Effet
        today = date.today()
        Effet.objects.create(
            company=company, sens=Effet.Sens.RECEVOIR,
            montant=Decimal('1000'), date_emission=today,
            date_echeance=today + timedelta(days=15))

    def _badges(self, resp):
        return {b['app']: b for b in resp.data['badges']}

    def test_la_reponse_complete_porte_tuiles_ET_badges(self):
        self._seed_projets(self.company, 2)
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        # Forme historique préservée (aucune régression ARC40).
        self.assertIn('tuiles', resp.data)
        self.assertEqual(resp.data['count'], len(resp.data['tuiles']))
        badges = self._badges(resp)
        self.assertIn('gestion_projet', badges)
        self.assertEqual(badges['gestion_projet']['valeur'], 2)

    def test_vue_badges_renvoie_les_badges_SEULS(self):
        self._seed_projets(self.company, 3)
        resp = self.api.get(URL, {'vue': 'badges'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('tuiles', resp.data)
        self.assertEqual(resp.data['count'], len(resp.data['badges']))
        self.assertEqual(self._badges(resp)['gestion_projet']['valeur'], 3)

    def test_cloisonnement_societe_les_compteurs_de_A_sont_invisibles_de_B(self):
        """Multi-tenant strict : le badge de A ne fuit jamais chez B."""
        self._seed_projets(self.company, 5)
        # B n'a AUCUN projet : elle ne doit voir aucun badge projets.
        resp_b = auth(self.autre_user).get(URL, {'vue': 'badges'})
        self.assertNotIn('gestion_projet', self._badges(resp_b))
        # Et A voit bien les siens, à leur valeur exacte.
        resp_a = self.api.get(URL, {'vue': 'badges'})
        self.assertEqual(self._badges(resp_a)['gestion_projet']['valeur'], 5)
        # Une donnée de B n'augmente pas le badge de A.
        self._seed_projets(self.other, 4)
        resp_a2 = self.api.get(URL, {'vue': 'badges'})
        self.assertEqual(self._badges(resp_a2)['gestion_projet']['valeur'], 5)

    def test_module_desactive_na_pas_de_badge(self):
        self._seed_projets(self.company, 2)
        self._seed_compta(self.company)
        ModuleToggle.objects.create(
            company=self.company, module='gestion_projet', actif=False)
        badges = self._badges(self.api.get(URL, {'vue': 'badges'}))
        self.assertNotIn('gestion_projet', badges)
        # compta, restée active, garde le sien.
        self.assertIn('compta', badges)

    def test_superuser_sans_societe_recoit_une_liste_vide(self):
        su = User.objects.create_superuser(
            username='ody10_su', password='x', email='ody10su@example.com')
        resp = auth(su).get(URL, {'vue': 'badges'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['badges'], [])
