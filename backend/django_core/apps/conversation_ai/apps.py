"""Configuration de l'app « conversation_ai » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class ConversationAiConfig(AppConfig):
    """Conversations commerciales — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.conversation_ai'
    label = 'conversation_ai'
    verbose_name = 'Conversations commerciales'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'conversation_ai',
        'sku': 'generic',
        'label': 'Conversations commerciales',
        'icone': 'phone',
        'depends': [],
        'installable': True,
        'description': "Enregistrements d'appels commerciaux : transcription asynchrone (key-gated STT) et analyse du transcript — sans clé, l'appel reste « non transcrit » sans erreur.",
        'categorie': 'Commercial',
        'parked': True,
    }
