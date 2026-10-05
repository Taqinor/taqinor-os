"""ACAL229 — chaque ``@action`` du calepinage se RÉSOUT vers elle-même.

Constat C-ACAL-128 (C13, S2). ``url_path='export.csv'`` (non échappé) est
inséré TEL QUEL dans la regex du routeur DRF : le point accepte n'importe quel
caractère, donc ``export.csv/`` capturait ``export-csv/`` — l'onglet Séries et
le tapis horaire recevaient le tableur modules/chaînes au lieu de la série de
simulation. Les 20 ``url_path`` pointés du module échappent désormais leur
point (``r'export\\.csv'``) ; le chemin servi, l'``url_name`` et ``reverse()``
sont inchangés.

Ce fichier résout les VRAIES URL (``django.urls.resolve``), il ne compare pas
des chaînes.

Run :
    python manage.py test apps.calepinage.tests.test_acal_routes_resolues -v2
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'


def _actions():
    from apps.calepinage import urls  # noqa: F401 — exécute les greffes
    from apps.calepinage.views.calepinages import CalepinageViewSet

    return CalepinageViewSet.get_extra_actions()


def _chemin(action, pk='1'):
    """L'URL servie : le point échappé de la regex est un point littéral."""
    segment = action.url_path.replace('\\.', '.')
    if action.detail:
        return f'{BASE}{pk}/{segment}/'
    return f'{BASE}{segment}/'


class RoutesResoluesTest(SimpleTestCase):
    def test_chaque_action_se_resout_vers_elle_meme(self):
        verifiees = 0
        for action in _actions():
            if '(?P' in action.url_path:   # sous-route à paramètre : hors champ
                continue
            chemin = _chemin(action)
            with self.subTest(action=action.__name__, chemin=chemin):
                cible = resolve(chemin).func
                self.assertIn(
                    action.__name__, set(getattr(cible, 'actions', {})
                                         .values()),
                    f"« {chemin} » est servi par {getattr(cible, 'actions', None)}"
                    f" et non par l'action « {action.__name__} » : un "
                    "url_path non échappé en capture un autre (ACAL229).")
            verifiees += 1
        self.assertGreater(verifiees, 20)

    def test_les_url_path_pointes_sont_echappes(self):
        for action in _actions():
            sans_groupe = action.url_path.split('(?P')[0]
            with self.subTest(action=action.__name__):
                self.assertNotRegex(
                    sans_groupe.replace('\\.', ''), r'\.',
                    f"url_path « {action.url_path} » : un point NON échappé "
                    "accepte n'importe quel caractère dans la regex du "
                    "routeur (ACAL229) — écrire r'nom\\.ext'.")

    def test_reverse_inchange(self):
        self.assertEqual(reverse('calepinage-export-csv', args=['1']),
                         f'{BASE}1/export.csv/')
        self.assertEqual(
            reverse('calepinage-export-csv-simulation', args=['1']),
            f'{BASE}1/export-csv/')


class ExportsHttpTest(TestCase):
    """Le client HTTP RÉEL atteint chacun des deux exports CSV."""

    def setUp(self):
        societe = Company.objects.create(nom='ACAL229', slug='acal229')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='acal229', password='x',
                                        company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 229')
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Série 229',
            resultat={'serie_horaire': {'points': [
                {'annee': 2020, 'mois': 1, 'jour': 1, 'heure': h,
                 'p_w': 1000.0 * h, 'gi_w_m2': 100.0, 't2m_c': 15.0}
                for h in range(3)]}})

    def test_export_csv_http_sert_la_serie_horaire(self):
        reponse = self.api.get(
            f'{BASE}{self.calepinage.pk}/export-csv/', {'quoi': 'horaire'})
        self.assertEqual(reponse.status_code, 200,
                         getattr(reponse, 'data', reponse.content[:200]))
        texte = reponse.content.decode('utf-8-sig')
        lignes = [ligne for ligne in texte.splitlines() if ligne]
        self.assertTrue(
            any(ligne.startswith('annee;mois;jour;heure') for ligne in lignes),
            f"export-csv/ ne sert pas la série horaire : {lignes[:8]}")
        self.assertIn('calepinage-%s-horaire.csv' % self.calepinage.pk,
                      reponse['Content-Disposition'])

    def test_export_dot_csv_sert_toujours_le_tableur(self):
        chemin = f'{BASE}{self.calepinage.pk}/export.csv/'
        self.assertEqual(resolve(chemin).func.actions.get('get'),
                         'export_csv')
        reponse = self.api.get(chemin, {'feuille': 'Chaines'})
        # Le tableur (CAL179) — jamais la série de simulation : ni son
        # en-tête de provenance, ni son refus (« exports_disponibles »).
        if reponse.status_code == 200:
            texte = reponse.content.decode('utf-8-sig', errors='replace')
            self.assertNotIn('annee;mois;jour;heure', texte)
            self.assertNotIn('Module Calepinage', texte)
        else:
            self.assertNotIn('exports_disponibles', reponse.data)
