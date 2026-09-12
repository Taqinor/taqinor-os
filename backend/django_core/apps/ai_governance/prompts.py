"""NTAI5 — Côté APP de la bibliothèque de prompts (résolveur + versions).

``core.ai.prompts`` connaît les défauts CODE et sait rendre un prompt ; c'est
ici que vivent les surcharges d'une société et leur historique. Les DÉFAUTS
des features de cette app y sont aussi déclarés, pour que l'écran de
paramétrage puisse proposer « voici la clé, voici le texte actuel, voici ce
que vous pouvez changer ».
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Résolution d'une surcharge société
# ─────────────────────────────────────────────────────────────────────────────

def resoudre_prompt(company, cle):
    """Corps surchargé pour ``(company, cle)``, ou ``None``.

    ``None`` = pas de surcharge ACTIVE → ``core`` retombe sur le défaut code.
    Scopé société par construction : la clé seule ne suffit jamais à lire une
    ligne."""
    from .models import PromptTemplate

    if company is None:
        return None
    filtre = ({'company_id': company} if isinstance(company, int)
              else {'company': company})
    gabarit = PromptTemplate.objects.filter(
        cle=cle, actif=True, **filtre).only('corps').first()
    return gabarit.corps if gabarit else None


def connect_prompt_resolver():
    """Branche le résolveur sur la fondation (appelé par ``apps.py``)."""
    from core.ai.prompts import register_prompt_resolver

    register_prompt_resolver(resoudre_prompt)


# ─────────────────────────────────────────────────────────────────────────────
# NTAI7 — Consentement IA par feature
# ─────────────────────────────────────────────────────────────────────────────

def resoudre_toggle(company, feature_key):
    """``True``/``False`` si la société a un avis, ``None`` sinon.

    ``None`` (aucune ligne) laisse la feature ACTIVE : le refus est toujours
    explicite."""
    from .models import AiFeatureToggle

    if company is None:
        return None
    filtre = ({'company_id': company} if isinstance(company, int)
              else {'company': company})
    ligne = AiFeatureToggle.objects.filter(
        feature_key=feature_key, **filtre).only('actif').first()
    return None if ligne is None else ligne.actif


def connect_feature_toggles():
    """Branche le résolveur de consentement (appelé par ``apps.py``)."""
    from core.ai.services import register_feature_toggle_resolver

    register_feature_toggle_resolver(resoudre_toggle)


# ─────────────────────────────────────────────────────────────────────────────
# Versions immuables
# ─────────────────────────────────────────────────────────────────────────────

def figer_version(gabarit, *, user=None):
    """Fige le corps courant de ``gabarit`` dans une nouvelle version.

    Le numéro est attribué CÔTÉ SERVEUR (dernier + 1). Ne fige rien si le
    corps est identique à la dernière version — l'historique raconte les
    CHANGEMENTS, pas les enregistrements."""
    from .models import PromptTemplateVersion

    derniere = (PromptTemplateVersion.objects
                .filter(template=gabarit).order_by('-numero').first())
    if derniere is not None and derniere.corps == gabarit.corps:
        return derniere
    numero = (derniere.numero + 1) if derniere else 1
    return PromptTemplateVersion.objects.create(
        company=gabarit.company, template=gabarit, numero=numero,
        corps=gabarit.corps, cree_par=user)


# ─────────────────────────────────────────────────────────────────────────────
# Vue « prompts effectifs » (code + surcharges)
# ─────────────────────────────────────────────────────────────────────────────

def prompts_effectifs(company) -> list:
    """Pour chaque clé connue du code : le corps EFFECTIF et son origine.

    C'est ce que l'écran de paramétrage affiche : la liste exhaustive de ce
    qu'une société peut surcharger, et ce qui s'applique réellement
    aujourd'hui."""
    from core.ai.prompts import available_prompts, effective_prompt, placeholders

    lignes = []
    for cle in available_prompts():
        corps, origine = effective_prompt(company, cle)
        lignes.append({
            'cle': cle,
            'corps': corps,
            'origine': origine,
            'placeholders': placeholders(corps),
        })
    return lignes


# ─────────────────────────────────────────────────────────────────────────────
# Défauts CODE des features de cette app
# ─────────────────────────────────────────────────────────────────────────────

def enregistrer_defauts():
    """Déclare les défauts code des copilotes (appelé par ``apps.py``).

    Ces textes existaient déjà en constantes de module ; ils deviennent le
    « défaut » de la bibliothèque, sans changer une virgule de leur contenu —
    une société qui ne surcharge rien obtient exactement le même prompt
    qu'avant."""
    from core.ai.prompts import register_default_prompt

    from . import services

    register_default_prompt('ai.description_produit.system',
                            services.PRODUIT_DESCRIPTION_SYSTEM)
    register_default_prompt('ai.cr_intervention.system', services.CR_SYSTEM)
    register_default_prompt('ai.rapport_periode.system',
                            services.RAPPORT_SYSTEM)
    register_default_prompt('ai.assistant_config.system',
                            services.ASSISTANT_CONFIG_SYSTEM)
    register_default_prompt('ai.recherche_globale.system',
                            services.RECHERCHE_GLOBALE_SYSTEM)
    for canal, consigne in services.REDACTION_CONSIGNE_CANAL.items():
        register_default_prompt(f'ai.rediger.{canal}', consigne)
