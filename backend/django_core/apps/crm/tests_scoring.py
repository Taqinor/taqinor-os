"""QJ6 — Tests du score de qualité des leads (rule-based scoring + hot-list sort).

Couvre :
  - Calcul du score pour des leads représentatifs (haut / bas / moyen)
  - Signaux individuels : facture_hiver, regularisation_8221, whatsapp_opt_in,
    canal, type_installation, GPS, orientation, ombrage, recency
  - score_label (Chaud / Tiede / Froid)
  - compute_lead_score alias identique à compute_score
  - Isolation multi-tenant : un utilisateur ne voit que les leads de sa société
  - Le champ score est exposé en lecture seule sur le sérialiseur
  - L'endpoint ?ordering=-score trie correctement (sans DB ici : comparaison
    directe sur les valeurs calculées)
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.crm.scoring import compute_score, compute_lead_score, score_label


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_lead(**kwargs):
    """Construit un Lead factice EN MÉMOIRE (non persisté) avec date_creation
    récente. Permet de tester la fonction de score sans DB."""
    defaults = {
        'nom': 'Test',
        'date_creation': timezone.now(),
        'facture_hiver': None,
        'facture_ete': None,
        'ete_differente': False,
        'canal': None,
        'type_installation': None,
        'gps_lat': None,
        'gps_lng': None,
        'whatsapp_opt_in': None,
        'regularisation_8221': False,
        'orientation': None,
        'ombrage': None,
        'telephone': None,
        'email': None,
        'ville': None,
        'surface_toiture_m2': None,
        'type_toiture': None,
        'whatsapp': None,
        'raccordement': None,
        'score': None,
    }
    defaults.update(kwargs)

    class FakeLead:
        pass

    lead = FakeLead()
    for k, v in defaults.items():
        setattr(lead, k, v)
    return lead


# ── Tests de scoring ──────────────────────────────────────────────────────────

class TestComputeScoreSignals(TestCase):
    """Vérifie que chaque signal contribue bien au score."""

    def test_empty_lead_scores_low(self):
        """Un lead entièrement vide doit avoir un score bas (uniquement recency)."""
        lead = _make_lead()
        score = compute_score(lead)
        # Score = 0 complétude + 0 facture + 0 canal + 0 type + recency (<=15)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 15)

    def test_high_bill_increases_score(self):
        lead_low = _make_lead(facture_hiver=200)
        lead_high = _make_lead(facture_hiver=12000)
        self.assertGreater(compute_score(lead_high), compute_score(lead_low))

    def test_bill_10000_gives_max_bill_score(self):
        lead = _make_lead(facture_hiver=10000)
        lead_no_bill = _make_lead(facture_hiver=None)
        diff = compute_score(lead) - compute_score(lead_no_bill)
        # 20 (_W_BILL) + 3 (complétude : facture_hiver renseignée compte 1 champ).
        self.assertEqual(diff, 23)

    def test_regularisation_8221_adds_5_pts(self):
        lead_no = _make_lead(regularisation_8221=False)
        lead_yes = _make_lead(regularisation_8221=True)
        diff = compute_score(lead_yes) - compute_score(lead_no)
        self.assertEqual(diff, 5)  # _W_82_21 = 5

    def test_whatsapp_opt_in_adds_3_pts(self):
        lead_no = _make_lead(whatsapp_opt_in=None)
        lead_yes = _make_lead(whatsapp_opt_in=True)
        diff = compute_score(lead_yes) - compute_score(lead_no)
        self.assertEqual(diff, 3)  # _W_WA_OPT_IN = 3

    def test_gps_present_adds_3_pts(self):
        from decimal import Decimal
        lead_no = _make_lead(gps_lat=None)
        lead_yes = _make_lead(gps_lat=Decimal('33.589886'))
        diff = compute_score(lead_yes) - compute_score(lead_no)
        # GPS adds _W_GPS = 3 to score
        self.assertEqual(diff, 3)

    def test_good_orientation_adds_2_pts(self):
        lead_bad = _make_lead(orientation='est')
        lead_good = _make_lead(orientation='sud')
        diff = compute_score(lead_good) - compute_score(lead_bad)
        self.assertEqual(diff, 2)  # _W_ORIENTATION = 2

    def test_no_ombrage_adds_2_pts(self):
        lead_bad = _make_lead(ombrage='important')
        lead_good = _make_lead(ombrage='aucun')
        diff = compute_score(lead_good) - compute_score(lead_bad)
        self.assertEqual(diff, 2)  # _W_OMBRAGE = 2

    def test_reference_canal_highest(self):
        lead_ref = _make_lead(canal='reference')
        lead_meta = _make_lead(canal='meta_ads')
        self.assertGreater(compute_score(lead_ref), compute_score(lead_meta))

    def test_industriel_type_highest(self):
        lead_ind = _make_lead(type_installation='industriel')
        lead_res = _make_lead(type_installation='residentiel')
        self.assertGreater(compute_score(lead_ind), compute_score(lead_res))

    def test_recency_today_beats_old(self):
        lead_new = _make_lead(date_creation=timezone.now())
        old_date = timezone.now() - datetime.timedelta(days=200)
        lead_old = _make_lead(date_creation=old_date)
        self.assertGreater(compute_score(lead_new), compute_score(lead_old))

    def test_score_capped_at_100(self):
        """Un lead parfait ne dépasse pas 100."""
        from decimal import Decimal
        lead = _make_lead(
            facture_hiver=15000,
            canal='reference',
            type_installation='industriel',
            regularisation_8221=True,
            whatsapp_opt_in=True,
            gps_lat=Decimal('33.5'),
            orientation='sud',
            ombrage='aucun',
            telephone='0612345678',
            email='test@test.ma',
            ville='Casablanca',
            surface_toiture_m2=Decimal('100'),
            type_toiture='terrasse_beton',
            whatsapp='0612345678',
            raccordement='triphase',
            date_creation=timezone.now(),
        )
        self.assertLessEqual(compute_score(lead), 100)

    def test_score_non_negative(self):
        """Le score ne peut jamais être négatif."""
        lead = _make_lead()
        self.assertGreaterEqual(compute_score(lead), 0)

    def test_compute_lead_score_alias(self):
        """compute_lead_score est un alias identique à compute_score."""
        lead = _make_lead(facture_hiver=3000, canal='reference')
        self.assertEqual(compute_score(lead), compute_lead_score(lead))

    def test_representative_high_lead(self):
        """Lead chaud typique : grosse facture, référence, GPS, 82-21."""
        from decimal import Decimal
        lead = _make_lead(
            facture_hiver=8000,
            canal='reference',
            type_installation='commercial',
            regularisation_8221=True,
            whatsapp_opt_in=True,
            gps_lat=Decimal('33.5'),
            orientation='sud',
            ombrage='aucun',
            date_creation=timezone.now(),
        )
        score = compute_score(lead)
        self.assertGreaterEqual(score, 60)
        self.assertEqual(score_label(score), 'Chaud')

    def test_representative_low_lead(self):
        """Lead froid typique : pas de facture, canal faible, vieux."""
        old_date = timezone.now() - datetime.timedelta(days=180)
        lead = _make_lead(
            canal='meta_ads',
            date_creation=old_date,
        )
        score = compute_score(lead)
        self.assertLessEqual(score, 40)
        self.assertEqual(score_label(score), 'Froid')


class TestScoreLabel(TestCase):
    """Vérifie les seuils du libellé de score."""

    def test_chaud_at_70(self):
        self.assertEqual(score_label(70), 'Chaud')

    def test_chaud_at_100(self):
        self.assertEqual(score_label(100), 'Chaud')

    def test_tiede_at_45(self):
        self.assertEqual(score_label(45), 'Tiède')

    def test_tiede_at_69(self):
        self.assertEqual(score_label(69), 'Tiède')

    def test_froid_at_0(self):
        self.assertEqual(score_label(0), 'Froid')

    def test_froid_at_44(self):
        self.assertEqual(score_label(44), 'Froid')


# ── Tests multi-tenant ────────────────────────────────────────────────────────

class TestScoringMultiTenant(TestCase):
    """Isolation multi-tenant : un utilisateur ne score/voit que ses leads."""

    def setUp(self):
        from authentication.models import Company
        from django.contrib.auth import get_user_model
        from apps.roles.models import Role, RESPONSABLE_PERMISSIONS

        User = get_user_model()

        self.company_a, _ = Company.objects.get_or_create(
            slug='score-co-a', defaults={'nom': 'Score Co A'})
        self.company_b, _ = Company.objects.get_or_create(
            slug='score-co-b', defaults={'nom': 'Score Co B'})

        role_a, _ = Role.objects.get_or_create(
            company=self.company_a, nom='Responsable',
            defaults={'permissions': RESPONSABLE_PERMISSIONS, 'est_systeme': True})
        role_b, _ = Role.objects.get_or_create(
            company=self.company_b, nom='Responsable',
            defaults={'permissions': RESPONSABLE_PERMISSIONS, 'est_systeme': True})

        self.user_a = User.objects.create_user(
            username='score_user_a', password='x',
            role=role_a, role_legacy='responsable', company=self.company_a)
        self.user_b = User.objects.create_user(
            username='score_user_b', password='x',
            role=role_b, role_legacy='responsable', company=self.company_b)

        self.lead_a = Lead.objects.create(
            company=self.company_a, nom='Alpha',
            facture_hiver=5000, canal='reference')
        self.lead_b = Lead.objects.create(
            company=self.company_b, nom='Beta',
            facture_hiver=500, canal='meta_ads')

    def test_scores_are_company_independent(self):
        """Le score d'un lead de la société A ne dépend pas de ceux de la société B."""
        score_a = compute_score(self.lead_a)
        score_b = compute_score(self.lead_b)
        # Le lead A doit scorer plus haut (grosse facture + référence)
        self.assertGreater(score_a, score_b)

    def test_api_only_returns_own_company_leads(self):
        """L'endpoint /crm/leads/ ne retourne que les leads de la société courante."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_a)}')
        resp = api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        ids = [item['id'] for item in (resp.data.get('results') or resp.data)]
        self.assertIn(self.lead_a.id, ids)
        self.assertNotIn(self.lead_b.id, ids)

    def test_score_field_present_in_api_response(self):
        """Le champ score est exposé en lecture seule dans l'API."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_a)}')
        resp = api.get(f'/api/django/crm/leads/{self.lead_a.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('score', resp.data)
        self.assertIsInstance(resp.data['score'], int)

    def test_score_not_writable_from_request(self):
        """Le score ne peut pas être forcé depuis le corps de la requête."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_a)}')
        resp = api.patch(
            f'/api/django/crm/leads/{self.lead_a.id}/',
            {'score': 99}, format='json')
        self.assertEqual(resp.status_code, 200)
        # Le score retourné doit être le score calculé, pas 99 forcé
        actual = resp.data['score']
        expected = compute_score(self.lead_a)
        # La réponse reflète le score calculé à la volée
        self.assertEqual(actual, expected)


# ── VX221 — décomposition « pourquoi ce score » ──────────────────────────────

class TestScoreReasons(TestCase):
    """VX221 — ``score_reasons`` expose les composantes NON NULLES du score,
    triées par points décroissants, sans recalcul divergent de compute_score."""

    def test_reasons_only_non_zero_sorted_desc(self):
        from apps.crm.scoring import score_reasons
        lead = _make_lead(
            facture_hiver=10000,      # facture → 20
            canal='reference',        # canal → 15
            type_installation='industriel',  # type → 8
        )
        reasons = score_reasons(lead)
        # Aucune composante à 0 n'est exposée.
        self.assertTrue(all(r['points'] > 0 for r in reasons))
        # Triée par points décroissants.
        pts = [r['points'] for r in reasons]
        self.assertEqual(pts, sorted(pts, reverse=True))
        # Chaque entrée porte facteur + label + points.
        for r in reasons:
            self.assertIn('facteur', r)
            self.assertIn('label', r)
            self.assertIn('points', r)
        # Le facteur « facture » (20) domine.
        self.assertEqual(reasons[0]['facteur'], 'facture')
        self.assertEqual(reasons[0]['points'], 20)

    def test_reasons_are_pure_exposition_of_components(self):
        """La somme des points bornée à 100 == compute_score : aucune
        pondération différente n'est introduite."""
        from apps.crm.scoring import score_reasons
        lead = _make_lead(facture_hiver=3000, canal='site_web')
        total = sum(r['points'] for r in score_reasons(lead))
        self.assertEqual(min(total, 100), compute_score(lead))

    def test_empty_lead_has_some_reasons_or_none(self):
        """Un lead quasi vide n'expose que ses facteurs positifs (recency)."""
        from apps.crm.scoring import score_reasons
        lead = _make_lead()  # date_creation récente → recency > 0
        reasons = score_reasons(lead)
        facteurs = {r['facteur'] for r in reasons}
        self.assertIn('recency', facteurs)


class TestScoreReasonsApi(TestScoringMultiTenant):
    """VX221 — ``score_reasons`` est exposé, company-scopé, en lecture seule."""

    def test_score_reasons_present_and_scoped(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_a)}')
        resp = api.get(f'/api/django/crm/leads/{self.lead_a.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('score_reasons', resp.data)
        reasons = resp.data['score_reasons']
        self.assertIsInstance(reasons, list)
        # lead_a : grosse facture + référence → au moins ces 2 facteurs.
        facteurs = {r['facteur'] for r in reasons}
        self.assertIn('facture', facteurs)
        self.assertIn('canal', facteurs)
        # Un utilisateur d'une autre société ne peut pas lire ce lead.
        api_b = APIClient()
        api_b.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_b)}')
        resp_b = api_b.get(f'/api/django/crm/leads/{self.lead_a.id}/')
        self.assertEqual(resp_b.status_code, 404)

    def test_ordering_by_score_desc(self):
        """?ordering=-score trie les leads de la plus haute à la plus basse note."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        # Crée un deuxième lead faible dans la société A
        lead_low = Lead.objects.create(
            company=self.company_a, nom='Low',
            facture_hiver=100, canal='meta_ads')
        # Recompute stored scores via the service
        from apps.crm.services import recompute_lead_score
        recompute_lead_score(self.lead_a)
        recompute_lead_score(lead_low)

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user_a)}')
        resp = api.get('/api/django/crm/leads/?ordering=-score')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results') or resp.data
        ids = [r['id'] for r in results]
        # lead_a (score elevé) doit précéder lead_low
        self.assertLess(ids.index(self.lead_a.id), ids.index(lead_low.id))

    def test_recompute_lead_score_persists(self):
        """recompute_lead_score() écrit le score sur le champ score du lead."""
        from apps.crm.services import recompute_lead_score
        recompute_lead_score(self.lead_a)
        self.lead_a.refresh_from_db()
        expected = compute_score(self.lead_a)
        self.assertEqual(self.lead_a.score, expected)
