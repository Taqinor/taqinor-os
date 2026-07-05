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
  ``views.py`` des apps métier, tout ``get_object_or_404(<Model>, pk=…)`` SANS
  mot-clé de scoping (société/portée) explicite — dette à migrer vers le
  helper. Ratchet : ne doit jamais AUGMENTER au-delà du baseline figé ici.
"""
from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.records.models import Tag
from core import object_scope_scan
from core.selectors import get_company_object

User = get_user_model()

# Baseline de la dette de get_object_or_404() non scopés (YRBAC11). Ne doit
# jamais AUGMENTER — 0 aujourd'hui (les rares usages business-app existants
# scopent déjà par company explicitement).
UNSCOPED_DEBT_BASELINE = {}


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
