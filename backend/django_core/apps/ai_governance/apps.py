from django.apps import AppConfig


class AiGovernanceConfig(AppConfig):
    """AppConfig du module « apps.ai_governance » (Groupe NTAI).

    Couche AI-first posée AU-DESSUS de la fondation ``core.ai`` (fournisseurs
    OCR/STT/LLM key-gated, NO-OP-safe) : copilotes contextuels, générateurs de
    brouillons et surveillance des modèles. AUCUNE de ces surfaces n'écrit dans
    un modèle métier sans une action explicite de l'utilisateur, et toutes
    dégradent proprement quand aucune clé LLM n'est configurée.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_governance'
    verbose_name = 'Gouvernance IA'
    module_manifest = {
        'key': 'ai_governance',
        'sku': 'generic',
        'label': 'Gouvernance IA',
        'icone': 'cpu',
        'depends': [],
        'installable': True,
        'description': (
            "Copilotes IA contextuels (brouillons, comptes rendus, "
            "descriptions) et surveillance des modèles — sans clé, tout "
            "dégrade proprement."
        ),
        'categorie': 'Technique',
    }

    def ready(self):
        # NTAI17 — branche « dépôt d'une pièce GED → job de traitement IA ».
        # Référence par CHAÎNE au modèle GED (aucun import d'app métier) et
        # no-op complet tant que ``AI_DOCUMENT_JOBS_ENABLED`` est éteint.
        from .receivers import connect_receivers
        connect_receivers()

        # NTAI1 — branche le puits du journal d'usage IA sur la fondation
        # ``core.ai.usage`` : core mesure, cette app persiste. Sans cette
        # inscription, ``record_usage`` est un no-op complet (aucune ligne).
        from .usage import connect_usage_sink
        connect_usage_sink()
