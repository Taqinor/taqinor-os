"""CIQ428 — indicateur INTERNE « audit énergétique obligatoire probable »
(loi 47-09, décret 2-17-746), sur la seule électricité DÉCLARÉE.

Décret 2-17-746 : 1 GWh d'électricité = 86 tep ; seuil 500 tep (tertiaire —
commercial), 1 500 tep (industrie). Les carburants ne sont pas comptés :
l'électricité seule est une borne basse, donc jamais « non soumis ».

Run :
    python manage.py test apps.crm.tests_ciq428_audit_47_09 -v 2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import audit_energetique as ae
from apps.crm.models import Lead

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pro.json').read_text(encoding='utf-8'))


def _entrees_mensuel(kwh_mensuel, colonne='conso_mensuelle_kwh'):
    return {'entrees': [{'colonne': colonne, 'valeur': kwh_mensuel,
                         'provenance': {'origine': 'lead', 'detail': 'client'}}]}


class Seuils(SimpleTestCase):
    def test_constantes_sourcees(self):
        self.assertEqual(ae.SEUIL_TEP_INDUSTRIE, 1500)
        self.assertEqual(ae.SEUIL_TEP_TERTIAIRE, 500)
        self.assertEqual(ae.TEP_PAR_GWH_ELECTRICITE, 86)
        self.assertIn('mem.gov.ma', ae.SOURCE['url'])

    def test_commercial_6_gwh_atteint(self):
        r = ae.indicateur_audit_47_09(6_000_000, None, 'commercial')
        self.assertEqual(r['tep_electricite'], 516)
        self.assertEqual(r['statut'], 'seuil_atteint_electricite_seule')
        self.assertEqual(r['seuil_tep'], 500)
        self.assertEqual(r['secteur'], 'tertiaire')

    def test_commercial_5_gwh_non_determine(self):
        r = ae.indicateur_audit_47_09(5_000_000, None, 'commercial')
        self.assertEqual(r['tep_electricite'], 430)
        self.assertEqual(r['statut'], 'non_determine')
        self.assertIn('carburants ne sont pas comptés', r['motif'])
        self.assertNotIn('non soumis', json.dumps(r, ensure_ascii=False))

    def test_industriel(self):
        r = ae.indicateur_audit_47_09(6_000_000, None, 'industriel')
        self.assertEqual(r['statut'], 'non_determine')
        r = ae.indicateur_audit_47_09(18_000_000, None, 'industriel')
        self.assertEqual(r['tep_electricite'], 1548)
        self.assertEqual(r['statut'], 'seuil_atteint_electricite_seule')

    def test_kwh_mensuel_fois_douze(self):
        r = ae.indicateur_du_lead('commercial', _entrees_mensuel(500_000))
        self.assertEqual(r['tep_electricite'], 516)

    def test_releve_douze_mois_additionne(self):
        entrees = {'entrees': [{'colonne': 'releve_conso', 'valeur': [
            {'mois': f'2025-{m:02d}', 'kwh': 500_000} for m in range(1, 13)],
            'provenance': {'origine': 'lead', 'detail': 'facture'}}]}
        r = ae.indicateur_du_lead('commercial', entrees)
        self.assertEqual(r['tep_electricite'], 516)
        self.assertEqual(r['provenance']['detail'], 'facture')

    def test_sans_kwh_ou_facture_mad_ou_tranche_null_et_motif(self):
        for entrees in (
                {'entrees': []},
                None,
                {'entrees': [{'colonne': 'facture_hiver', 'valeur': 90000,
                              'provenance': {}}]}):
            r = ae.indicateur_du_lead('commercial', entrees)
            self.assertIsNone(r['statut'])
            self.assertIsNone(r['tep_electricite'])
            self.assertTrue(r['motif'])

    def test_residentiel_ne_porte_rien(self):
        for segment in ('residentiel', 'agricole', None):
            self.assertIsNone(ae.indicateur_du_lead(segment, _entrees_mensuel(1e9)))


class JamaisSurUneSortieClient(SimpleTestCase):
    def test_grep_hors_quote_engine_public_et_site(self):
        racine = Path(__file__).resolve().parents[4]
        cibles = [
            racine / 'backend' / 'django_core' / 'apps' / 'ventes' / 'quote_engine',
            racine / 'backend' / 'django_core' / 'apps' / 'ventes' / 'public_views.py',
            # SPL245-SPL253 (#796) — public_views découpé dans ``public/``.
            racine / 'backend' / 'django_core' / 'apps' / 'ventes' / 'public',
            racine / 'apps' / 'web',
        ]
        for cible in cibles:
            fichiers = [cible] if cible.is_file() else (
                [f for f in cible.rglob('*') if f.is_file()
                 and 'node_modules' not in f.parts
                 and f.suffix in ('.py', '.js', '.jsx', '.ts', '.astro', '.html', '.json')]
                if cible.exists() else [])
            for f in fichiers:
                self.assertNotIn('audit_47_09',
                                 f.read_text(encoding='utf-8', errors='ignore'), str(f))

    def test_le_contrat_porte_la_cle(self):
        self.assertIn('audit_47_09', CONTRAT['exemple']['indicateurs_internes'])


class ServiAuDetailSeulement(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq428-api', defaults={'nom': 'CIQ428 Api'})
        self.user = User.objects.create_user(
            username='ciq428_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Hôtel', type_installation='commercial',
            conso_mensuelle_kwh=500000)

    def test_detail_sert_l_indicateur(self):
        lu = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        bloc = lu['indicateurs_internes']['audit_47_09']
        self.assertEqual(bloc['statut'], 'seuil_atteint_electricite_seule')
        self.assertEqual(bloc['tep_electricite'], 516)

    def test_residentiel_detail_null(self):
        lead = Lead.objects.create(company=self.company, nom='Villa',
                                   type_installation='residentiel')
        lu = self.api.get(f'/api/django/crm/leads/{lead.id}/').data
        self.assertIsNone(lu['indicateurs_internes']['audit_47_09'])

    def test_la_liste_ne_porte_pas_la_cle_et_garde_ses_requetes(self):
        def _compte():
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/crm/leads/')
            self.assertEqual(resp.status_code, 200)
            return resp, len(ctx.captured_queries)

        resp, avant = _compte()
        for ligne in resp.data.get('results', resp.data):
            self.assertNotIn('indicateurs_internes', ligne)
        Lead.objects.filter(pk=self.lead.pk).update(conso_mensuelle_kwh=900000)
        _resp, apres = _compte()
        self.assertEqual(apres, avant)
