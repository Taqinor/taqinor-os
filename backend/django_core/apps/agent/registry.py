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

# Carte de résultat — indice de RENDU posé par l'action (contrat
# ``contract_samples/assistant_reponse.json``). Ensemble FERMÉ : l'écran ne sait
# rendre que ces cartes (« catalogue contrôlé », jamais une interface écrite par
# le modèle). ``None`` = carte générique « Action effectuée ». Le relais FastAPI
# recopie cette valeur telle quelle dans ``cartes[].carte`` ; ``donnees`` y est
# le corps JSON de l'endpoint de l'action, sans remise en forme.
CARTES = frozenset({
    'liste_leads',    # recherche de leads : {total, limite, lignes[]}
    'file_touches',   # file de suivi : {portee, total, limite, lignes[]}
    'matin',          # digest du matin : {relances, visites, devis_sans_reponse, …}
    'fiche_lead',     # résumé d'un lead : {identite, etape, chatter[], devis[], …}
    'touche',         # une touche prête : {touche, lead, message|appel, refus}
    'suite_touche',   # touche traitée : étape + prochaine_touche
    'wa_message',     # texte prêt + lien wa.me (brouillon de suivi)
    'wa_devis',       # envoi de devis : {wa_url, message, links[], lead_id, devis_ids}
    'document',       # lien vers un PDF client (/proposal)
    'visite',         # visite planifiée : {visite, prochaine_touche}
    'diagnostic',     # état technique (admin) : santé, problèmes récents
})

# Lot de déploiement d'une action (interrupteur ``ASSISTANT_COPILOTE`` lu par
# :func:`for_user`) : ``None`` = toujours au catalogue ; ``copilote`` = servie
# seulement aux comptes pour qui le copilote commercial est ALLUMÉ ; ``herite``
# = servie seulement tant qu'il est ÉTEINT pour le compte (ancien outil que le
# copilote remplace). Un outil neuf vu par le modèle change le comportement de
# production au merge : il naît dans le lot ``copilote``, jamais hors lot.
LOT_COPILOTE = 'copilote'
LOT_HERITE = 'herite'
LOTS = frozenset({LOT_COPILOTE, LOT_HERITE})

# Types d'objets métier qu'une entrée d'action peut désigner (champ ``objets``),
# résolus en libellés par ``GET /api/django/agent/libelles/`` (contrat
# ``contract_samples/assistant_libelles.json``).
OBJETS = frozenset({'lead', 'devis', 'touche', 'facture', 'client'})


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
      * ``carte`` — carte de résultat à rendre (clé de :data:`CARTES`), ou
        ``None`` pour la carte générique.
      * ``lot`` — lot de déploiement (clé de :data:`LOTS`) ou ``None``.
      * ``objets`` — ``{nom d'entrée: type d'objet}`` (types de
        :data:`OBJETS`) : quelles entrées désignent un objet métier. Le relais
        s'en sert pour NOMMER l'objet dans l'aperçu d'une proposition
        (« Accepter un devis — DEV-202611-0045, Benali » au lieu de « id=45 »).
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
    carte: Optional[str] = None
    lot: Optional[str] = None
    objets: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.risk not in RISK_CHOICES:
            raise ValueError(
                f"AgentAction {self.key!r}: risk {self.risk!r} invalide "
                f"(attendu l'un de {sorted(RISK_CHOICES)})"
            )
        if not self.key:
            raise ValueError('AgentAction: key est obligatoire')
        if self.carte is not None and self.carte not in CARTES:
            raise ValueError(
                f"AgentAction {self.key!r}: carte {self.carte!r} inconnue "
                f"(attendu l'une de {sorted(CARTES)})"
            )
        if self.lot is not None and self.lot not in LOTS:
            raise ValueError(
                f"AgentAction {self.key!r}: lot {self.lot!r} inconnu "
                f"(attendu l'un de {sorted(LOTS)})"
            )
        inconnus = sorted(set(self.objets.values()) - OBJETS)
        if inconnus:
            raise ValueError(
                f"AgentAction {self.key!r}: objets {inconnus!r} inconnus "
                f"(attendu parmi {sorted(OBJETS)})"
            )

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
            'carte': self.carte,
            'lot': self.lot,
            'objets': dict(self.objets),
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


# ── ARC33 — auto-découverte des actions agent depuis les manifestes ─────────
# ``apps/<x>/platform.py`` (surface ``agent_actions_module``, ARC28). Avant
# ARC33, brancher une app sur l'agent exigeait un ``agent_actions.py`` PLUS un
# appel explicite dans son ``AppConfig.ready()`` (5 apps sur 35 l'avaient).
# Désormais : déclarer le module dotted dans le manifeste suffit —
# :func:`autodiscover_from_platform_manifests` (appelé par
# ``AgentConfig.ready()``) importe le module et appelle sa fonction
# ``register_actions()`` (convention, idempotente). Les clés ainsi découvertes
# sont ATTRIBUÉES à leur module dotted (``_DISCOVERED``) pour le gatage
# ``ModuleToggle`` (ODX23) : un module OFF pour la société disparaît du
# catalogue ``for_user``. Les 5 apps historiques qui s'enregistrent encore
# depuis leur propre ``ready()`` ne sont PAS attribuées (leur fonction ne suit
# pas la convention) → leur comportement reste STRICTEMENT identique
# (non-régression) ; elles migreront vers le manifeste à leur rythme.
_DISCOVERED: "Dict[str, set]" = {}


def autodiscover_from_platform_manifests() -> None:
    """Importe et enregistre les actions agent déclarées par les manifestes.

    Pour chaque manifeste ``core.platform`` dont ``agent_actions_module`` est
    non vide : importe le module dotted, appelle sa fonction
    ``register_actions()`` si elle existe (convention — idempotente, comme les
    enregistrements historiques), et attribue au module les clés NOUVELLES
    apparues dans le registre pendant l'appel (union sur ré-appels : un
    ``ready()`` ré-exécuté n'efface jamais une attribution).

    Idempotente et sûre à l'import : un module déjà importé est réutilisé
    (cache d'import Python) ; une fonction ``register_actions`` absente est un
    no-op silencieux (cas des apps historiques à convention de nom propre,
    ex. ``register_crm_actions`` — elles restent branchées par leur propre
    ``AppConfig.ready()``).
    """
    import importlib

    from core import platform as core_platform

    for manifest in core_platform.collect_platform_manifests().values():
        dotted = manifest.get('agent_actions_module')
        if not dotted:
            continue
        mod = importlib.import_module(dotted)
        avant = set(_REGISTRY)
        fn = getattr(mod, 'register_actions', None)
        if callable(fn):
            fn()
        nouvelles = set(_REGISTRY) - avant
        _DISCOVERED.setdefault(dotted, set()).update(nouvelles)


def _hidden_keys_for(user) -> set:
    """Clés d'actions masquées pour ``user`` par le gatage ``ModuleToggle``.

    Une action DÉCOUVERTE (attribuée à un ``agent_actions_module`` de
    manifeste) est masquée quand son module n'est plus visible pour la société
    de l'utilisateur (``core.platform.agent_actions_modules(company)`` — un
    module OFF disparaît de toutes les surfaces, ODX23/ARC28). Les actions non
    attribuées (builtins + enregistrements historiques hors manifeste) ne sont
    jamais masquées ici (comportement d'avant ARC33 préservé)."""
    if not _DISCOVERED:
        return set()
    company = getattr(user, 'company', None)
    if company is None:
        return set()
    from core import platform as core_platform

    visibles = core_platform.agent_actions_modules(company)
    hidden: set = set()
    for dotted, keys in _DISCOVERED.items():
        if dotted not in visibles:
            hidden.update(keys)
    return hidden


def copilote_allume_pour(user) -> bool:
    """Le copilote commercial est-il ALLUMÉ pour ``user`` (COP-G1) ?

    Lit le réglage Django ``ASSISTANT_COPILOTE`` : ``tous`` → allumé pour tout
    compte ; ``admins`` (défaut) → seulement pour un administrateur (même
    critère que les vues de l'agent : ``is_admin_role``, superuser compris) ;
    ``aucun`` ou toute AUTRE valeur (faute de frappe, chaîne vide) → éteint —
    un interrupteur mal écrit ne doit jamais allumer un outil que le modèle
    voit."""
    from django.conf import settings

    mode = str(getattr(settings, 'ASSISTANT_COPILOTE', 'admins') or '')
    mode = mode.strip().lower()
    if mode == 'tous':
        return True
    if mode == 'admins':
        return bool(getattr(user, 'is_admin_role', False))
    return False


def _lot_servi(action: AgentAction, copilote: bool) -> bool:
    """Le lot de déploiement de ``action`` est-il servi selon l'interrupteur ?"""
    if action.lot == LOT_COPILOTE:
        return copilote
    if action.lot == LOT_HERITE:
        return not copilote
    return True


def for_user(user) -> List[AgentAction]:
    """Sous-ensemble du catalogue que ``user`` a le droit d'exécuter.

    Filtre par permission (et donc, via le rôle/société de l'utilisateur, de
    façon société-aware : un utilisateur ne porte de permissions qu'au travers
    d'un rôle rattaché à SA société). L'endpoint cible re-vérifie permission +
    société à l'exécution — ce filtre n'est qu'un premier garde-fou côté
    catalogue.

    ARC33 — les actions AUTO-DÉCOUVERTES d'un module ``ModuleToggle``-OFF pour
    la société du caller sont absentes du catalogue (gatage par société,
    quel que soit le rôle — même sémantique que la recherche globale).

    COP-G1 — l'interrupteur ``ASSISTANT_COPILOTE`` (:func:`copilote_allume_pour`)
    sert le lot ``copilote`` seulement s'il est allumé pour ce compte et le lot
    ``herite`` seulement s'il est éteint. Tout appelant (catalogue, confirmation
    d'une action) passe par cette fonction : la règle n'existe qu'ici.
    """
    hidden = _hidden_keys_for(user)
    copilote = copilote_allume_pour(user)
    return [
        a for a in all_actions()
        if a.key not in hidden and _lot_servi(a, copilote)
        and _user_may_run(user, a)
    ]


def _register_builtin_actions() -> None:
    """Enregistre le catalogue d'actions livré par défaut.

    Idempotent : ne ré-enregistre pas une action déjà présente (sûr si le
    module est importé plusieurs fois). Permissions tirées de
    ``apps.roles.models.ALL_PERMISSIONS``.
    """
    builtins = [
        # FG351 — Action d'ÉCRITURE en langage naturel (« crée le client… »).
        # Écriture GARDÉE : `risk=RISK_OUTWARD` force le motif propose→confirm
        # côté relais FastAPI (l'outil renvoie une PROPOSITION signée à
        # confirmer, il n'exécute JAMAIS directement). Django reste l'autorité
        # finale : permission ERP + société sont re-vérifiées à l'exécution (la
        # société est toujours imposée côté serveur via perform_create, jamais
        # lue du corps fourni par l'agent).
        # COP-G2 — retirés du catalogue : ``crm.lead.create`` (doublon masqué :
        # la déclaration de ``apps/crm/agent_actions.py`` est la seule) et
        # ``ventes.devis.proposal_pdf`` (même route /proposal que
        # ``ventes.devis.generer_pdf``, déclarée dans ``apps/ventes``). L'action
        # « créer un devis » VIDE reste retirée à dessein : le Copilote crée
        # TOUJOURS un devis dimensionné via l'auto-devis
        # (``ventes.devis.creer_auto`` → POST /ventes/devis/auto/). On n'expose
        # plus de chemin produisant un brouillon à 0 DH.
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
        # FG352 — Outil de RÉCUPÉRATION RAG / DocQA. Action de LECTURE pure
        # (risk=internal) : renvoie les passages de documents/manuels les plus
        # proches d'une question, scopés société + ACL coffre-fort côté serveur.
        # KEY-GATED : sans clé d'embedding, l'endpoint renvoie `enabled=false` et
        # une liste vide (no-op propre, aucun coût). Aucune permission ERP requise
        # ici — l'endpoint GED re-vérifie le rôle + la société à l'exécution.
        AgentAction(
            key='ged.docqa.retrieve',
            label='Rechercher dans les documents (DocQA)',
            description=(
                "Récupère les passages de documents et manuels les plus "
                "pertinents pour une question (RAG sémantique sur le magasin "
                "pgvector). Lecture seule, scopée à la société et à l'ACL "
                "coffre-fort de l'utilisateur. Sans clé d'embedding configurée, "
                "renvoie un résultat vide (fonctionnalité désactivée)."
            ),
            endpoint='/api/django/ged/documents/docqa/',
            method='GET',
            inputs={
                'type': 'object',
                'properties': {
                    'q': {'type': 'string'},
                    'k': {'type': 'integer'},
                },
                'required': ['q'],
            },
            required_permission=None,
            risk=RISK_INTERNAL,
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
            # COP-G2 — outil sans entrée, remplacé par ``crm.lead.chercher``
            # (lot copilote) : servi seulement tant que le copilote est éteint.
            lot=LOT_HERITE,
        ),
        # XPLT18 — Proposer une règle d'automatisation en langage naturel.
        # Le LLM produit un brouillon STRUCTURÉ (trigger_type/action_type du
        # catalogue FERMÉ apps.automation.models.TriggerType/ActionType —
        # jamais de code libre), présenté propose→confirm (risk=outward). La
        # règle créée est TOUJOURS désactivée (revue admin) — voir
        # apps.automation.services.create_draft_rule_from_agent, qui
        # re-valide le brouillon contre le catalogue fermé côté serveur.
        AgentAction(
            key='automation.rule.propose_draft',
            label="Proposer une règle d'automatisation",
            description=(
                "Crée un brouillon de règle d'automatisation (si/alors) à "
                "partir d'une description en langage naturel. Le "
                "déclencheur et l'action doivent appartenir au catalogue "
                "fermé existant (jamais de code libre). La règle est "
                "TOUJOURS créée désactivée : elle attend une revue admin "
                "dans Paramètres → Automatisations avant de pouvoir "
                "s'exécuter."
            ),
            endpoint='/api/django/agent/actions/automation-draft/',
            method='POST',
            inputs={
                'type': 'object',
                'properties': {
                    'nom': {'type': 'string'},
                    'trigger_type': {'type': 'string'},
                    'trigger_config': {'type': 'object'},
                    'action_type': {'type': 'string'},
                    'action_config': {'type': 'object'},
                },
                'required': ['nom', 'trigger_type', 'action_type'],
            },
            # COP-G2 — la route est ``IsAdminRole`` (``roles_gerer``, le critère
            # d'administrateur) : la permission du catalogue suit la garde réelle
            # (offerte à un commercial, elle répondait toujours 403).
            required_permission='roles_gerer',
            risk=RISK_OUTWARD,
            confirm_summary=(
                "Créer un brouillon de règle d'automatisation (désactivée, "
                "à valider par un administrateur)."),
        ),
        # COP-G6 — diagnostic pour l'ADMINISTRATEUR (« qu'est-ce qui a cassé
        # hier ? », « l'assistant marche-t-il ? ») : lecture seule de
        # ``reporting/assistant/diagnostic/`` (problèmes de SA société, santé de
        # la plateforme pour un super-utilisateur, journal de l'assistant).
        # Neuve : lot ``copilote`` (le modèle ne la voit que copilote allumé) ;
        # ``roles_gerer`` = le critère d'administrateur de la route (``IsAdminRole``).
        AgentAction(
            key='reporting.assistant.diagnostic',
            label="Diagnostic de l'ERP et de l'assistant",
            description=(
                "Sert à : dire ce qui a cassé récemment dans l'ERP (problèmes "
                "vécus par les utilisateurs de la société, regroupés), l'état "
                "de l'assistant (erreurs, repli, coût) et ses signalements "
                "récents. Ne pas utiliser pour : une question métier (leads, "
                "devis) ni une panne que tu peux voir à l'écran. Exemple : "
                "« qu'est-ce qui a cassé hier ? » → jours=1. Résultat : "
                "problèmes, assistant, signalements ; administrateurs seulement."
            ),
            endpoint='/api/django/reporting/assistant/diagnostic/',
            method='GET',
            inputs={
                'type': 'object',
                'properties': {
                    'jours': {
                        'type': 'integer',
                        'description': 'Fenêtre en jours, de 1 à 7 (défaut 1 : hier).',
                    },
                },
            },
            required_permission='roles_gerer',
            risk=RISK_INTERNAL,
            carte='diagnostic',
            lot=LOT_COPILOTE,
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
