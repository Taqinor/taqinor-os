"""Tests YDATA21 — scripts/check_tenant_isolation.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_tenant_isolation -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_tenant_isolation as cti  # noqa: E402


class TestSurfaceEnumeration(unittest.TestCase):
    """AUD828 (M-07) -- ROUGE d'abord: before the fix, a views_*.py PREFIX
    file, a serializers_*.py PREFIX file, and anything under core/
    authentication were NEVER OPENED by the guard at all (not "scanned and
    found clean" -- never even read). This pins the surface itself, not the
    per-class detection logic already covered above."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(self._tmp.cleanup)
        self.apps_dir = Path(self._tmp.name) / "apps"
        self.core_dir = Path(self._tmp.name) / "core"
        self.auth_dir = Path(self._tmp.name) / "authentication"
        for d in (self.apps_dir, self.core_dir, self.auth_dir):
            d.mkdir(parents=True)
        self.app_dir = self.apps_dir / "demo"
        self.app_dir.mkdir()

        self._orig = (cti.APPS_DIR, cti.CORE_DIR, cti.AUTH_DIR)
        cti.APPS_DIR = self.apps_dir
        cti.CORE_DIR = self.core_dir
        cti.AUTH_DIR = self.auth_dir
        self.addCleanup(self._restore)

    def _restore(self):
        cti.APPS_DIR, cti.CORE_DIR, cti.AUTH_DIR = self._orig

    def test_views_prefix_file_opened(self):
        f = self.app_dir / "views_qualification.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cti._iter_view_files()))

    def test_serializers_prefix_file_opened(self):
        f = self.app_dir / "serializers_bar.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cti._iter_serializer_files()))

    def test_core_views_file_opened(self):
        f = self.core_dir / "views.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cti._iter_view_files()))

    def test_authentication_views_prefix_file_opened(self):
        f = self.auth_dir / "views_console.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cti._iter_view_files()))

    def test_viewsets_module_not_treated_as_views_file(self):
        """A loose 'views*.py' wildcard would ALSO match viewsets.py (a
        base-class module, not an endpoint module) -- must not be opened."""
        f = self.core_dir / "viewsets.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertNotIn(f, list(cti._iter_view_files()))

    def test_no_duplicate_yield_when_patterns_overlap(self):
        f = self.app_dir / "views.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        files = list(cti._iter_view_files())
        self.assertEqual(files.count(f), 1)


def _view_codes(src):
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = Path(fh.name)
    try:
        _views, findings = cti.check_view_file(path)
        return {code for code, _key, _msg in findings}
    finally:
        path.unlink()


def _serializer_codes(src):
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = Path(fh.name)
    try:
        return {code for code, _key, _msg in cti.serializer_company_writable(path)}
    finally:
        path.unlink()


NAKED_VIEWSET = '''
from rest_framework import viewsets


class ProduitViewSet(viewsets.ModelViewSet):
    queryset = Produit.objects.all()
    serializer_class = ProduitSerializer
'''

SCOPED_GET_QUERYSET = '''
from rest_framework import viewsets


class ProduitViewSet(viewsets.ModelViewSet):
    serializer_class = ProduitSerializer

    def get_queryset(self):
        return Produit.objects.filter(company=self.request.user.company)
'''

SCOPED_BASE = '''
from core.viewsets import CompanyScopedModelViewSet


class ProduitViewSet(CompanyScopedModelViewSet):
    queryset = Produit.objects.all()
'''

PLAIN_APIVIEW_EXEMPT = '''
from rest_framework.views import APIView


class PingView(APIView):
    def get(self, request):
        return Response({'ok': True})
'''

COMPANY_FROM_BODY = '''
from rest_framework import viewsets


class ProduitViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Produit.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(company=serializer.validated_data['company'])
'''

SERIALIZER_WRITABLE = '''
from rest_framework import serializers


class ProduitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produit
        fields = ['id', 'company', 'nom']
'''

SERIALIZER_HIDDENFIELD_OK = '''
from rest_framework import serializers


class ProduitSerializer(serializers.ModelSerializer):
    company = serializers.HiddenField(default=CurrentCompanyDefault())

    class Meta:
        model = Produit
        fields = ['id', 'company', 'nom']
'''

SERIALIZER_ALL_READONLY_OK = '''
from rest_framework import serializers


class ProduitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produit
        fields = ['id', 'company', 'nom']
        read_only_fields = fields
'''


class TestTenantIsolation(unittest.TestCase):
    def test_naked_modelviewset_flagged(self):
        self.assertIn("COMPANY_FILTER_MISSING", _view_codes(NAKED_VIEWSET))

    def test_scoped_get_queryset_ok(self):
        self.assertNotIn("COMPANY_FILTER_MISSING",
                         _view_codes(SCOPED_GET_QUERYSET))

    def test_scoped_base_ok(self):
        self.assertNotIn("COMPANY_FILTER_MISSING", _view_codes(SCOPED_BASE))

    def test_plain_apiview_exempt(self):
        self.assertEqual(_view_codes(PLAIN_APIVIEW_EXEMPT), set())

    def test_company_from_body_flagged(self):
        self.assertIn("COMPANY_FROM_BODY", _view_codes(COMPANY_FROM_BODY))

    def test_serializer_writable_company_flagged(self):
        self.assertIn("SERIALIZER_COMPANY_WRITABLE",
                      _serializer_codes(SERIALIZER_WRITABLE))

    def test_serializer_hiddenfield_ok(self):
        self.assertEqual(_serializer_codes(SERIALIZER_HIDDENFIELD_OK), set())

    def test_serializer_all_readonly_ok(self):
        self.assertEqual(_serializer_codes(SERIALIZER_ALL_READONLY_OK), set())


if __name__ == "__main__":
    unittest.main()
