"""`AuditLog` gagne une surface LECTURE SEULE dans l'admin Django (voir
`apps/audit/admin.py`) : le modèle n'avait jusqu'ici aucun `admin.py` — la
trace produite automatiquement par `apps.audit.signals.TRACKED_MODELS`
(`stock.Produit`/`crm.Client` y figurent) pour toute modification faite
depuis /admin/ (y compris un `prix_achat`/`courbe_pompe` modifié) restait
invisible depuis l'admin lui-même.

Même patron minimal que
`apps/crm/tests_qx16_payload_replay.py::WebsiteLeadPayloadAdminReadOnlyTests`.
"""
from django.contrib.admin.sites import site as admin_site
from django.test import TestCase

from apps.audit.models import AuditLog


class AuditLogAdminReadOnlyTests(TestCase):
    def test_registered_and_read_only(self):
        model_admin = admin_site._registry[AuditLog]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertIn('action', model_admin.list_display)
        self.assertIn('object_repr', model_admin.list_display)
        self.assertIn('detail', model_admin.list_display)
        self.assertIn('timestamp', model_admin.list_display)
