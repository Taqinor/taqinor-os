from django.apps import AppConfig


class ConversationAiConfig(AppConfig):
    """AppConfig du module « apps.conversation_ai » (Groupe NTAI).

    Conversations commerciales ENREGISTRÉES (appels téléphoniques téléversés) :
    stockage de l'enregistrement, transcription asynchrone key-gated (STT) et
    analyse du transcript. Le module ne CRÉE jamais un enregistrement lui-même
    et n'écrit jamais dans le CRM sans confirmation humaine.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.conversation_ai'
    verbose_name = 'Conversations commerciales'
    module_manifest = {
        # Clé ``ModuleToggle`` (unique dans tout le dépôt, obligatoire) —
        # IDENTIQUE au 2ᵉ segment d'URL (`api/django/conversation_ai/`), donc
        # aucune entrée ``PREFIX_TO_MODULE`` n'est nécessaire.
        'key': 'conversation_ai',
        'label': 'Conversations commerciales',
        'icone': 'phone',
        'depends': [],
        'installable': True,
        'description': (
            "Enregistrements d'appels commerciaux : transcription "
            'asynchrone (key-gated STT) et analyse du transcript — sans clé, '
            "l'appel reste « non transcrit » sans erreur."
        ),
        'categorie': 'Commercial',
    }
