"""YRBAC11 — sweep object-level : garde objet explicite sur les vues
fonctionnelles/actions custom qui chargent un objet par ID.

``TenantMixin`` scope le queryset générique d'un ``ModelViewSet``, mais les
``@api_view``/``@action``/vues fonctionnelles qui font
``get_object_or_404(Model, pk=…)`` (ou l'équivalent ``Model.objects.get(pk=…)``)
à la main peuvent oublier de re-borner à la société de l'appelant. Ce module
teste :

* ``core.selectors.get_company_object`` — le helper canonique (404 indistinct
  d'un pk inexistant, superuser-sans-société voit tout, superuser AVEC société
  reste scopé, ``extra_scope``/``extra_filters`` s'appliquent) ;
* ``core.object_scope_scan`` — le garde-fou statique qui liste, dans les
  ``views.py``/``views_*.py``/``*_views.py``/``views/*.py`` des apps métier,
  tout ``get_object_or_404(<Model>, pk=…)`` OU ``Model.objects.get(pk=…)``
  SANS mot-clé de scoping (société/portée) explicite — dette à migrer vers
  le helper. Ratchet : ne doit jamais AUGMENTER au-delà du baseline figé ici.

AUD828 (core-C12) — avant ce correctif, ``object_scope_scan.py`` ne
détectait JAMAIS la forme ``Model.objects.get(pk=…)`` malgré ce docstring
qui l'annonçait couverte, et exemptait ``audit``/``reporting``/
``dataimport``/``parametres`` (des apps métier réelles, pas des apps
fondation). Le baseline ci-dessous est RECALIBRÉ sur le compte réel après
élargissement (19 sites sur 6 apps, 0 sur audit/reporting/dataimport/
parametres eux-mêmes) — un ratchet, pas une preuve d'innocuité : chaque
site reste de la dette à migrer vers ``get_company_object``.
"""
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.records.models import Tag
from core import object_scope_scan
from core.selectors import get_company_object

User = get_user_model()

# Baseline de la dette de get_object_or_404()/Model.objects.get(pk=…) non
# scopés (YRBAC11). AUD828 (core-C12) — RECALIBRÉ sur le compte réel après
# élargissement de la surface (Model.objects.get + views_*.py + apps
# métier retirées de _EXEMPT_APPS) : 19 sites neufs, 0 constat vivant sur
# audit/reporting/dataimport/parametres eux-mêmes. Ne doit jamais AUGMENTER
# au-delà de ces valeurs.
UNSCOPED_DEBT_BASELINE = {
    "crm": 7,
    "immobilier": 2,
    "installations": 3,
    "sav": 5,
    "stock": 1,
    "ventes": 1,
}


class ObjectScopeScanRatchetTests(SimpleTestCase):
    def setUp(self):
        self.counts = object_scope_scan.unscoped_counts()

    def test_no_app_exceeds_its_baseline(self):
        regressions = []
        for app, count in self.counts.items():
            baseline = UNSCOPED_DEBT_BASELINE.get(app, 0)
            if count > baseline:
                regressions.append(
                    f"  {app}: {count} get_object_or_404 non scopés "
                    f"(baseline {baseline}) — utilisez "
                    "core.selectors.get_company_object ou ajoutez "
                    "company=/owner= explicitement.")
        self.assertEqual(
            regressions, [],
            "Nouveaux get_object_or_404(<Model>, pk=…) sans garde objet "
            "explicite :\n" + "\n".join(regressions))


class ObjectScopeScanSurfaceTests(SimpleTestCase):
    """AUD828 (core-C12) -- ROUGE d'abord: before this fix, none of these
    three patterns were ever detected -- not "scanned and found clean",
    never even matched:
      * ``Model.objects.get(pk=...)`` (the module's OWN docstring already
        claimed this coverage, but the code never implemented it) ;
      * a ``views_*.py`` PREFIX file (only the ``*_views.py`` SUFFIX was
        recognised) ;
      * a business app previously listed in ``_EXEMPT_APPS``
        (audit/reporting/dataimport/parametres) -- these carry real tenant
        data and are no longer exempt.
    """

    def setUp(self):
        # _rel() below does path.relative_to(DJANGO_CORE_ROOT) -- the
        # fixture tree must live INSIDE it. Never under a 'tests' or
        # 'migrations' segment: _is_view_file() excludes those BY PATH
        # PART anywhere in the path, not just as an app-relative subfolder.
        self._tmp = tempfile.TemporaryDirectory(
            dir=object_scope_scan.DJANGO_CORE_ROOT, prefix="oss_scratch_")
        self.addCleanup(self._tmp.cleanup)
        self.apps_root = Path(self._tmp.name)
        self._orig_apps_root = object_scope_scan.APPS_ROOT
        object_scope_scan.APPS_ROOT = self.apps_root
        self.addCleanup(self._restore)

    def _restore(self):
        object_scope_scan.APPS_ROOT = self._orig_apps_root

    def _write(self, app, filename, src):
        app_dir = self.apps_root / app
        app_dir.mkdir(parents=True, exist_ok=True)
        f = app_dir / filename
        f.write_text(src, encoding="utf-8")
        return f

    def test_model_objects_get_pk_unscoped_detected(self):
        self._write("demo", "views.py", (
            "def voir(request, pk):\n"
            "    obj = Devis.objects.get(pk=pk)\n"
            "    return obj\n"
        ))
        counts = object_scope_scan.unscoped_counts()
        self.assertEqual(counts.get("demo"), 1)

    def test_model_objects_get_scoped_by_company_not_flagged(self):
        self._write("demo", "views.py", (
            "def voir(request, pk):\n"
            "    obj = Devis.objects.get(pk=pk, company=request.user.company)\n"
            "    return obj\n"
        ))
        counts = object_scope_scan.unscoped_counts()
        self.assertNotIn("demo", counts)

    def test_views_prefix_file_scanned(self):
        self._write("demo", "views_qualification.py", (
            "def voir(request, pk):\n"
            "    obj = Devis.objects.get(pk=pk)\n"
            "    return obj\n"
        ))
        counts = object_scope_scan.unscoped_counts()
        self.assertEqual(counts.get("demo"), 1)

    def test_previously_exempt_business_app_now_scanned(self):
        self._write("reporting", "views.py", (
            "def voir(request, pk):\n"
            "    obj = RapportSnapshot.objects.get(pk=pk)\n"
            "    return obj\n"
        ))
        counts = object_scope_scan.unscoped_counts()
        self.assertEqual(counts.get("reporting"), 1)

    def test_foundation_app_still_exempt(self):
        self._write("authentication", "views.py", (
            "def voir(request, pk):\n"
            "    obj = CustomUser.objects.get(pk=pk)\n"
            "    return obj\n"
        ))
        counts = object_scope_scan.unscoped_counts()
        self.assertNotIn("authentication", counts)


class GetCompanyObjectTests(TestCase):
    """Prouve l'isolation cross-tenant du helper canonique sur un modèle réel
    (``records.Tag`` — FK ``company`` simple, aucune dépendance métier)."""

    @classmethod
    def setUpTestData(cls):
        cls.company_a = Company.objects.get_or_create(
            slug="yrbac11-a", defaults={"nom": "YRBAC11 A"})[0]
        cls.company_b = Company.objects.get_or_create(
            slug="yrbac11-b", defaults={"nom": "YRBAC11 B"})[0]
        cls.tag_a = Tag.objects.create(company=cls.company_a, nom="Tag A")
        cls.tag_b = Tag.objects.create(company=cls.company_b, nom="Tag B")
        cls.user_a = User.objects.create_user(
            username="yrbac11-user-a", password="x", company=cls.company_a)
        cls.superuser_no_company = User.objects.create_user(
            username="yrbac11-super-no-co", password="x", is_superuser=True)
        cls.superuser_with_company = User.objects.create_user(
            username="yrbac11-super-co", password="x", is_superuser=True,
            company=cls.company_a)

    def test_own_company_object_is_returned(self):
        obj = get_company_object(Tag, self.tag_a.pk, self.user_a)
        self.assertEqual(obj.pk, self.tag_a.pk)

    def test_cross_tenant_object_raises_404(self):
        """Un id d'une AUTRE société → 404, indistinct d'un id inexistant."""
        with self.assertRaises(Http404):
            get_company_object(Tag, self.tag_b.pk, self.user_a)

    def test_nonexistent_id_raises_same_404(self):
        with self.assertRaises(Http404):
            get_company_object(Tag, 99999999, self.user_a)

    def test_superuser_without_company_sees_all(self):
        """Comportement plateforme historique (identique à TenantMixin)."""
        obj = get_company_object(Tag, self.tag_b.pk, self.superuser_no_company)
        self.assertEqual(obj.pk, self.tag_b.pk)

    def test_superuser_with_company_stays_scoped(self):
        """Un superuser AVEC société reste scopé (usage ERP normal)."""
        obj = get_company_object(
            Tag, self.tag_a.pk, self.superuser_with_company)
        self.assertEqual(obj.pk, self.tag_a.pk)
        with self.assertRaises(Http404):
            get_company_object(
                Tag, self.tag_b.pk, self.superuser_with_company)

    def test_extra_filters_applied(self):
        with self.assertRaises(Http404):
            get_company_object(
                Tag, self.tag_a.pk, self.user_a, nom="Nom différent")
        obj = get_company_object(
            Tag, self.tag_a.pk, self.user_a, nom="Tag A")
        self.assertEqual(obj.pk, self.tag_a.pk)

    def test_extra_scope_callable_applied(self):
        """``extra_scope`` peut narrower davantage (ex. portée d'équipe)."""
        def _never(qs, user):
            return qs.none()
        with self.assertRaises(Http404):
            get_company_object(
                Tag, self.tag_a.pk, self.user_a, extra_scope=_never)

    def test_accepts_prebuilt_queryset(self):
        """Un queryset pré-construit (select_related…) est accepté tel quel."""
        qs = Tag.objects.select_related("company")
        obj = get_company_object(qs, self.tag_a.pk, self.user_a)
        self.assertEqual(obj.pk, self.tag_a.pk)
