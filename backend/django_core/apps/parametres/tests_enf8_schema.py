"""ENF8 — schéma OpenAPI exact de l'app parametres (décision D2 : JSON seul).

Garde : les vues SANS upload n'acceptent que du JSON (le multipart rendait
les booléens intypables) ; les deux routes d'upload gardent le multipart.
"""
from django.test import SimpleTestCase
from rest_framework.parsers import JSONParser, MultiPartParser

from . import views_uploads
from .views_approvals import ApprovalPolicyViewSet
from .views_email import EmailTemplateViewSet
from .views_realisations import RealisationViewSet
from .views_referentiels import (
    CadenceRelanceEtapeViewSet, ConditionPaiementViewSet, TauxTVAViewSet,
    UniteMesureViewSet,
)
from .views_statuses import StatutConfigViewSet
from .views_translations import TranslationOverrideViewSet


class ParametresParsersTests(SimpleTestCase):
    def test_vues_sans_upload_json_seul(self):
        for vue in (
            ApprovalPolicyViewSet, EmailTemplateViewSet, RealisationViewSet,
            CadenceRelanceEtapeViewSet, ConditionPaiementViewSet,
            TauxTVAViewSet, UniteMesureViewSet, StatutConfigViewSet,
            TranslationOverrideViewSet,
        ):
            with self.subTest(vue=vue.__name__):
                self.assertEqual(vue.parser_classes, [JSONParser])

    def test_uploads_gardent_le_multipart(self):
        for fn in (views_uploads.upload_logo, views_uploads.upload_signature):
            with self.subTest(vue=fn.__name__):
                self.assertEqual(fn.cls.parser_classes, [MultiPartParser])
