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
from .views_audit import settings_audit_log
from .views_documents import (
    get_document_templates,
    update_document_templates,
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
    'get_document_templates',
    'update_document_templates',
]
