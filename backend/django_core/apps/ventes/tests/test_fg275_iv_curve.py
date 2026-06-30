"""FG275 — tests de la capture de courbe I-V par string.

Couvre : calcul pur de l'écart Pmax & du verdict défaut, dérivation serveur
(écart/défaut jamais du corps), répercussion sur le résultat de la recette
parente, isolation société, filtre ?defaut=.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg275_iv_curve -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, CommissioningTest, IVCurveCapture
from apps.ventes.commissioning import evaluate_iv_curve
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_recette(company, user, ref='DEV-FG275-1', **kw):
    client = Client.objects.create(
        company=company, nom='Fassi', prenom='Reda',
        email=f'r_{ref}@example.com', telephone='+212677777777')
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='accepte', created_by=user)
    return CommissioningTest.objects.create(
        company=company, devis=devis, isolement_ok=True, polarite_ok=True,
        continuite_terre_ok=True, controle_onduleur_ok=True, **kw)


class EvaluateIvCurveTest(SimpleTestCase):
    def test_within_tolerance_no_defect(self):
        ecart, defaut = evaluate_iv_curve(
            pmax_mesure_w=4900, pmax_attendu_w=5000, tolerance_pct=8)
        self.assertAlmostEqual(ecart, -2.0, places=1)
        self.assertFalse(defaut)

    def test_below_tolerance_is_defect(self):
        ecart, defaut = evaluate_iv_curve(
            pmax_mesure_w=4300, pmax_attendu_w=5000, tolerance_pct=8)
        self.assertAlmostEqual(ecart, -14.0, places=1)
        self.assertTrue(defaut)

    def test_overperformance_not_defect(self):
        ecart, defaut = evaluate_iv_curve(
            pmax_mesure_w=5200, pmax_attendu_w=5000, tolerance_pct=8)
        self.assertGreater(ecart, 0)
        self.assertFalse(defaut)

    def test_missing_data_returns_none(self):
        self.assertEqual(evaluate_iv_curve(pmax_mesure_w=None,
                                           pmax_attendu_w=5000),
                         (None, False))
        self.assertEqual(evaluate_iv_curve(pmax_mesure_w=5000,
                                           pmax_attendu_w=0),
                         (None, False))


class IVCurveApiTest(TestCase):
    def setUp(self):
        self.company = make_company('iv-acme')
        self.other = make_company('iv-other')
        self.user = make_user(self.company, 'iv_user')
        self.recette = make_recette(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/courbes-iv/'

    def test_defect_derived_and_cascades_to_recette(self):
        # Recette toute-conforme au départ.
        self.recette.refresh_from_db()
        # Capture sous-performante → défaut dérivé serveur → recette
        # devient non_conforme.
        resp = self.api.post(self.url, {
            'recette': self.recette.id, 'string_label': 'S1',
            'pmax_mesure_w': '4200.00', 'pmax_attendu_w': '5000.00',
            'defaut_detecte': False,  # tentative ignorée
            'ecart_pmax_pct': '0',  # tentative ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        iv = IVCurveCapture.objects.get(id=resp.data['id'])
        self.assertTrue(iv.defaut_detecte)
        self.assertLess(float(iv.ecart_pmax_pct), -8)
        self.assertEqual(iv.company_id, self.company.id)
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'non_conforme')

    def test_healthy_string_keeps_recette_conforme(self):
        self.api.post(self.url, {
            'recette': self.recette.id, 'string_label': 'S2',
            'pmax_mesure_w': '4950.00', 'pmax_attendu_w': '5000.00',
        }, format='json')
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'conforme')

    def test_recette_of_other_company_refused(self):
        other_user = make_user(self.other, 'iv_o')
        other_recette = make_recette(self.other, other_user,
                                     ref='DEV-OTHER-IV')
        resp = self.api.post(self.url, {
            'recette': other_recette.id, 'string_label': 'X',
            'pmax_mesure_w': '4000', 'pmax_attendu_w': '5000',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_filter_defaut(self):
        IVCurveCapture.objects.create(
            company=self.company, recette=self.recette, string_label='ok',
            ecart_pmax_pct=-1, defaut_detecte=False)
        IVCurveCapture.objects.create(
            company=self.company, recette=self.recette, string_label='ko',
            ecart_pmax_pct=-20, defaut_detecte=True)
        resp = self.api.get(self.url, {'defaut': '1'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertTrue(all(r['defaut_detecte'] for r in rows))
        self.assertEqual(len(rows), 1)

    def test_delete_recomputes_recette(self):
        # Une capture défectueuse rend la recette non_conforme.
        resp = self.api.post(self.url, {
            'recette': self.recette.id, 'string_label': 'bad',
            'pmax_mesure_w': '4000', 'pmax_attendu_w': '5000',
        }, format='json')
        iv_id = resp.data['id']
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'non_conforme')
        # Suppression → plus de défaut → recette redevient conforme.
        self.api.delete(f'{self.url}{iv_id}/')
        self.recette.refresh_from_db()
        self.assertEqual(self.recette.resultat, 'conforme')
