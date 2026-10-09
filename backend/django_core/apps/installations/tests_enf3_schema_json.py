"""ENF3 — décision fondateur D2 : JSON seul sur les vues sans dépôt de fichier.

Garde STATIQUE (aucune base) : tout viewset du routeur installations n'accepte
que ``JSONParser`` ; seules les actions d'upload repassent en multipart.
"""
from django.test import SimpleTestCase
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.installations.urls import router
from apps.installations.views import InterventionViewSet, InstallationViewSet
from apps.installations.views.field_sync import FieldSyncView


class InstallationsJsonOnlyTests(SimpleTestCase):
    def test_tous_les_viewsets_sont_json_seul(self):
        for _prefix, viewset, _basename in router.registry:
            self.assertEqual(
                list(viewset.parser_classes), [JSONParser],
                f'{viewset.__name__} doit être JSON seul (D2)')

    def test_sync_json_seul(self):
        self.assertEqual(list(FieldSyncView.parser_classes), [JSONParser])

    def test_actions_upload_multipart(self):
        for action in (InterventionViewSet.ajouter_photo,
                       InterventionViewSet.ajouter_memo,
                       InstallationViewSet.ajouter_releve):
            parsers = list(action.kwargs['parser_classes'])
            self.assertIn(MultiPartParser, parsers)
            self.assertIn(FormParser, parsers)
