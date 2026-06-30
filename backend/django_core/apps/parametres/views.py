"""Vues de l'app Paramètres — surface d'import publique.

Éclatées par domaine (un fichier par domaine) pour permettre des évolutions
parallèles. Ré-exportées ici pour que ``urls.py`` (``from . import views`` →
``views.get_profile`` …) et tout import existant continuent de résoudre vers
les mêmes fonctions, aux mêmes endpoints, sans changement de comportement."""
from .views_profile import get_profile, update_profile
from .views_uploads import (
    delete_logo,
    delete_signature,
    upload_logo,
    upload_signature,
)
from .views_messages import messages_endpoint
from .views_audit import settings_audit_log, settings_audit_sections
from .views_documents import (
    get_document_templates,
    update_document_templates,
)
from .views_tariff import (
    compute_roi,
    get_productible,
    get_tariff_settings,
    update_tariff_settings,
)

__all__ = [
    'get_profile',
    'update_profile',
    'upload_logo',
    'upload_signature',
    'delete_logo',
    'delete_signature',
    'messages_endpoint',
    'settings_audit_log',
    'settings_audit_sections',
    'get_document_templates',
    'update_document_templates',
    'get_tariff_settings',
    'update_tariff_settings',
    'compute_roi',
    'get_productible',
]
