"""AACQ26 — Parité du « coût par lead » : UNE fonction (``metrics.cout_par_lead``)
qui nomme sa source ; chaque sortie libellée « coût par lead » (cockpit,
``variant_table``, brief, règles) passe par elle et affiche sa source ; un
calcul dépense ÷ leads hors de cette fonction fait échouer ce test (AST).
"""
import ast
import datetime
import pathlib
from decimal import Decimal
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import brief as brief_mod, metrics, reporting
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, InsightSnapshot,
)

MODULE_DIR = pathlib.Path(metrics.__file__).resolve().parent


def modules_surveilles():
    """AACQ103 — tout ``*.py`` d'``apps/adsengine`` hors ``tests/`` et
    ``migrations/`` (la garde ne lit plus 4 fichiers seulement)."""
    return sorted(
        p for p in MODULE_DIR.rglob('*.py')
        if not {'tests', 'migrations'} & set(p.relative_to(MODULE_DIR).parts))


def _noms(node):
    return {n.id.lower() for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr.lower() for n in ast.walk(node) if isinstance(n, ast.Attribute)} | {
        str(n.value).lower() for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _est_nom_cpl(cible):
    """Cible d'affectation nommée ``cpl`` / ``…_cpl`` (``cpl_norm`` : non)."""
    nom = cible.id.lower() if isinstance(cible, ast.Name) else ''
    return nom == 'cpl' or nom.endswith('_cpl')


def divisions_hors_fonction(source):
    """Divisions ``<…spend…> / <…lead…>`` hors de ``cout_par_lead``, et toute
    division affectée à un nom ``cpl`` (AACQ103) ; un diviseur qui est lui-même
    un CPL (``cpl_healthy / cpl``) n'est pas visé."""
    tree = ast.parse(source)
    autorisees = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == 'cout_par_lead':
            autorisees |= {id(n) for n in ast.walk(fn)}
    trouvees = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and id(node) not in autorisees):
            gauche, droite = _noms(node.left), _noms(node.right)
            if (any('spend' in g for g in gauche)
                    and any('lead' in d for d in droite)):
                trouvees.append(node.lineno)
    for node in ast.walk(tree):
        if (isinstance(node, (ast.Assign, ast.AnnAssign))
                and node.value is not None and id(node) not in autorisees):
            cibles = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(_est_nom_cpl(c) for c in cibles):
                continue
            for div in ast.walk(node.value):
                if (isinstance(div, ast.BinOp) and isinstance(div.op, ast.Div)
                        and not any(_est_nom_cpl(n) or (
                            isinstance(n, ast.Name) and 'cpl' == n.id.lower())
                            for n in ast.walk(div.right))
                        and div.lineno not in trouvees):
                    trouvees.append(div.lineno)
    return sorted(trouvees)


class GardeAstTests(SimpleTestCase):
    def test_aucune_division_depense_par_leads_hors_fonction(self):
        modules = modules_surveilles()
        self.assertGreater(len(modules), 20)
        for chemin in modules:
            with self.subTest(module=chemin.name):
                source = chemin.read_text(encoding='utf-8')
                self.assertEqual(divisions_hors_fonction(source), [])

    def test_le_garde_detecte_une_reintroduction(self):
        fautif = "def f(spend, leads):\n    return spend / leads\n"
        self.assertEqual(divisions_hors_fonction(fautif), [2])
        # AACQ103 — division affectée à un nom ``cpl`` (diviseur sans « lead »).
        self.assertEqual(divisions_hors_fonction(
            "def g(a, total):\n    cpl = a / total\n"), [2])
        self.assertEqual(divisions_hors_fonction(
            "def g(a, total):\n    ad_cpl = (a / total) if total else None\n"),
            [2])
        # Diviseur lui-même un CPL, cible ``cpl_norm`` : non visé.
        self.assertEqual(divisions_hors_fonction(
            "def g(h, cpl):\n    cpl_norm = h / cpl\n"), [])
        self.assertEqual(divisions_hors_fonction(
            "def cout_par_lead(spend, leads, *, source):\n"
            "    return spend / leads\n"), [])

    def test_normalisation_insight_passe_par_la_fonction(self):
        """AACQ103 — le CPL « résultats » de ``normalize_insight_row`` sort de
        ``cout_par_lead`` : mêmes chiffres, ``None`` sans résultat."""
        from apps.adsengine.platforms.base import normalize_insight_row
        self.assertEqual(normalize_insight_row(
            {'spend': '1000', 'results': '40'})['cpl'], 25.0)
        self.assertIsNone(normalize_insight_row(
            {'spend': '1000', 'results': '0'})['cpl'])
        self.assertEqual(normalize_insight_row(
            {'spend': '1000', 'results': '40', 'cpl': '30'})['cpl'], 30.0)


class PariteCplTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Par', slug='aacq26-par')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c-26', name='Leads',
            status='ACTIVE', objective='OUTCOME_LEADS')
        self.today = timezone.now().date()

    def test_fonction_unique_et_sources(self):
        cas = {
            'leads_meta': 'leads Meta', 'formulaires_meta': 'formulaires Meta',
            'odoo': 'leads Odoo', 'crm': 'leads CRM attribués',
        }
        for source, libelle in cas.items():
            with self.subTest(source=source):
                r = metrics.cout_par_lead(Decimal('1000'), 10, source=source)
                self.assertEqual(r.valeur, Decimal('100'))
                self.assertEqual(r.source_fr, libelle)
        self.assertIsNone(metrics.cout_par_lead(
            Decimal('1000'), 0, source='crm').valeur)
        self.assertEqual(len(set(cas.values())), 4)  # sources distinctes
        with self.assertRaises(ValueError):
            metrics.cout_par_lead(1, 1, source='inconnue')

    def test_brief_nomme_sa_source(self):
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.camp.pk,
            date=self.today, spend='1000.00', results=40, leads_count=10)
        brief = brief_mod.build_brief(self.company, create_proposals=False)
        self.assertEqual(brief.data['cpl_semaine'], '100.00')  # ÷ 10 leads
        self.assertEqual(brief.data['cpl_source'], 'leads Meta')
        self.assertIn('Coût par lead (semaine, leads Meta) : 100.00',
                      brief.markdown)

    def test_variant_table_nomme_sa_source(self):
        fake = {'variants': [{
            'meta_id': 'ad-26', 'name': 'Ad', 'spend': '1000.00', 'leads': 5,
            'qualified': 0, 'signed': 0, 'cost_per_qualified_lead': None,
            'cost_per_signature': None, 'lead_ids': [],
            'signed_lead_ids': [], 'junk': 0, 'junk_rate': None,
            'appointments': 0, 'no_show': 0, 'no_show_rate': None}],
            'unresolved': {}, 'organic_excluded_count': 0}
        with mock.patch('apps.adsengine.attribution.variant_attribution',
                        return_value=fake):
            data = reporting.variant_table(self.company)
        row = data['variants'][0]
        self.assertEqual(row['cost_per_lead'], '200.00')
        self.assertEqual(row['cost_per_lead_source'], 'leads CRM attribués')

    def test_cockpit_nomme_ses_sources(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-26', name='AS',
            status='ACTIVE', campaign=self.camp)
        AdMirror.objects.create(
            company=self.company, meta_id='ad-26', name='Ad', status='ACTIVE',
            adset=adset)
        rows = metrics.ads_cockpit_rows(self.company)
        rows = rows.get('ads', rows) if isinstance(rows, dict) else rows
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['cpl_source'], 'formulaires Meta')
            self.assertEqual(row['cpl_odoo_source'], 'leads Odoo')

    def test_regles_passent_par_la_meme_definition(self):
        from apps.adsengine import rules_engine
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        for d in range(5):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.camp.pk,
                date=self.today - datetime.timedelta(days=d),
                spend='200.00', results=8, leads_count=2)
        snaps = list(InsightSnapshot.objects.filter(object_id=self.camp.pk))
        value, _ = rules_engine._derived_metric(
            snaps, 'cpl', lead_field='leads_count')
        attendu = metrics.cout_par_lead(
            Decimal('1000'), 10, source='leads_meta').valeur
        self.assertAlmostEqual(value, float(attendu))
