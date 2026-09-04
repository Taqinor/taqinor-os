"""AUD803 — le lien public de rapport partagé servait catalogue + stocks +
funnel leads SANS authentification NI révocation, alors que la révocabilité est
la justification écrite du dispositif.

Constat d'origine : ``rapport_partage_public`` est
``@authentication_classes([]) @permission_classes([AllowAny])`` et
``resolve_report_token`` ne faisait qu'un ``SavedReport.objects.filter(pk=…)
.first()`` — aucun état révocable. Seule une expiration à 7 jours bornait
l'exposition. L'en-tête du module fonde pourtant tout le dispositif sur « un
.xlsx qui circule ne se révoque pas »… alors que le LIEN ne se révoquait pas
davantage. Scénario : un lien transféré dans un groupe WhatsApp expose stocks,
catalogue et leads pendant sept jours, sans aucune trace côté serveur au-delà
du throttle par IP.

Après correctif : ``SavedReport.partage_revoque_le`` coupe le lien
immédiatement (même 404 générique — jamais d'indice sur le motif), et chaque
résolution RÉUSSIE écrit une ligne ``AccesRapportPartage`` (IP + horodatage).
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from . import diffusion_views
from .models import AccesRapportPartage, SavedReport

URL = '/api/django/reporting/rapports-partages/{token}/'


class Aud803RevocationDuLienPublicTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD803 Co')
        self.report = SavedReport.objects.create(
            company=self.company, name='Stock', target_kind='stock')
        self.token = diffusion_views.make_report_token(self.report)

    # ── Révocation ────────────────────────────────────────────────────────
    def test_un_rapport_neuf_a_son_partage_actif(self):
        self.assertIsNone(self.report.partage_revoque_le)
        self.assertTrue(self.report.partage_actif)

    def test_le_lien_sert_tant_qu_il_n_est_pas_revoque(self):
        res = self.client.get(URL.format(token=self.token))
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml', res['Content-Type'])

    def test_un_lien_revoque_ne_sert_plus(self):
        self.report.partage_revoque_le = timezone.now()
        self.report.save(update_fields=['partage_revoque_le'])
        res = self.client.get(URL.format(token=self.token))
        self.assertEqual(res.status_code, 404)

    def test_la_resolution_refuse_un_rapport_revoque(self):
        self.report.partage_revoque_le = timezone.now()
        self.report.save(update_fields=['partage_revoque_le'])
        self.assertIsNone(
            diffusion_views.resolve_report_token(self.token))

    def test_le_404_de_revocation_est_indiscernable_d_un_jeton_invalide(self):
        """Jamais d'indice sur l'existence du rapport ni sur le motif."""
        self.report.partage_revoque_le = timezone.now()
        self.report.save(update_fields=['partage_revoque_le'])
        revoque = self.client.get(URL.format(token=self.token))
        invalide = self.client.get(URL.format(token='pas-un-jeton'))
        self.assertEqual(revoque.status_code, invalide.status_code)
        self.assertEqual(revoque.json(), invalide.json())

    # ── Trace d'accès ─────────────────────────────────────────────────────
    def test_chaque_acces_reussi_ecrit_une_trace(self):
        self.assertEqual(AccesRapportPartage.objects.count(), 0)
        self.client.get(URL.format(token=self.token))
        self.client.get(URL.format(token=self.token))
        traces = AccesRapportPartage.objects.filter(saved_report=self.report)
        self.assertEqual(traces.count(), 2)
        trace = traces.first()
        self.assertEqual(trace.company, self.company)
        self.assertIsNotNone(trace.consulte_le)

    def test_la_trace_porte_l_ip_transmise_par_le_proxy(self):
        self.client.get(URL.format(token=self.token),
                        HTTP_X_FORWARDED_FOR='203.0.113.7, 10.0.0.1')
        trace = AccesRapportPartage.objects.get(saved_report=self.report)
        self.assertEqual(trace.ip, '203.0.113.7')

    def test_un_jeton_invalide_n_ecrit_aucune_trace(self):
        self.client.get(URL.format(token='pas-un-jeton'))
        self.assertEqual(AccesRapportPartage.objects.count(), 0)

    def test_un_lien_revoque_n_ecrit_aucune_trace(self):
        self.report.partage_revoque_le = timezone.now()
        self.report.save(update_fields=['partage_revoque_le'])
        self.client.get(URL.format(token=self.token))
        self.assertEqual(AccesRapportPartage.objects.count(), 0)
