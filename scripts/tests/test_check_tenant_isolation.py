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
