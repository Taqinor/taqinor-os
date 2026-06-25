"""AG1 — Registre d'actions agentiques (catalogue déclaré en code).

Ce module ne contient AUCUN modèle de base de données : les actions que
l'agent (relais FastAPI + JWT utilisateur) peut proposer sont déclarées en
code via :class:`AgentAction` et enregistrées dans un registre de niveau
module avec :func:`register`. :func:`for_user` renvoie le sous-ensemble que
l'utilisateur courant a le droit d'exécuter (permission- et société-aware).

Le catalogue est PUREMENT des métadonnées : aucune exécution ici. L'exécution
garde le motif existant — FastAPI relaie le JWT de l'utilisateur vers
l'``endpoint`` nommé, et Django re-vérifie la permission + la société à ce
moment-là. Ce module ne fait que dire à l'agent ce qui EST possible pour le
caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Niveaux de risque d'une action — utilisés par l'UI/l'agent pour décider
# s'il faut demander une confirmation avant d'exécuter.
RISK_INTERNAL = 'internal'        # effet interne seulement (lecture/écriture interne)
RISK_OUTWARD = 'outward'          # effet visible à l'extérieur (email, PDF client…)
RISK_IRREVERSIBLE = 'irreversible'  # destructif / non réversible (suppression…)

RISK_CHOICES = frozenset({RISK_INTERNAL, RISK_OUTWARD, RISK_IRREVERSIBLE})


@dataclass(frozen=True)
class AgentAction:
    """Descripteur immuable d'une action que l'agent peut proposer.

    Champs :
      * ``key`` — identifiant stable et unique de l'action.
      * ``label`` — libellé court lisible (FR).
      * ``description`` — description en langage clair de ce que fait l'action.
      * ``inputs`` — JSON Schema (dict) décrivant les paramètres attendus.
      * ``endpoint`` — gabarit de chemin de l'endpoint cible (ex.
        ``/api/django/ventes/devis/{id}/proposal/``).
      * ``method`` — verbe HTTP (GET/POST/PATCH/DELETE…).
      * ``required_permission`` — code de permission ERP requis (ou ``None``
        pour « tout utilisateur authentifié »). Voir
        ``apps.roles.models.ALL_PERMISSIONS``.
      * ``risk`` — ``internal`` | ``outward`` | ``irreversible``.
      * ``confirm_summary`` — résumé optionnel à montrer avant exécution.
    """

    key: str
    label: str
    description: str
    endpoint: str
    method: str = 'GET'
    inputs: Dict[str, Any] = field(default_factory=dict)
    required_permission: Optional[str] = None
    risk: str = RISK_INTERNAL
    confirm_summary: Optional[str] = None

    def __post_init__(self) -> None:
        if self.risk not in RISK_CHOICES:
            raise ValueError(
                f"AgentAction {self.key!r}: risk {self.risk!r} invalide "
                f"(attendu l'un de {sorted(RISK_CHOICES)})"
            )
        if not self.key:
            raise ValueError('AgentAction: key est obligatoire')

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable (catalogue exposé par l'API)."""
        return {
            'key': self.key,
            'label': self.label,
            'description': self.description,
            'inputs': self.inputs,
            'endpoint': self.endpoint,
            'method': self.method.upper(),
            'required_permission': self.required_permission,
            'risk': self.risk,
            'confirm_summary': self.confirm_summary,
        }


# Registre de niveau module — source unique de vérité du catalogue.
_REGISTRY: "Dict[str, AgentAction]" = {}


def register(action: AgentAction) -> AgentAction:
    """Enregistre une action dans le registre global.

    Lève ``ValueError`` si la ``key`` est déjà prise (les clés sont uniques).
    Retourne l'action pour permettre un usage en expression.
    """
    if not isinstance(action, AgentAction):
        raise TypeError('register() attend un AgentAction')
    if action.key in _REGISTRY:
        raise ValueError(f"Action déjà enregistrée : {action.key!r}")
    _REGISTRY[action.key] = action
    return action


def unregister(key: str) -> None:
    """Retire une action du registre (utile pour les tests)."""
    _REGISTRY.pop(key, None)


def all_actions() -> List[AgentAction]:
    """Toutes les actions enregistrées, triées par clé (déterministe)."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def _user_may_run(user, action: AgentAction) -> bool:
    """L'utilisateur a-t-il le droit d'exécuter cette action ?

    Reproduit la sémantique des permissions ERP existantes
    (``CustomUser.has_erp_permission``) : superuser → tout ; sinon il faut
    porter le code de permission requis. Une action sans
    ``required_permission`` est ouverte à tout utilisateur authentifié.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if action.required_permission is None:
        return True
    has_perm = getattr(user, 'has_erp_permission', None)
    if not callable(has_perm):
        return False
    return bool(has_perm(action.required_permission))


def for_user(user) -> List[AgentAction]:
    """Sous-ensemble du catalogue que ``user`` a le droit d'exécuter.

    Filtre par permission (et donc, via le rôle/société de l'utilisateur, de
    façon société-aware : un utilisateur ne porte de permissions qu'au travers
    d'un rôle rattaché à SA société). L'endpoint cible re-vérifie permission +
    société à l'exécution — ce filtre n'est qu'un premier garde-fou côté
    catalogue.
    """
    return [a for a in all_actions() if _user_may_run(user, a)]


def _register_builtin_actions() -> None:
    """Enregistre le catalogue d'actions livré par défaut.

    Idempotent : ne ré-enregistre pas une action déjà présente (sûr si le
    module est importé plusieurs fois). Permissions tirées de
    ``apps.roles.models.ALL_PERMISSIONS``.
    """
    builtins = [
        # FG351 — Actions d'ÉCRITURE en langage naturel (« crée un devis pour… »,
        # « ajoute un lead… », « crée le client… »). Ce sont des écritures
        # GARDÉES : `risk=RISK_OUTWARD` force le motif propose→confirm côté
        # relais FastAPI (l'outil renvoie une PROPOSITION signée à confirmer,
        # il n'exécute JAMAIS directement). Django reste l'autorité finale :
        # permission ERP + société sont re-vérifiées à l'exécution (la société
        # est toujours imposée côté serveur via perform_create, jamais lue du
        # corps fourni par l'agent).
        # NOTE — l'action « créer un devis » VIDE est retirée à dessein : le
        # Copilote crée TOUJOURS un devis dimensionné via l'auto-devis
        # (``ventes.devis.creer_auto`` → POST /ventes/devis/auto/, déclaré dans
        # apps/ventes/agent_actions.py). On n'expose plus de chemin produisant
        # un brouillon à 0 DH.
        AgentAction(
            key='crm.client.create',
            label='Créer un client',
            description=(
                "Crée un nouveau client (fiche contact) pour la société. "
                "L'agent fournit au moins le nom ; le serveur impose la société "
                "et trace le créateur. Écriture sensible : confirmation requise "
                "avant exécution."
            ),
            endpoint='/api/django/crm/clients/',
            method='POST',
            inputs={
                'type': 'object',
                'properties': {
                    'nom': {'type': 'string'},
                    'prenom': {'type': 'string'},
                    'email': {'type': 'string'},
                    'telephone': {'type': 'string'},
                    'adresse': {'type': 'string'},
                    'type_client': {'type': 'string'},
                },
                'required': ['nom'],
            },
            required_permission='crm_creer',
            risk=RISK_OUTWARD,
            confirm_summary='Créer la fiche client.',
        ),
        AgentAction(
            key='crm.lead.create',
            label='Créer un lead',
            description=(
                "Crée un nouveau lead (opportunité) pour la société. L'agent "
                "fournit au moins le nom ; le serveur impose la société et le "
                "propriétaire. Écriture sensible : confirmation requise avant "
                "exécution."
            ),
            endpoint='/api/django/crm/leads/',
            method='POST',
            inputs={
                'type': 'object',
                'properties': {
                    'nom': {'type': 'string'},
                    'prenom': {'type': 'string'},
                    'email': {'type': 'string'},
                    'telephone': {'type': 'string'},
                    'ville': {'type': 'string'},
                    'source': {'type': 'string'},
                },
                'required': ['nom'],
            },
            required_permission='crm_creer',
            risk=RISK_OUTWARD,
            confirm_summary='Créer le lead.',
        ),
        AgentAction(
            key='ventes.devis.proposal_pdf',
            label='Générer le PDF de proposition',
            description=(
                "Génère le PDF client (premium) d'un devis via /proposal — "
                "l'unique chemin de PDF de devis destiné au client."
            ),
            endpoint='/api/django/ventes/devis/{id}/proposal/',
            method='GET',
            inputs={
                'type': 'object',
                'properties': {'id': {'type': 'integer'}},
                'required': ['id'],
            },
            required_permission='ventes_pdf',
            risk=RISK_OUTWARD,
            confirm_summary='Produire le PDF de devis destiné au client.',
        ),
        AgentAction(
            key='crm.lead.list',
            label='Lister les leads',
            description='Liste les leads (opportunités) de la société.',
            endpoint='/api/django/crm/leads/',
            method='GET',
            inputs={'type': 'object', 'properties': {}},
            required_permission='crm_voir',
            risk=RISK_INTERNAL,
        ),
        AgentAction(
            key='stock.produit.delete',
            label='Supprimer un produit',
            description='Supprime définitivement un produit du catalogue.',
            endpoint='/api/django/stock/produits/{id}/',
            method='DELETE',
            inputs={
                'type': 'object',
                'properties': {'id': {'type': 'integer'}},
                'required': ['id'],
            },
            required_permission='stock_supprimer',
            risk=RISK_IRREVERSIBLE,
            confirm_summary='Suppression irréversible du produit.',
        ),
    ]
    for action in builtins:
        if action.key not in _REGISTRY:
            _REGISTRY[action.key] = action


_register_builtin_actions()
