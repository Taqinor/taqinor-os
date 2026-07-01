"""QK2 — Signaux de maturité d'achat dans le score de qualité des leads.

Couvre :
  - Chaque nouveau signal (ownership, project_timeline, financing_intent,
    roof_age, distributeur) contribue au score avec sa pondération exacte ;
  - Un lead sans ces champs garde exactement son score d'avant (rétro-compat) ;
  - Le score reste borné [0, 100] ;
  - La hot-list : le tri persisté ?ordering=-score reflète la maturité réelle.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.crm.scoring import compute_score


def _make_lead(**kwargs):
    """Lead factice EN MÉMOIRE (non persisté) — même patron que tests_scoring."""
    defaults = {
        'nom': 'Test',
        'date_creation': timezone.now(),
        'facture_hiver': None,
        'canal': None,
        'type_installation': None,
        'gps_lat': None,
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
        # QK1 — signaux de qualification
        'distributeur': None,
        'roof_age': None,
        'ownership': None,
        'project_timeline': None,
        'financing_intent': None,
        'futures_charges': None,
    }
    defaults.update(kwargs)

    class FakeLead:
        pass

    lead = FakeLead()
    for k, v in defaults.items():
        setattr(lead, k, v)
    return lead


class TestReadinessSignals(TestCase):
    """Chaque signal QK2 contribue avec sa pondération exacte."""

    def test_proprietaire_adds_6(self):
        diff = (compute_score(_make_lead(ownership='proprietaire'))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 6)

    def test_locataire_adds_0(self):
        self.assertEqual(compute_score(_make_lead(ownership='locataire')),
                         compute_score(_make_lead()))

    def test_timeline_immediat_adds_8(self):
        diff = (compute_score(_make_lead(project_timeline='immediat'))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 8)

    def test_timeline_gradient(self):
        s_imm = compute_score(_make_lead(project_timeline='immediat'))
        s_3m = compute_score(_make_lead(project_timeline='3_mois'))
        s_6m = compute_score(_make_lead(project_timeline='6_mois'))
        s_tard = compute_score(_make_lead(project_timeline='plus_tard'))
        self.assertGreater(s_imm, s_3m)
        self.assertGreater(s_3m, s_6m)
        self.assertGreater(s_6m, s_tard)

    def test_financing_cash_adds_6(self):
        diff = (compute_score(_make_lead(financing_intent='cash'))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 6)

    def test_financing_credit_beats_indecis(self):
        self.assertGreater(
            compute_score(_make_lead(financing_intent='credit')),
            compute_score(_make_lead(financing_intent='indecis')))

    def test_roof_age_recent_adds_2(self):
        diff = (compute_score(_make_lead(roof_age=5))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 2)

    def test_roof_age_vieillissante_adds_1(self):
        diff = (compute_score(_make_lead(roof_age=20))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 1)

    def test_roof_age_ancienne_adds_0(self):
        self.assertEqual(compute_score(_make_lead(roof_age=40)),
                         compute_score(_make_lead()))

    def test_distributeur_renseigne_adds_2(self):
        diff = (compute_score(_make_lead(distributeur='onee'))
                - compute_score(_make_lead()))
        self.assertEqual(diff, 2)

    def test_lead_sans_signaux_score_inchange(self):
        """Rétro-compat : un objet SANS les attributs QK1 (lead historique /
        FakeLead partiel) score comme avant — getattr défensif."""
        class Bare:
            nom = 'Bare'
            date_creation = timezone.now()
            facture_hiver = None
            canal = None
            type_installation = None
            gps_lat = None
            whatsapp_opt_in = None
            regularisation_8221 = False
            orientation = None
            ombrage = None

        self.assertEqual(compute_score(Bare()), compute_score(_make_lead()))

    def test_full_readiness_lead_hotter(self):
        """Maturité complète = +24 pts par rapport au même lead sans signaux."""
        base = _make_lead(facture_hiver=3000, canal='site_web')
        hot = _make_lead(
            facture_hiver=3000, canal='site_web',
            ownership='proprietaire', project_timeline='immediat',
            financing_intent='cash', roof_age=3, distributeur='lydec')
        self.assertEqual(compute_score(hot) - compute_score(base), 24)

    def test_score_reste_borne_a_100(self):
        from decimal import Decimal
        lead = _make_lead(
            facture_hiver=15000, canal='reference',
            type_installation='industriel', regularisation_8221=True,
            whatsapp_opt_in=True, gps_lat=Decimal('33.5'),
            orientation='sud', ombrage='aucun',
            telephone='0612345678', email='x@x.ma', ville='Casa',
            surface_toiture_m2=Decimal('100'), type_toiture='terrasse_beton',
            whatsapp='0612345678', raccordement='triphase',
            ownership='proprietaire', project_timeline='immediat',
            financing_intent='cash', roof_age=2, distributeur='redal',
        )
        self.assertEqual(compute_score(lead), 100)

    def test_vieux_lead_froid_reste_froid(self):
        old = _make_lead(
            date_creation=timezone.now() - datetime.timedelta(days=200),
            ownership='locataire', project_timeline='plus_tard',
            financing_intent='indecis')
        self.assertLessEqual(compute_score(old), 20)


class TestReadinessHotList(TestCase):
    """La hot-list (?ordering=-score) reflète la maturité d'achat réelle."""

    def setUp(self):
        from authentication.models import Company
        from django.contrib.auth import get_user_model
        from apps.roles.models import Role, RESPONSABLE_PERMISSIONS

        User = get_user_model()
        self.company, _ = Company.objects.get_or_create(
            slug='qk2-co', defaults={'nom': 'QK2 Co'})
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Responsable',
            defaults={'permissions': RESPONSABLE_PERMISSIONS,
                      'est_systeme': True})
        self.user = User.objects.create_user(
            username='qk2_user', password='x',
            role=role, role_legacy='responsable', company=self.company)

    def test_hot_list_ordonnee_par_maturite(self):
        """Deux leads identiques sauf la maturité : le mûr précède le tiède."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.crm.services import recompute_lead_score

        tiede = Lead.objects.create(
            company=self.company, nom='Tiède',
            facture_hiver=2000, canal='site_web')
        chaud = Lead.objects.create(
            company=self.company, nom='Chaud',
            facture_hiver=2000, canal='site_web',
            ownership='proprietaire', project_timeline='immediat',
            financing_intent='cash', roof_age=4, distributeur='onee')
        recompute_lead_score(tiede)
        recompute_lead_score(chaud)

        chaud.refresh_from_db()
        tiede.refresh_from_db()
        self.assertGreater(chaud.score, tiede.score)

        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get('/api/django/crm/leads/?ordering=-score')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results') or resp.data
        ids = [r['id'] for r in results]
        self.assertLess(ids.index(chaud.id), ids.index(tiede.id))

    def test_recompute_persiste_les_signaux(self):
        """recompute_lead_score intègre les signaux QK2 dans le score stocké."""
        from apps.crm.services import recompute_lead_score
        lead = Lead.objects.create(
            company=self.company, nom='Persist',
            ownership='proprietaire', project_timeline='immediat')
        recompute_lead_score(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.score, compute_score(lead))
        self.assertGreaterEqual(lead.score, 14)  # 6 + 8 au moins
