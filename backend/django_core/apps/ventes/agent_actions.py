"""AG4/AG5 — Actions agentiques Ventes (catalogue déclaré en code).

Déclare, via le registre AG1 (:mod:`apps.agent.registry`), les actions du flux
devis → bon de commande → facture → encaissement que l'agent (relais FastAPI +
JWT utilisateur) peut PROPOSER. Ce module est PUREMENT des métadonnées : aucune
exécution ici et AUCUN nouvel endpoint — chaque action pointe vers un endpoint
Ventes EXISTANT, qui re-vérifie permission ET société à l'exécution.

Multi-tenant : ``company`` n'apparaît JAMAIS dans le schéma ``inputs`` — la
société est forcée côté serveur (``perform_create`` / l'action de viewset) à
partir de ``request.user.company`` ; elle ne doit jamais provenir du corps.
``creer_auto`` accepte un ``lead`` (ou un ``client``, dont on remonte au lead) :
le devis est DIMENSIONNÉ depuis la fiche lead puis le client résolu côté serveur
(``apps.crm.services.resolve_client_for_lead``), jamais dupliqué. Il n'existe
plus d'action de création « vide » — le Copilote crée toujours un devis chiffré.

Niveaux de risque (qui pilotent le garde-fou propose→confirm) :
  * AG4 ``creer_auto``         → INTERNAL  (devis dimensionné, écriture interne)
  * AG4 ``ligne_ajouter`` / ``ligne_modifier`` / ``remise`` → INTERNAL (édition brouillon)
  * AG4 ``ligne_supprimer``    → OUTWARD   (retrait de ligne — confirmation)
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

# Action — Créer un devis AUTOMATIQUE (résidentiel). Endpoint réel : POST
# /api/django/ventes/devis/auto/ (DevisViewSet.auto). C'est le SEUL chemin de
# création de devis offert à l'agent : il dimensionne l'installation à partir de
# la fiche lead (facture d'hiver / taille souhaitée), choisit panneaux + onduleur
# (+ batterie si le lead la souhaite) dans le catalogue, force la société et le
# created_by côté serveur, et numérote. Il ne crée JAMAIS un devis vide : si une
# donnée manque, le serveur répond 422 avec le champ à compléter pour que l'agent
# le demande.
CREER_AUTO = AgentAction(
    key='ventes.devis.creer_auto',
    label='Créer un devis (automatique)',
    description=(
        "Crée un devis RÉSIDENTIEL automatiquement dimensionné à partir de la "
        "fiche du lead (facture d'électricité ou taille souhaitée). C'EST LE "
        "SEUL moyen de créer un devis : il choisit panneaux, onduleur et "
        "batterie depuis le catalogue. Fournir le 'lead' (ou le 'client', dont "
        "on remonte au lead). Si une donnée de dimensionnement manque, le serveur "
        "l'indique (422) pour que tu la demandes — il ne crée jamais de devis "
        "vide. Pour l'industriel/agricole, le serveur oriente vers le générateur."
    ),
    endpoint='/api/django/ventes/devis/auto/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'lead': {
                'type': 'integer',
                'description': 'Identifiant du lead (porteur du profil énergétique).',
            },
            'client': {
                'type': 'integer',
                'description': (
                    'Identifiant du client — on remonte au lead le plus récent '
                    'qui lui est rattaché.'
                ),
            },
            'taux_tva': {'type': 'string'},
            'remise_globale': {'type': 'string'},
        },
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
)


# Action — Ajouter une ligne à un devis brouillon. Endpoint réel : POST
# /api/django/ventes/devis-lignes/ (LigneDevisViewSet). La société est imposée
# côté serveur (la ligne doit cibler un devis de la société du caller).
LIGNE_AJOUTER = AgentAction(
    key='ventes.devis.ligne_ajouter',
    label='Ajouter une ligne au devis',
    description=(
        "Ajoute une ligne de produit à un devis brouillon. Fournir 'devis' (id), "
        "'produit' (id du catalogue), 'quantite' et le 'prix_unitaire' (HT, même "
        "base que le devis) ; 'designation' et 'remise' (%) optionnels."
    ),
    endpoint='/api/django/ventes/devis-lignes/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'devis': {'type': 'integer'},
            'produit': {'type': 'integer'},
            'designation': {'type': 'string'},
            'quantite': {'type': 'string'},
            'prix_unitaire': {'type': 'string'},
            'remise': {'type': 'string'},
        },
        'required': ['devis', 'produit', 'quantite'],
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
)


# Action — Modifier une ligne de devis. Endpoint réel : PATCH
# /api/django/ventes/devis-lignes/{id}/ (LigneDevisViewSet). Pour viser « la
# batterie », l'agent liste d'abord les lignes du devis puis agit par id.
LIGNE_MODIFIER = AgentAction(
    key='ventes.devis.ligne_modifier',
    label='Modifier une ligne de devis',
    description=(
        "Modifie une ligne d'un devis brouillon (prix unitaire, quantité, remise "
        "ou désignation). Fournir l'id de la LIGNE et les champs à changer. "
        "'prix_unitaire' est en HT (même base que le devis). Pour retrouver la "
        "ligne visée (ex. « la batterie »), liste d'abord les lignes du devis."
    ),
    endpoint='/api/django/ventes/devis-lignes/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'prix_unitaire': {'type': 'string'},
            'quantite': {'type': 'string'},
            'remise': {'type': 'string'},
            'designation': {'type': 'string'},
        },
        'required': ['id'],
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
)


# Action — Retirer une ligne d'un devis brouillon. Endpoint réel : DELETE
# /api/django/ventes/devis-lignes/{id}/ (LigneDevisViewSet). Suppression → on
# demande une confirmation avant exécution.
LIGNE_SUPPRIMER = AgentAction(
    key='ventes.devis.ligne_supprimer',
    label='Retirer une ligne de devis',
    description=(
        "Retire une ligne d'un devis brouillon (par id de ligne). À confirmer "
        "avant exécution."
    ),
    endpoint='/api/django/ventes/devis-lignes/{id}/',
    method='DELETE',
    inputs={
        'type': 'object',
        'properties': {'id': {'type': 'integer'}},
        'required': ['id'],
    },
    required_permission=_PERM_CREER,
    risk=RISK_OUTWARD,
    confirm_summary='Retirer cette ligne du devis.',
)


# Action — Remise globale d'un devis. Endpoint réel : PATCH
# /api/django/ventes/devis/{id}/ (DevisViewSet.partial_update). Définit le
# pourcentage de remise globale d'un devis brouillon.
REMISE_DEVIS = AgentAction(
    key='ventes.devis.remise',
    label='Appliquer une remise au devis',
    description=(
        "Définit la remise globale (en %) d'un devis brouillon. Fournir l'id du "
        "DEVIS et 'remise_globale'."
    ),
    endpoint='/api/django/ventes/devis/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'remise_globale': {'type': 'string'},
        },
        'required': ['id', 'remise_globale'],
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
    # AG4 — création (TOUJOURS automatique) + édition par chat
    CREER_AUTO,
    LIGNE_AJOUTER,
    LIGNE_MODIFIER,
    LIGNE_SUPPRIMER,
    REMISE_DEVIS,
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
