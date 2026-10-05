"""PUB70 — Veille concurrentielle (périmètre HONNÊTE, zéro scraping).

Prouve : la couverture de l'API PAR PAYS (VEIL10 : UE couverte, GB à
confirmer, MA/US/AU non couverts, UK/EL refusés) ; le lien Ad Library WEB
profond ; la cadence par concurrent sur des saisies MANUELLES ; les observations
transformées en matière de brief. Aucun appel réseau — que de la saisie humaine.
"""
import datetime
import json
import pathlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import competitor_intel as ci
from apps.adsengine.models import CompetitorAdObservation, CompetitorPage

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


PAYS_UE_ATTENDUS = (
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
    'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK',
    'SI', 'ES', 'SE',
)


def _contrat(nom):
    return json.loads(
        (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
         / nom).read_text(encoding='utf-8'))


class ApiCoverageFindingTests(TestCase):
    """VEIL10 — la couverture de l'API Ad Library se lit PAR PAYS (les 31 codes
    de la table : 27 UE + GB + MA/US/AU) ; ``UK``/``EL`` sont refusés."""

    def test_27_pays_ue_couverts(self):
        self.assertEqual(len(PAYS_UE_ATTENDUS), 27)
        for code in PAYS_UE_ATTENDUS:
            with self.subTest(pays=code):
                self.assertEqual(ci.statut_couverture(code), 'couvert')
                self.assertTrue(ci.ad_library_api_covers_commercial(code))
                # insensible à la casse
                self.assertTrue(
                    ci.ad_library_api_covers_commercial(code.lower()))

    def test_gb_a_confirmer_donc_pas_couvert(self):
        self.assertEqual(ci.statut_couverture('GB'), 'a_confirmer')
        self.assertFalse(ci.ad_library_api_covers_commercial('GB'))

    def test_ma_us_au_non_couverts(self):
        for code in ('MA', 'US', 'AU'):
            with self.subTest(pays=code):
                self.assertEqual(ci.statut_couverture(code), 'non_couvert')
                self.assertFalse(ci.ad_library_api_covers_commercial(code))

    def test_codes_non_iso_refuses(self):
        for code in ('UK', 'EL', 'uk', 'el'):
            with self.subTest(pays=code):
                self.assertFalse(ci.ad_library_api_covers_commercial(code))
                ligne = ci.couverture_pays(code)
                self.assertEqual(ligne['statut'], 'non_couvert')
                self.assertIn('ISO', ligne['motif_fr'])

    def test_vide_ou_inconnu_jamais_couvert(self):
        for code in (None, '', '  ', 'ZZ', 'XX'):
            with self.subTest(pays=code):
                self.assertFalse(ci.ad_library_api_covers_commercial(code))
        # appel sans argument : plus de défaut « MA » implicite, jamais vrai
        self.assertFalse(ci.ad_library_api_covers_commercial())

    def test_table_couvre_31_codes(self):
        codes = [ligne['pays'] for ligne in ci.couverture_liste()]
        self.assertEqual(len(codes), 31)
        self.assertEqual(set(codes),
                         set(PAYS_UE_ATTENDUS) | {'GB', 'MA', 'US', 'AU'})
        self.assertNotIn('UK', codes)
        self.assertNotIn('EL', codes)

    def test_finding_sans_booleen_global(self):
        finding = ci.AD_LIBRARY_API_FINDING
        self.assertNotIn('covers_commercial', finding)
        self.assertEqual(finding['automation_status'], 'GATED')
        self.assertIn('pays', finding['reason_fr'])
        # l'ancien texte global faux (sans pays) a disparu
        self.assertNotIn('ne renvoie que ' + 'les publicités politiques',
                         finding['reason_fr'])


class DeepLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Veille Co', slug='veille-co')

    def test_deep_link_with_page_id(self):
        page = CompetitorPage.objects.create(
            company=self.company, name='SolaireX', page_id='12345',
            country='MA')
        url = page.ad_library_url()
        self.assertIn('view_all_page_id=12345', url)
        self.assertIn('country=MA', url)
        self.assertIn('facebook.com/ads/library', url)

    def test_deep_link_falls_back_to_name_search(self):
        page = CompetitorPage.objects.create(
            company=self.company, name='Solaire Y', country='MA')
        url = page.ad_library_url()
        self.assertIn('q=Solaire%20Y', url)


class CadenceTimelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cad Co', slug='cad-co')
        self.today = datetime.date(2026, 7, 19)
        self.page = CompetitorPage.objects.create(
            company=self.company, name='Concurrent A')

    def _obs(self, day, hook='hook'):
        return CompetitorAdObservation.objects.create(
            company=self.company, competitor_page=self.page,
            observed_at=day, hook_text=hook, angle='ROI')

    def test_cadence_counts_manual_entries_per_week(self):
        self._obs(datetime.date(2026, 7, 15))
        self._obs(datetime.date(2026, 7, 16))
        self._obs(datetime.date(2026, 7, 8))
        rows = ci.cadence_timeline(self.company, weeks=8, today=self.today)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total'], 3)
        self.assertEqual(len(rows[0]['par_semaine']), 2)  # deux semaines ISO

    def test_brief_material_excludes_empty_observations(self):
        self._obs(datetime.date(2026, 7, 15), hook='Économisez dès le 1er mois')
        CompetitorAdObservation.objects.create(
            company=self.company, competitor_page=self.page,
            observed_at=self.today, hook_text='', angle='')  # vide → ignorée
        material = ci.observations_as_brief_material(self.company)
        self.assertEqual(len(material), 1)
        self.assertIn('Économisez', material[0]['hook_text'])


class VeilleApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Api Co', slug='api-co')
        self.user = make_user(
            self.company, 'veille_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_veille_endpoint_returns_finding(self):
        CompetitorPage.objects.create(company=self.company, name='X')
        resp = auth(self.user).get('/api/django/adsengine/concurrents/veille/')
        self.assertEqual(resp.status_code, 200, resp.data)
        # VEIL10 — la route garde ses trois clés ; le finding ne porte plus de
        # booléen global mais renvoie à la couverture PAR PAYS.
        self.assertEqual(set(resp.data),
                         {'finding', 'cadence', 'brief_material'})
        self.assertNotIn('covers_commercial', resp.data['finding'])
        self.assertEqual(resp.data['finding']['couverture_url'],
                         '/api/django/adsengine/veille/couverture/')

    def test_couverture_par_pays_au_format_du_contrat(self):
        """VEIL10 — ``GET veille/couverture/`` sert la forme EXACTE du contrat
        ``veille_couverture.json`` (VEIL1)."""
        contrat = _contrat('veille_couverture.json')['exemple']
        resp = auth(self.user).get('/api/django/adsengine/veille/couverture/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(contrat))
        self.assertEqual(set(resp.data['acces']), set(contrat['acces']))
        cles_ligne = set(contrat['couverture'][0])
        par_pays = {}
        for ligne in resp.data['couverture']:
            self.assertEqual(set(ligne), cles_ligne)
            par_pays[ligne['pays']] = ligne
        # Les lignes d'exemple du contrat sont servies à l'identique.
        for attendu in contrat['couverture']:
            self.assertEqual(par_pays[attendu['pays']], attendu)
        self.assertEqual(resp.data['acces']['etat'], 'non_configure')
        texte = json.dumps(resp.data)
        self.assertNotIn('spend', texte)
        self.assertNotIn('impressions', texte)

    def test_couverture_exige_adsengine_view(self):
        sans = make_user(self.company, 'veille_sans', [])
        resp = auth(sans).get('/api/django/adsengine/veille/couverture/')
        self.assertEqual(resp.status_code, 403)

    def test_competitor_create_forces_company(self):
        other = Company.objects.create(nom='Other', slug='other-veille')
        resp = auth(self.user).post(
            '/api/django/adsengine/concurrents/',
            {'name': 'NouveauConcurrent', 'company': other.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        page = CompetitorPage.objects.get(id=resp.data['id'])
        self.assertEqual(page.company_id, self.company.id)
