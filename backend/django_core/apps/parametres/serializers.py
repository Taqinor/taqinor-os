"""Sérialiseurs de l'app Paramètres — surface d'import publique.

Éclatés par domaine (un fichier par domaine) pour permettre des évolutions
parallèles. Ré-exportés ici pour que
``from apps.parametres.serializers import …`` continue de fonctionner à
l'identique. Aucun changement de champ ni de comportement."""
from .serializers_company import CompanyProfileSerializer
from .serializers_audit import SettingsAuditLogSerializer
from .serializers_documents import DocumentTemplatesSerializer
from .serializers_tariff import TariffSettingsSerializer
from .serializers_translations import TranslationOverrideSerializer

__all__ = [
    'CompanyProfileSerializer',
    'SettingsAuditLogSerializer',
    'DocumentTemplatesSerializer',
    'TariffSettingsSerializer',
    'TranslationOverrideSerializer',
]
