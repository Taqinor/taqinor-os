"""PUB28 — Taxonomie junk-lead (MotifPerte.est_junk) + taux par ad.

Couvre :
  - modèle : ``MotifPerte.est_junk`` additif, défaut False (motifs existants
    inchangés) ;
  - ``seed_motifs_perte`` : idempotent, additive-only, ne touche jamais une
    société ayant déjà des motifs (même patron que ``seed_canaux``) ;
  - amorçage paresseux au premier ``GET /motifs-perte/`` ;
  - ``attribution_lead_rows`` : ``junk`` distinct de ``qualified`` (un lead
    perdu avec un motif junk n'est ni qualifié ni « juste » non qualifié) ;
  - ``apps.adsengine.attribution.variant_attribution`` : ``junk``/``junk_rate``
    par ad ;
  - ``apps.adsengine.reporting.variant_table`` : propage junk/junk_rate.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, MotifPerte
from apps.crm.selectors import attribution_lead_rows
from apps.crm.views import _DEFAULT_MOTIFS_PERTE, seed_motifs_perte

User = get_user_model()


def make_company(slug, nom=None):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom or slug})
    return c


def make_api(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class MotifPerteModelTests(TestCase):
    def test_est_junk_defaults_false(self):
        co = make_company('pub28-model')
        motif = MotifPerte.objects.create(company=co, nom='Prix trop élevé')
        self.assertFalse(motif.est_junk)


class SeedMotifsPerteTests(TestCase):
    def test_seeds_standard_motifs_with_correct_junk_flags(self):
        co = make_company('pub28-seed')
        seed_motifs_perte(co)
        noms = {m.nom: m.est_junk for m in MotifPerte.objects.filter(company=co)}
        self.assertEqual(len(noms), len(_DEFAULT_MOTIFS_PERTE))
        self.assertTrue(noms['Numéro invalide'])
        self.assertTrue(noms['Spam/bot'])
        self.assertTrue(noms['Hors zone'])
        self.assertTrue(noms['Jamais répondu'])
        self.assertFalse(noms['Prix'])
        self.assertFalse(noms['Concurrent'])
        self.assertFalse(noms['Reporté'])

    def test_idempotent_rerun_never_duplicates(self):
        co = make_company('pub28-seed-idem')
        seed_motifs_perte(co)
        seed_motifs_perte(co)
        self.assertEqual(
            MotifPerte.objects.filter(company=co).count(),
            len(_DEFAULT_MOTIFS_PERTE))

    def test_never_touches_company_with_existing_motifs(self):
        """Additive-only : une société ayant déjà UN motif personnalisé
        n'est jamais complétée par le seed (même garantie que seed_canaux)."""
        co = make_company('pub28-seed-existing')
        MotifPerte.objects.create(company=co, nom='Motif perso fondateur')
        seed_motifs_perte(co)
        self.assertEqual(MotifPerte.objects.filter(company=co).count(), 1)

    def test_seed_is_per_company(self):
        co1 = make_company('pub28-seed-c1')
        co2 = make_company('pub28-seed-c2')
        seed_motifs_perte(co1)
        self.assertEqual(MotifPerte.objects.filter(company=co2).count(), 0)


class MotifPerteListSeedsLazilyTests(TestCase):
    def test_first_list_call_seeds_motifs(self):
        co = make_company('pub28-lazy')
        user = User.objects.create_user(
            username='pub28-lazy-user', password='x', company=co)
        api = make_api(user)
        self.assertEqual(MotifPerte.objects.filter(company=co).count(), 0)
        resp = api.get('/api/django/crm/motifs-perte/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            MotifPerte.objects.filter(company=co).count(),
            len(_DEFAULT_MOTIFS_PERTE))
        # est_junk est bien exposé par le serializer.
        payload = resp.json()
        rows = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        junk_names = {r['nom'] for r in rows if r['est_junk']}
        self.assertIn('Numéro invalide', junk_names)


class AttributionLeadRowsJunkTests(TestCase):
    def setUp(self):
        self.co = make_company('pub28-attr')
        MotifPerte.objects.create(
            company=self.co, nom='Numéro invalide', est_junk=True)
        MotifPerte.objects.create(company=self.co, nom='Prix', est_junk=False)

    def test_junk_lead_flagged_and_never_qualified(self):
        Lead.objects.create(
            company=self.co, nom='Junk', perdu=True,
            motif_perte='Numéro invalide', meta_ad_id='ad_1')
        rows = attribution_lead_rows(self.co)
        row = rows[0]
        self.assertTrue(row['junk'])
        self.assertFalse(row['qualified'])

    def test_real_loss_motif_not_junk(self):
        Lead.objects.create(
            company=self.co, nom='Perdu réel', perdu=True,
            motif_perte='Prix', meta_ad_id='ad_1')
        rows = attribution_lead_rows(self.co)
        row = rows[0]
        self.assertFalse(row['junk'])
        self.assertFalse(row['qualified'])

    def test_case_insensitive_motif_match(self):
        Lead.objects.create(
            company=self.co, nom='Junk casse', perdu=True,
            motif_perte='  numéro INVALIDE  ', meta_ad_id='ad_1')
        rows = attribution_lead_rows(self.co)
        self.assertTrue(rows[0]['junk'])

    def test_non_perdu_lead_never_junk_even_with_junk_motif_text(self):
        Lead.objects.create(
            company=self.co, nom='Vivant', perdu=False,
            motif_perte='Numéro invalide', meta_ad_id='ad_1')
        rows = attribution_lead_rows(self.co)
        self.assertFalse(rows[0]['junk'])


class VariantAttributionJunkRateTests(TestCase):
    def test_junk_rate_per_ad(self):
        from apps.adsengine import attribution
        from apps.adsengine.models import (
            AdCampaignMirror, AdSetMirror, AdMirror,
        )

        co = make_company('pub28-variant')
        MotifPerte.objects.create(
            company=co, nom='Numéro invalide', est_junk=True)
        camp = AdCampaignMirror.objects.create(
            company=co, meta_id='cmp_j', name='Campagne', status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=co, meta_id='ast_j', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=co, meta_id='ad_j', name='Ad Junk', adset=adset)

        # 4 leads : 1 junk, 1 qualifié (SIGNED), 2 non qualifiés (NEW).
        from apps.crm.stages import NEW, SIGNED
        Lead.objects.create(
            company=co, nom='J1', meta_ad_id='ad_j', perdu=True,
            motif_perte='Numéro invalide', stage=NEW)
        Lead.objects.create(
            company=co, nom='Q1', meta_ad_id='ad_j', stage=SIGNED)
        Lead.objects.create(company=co, nom='N1', meta_ad_id='ad_j', stage=NEW)
        Lead.objects.create(company=co, nom='N2', meta_ad_id='ad_j', stage=NEW)

        res = attribution.variant_attribution(co)
        v = res['variants'][0]
        self.assertEqual(v['leads'], 4)
        self.assertEqual(v['junk'], 1)
        self.assertEqual(v['junk_rate'], 0.25)

    def test_junk_rate_none_when_no_leads(self):
        from apps.adsengine import attribution
        from apps.adsengine.models import (
            AdCampaignMirror, AdSetMirror, AdMirror,
        )

        co = make_company('pub28-variant-empty')
        camp = AdCampaignMirror.objects.create(
            company=co, meta_id='cmp_e', name='Campagne', status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=co, meta_id='ast_e', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=co, meta_id='ad_e', name='Ad Vide', adset=adset)
        res = attribution.variant_attribution(co)
        v = res['variants'][0]
        self.assertEqual(v['junk'], 0)
        self.assertIsNone(v['junk_rate'])


class ReportingVariantTableJunkTests(TestCase):
    def test_variant_table_exposes_junk_fields(self):
        from apps.adsengine import reporting
        from apps.adsengine.models import (
            AdCampaignMirror, AdSetMirror, AdMirror,
        )

        co = make_company('pub28-reporting')
        MotifPerte.objects.create(
            company=co, nom='Spam/bot', est_junk=True)
        camp = AdCampaignMirror.objects.create(
            company=co, meta_id='cmp_r', name='Campagne', status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=co, meta_id='ast_r', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=co, meta_id='ad_r', name='Ad Report', adset=adset)
        Lead.objects.create(
            company=co, nom='J', meta_ad_id='ad_r', perdu=True,
            motif_perte='Spam/bot')

        table = reporting.variant_table(co)
        v = table['variants'][0]
        self.assertIn('junk', v)
        self.assertIn('junk_rate', v)
        self.assertEqual(v['junk'], 1)
