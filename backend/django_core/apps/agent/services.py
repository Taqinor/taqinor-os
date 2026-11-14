"""YHARD2 — services d'écriture pour le journal des actions IA confirmées.

Deux responsabilités :

  * :func:`log_confirmed_action` — appelée au moment où une action proposée
    par l'agent est CONFIRMÉE par l'utilisateur (jamais à la simple
    proposition, qui reste éphémère côté agent/Redis, hors périmètre ici).
    Crée une ``AgentActionLog`` scopée société, avec la cible résultante si
    fournie ;
  * :func:`annuler_action` — pour une action réversible (``risk_level`` !=
    ``irreversible``) non déjà annulée, inverse son effet en appelant un
    HANDLER DE ROLLBACK enregistré par la clé d'action, puis marque
    ``undone_at``. Refuse toute action irréversible ou déjà annulée.

Aucune app métier n'est importée ICI (satellite technique, jamais importé par
une app de domaine) : un handler de rollback est du code appartenant à l'app
métier concernée, enregistré dans ce module via :func:`register_undo_handler`
— exactement le même motif que ``apps.agent.registry`` (registre en mémoire,
alimenté par les apps qui en ont besoin, jamais l'inverse).
"""
from __future__ import annotations

import logging
import hashlib
import hmac
import json
import os
import re
import unicodedata
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.utils import timezone

from .models import AgentActionLog

logger = logging.getLogger(__name__)

# Registre des handlers de rollback, indexé par action_key. Chaque handler est
# une fonction ``(log: AgentActionLog) -> str`` qui inverse l'effet de
# l'action et renvoie un court détail texte (journalisé dans ``undo_detail``).
# Alimenté par les apps métier via :func:`register_undo_handler` (jamais
# l'inverse — cette app reste dépendance-descendante uniquement).
_UNDO_HANDLERS: Dict[str, Callable[[AgentActionLog], str]] = {}


def register_undo_handler(action_key: str, handler: Callable[[AgentActionLog], str]):
    """Enregistre (idempotent — dernier appel gagne) un handler de rollback
    pour ``action_key``. Utilisable comme fonction directe ou décorateur."""
    _UNDO_HANDLERS[action_key] = handler
    return handler


def has_undo_handler(action_key: str) -> bool:
    return action_key in _UNDO_HANDLERS


class ActionNotUndoableError(Exception):
    """Levée quand l'annulation est refusée (irréversible / déjà annulée /
    aucun handler enregistré)."""


# ── AANA18 — preuve qu'une confirmation a REELLEMENT ete emise par l'agent ────
# C-AANA-008 : ``POST /agent/logs/confirmer/`` acceptait n'importe quel corps
# d'un utilisateur authentifie. Un compte SANS ``crm_creer`` forgeait un journal
# ``crm.client.create`` pointant sur un client PREEXISTANT ; l'annulation par un
# admin SUPPRIMAIT ensuite ce client (sonde du 05/10 : 201 puis suppression).
# Desormais le relais FastAPI signe, APRES l'execution reelle, une preuve HMAC
# avec un secret partage (``AGENT_HMAC_SECRET``, jamais expose au navigateur) ;
# Django la recalcule pour l'utilisateur et la societe de LA REQUETE. Sans
# secret configure : toute confirmation est refusee (fail-closed). Format
# canonique (identique des deux cotes, verifie par le contrat
# ``contract_samples/logs_confirmer.json``) : JSON trie, compact, UTF-8 de
# {v, action_key, company_id, user_id, inputs, object_id} ; HMAC-SHA256 hex.
PREUVE_VERSION = 1


def agent_hmac_secret() -> str:
    """Secret partage Django <-> FastAPI ('' si non configure)."""
    return (getattr(settings, 'AGENT_HMAC_SECRET', '')
            or os.environ.get('AGENT_HMAC_SECRET', '') or '')


def message_preuve_confirmation(*, action_key: str, company_id: int,
                                user_id: int, inputs: Optional[Dict[str, Any]],
                                object_id: Any) -> str:
    """Message canonique signe (meme octets que cote FastAPI)."""
    return json.dumps(
        {
            'v': PREUVE_VERSION,
            'action_key': action_key,
            'company_id': int(company_id),
            'user_id': int(user_id),
            'inputs': inputs or {},
            'object_id': '' if object_id in (None, '') else str(object_id),
        },
        sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    )


def calculer_preuve_confirmation(*, secret: str, **champs) -> str:
    return hmac.new(
        secret.encode('utf-8'),
        message_preuve_confirmation(**champs).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def preuve_confirmation_valide(preuve: Any, **champs) -> bool:
    """True si ``preuve`` est la signature de ces champs par le secret partage.
    Fail-closed : secret absent, preuve absente ou mal formee -> False."""
    secret = agent_hmac_secret()
    if not secret or not isinstance(preuve, str) or not preuve:
        return False
    try:
        attendue = calculer_preuve_confirmation(secret=secret, **champs)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(preuve, attendue)


def log_confirmed_action(
    *, company, user, action_key: str, risk_level: str,
    inputs: Optional[Dict[str, Any]] = None, proposal_hash: str = '',
    proposed_at=None, resulted_object=None,
) -> AgentActionLog:
    """Journalise la confirmation d'une action IA (société forcée par
    l'appelant — jamais déduite du corps de requête). ``resulted_object`` est
    l'instance créée/modifiée par l'action, si connue au moment de l'appel
    (content_type + object_id + repr dérivés automatiquement)."""
    content_type = None
    object_id = ''
    object_repr = ''
    if resulted_object is not None:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(resulted_object.__class__)
        object_id = str(getattr(resulted_object, 'pk', '') or '')
        try:
            object_repr = str(resulted_object)[:255]
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
            logger.warning("services.log_confirmed_action : erreur ignorée (mode dégradé)", exc_info=True)
            object_repr = ''

    return AgentActionLog.objects.create(
        company=company,
        user=user if (user and getattr(user, 'is_authenticated', False)) else None,
        action_key=action_key,
        risk_level=risk_level,
        proposal_hash=proposal_hash or '',
        inputs_json=inputs or {},
        proposed_at=proposed_at,
        executed_at=timezone.now(),
        content_type=content_type,
        object_id=object_id,
        object_repr=object_repr,
    )


def annuler_action(log: AgentActionLog, *, user=None) -> AgentActionLog:
    """Annule une action réversible. Lève :class:`ActionNotUndoableError` si
    l'action est irréversible, déjà annulée, ou sans handler enregistré pour
    sa ``action_key`` (fail-closed — jamais un no-op silencieux qui ferait
    croire à un rollback qui n'a pas eu lieu)."""
    if log.risk_level == AgentActionLog.RiskLevel.IRREVERSIBLE:
        raise ActionNotUndoableError(
            f"L'action « {log.action_key} » est irréversible — annulation refusée.")
    if log.is_undone:
        raise ActionNotUndoableError(
            f"L'action « {log.action_key} » (log #{log.pk}) a déjà été annulée.")

    handler = _UNDO_HANDLERS.get(log.action_key)
    if handler is None:
        raise ActionNotUndoableError(
            f"Aucun handler de rollback enregistré pour « {log.action_key} ».")

    detail = handler(log) or ''
    log.undone_at = timezone.now()
    log.undo_detail = detail
    log.save(update_fields=['undone_at', 'undo_detail'])
    return log


# ── AIC11 — anonymisation de l'export des événements (contrat AIC2) ──────────
# Règles écrites UNE fois dans ``contract_samples/assistant_export.json`` (clé
# ``anonymisation``) ; ce nettoyeur PUR les applique dans l'ordre déclaré :
# téléphones, puis e-mails, puis noms, puis suites de ≥ 6 chiffres.
_TELEPHONE = re.compile(r'(?<![\w+])\+?\d(?:[ .\-]?\d){8,}(?!\w)')
_EMAIL = re.compile(r'[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+')
_SUITE_CHIFFRES = re.compile(r'\d{6,}')


def _replier(caractere: str) -> str:
    """Un caractère -> sa forme sans accent, minuscule (longueur 1 conservée)."""
    base = ''.join(c for c in unicodedata.normalize('NFD', caractere)
                   if not unicodedata.combining(c))
    return (base[:1] or caractere).lower()


def anonymiser_texte(texte, noms=()) -> str:
    """Nettoie ``texte`` : téléphones -> [tel], e-mails -> [email], ``noms``
    (nom/prénom du lead ou du client, insensible à la casse et aux accents)
    -> [client], suites de ≥ 6 chiffres -> [num]. Fonction pure."""
    if not texte:
        return texte
    texte = _TELEPHONE.sub('[tel]', str(texte))
    texte = _EMAIL.sub('[email]', texte)
    for nom in sorted({n.strip() for n in noms if n and len(n.strip()) >= 2},
                      key=len, reverse=True):
        replie = ''.join(_replier(c) for c in texte)
        cible = ''.join(_replier(c) for c in nom)
        morceaux, debut = [], 0
        for m in re.finditer(r'(?<!\w)' + re.escape(cible) + r'(?!\w)', replie):
            morceaux.append(texte[debut:m.start()] + '[client]')
            debut = m.end()
        texte = ''.join(morceaux) + texte[debut:]
    # « Ahmed Benali » -> un seul [client], pas deux.
    texte = re.sub(r'\[client\](?:\s+\[client\])+', '[client]', texte)
    return _SUITE_CHIFFRES.sub('[num]', texte)


def hacher_identifiant(valeur, secret: str) -> str:
    """HMAC-SHA256 hex minuscule de ``str(valeur)`` (clé AGENT_HMAC_SECRET,
    UTF-8) — même secret et même encodage que ``logs_confirmer.json``."""
    return hmac.new(secret.encode('utf-8'), str(valeur).encode('utf-8'),
                    hashlib.sha256).hexdigest()


# ── AIC12 — coût estimé de l'assistant (contrat assistant_stats.json) ────────
# Prix par million de tokens relevés le 27/10/2026 (USD) — constantes NOMMÉES,
# jamais lues du corps. `cache_read` a son propre prix (0,1 × l'entrée).
# Un modèle absent (repli Groq gratuit) coûte 0.
PRIX_MTOK_RELEVE_LE = '2026-10-27'
# COP-G5 — ``cache_write`` = ÉCRITURE de cache d'une heure (2 × l'entrée, la
# durée que prend le relais : le manuel est mis en cache 1 h) ; elle était
# comptée comme du simple « input » et sous-estimait le coût.
PRIX_MTOK_USD = {
    'claude-sonnet-5-5': {'input': 2.0, 'output': 10.0, 'cache_read': 0.10,
                          'cache_write': 4.0},
    'claude-haiku-5-5': {'input': 0.10, 'output': 0.50, 'cache_read': 0.01,
                         'cache_write': 0.20},
}
#: Clés de ``AssistantEvent.tokens`` (les seules écrites, les autres sont écartées).
CHAMPS_TOKENS = ('cache_read', 'cache_write', 'input', 'output')


def cout_estime_usd(modele: str, tokens: dict) -> float:
    """Σ tokens × prix ÷ 1 000 000 pour UN modèle (0 si modèle non tarifé)."""
    prix = PRIX_MTOK_USD.get(modele or '')
    if not prix or not isinstance(tokens, dict):
        return 0.0
    return sum(int(tokens.get(cle) or 0) * prix[cle]
               for cle in CHAMPS_TOKENS) / 1_000_000


# ── COP-G5 — erreur d'un événement et tampon technique du navigateur ─────────
# L'événement porte ``erreur = {status, outil, message, request_id?,
# diagnostic?}`` ; ``diagnostic`` est le tampon joint par l'écran sur
# « Signaler un problème » (forme du contrat ``assistant_reponse.json`` ->
# ``diagnostic``). Il vient du NAVIGATEUR via le relais : tout est BORNÉ ici
# (nombre d'entrées, longueur des chaînes) et tout champ inconnu est écarté —
# jamais de corps de requête ni de chaîne de requête.
DIAGNOSTIC_MAX_REQUETES = 15
DIAGNOSTIC_MAX_ERREURS = 10


def _texte_borne(valeur, longueur: int, *, sans_requete: bool = False) -> str:
    """Chaîne nettoyée (sans NUL, sans blancs de bord), tronquée à
    ``longueur`` ; ``sans_requete`` coupe à ``?`` / ``#`` (jamais de chaîne de
    requête dans une route). Autre type que ``str`` : chaîne vide."""
    if not isinstance(valeur, str):
        return ''
    texte = valeur.replace(chr(0), '')
    if sans_requete:
        texte = re.split(r'[?#]', texte, maxsplit=1)[0]
    return texte.strip()[:longueur]


def _entier_ou_none(valeur):
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


def _requete_diagnostic(brut):
    return {
        'methode': _texte_borne(brut.get('methode'), 10).upper(),
        'route': _texte_borne(brut.get('route'), 255, sans_requete=True),
        'statut': _entier_ou_none(brut.get('statut')),
        'duree_ms': _entier_ou_none(brut.get('duree_ms')),
        'request_id': _texte_borne(brut.get('request_id'), 64),
        'code': _texte_borne(brut.get('code'), 64),
        'il_y_a_s': _entier_ou_none(brut.get('il_y_a_s')),
    }


def _erreur_diagnostic(brut):
    return {
        'genre': _texte_borne(brut.get('genre'), 40),
        # Un message de script peut citer une saisie : mêmes règles que l'export.
        'message': anonymiser_texte(_texte_borne(brut.get('message'), 255)) or '',
        'il_y_a_s': _entier_ou_none(brut.get('il_y_a_s')),
    }


def _liste_bornee(valeur, maximum: int, fabrique):
    if not isinstance(valeur, list):
        return []
    return [fabrique(x) for x in valeur[:maximum] if isinstance(x, dict)]


def borner_diagnostic(diagnostic):
    """Tampon technique BORNÉ (``None`` si ``diagnostic`` n'est pas un objet) :
    15 requêtes et 10 erreurs au plus, chaînes tronquées, routes sans chaîne de
    requête, tout champ inconnu écarté."""
    if not isinstance(diagnostic, dict):
        return None
    en_ligne = diagnostic.get('en_ligne')
    return {
        'version': _texte_borne(diagnostic.get('version'), 40),
        'ecran': _texte_borne(diagnostic.get('ecran'), 255, sans_requete=True),
        'navigateur': _texte_borne(diagnostic.get('navigateur'), 40),
        'en_ligne': en_ligne if isinstance(en_ligne, bool) else None,
        'requetes': _liste_bornee(
            diagnostic.get('requetes'), DIAGNOSTIC_MAX_REQUETES,
            _requete_diagnostic),
        'erreurs': _liste_bornee(
            diagnostic.get('erreurs'), DIAGNOSTIC_MAX_ERREURS,
            _erreur_diagnostic),
    }


def borner_erreur(erreur):
    """``erreur`` d'un événement réduite à ``{status, outil, message,
    request_id?, diagnostic?}`` (``None`` si ce n'est pas un objet) : champs
    inconnus écartés, chaînes tronquées, ``diagnostic`` borné."""
    if not isinstance(erreur, dict):
        return None
    sortie = {
        'status': _entier_ou_none(erreur.get('status')) or 0,
        'outil': _texte_borne(erreur.get('outil'), 100),
        'message': _texte_borne(erreur.get('message'), 300),
    }
    request_id = _texte_borne(erreur.get('request_id'), 64)
    if request_id:
        sortie['request_id'] = request_id
    diagnostic = borner_diagnostic(erreur.get('diagnostic'))
    if diagnostic is not None:
        sortie['diagnostic'] = diagnostic
    return sortie
