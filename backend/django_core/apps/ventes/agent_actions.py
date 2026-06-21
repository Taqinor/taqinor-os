"""AG4/AG5 — Actions agentiques Ventes (catalogue déclaré en code).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions du flux
devis → bon de commande → facture → encaissement que l'agent (relais FastAPI +
JWT utilisateur) peut PROPOSER. Ce module est PUREMENT des métadonnées : aucune
exécution ici et AUCUN nouvel endpoint — chaque action pointe vers un endpoint
Ventes EXISTANT, qui re-vérifie permission ET société à l'exécution.

Multi-tenant : ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` — la
société est forcée côté serveur (``perform_create`` / l'action de viewset) à
partir de ``request.user.company`` ; elle ne doit jamais provenir du corps.
``creer_devis`` accepte un ``lead`` : le client est alors résolu côté serveur
(``apps.crm.services.resolve_client_for_lead``), jamais dupliqué.

Niveaux de risque (qui pilotent le garde-fou propose→confirm) :
  * AG4 ``creer_devis``        → INTERNAL  (écriture interne, pas d'effet externe)
  * AG4 ``generer_pdf_devis``  → INTERNAL  (rend le PDF, ne change aucun statut)
  * AG4 ``accepter_devis``     → OUTWARD   (marque le devis accepté → chantier)
  * AG5 ``convertir_en_bon_commande`` → OUTWARD (crée le BC du devis accepté)
  * AG5 ``generer_facture``    → OUTWARD   (émet la facture de tranche suivante)
  * AG5 ``enregistrer_paiement`` → IRREVERSIBLE (encaissement comptable, gardé
    par confirmation ; écrit un Paiement scopé société, montant validé > 0)

Permissions : les endpoints du flux devis/facture sont gardés par le viewset
avec ``IsResponsableOrAdmin`` (garde basée sur le RÔLE, pas un code ERP).
Comme le filtre catalogue AG1 (:func:`apps.agent.registry.for_user`) ne sait
raisonner que sur des codes de permission ERP, on adosse chaque action au code
ERP le plus proche que portent Responsable/Admin/Directeur — et que NE porte PAS
un utilisateur en lecture seule — pour que le catalogue expose bien l'action à
un responsable/admin et la cache à un lecteur seul :
  * création de devis        → ``ventes_creer``
  * génération du PDF devis   → ``ventes_pdf``
  * validation du flux (accepter / convertir / facturer / encaisser)
    → ``ventes_valider``
Le viewset reste l'autorité finale (il re-vérifie le rôle + la société).

Enregistrement : :func:`register_ventes_actions` est appelée depuis
``VentesConfig.ready()`` (import différé). Idempotente : sûre si ``ready()`` est
invoquée plusieurs fois (tests, autoreload).
"""
from __future__ import annotations

from apps.agent.registry import (
    AgentAction,
    RISK_INTERNAL,
    RISK_OUTWARD,
    RISK_IRREVERSIBLE,
    register,
)


# Codes ERP de rattachement (cf. docstring) — portés par Responsable/Admin/
# Directeur, jamais par un utilisateur en lecture seule (qui n'a que *_voir).
_PERM_CREER = 'ventes_creer'
_PERM_PDF = 'ventes_pdf'
_PERM_VALIDER = 'ventes_valider'


# ── AG4 ─────────────────────────────────────────────────────────────────────

# Action — Créer un devis. Endpoint réel : POST /api/django/ventes/devis/
# (DevisViewSet.create). La société et le created_by sont forcés côté serveur ;
# si ``lead`` est fourni sans ``client``, le client est résolu côté serveur
# depuis le lead (réutilise le lien/le client existant, sinon en crée un — sans
# doublon). La numérotation séquentielle est attribuée par le serveur.
CREER_DEVIS = AgentAction(
    key='ventes.devis.creer',
    label='Créer un devis',
    description=(
        "Crée un nouveau devis pour un client ou un lead. L'agent fournit les "
        "lignes et le marché ; le serveur résout le client à partir du lead, "
        "attribue la référence numérotée et force la société du caller."
    ),
    endpoint='/api/django/ventes/devis/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'client': {
                'type': 'integer',
                'description': 'Identifiant du client (optionnel si lead).',
            },
            'lead': {
                'type': 'integer',
                'description': (
                    'Identifiant du lead — le client est résolu côté serveur '
                    'depuis le lead (sans doublon).'
                ),
            },
            'statut': {'type': 'string'},
            'taux_tva': {'type': 'string'},
            'remise_globale': {'type': 'string'},
            'lignes': {'type': 'array', 'items': {'type': 'object'}},
        },
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
)


# Action — Générer le PDF client (premium) d'un devis via /proposal, l'UNIQUE
# chemin de PDF de devis destiné au client (CLAUDE.md règle #4). Endpoint réel :
# GET /api/django/ventes/devis/{id}/proposal/ (DevisViewSet.proposal). Les
# options de format passent par les query params, filtrées par la liste blanche
# serveur (``clean_pdf_options``). Le moteur ne fait que RENDRE : aucun statut
# ne change (préservation des statuts).
GENERER_PDF_DEVIS = AgentAction(
    key='ventes.devis.generer_pdf',
    label='Générer le PDF de proposition (devis)',
    description=(
        "Génère le PDF client (premium) d'un devis via /proposal — l'unique "
        "chemin de PDF de devis destiné au client. Les options de format "
        "(pdf_mode, include_etude…) sont filtrées par une liste blanche "
        "serveur. Ne change aucun statut."
    ),
    endpoint='/api/django/ventes/devis/{id}/proposal/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant du devis.',
            },
            # Options de format (liste blanche ``clean_pdf_options``) — passées
            # en query params ; la société/le devis bornent déjà le rendu.
            'pdf_mode': {
                'type': 'string',
                'description': "Format : 'full' (premium) ou 'onepage'.",
            },
            'include_etude': {
                'type': 'boolean',
                'description': "Ajoute la page Étude (4e page premium).",
            },
            'payment_mode': {'type': 'string'},
            'custom_acompte': {'type': 'string'},
            'show_monthly': {'type': 'boolean'},
            'devis_final': {'type': 'boolean'},
        },
        'required': ['id'],
    },
    required_permission=_PERM_PDF,
    risk=RISK_INTERNAL,
)


# Action — Accepter un devis. Endpoint réel : POST
# /api/django/ventes/devis/{id}/accepter/ (DevisViewSet.accepter). Marque le
# devis « accepté » (date + nom de la personne qui accepte), consigne
# l'acceptation dans le chatter et avance le funnel CRM (→ SIGNED) ; c'est le
# déclencheur de la création d'un chantier. Effet visible côté flux → OUTWARD,
# donc confirmation avant exécution.
ACCEPTER_DEVIS = AgentAction(
    key='ventes.devis.accepter',
    label='Accepter un devis',
    description=(
        "Marque un devis « accepté » (date + nom de la personne qui accepte) "
        "et déclenche la suite du flux (création de chantier). À confirmer "
        "avant exécution."
    ),
    endpoint='/api/django/ventes/devis/{id}/accepter/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant du devis à accepter.',
            },
            'nom': {
                'type': 'string',
                'description': 'Nom de la personne qui accepte.',
            },
            'date': {
                'type': 'string',
                'description': "Date d'acceptation (AAAA-MM-JJ ; défaut = ce jour).",
            },
            'option': {
                'type': 'string',
                'description': (
                    "Option retenue (« sans_batterie » / « avec_batterie ») — "
                    "obligatoire si le devis comporte deux options."
                ),
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_VALIDER,
    risk=RISK_OUTWARD,
    confirm_summary='Marquer ce devis comme accepté par le client.',
)


# ── AG5 ─────────────────────────────────────────────────────────────────────

# Action — Convertir un devis ACCEPTÉ en bon de commande. Endpoint réel : POST
# /api/django/ventes/devis/{id}/convertir-bc/ (DevisViewSet.convertir_en_bc).
# Crée le BonCommande (référence numérotée, société forcée) lié au devis. Effet
# sur le flux → OUTWARD, confirmation requise.
CONVERTIR_EN_BON_COMMANDE = AgentAction(
    key='ventes.devis.convertir_bc',
    label='Convertir le devis en bon de commande',
    description=(
        "Convertit un devis accepté en bon de commande (référence numérotée, "
        "société forcée côté serveur). À confirmer avant exécution."
    ),
    endpoint='/api/django/ventes/devis/{id}/convertir-bc/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant du devis accepté à convertir.',
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_VALIDER,
    risk=RISK_OUTWARD,
    confirm_summary='Créer le bon de commande de ce devis accepté.',
)


# Action — Générer la prochaine facture de tranche du devis. Endpoint réel :
# POST /api/django/ventes/devis/{id}/generer-facture/
# (DevisViewSet.generer_facture). Crée et émet la prochaine facture de
# l'échéancier (acompte, puis matériel, puis solde). Effet comptable visible →
# OUTWARD, confirmation requise.
GENERER_FACTURE = AgentAction(
    key='ventes.devis.generer_facture',
    label='Générer la facture (tranche suivante)',
    description=(
        "Génère et émet la prochaine facture de tranche de l'échéancier du "
        "devis (acompte → matériel → solde). Référence numérotée et société "
        "forcées côté serveur. À confirmer avant exécution."
    ),
    endpoint='/api/django/ventes/devis/{id}/generer-facture/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant du devis dont on facture une tranche.',
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_VALIDER,
    risk=RISK_OUTWARD,
    confirm_summary='Émettre la prochaine facture de tranche de ce devis.',
)


# Action — Enregistrer un paiement sur une facture. Endpoint réel (déjà présent,
# scopé société) : POST /api/django/ventes/factures/{id}/enregistrer-paiement/
# (FactureViewSet.enregistrer_paiement). Écrit un Paiement (société = celle de
# la facture, created_by = caller — jamais lus du corps), valide le montant
# (> 0, ≤ reste à payer) et passe la facture « Payée » quand elle est soldée.
# Geste comptable NON réversible → IRREVERSIBLE, confirmation requise.
ENREGISTRER_PAIEMENT = AgentAction(
    key='ventes.facture.enregistrer_paiement',
    label='Enregistrer un paiement',
    description=(
        "Enregistre un encaissement sur une facture (montant + date + mode). "
        "Le serveur force la société (celle de la facture) et l'auteur, valide "
        "le montant (> 0, sans dépasser le reste à payer) et solde la facture "
        "quand elle est entièrement réglée. Geste comptable non réversible — à "
        "confirmer avant exécution."
    ),
    endpoint='/api/django/ventes/factures/{id}/enregistrer-paiement/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'description': 'Identifiant de la facture encaissée.',
            },
            'montant': {
                'type': 'number',
                'description': 'Montant encaissé (strictement positif).',
            },
            'date_paiement': {
                'type': 'string',
                'description': 'Date du paiement (AAAA-MM-JJ).',
            },
            'mode': {
                'type': 'string',
                'description': 'Mode de paiement (espèces, virement, chèque…).',
            },
            'reference': {'type': 'string'},
            'note': {'type': 'string'},
        },
        'required': ['id', 'montant', 'date_paiement'],
    },
    required_permission=_PERM_VALIDER,
    risk=RISK_IRREVERSIBLE,
    confirm_summary='Enregistrer cet encaissement (irréversible).',
)


# Toutes les actions Ventes (AG4 puis AG5), dans l'ordre du flux.
VENTES_ACTIONS = (
    # AG4
    CREER_DEVIS,
    GENERER_PDF_DEVIS,
    ACCEPTER_DEVIS,
    # AG5
    CONVERTIR_EN_BON_COMMANDE,
    GENERER_FACTURE,
    ENREGISTRER_PAIEMENT,
)


def register_ventes_actions() -> None:
    """Enregistre les actions Ventes dans le registre AG1 (idempotent).

    Appelée depuis ``VentesConfig.ready()``. Ignore silencieusement un
    ré-enregistrement pour rester sûr si ``ready()`` est appelé plusieurs fois.
    """
    for action in VENTES_ACTIONS:
        try:
            register(action)
        except ValueError:
            # Déjà enregistrée — registre déterministe, rien à faire.
            pass
