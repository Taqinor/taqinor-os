"""Modèles de l'app Paramètres — surface d'import publique.

Le monolithe d'origine a été éclaté par domaine (un fichier par domaine) pour
que plusieurs réglages puissent évoluer en parallèle sans se gêner. Ce module
ré-exporte les classes pour que ``from apps.parametres.models import …`` (et la
découverte des modèles par Django) continue de fonctionner à l'identique.

Split SANS migration : ``app_label`` et noms de table inchangés
(``parametres_companyprofile`` / ``parametres_messagetemplate`` /
``parametres_settingsauditlog``)."""
from .models_company import CompanyProfile
from .models_messages import MESSAGE_TEMPLATE_DEFAULTS, MessageTemplate
from .models_audit import SettingsAuditLog
from .models_tariff import DEFAULT_RESIDENTIAL_TIERS, TariffSettings
from .models_translations import TranslationOverride
from .models_taxes import TAUX_TVA_MAROCAINS, TauxTVA
from .models_payment_terms import ConditionPaiement
from .models_units import UNITES_MESURE_DEFAUT, UniteMesure

__all__ = [
    'CompanyProfile',
    'MessageTemplate',
    'MESSAGE_TEMPLATE_DEFAULTS',
    'SettingsAuditLog',
    'TariffSettings',
    'DEFAULT_RESIDENTIAL_TIERS',
    'TranslationOverride',
    'TauxTVA',
    'TAUX_TVA_MAROCAINS',
    'ConditionPaiement',
    'UniteMesure',
    'UNITES_MESURE_DEFAUT',
]
