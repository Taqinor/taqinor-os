"""Fondation IA de l'OS — interfaces de fournisseurs IA, NO-OP par défaut.

Ce sous-paquet vit dans l'app de FONDATION ``core`` : il ne dépend d'AUCUNE app
métier ni satellite (contrat import-linter ``core-foundation-is-a-base-layer``).
Il n'expose que des INTERFACES génériques + des implémentations NO-OP qui ne
font aucun appel réseau, n'ajoutent aucune dépendance pip et ne coûtent rien
tant qu'aucune clé/fournisseur n'est configuré.

Les apps métier (stock, crm, installations…) consomment ces capacités depuis
LEUR couche ``services.py`` ; elles n'importent jamais ``core.ai`` pour réagir,
mais pour DEMANDER une capacité (OCR, transcription, vision-QA, synthèse,
prochaine-meilleure-action). Le défaut NO-OP garantit que tout fonctionne sans
clé : la fonctionnalité « ne fait simplement rien » plutôt que de casser.

Capacités couvertes (toutes NO-OP par défaut) :

  * OCR document (FG355 CIN/contrat, FG356 bon de livraison) — ``OCRProvider``.
  * Transcription audio → texte (FG357 notes terrain) — ``STTProvider``.
  * Contrôle qualité vision sur photos (FG358) — ``VisionQAProvider``.
  * Synthèse de fil (FG353) & brouillon de réponse (FG354) — ``LLMProvider``.

Sélection : ``core.ai.registry.get_provider(capability)`` lit le réglage
``settings.AI_PROVIDERS`` (dict capacité→clé) et retombe sur ``'noop'``.
"""
from core.ai.providers import (
    AIResult,
    LLMProvider,
    NoOpLLMProvider,
    NoOpOCRProvider,
    NoOpSTTProvider,
    NoOpVisionQAProvider,
    OCRProvider,
    STTProvider,
    VisionQAProvider,
)
from core.ai.registry import (
    available_providers,
    get_provider,
    is_capability_configured,
    register_provider,
)
from core.ai.schemas import (
    BON_LIVRAISON_SCHEMA,
    CIN_SCHEMA,
    CONTRAT_SCHEMA,
    OCRSchema,
    available_schemas,
    get_schema,
)
from core.ai.services import (
    CAMPAIGN_PROMPT_FORBIDDEN_TERMS,
    DEFAULT_PHOTO_QA_CHECKLIST,
    LIVECHAT_FORBIDDEN_TERMS,
    LIVECHAT_QUALIFICATION_SYSTEM_PROMPT,
    REPLY_CHANNELS,
    CampaignContentDraft,
    LivechatQualificationExtract,
    MatchedLine,
    NextBestAction,
    ReplyDraft,
    ThreadSummary,
    build_campaign_prompt,
    draft_campaign_content,
    draft_reply,
    extract_document,
    extract_livechat_qualification,
    format_thread,
    inspect_photo,
    match_ocr_lines,
    qualify_livechat_reply,
    recommend_next_action,
    recommend_next_action_ai,
    summarize_thread,
    transcribe_audio,
)

__all__ = [
    'AIResult',
    'LLMProvider',
    'OCRProvider',
    'STTProvider',
    'VisionQAProvider',
    'NoOpLLMProvider',
    'NoOpOCRProvider',
    'NoOpSTTProvider',
    'NoOpVisionQAProvider',
    'get_provider',
    'register_provider',
    'available_providers',
    'is_capability_configured',
    # Gabarits OCR (FG355/FG356)
    'OCRSchema',
    'CIN_SCHEMA',
    'CONTRAT_SCHEMA',
    'BON_LIVRAISON_SCHEMA',
    'get_schema',
    'available_schemas',
    # Services (FG355-FG359)
    'extract_document',
    'match_ocr_lines',
    'MatchedLine',
    'transcribe_audio',
    'inspect_photo',
    'DEFAULT_PHOTO_QA_CHECKLIST',
    'recommend_next_action',
    'recommend_next_action_ai',
    'NextBestAction',
    # Synthèse de fil & brouillon de réponse (FG353/FG354)
    'format_thread',
    'summarize_thread',
    'ThreadSummary',
    'draft_reply',
    'ReplyDraft',
    'REPLY_CHANNELS',
    # Livechat de qualification (XMKT37)
    'LIVECHAT_QUALIFICATION_SYSTEM_PROMPT',
    'LIVECHAT_FORBIDDEN_TERMS',
    'LivechatQualificationExtract',
    'qualify_livechat_reply',
    'extract_livechat_qualification',
    # Génération de contenu de campagne (XMKT34)
    'CampaignContentDraft',
    'CAMPAIGN_PROMPT_FORBIDDEN_TERMS',
    'build_campaign_prompt',
    'draft_campaign_content',
]
