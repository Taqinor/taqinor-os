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
  * AG4 ``ligne_ajouter`` / ``ligne_modifier`` / ``ligne_supprimer`` / ``remise``
    → OUTWARD (COP-G3 : toute action qui CHANGE un montant du devis passe par
    une proposition à confirmer — plus d'exécution immédiate ni de prix ou de
    remise appliqués sans que la commerciale ait lu le montant)
  * AG4 ``generer_pdf_devis``  → INTERNAL  (lit /proposal : carte « document »,
    le relais rend un LIEN, aucun statut ne change)
  * AG4 ``accepter_devis``     → OUTWARD   (marque le devis accepté → chantier)
  * AG5 ``convertir_en_bon_commande`` → OUTWARD (crée le BC du devis accepté)
  * AG5 ``generer_facture``    → IRREVERSIBLE (émet la tranche suivante avec son
    numéro légal ; lot ``herite`` — REP6)
  * AG5 ``enregistrer_paiement`` → IRREVERSIBLE (encaissement comptable, gardé
    par confirmation ; écrit un Paiement scopé société, montant validé > 0)

Permissions : les endpoints du flux devis/facture sont gardés par le viewset
avec ``IsResponsableOrAdmin`` (garde basée sur le RÔLE et le module) ou par un
code de la grille. Le filtre catalogue AG1 (:func:`apps.agent.registry.for_user`)
raisonne sur des codes ERP : on adosse chaque action au code que sa route exige
quand elle en exige un (``encaisser``, ``ventes_modifier``…), sinon au code du
module le plus proche — un test de PARITÉ (``apps/agent/tests/test_registry.py``)
compare le catalogue aux gardes réelles des routes :
  * création de devis        → ``ventes_creer``
  * remise globale           → ``ventes_modifier`` (PATCH du devis)
  * génération du PDF devis   → ``ventes_pdf``
  * accepter / convertir      → ``ventes_valider``
  * émettre une tranche, encaisser → ``encaisser`` (``PeutEncaisser``, ASEC29)
Le viewset reste l'autorité finale (il re-vérifie le rôle + la société).

Cartes (COP-G3) : l'action PDF porte ``carte='document'`` ; les actions qui
désignent un devis, une facture, un lead ou un client par un identifiant
déclarent ``objets`` pour que l'aperçu d'une proposition NOMME l'objet.

Enregistrement : :func:`register_ventes_actions` est appelée depuis
``VentesConfig.ready()`` (import différé). Idempotente : sûre si ``ready()`` est
invoquée plusieurs fois (tests, autoreload).
"""
from __future__ import annotations

from apps.agent.registry import (
    AgentAction,
    LOT_COPILOTE,
    LOT_HERITE,
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
# COP-G2 — gardes RÉELLES des routes (jamais un code « voisin ») : la remise est
# un PATCH du devis (``DroitDeLaGrille('ventes_modifier')``) et l'encaissement
# exige ``encaisser`` (``PeutEncaisser``, ASEC29).
_PERM_MODIFIER = 'ventes_modifier'
_PERM_ENCAISSER = 'encaisser'

#: REP6 — valeurs EXACTES de ``Paiement.Mode`` (apps/facturation/models.py),
#: recopiées (ce module n'importe aucun modèle) et tenues par le test.
MODES_PAIEMENT = ('especes', 'virement', 'cheque', 'carte', 'prelevement',
                  'autre')


# ── AG4 ─────────────────────────────────────────────────────────────────────

# Action — Créer un devis AUTOMATIQUE (4 marchés). Endpoint réel : POST
# /api/django/ventes/devis/auto/ (DevisViewSet.auto). C'est le SEUL chemin de
# création de devis offert à l'agent : il dimensionne l'installation à partir de
# la fiche lead (facture d'hiver / taille souhaitée), choisit panneaux + onduleur
# (+ batterie si le lead la souhaite) dans le catalogue, force la société et le
# created_by côté serveur, et numérote. Le MARCHÉ est lu sur le lead
# (``type_installation``, ``domain/creation_auto.py``) : résidentiel, commercial,
# industriel (moteur C&I) ou agricole (pompage) ; ``target_kwc`` / ``scenario``
# sont ceux de ``DevisAutoRequest`` (``views/openapi_docs.py``). Il ne crée
# JAMAIS un devis vide : si une donnée manque, le serveur répond 409 avec le
# champ à compléter pour que l'agent le demande.
CREER_AUTO = AgentAction(
    key='ventes.devis.creer_auto',
    label='Créer un devis (automatique)',
    description=(
        "Sert à : créer un devis brouillon dimensionné depuis la fiche lead ; "
        "le marché (résidentiel, commercial, industriel ou agricole) vient du "
        "type d'installation du lead. Ne pas utiliser pour : modifier un devis "
        "existant ni créer un devis vide (il n'y en a pas). Exemple : « devis "
        "de 6 kWc sans batterie pour le lead 42 » → lead=42, target_kwc=6, "
        "scenario=sans. Résultat : devis brouillon numéroté avec ses lignes ; "
        "409 nommant la donnée du lead à compléter."
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
            'target_kwc': {
                'type': 'number',
                'description': (
                    'Puissance cible en kWc (10 000 au plus). Absente : le '
                    'serveur dimensionne depuis le profil du lead.'
                ),
            },
            'scenario': {
                'type': 'string',
                'enum': ['sans', 'avec', 'les_deux'],
                'description': (
                    "Résidentiel seulement : « sans » ou « avec » batterie, "
                    "« les_deux » (défaut) pour proposer les deux options."
                ),
            },
            'taux_tva': {
                'type': 'number',
                'description': 'Taux de TVA en % (défaut : taux standard de la société).',
            },
            'remise_globale': {
                'type': 'number',
                'description': 'Remise globale en % (0 à 100).',
            },
        },
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
    # COP2-V4 — changement d'ÉCRAN seulement : la réponse (contrat
    # ``assistant_devis_cree.json``) se rend en carte « devis créé ».
    carte='devis_cree',
    objets={'lead': 'lead', 'client': 'client'},
)


# Action — Ajouter une ligne à un devis brouillon. Endpoint réel : POST
# /api/django/ventes/devis-lignes/ (LigneDevisViewSet). La société est imposée
# côté serveur (la ligne doit cibler un devis de la société du caller).
LIGNE_AJOUTER = AgentAction(
    key='ventes.devis.ligne_ajouter',
    label='Ajouter une ligne au devis',
    description=(
        "Sert à : ajouter un produit du catalogue à un devis brouillon ; ajoute "
        "un montant : proposition puis confirmation obligatoire. Ne pas "
        "utiliser pour : changer une ligne existante (ligne_modifier) ni créer "
        "un devis. Exemple : « ajoute 2 batteries au devis 12 » → devis=12, "
        "produit=<id>, quantite=2 ; prix_unitaire HT, designation, remise (%) "
        "optionnels. Résultat : la ligne est créée, les totaux recalculés."
    ),
    endpoint='/api/django/ventes/devis-lignes/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'devis': {'type': 'integer', 'description': 'Identifiant du devis brouillon.'},
            'produit': {'type': 'integer', 'description': 'Identifiant du produit du catalogue.'},
            'designation': {'type': 'string'},
            'quantite': {'type': 'number', 'description': 'Quantité (strictement positive).'},
            'prix_unitaire': {
                'type': 'number',
                'description': 'Prix unitaire HT ; absent = prix du catalogue.',
            },
            'remise': {'type': 'number', 'description': 'Remise de la ligne en %.'},
        },
        'required': ['devis', 'produit', 'quantite'],
    },
    required_permission=_PERM_CREER,
    # COP-G3 — ajouter une ligne CHANGE le total du devis (et peut y poser un
    # prix libre) : même règle que ``ligne_modifier`` / ``remise``.
    risk=RISK_OUTWARD,
    confirm_summary='Ajouter cette ligne au devis (le total change).',
    objets={'devis': 'devis'},
)


# Action — Modifier une ligne de devis. Endpoint réel : PATCH
# /api/django/ventes/devis-lignes/{id}/ (LigneDevisViewSet). L'id est celui de la
# LIGNE (COP2-V5 : ``ventes.devis.lignes``, lot copilote, les liste ; sans
# copilote, l'agent le demande s'il ne l'a pas). Prix, quantité et remise changent le montant du devis : COP-G3,
# proposition à confirmer — AIC98 : une baisse de prix de ligne (prix tapé) compte
# comme une remise pour le seuil d'approbation T17 (``profondeur_remise_effective``).
LIGNE_MODIFIER = AgentAction(
    key='ventes.devis.ligne_modifier',
    label='Modifier une ligne de devis',
    description=(
        "Sert à : changer le prix unitaire HT, la quantité, la remise ou la "
        "désignation d'une ligne de devis brouillon ; change un montant : "
        "proposition puis confirmation obligatoire. Ne pas utiliser pour : "
        "retirer une ligne ni la remise globale (remise). Exemple : « passe la "
        "batterie à 1 unité » → id=<id de la ligne>, quantite=1 ; sans id de "
        "ligne, demande-le. Résultat : ligne mise à jour, totaux recalculés."
    ),
    endpoint='/api/django/ventes/devis-lignes/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'description': 'Identifiant de la LIGNE de devis.'},
            'prix_unitaire': {'type': 'number', 'description': 'Prix unitaire HT.'},
            'quantite': {'type': 'number', 'description': 'Quantité (strictement positive).'},
            'remise': {'type': 'number', 'description': 'Remise de la ligne en %.'},
            'designation': {'type': 'string'},
        },
        'required': ['id'],
    },
    required_permission=_PERM_CREER,
    risk=RISK_OUTWARD,
    confirm_summary='Modifier cette ligne du devis (le total change).',
)


# Action — Retirer une ligne d'un devis brouillon. Endpoint réel : DELETE
# /api/django/ventes/devis-lignes/{id}/ (LigneDevisViewSet). Suppression → on
# demande une confirmation avant exécution.
LIGNE_SUPPRIMER = AgentAction(
    key='ventes.devis.ligne_supprimer',
    label='Retirer une ligne de devis',
    description=(
        "Sert à : retirer une ligne d'un devis brouillon, par id de ligne ; "
        "change un montant : proposition puis confirmation obligatoire. Ne pas "
        "utiliser pour : réduire une quantité (ligne_modifier). Exemple : « "
        "enlève la ligne 87 » → id=87. Résultat : la ligne disparaît du devis, "
        "totaux recalculés."
    ),
    endpoint='/api/django/ventes/devis-lignes/{id}/',
    method='DELETE',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'description': 'Identifiant de la LIGNE de devis.'},
        },
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
        "Sert à : fixer la remise globale (en %) d'un devis brouillon ; change "
        "un montant : proposition puis confirmation obligatoire. Ne pas "
        "utiliser pour : la remise d'une seule ligne (ligne_modifier). "
        "Exemple : « remise de 2 % sur le devis 12 » → id=12, "
        "remise_globale=2. Résultat : remise appliquée, totaux HT, TVA et TTC "
        "recalculés."
    ),
    endpoint='/api/django/ventes/devis/{id}/',
    method='PATCH',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'description': 'Identifiant du devis brouillon.'},
            'remise_globale': {
                'type': 'number',
                'description': 'Remise globale en % (0 à 100).',
            },
        },
        'required': ['id', 'remise_globale'],
    },
    required_permission=_PERM_MODIFIER,
    # COP-G3 — une remise n'est plus appliquée sans confirmation : l'exécution
    # était immédiate et sans borne (la garde d'approbation du serveur ne couvre
    # que l'ENVOI, et seulement si un seuil est réglé).
    risk=RISK_OUTWARD,
    confirm_summary='Appliquer cette remise globale au devis.',
    objets={'id': 'devis'},
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
        "Sert à : obtenir le lien du PDF client d'un devis. PDF client = "
        "`/proposal` uniquement (règle #4) ; options pdf_mode (full/onepage), "
        "include_etude, include_calepinage, langue. Ne pas utiliser pour : une "
        "facture ni un autre format de devis, il n'en existe pas. Exemple : "
        "« PDF du devis 12 en une page » → id=12, pdf_mode=onepage. Résultat : "
        "un lien vers le PDF, rien n'est envoyé ; aucun statut ne change."
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
            # en query params, tels que la route les LIT (``devis_pdf.proposal``) :
            # ``payment_mode`` et ``custom_acompte`` n'y sont jamais lus (retirés).
            'pdf_mode': {
                'type': 'string',
                'enum': ['full', 'onepage'],
                'description': "Format : 'full' (premium) ou 'onepage'.",
            },
            'include_etude': {
                'type': 'boolean',
                'description': "Ajoute la page Étude (4e page, résidentiel).",
            },
            'include_calepinage': {
                'type': 'boolean',
                'description': "Ajoute (true) ou retire (false) la planche de calepinage.",
            },
            'langue': {
                'type': 'string',
                'description': "Langue du document (code court, ex. fr) ; absente : celle du client.",
            },
            'show_monthly': {'type': 'boolean'},
            'devis_final': {'type': 'boolean'},
        },
        'required': ['id'],
    },
    required_permission=_PERM_PDF,
    risk=RISK_INTERNAL,
    # COP-G3 — l'action ne fait que LIRE /proposal : le relais rend le LIEN
    # (contrat ``assistant_document.json``), jamais le PDF binaire lu comme JSON.
    carte='document',
    objets={'id': 'devis'},
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
        "Sert à : marquer un devis accepté par le client (nom, date, option si "
        "le devis en a deux) ; change un statut : proposition puis "
        "confirmation obligatoire. Ne pas utiliser pour : un accord oral non "
        "confirmé ni un devis brouillon à modifier. Exemple : « M. Alaoui a "
        "signé le devis 12, avec batterie » → id=12, nom, "
        "option=avec_batterie. Résultat : devis accepté, lead passé à Signé, "
        "chantier déclenché."
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
    objets={'id': 'devis'},
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
        "Sert à : créer le bon de commande d'un devis déjà accepté ; change "
        "un statut : proposition puis confirmation obligatoire. Ne pas "
        "utiliser pour : un devis non accepté (accepter d'abord) ni pour "
        "facturer. Exemple : « lance la commande du devis 12 » → id=12. "
        "Résultat : bon de commande numéroté lié au devis, société forcée "
        "côté serveur."
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
    objets={'id': 'devis'},
)


# Action — Émettre la prochaine facture de tranche du devis. Endpoint réel :
# POST /api/django/ventes/devis/{id}/generer-facture/
# (DevisViewSet.generer_facture, porte « api-only » fermée côté écran). REP6
# (copilote vague 2, B-7) : la route ÉMET la tranche suivante avec son NUMÉRO
# LÉGAL (``creer_facture_tranche``) — ce n'est pas un brouillon ; une facture
# émise ne s'annule que par un avoir → IRREVERSIBLE. Garde réelle :
# ``IsResponsableOrAdmin`` (décorateur) PUIS ``PeutEncaisser`` DANS LE CORPS
# (403 ``MOTIF_SANS_ENCAISSER``) : le code du catalogue est ``encaisser``
# (l'Admin Ventes, ``ventes_valider`` sans ``encaisser``, voyait l'outil et
# recevait 403). Lot ``herite`` : servi seulement copilote ÉTEINT ; sous le
# copilote, la facturation passe par un BROUILLON (vague 2B).
GENERER_FACTURE = AgentAction(
    key='ventes.devis.generer_facture',
    label='Émettre la facture (numéro légal, ne s\'annule que par un avoir)',
    description=(
        "Sert à : émettre la prochaine facture de tranche de l'échéancier du "
        "devis (acompte → matériel → solde) avec son numéro légal ; change "
        "un statut : proposition puis confirmation obligatoire — irréversible, "
        "une facture émise ne s'annule que par un avoir. Ne pas utiliser "
        "pour : encaisser un paiement (enregistrer_paiement), préparer un "
        "brouillon ni un devis non accepté. Exemple : « facture l'acompte du "
        "devis 12 » → id=12. Résultat : facture numérotée émise ; 409 si rien "
        "n'est à facturer, 403 en blocage crédit."
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
    required_permission=_PERM_ENCAISSER,
    risk=RISK_IRREVERSIBLE,
    confirm_summary=(
        "Émettre la prochaine facture de tranche de ce devis : numéro légal, "
        "ne s'annule que par un avoir."),
    lot=LOT_HERITE,
    objets={'id': 'devis'},
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
        "Sert à : enregistrer un encaissement sur une facture (montant, date, "
        "mode) ; change un statut : proposition puis confirmation obligatoire "
        "— geste comptable non réversible. Ne pas utiliser pour : une "
        "promesse de paiement ni un montant supérieur au reste à payer. "
        "Exemple : « 15 000 DH reçus par virement sur la facture 30 » → id=30, "
        "montant=15000, date_paiement, mode=virement. Résultat : paiement "
        "enregistré ; facture soldée quand tout est réglé ; un refus « "
        "paiement similaire » veut dire déjà enregistré : ne pas le reproposer."
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
                'format': 'date',
                'description': ('Jour du règlement (AAAA-MM-JJ), dicté ou '
                                'du jour, jamais deviné.'),
            },
            'mode': {
                'type': 'string',
                # REP6 (B-8) — valeurs EXACTES de ``Paiement.Mode``
                # (apps/facturation/models.py) : « espèces » / « chèque »
                # accentués étaient refusés.
                'enum': list(MODES_PAIEMENT),
                'description': 'Mode de paiement : ' + ', '.join(MODES_PAIEMENT) + '.',
            },
            'reference': {'type': 'string'},
            'note': {'type': 'string'},
        },
        'required': ['id', 'montant', 'date_paiement'],
    },
    required_permission=_PERM_ENCAISSER,
    risk=RISK_IRREVERSIBLE,
    confirm_summary='Enregistrer cet encaissement (irréversible).',
    objets={'id': 'facture'},
)


# AIC99 — d'où vient un chiffre du devis : LECTURE des routes d'étude
# existantes, choisie par ``bloc`` selon le marché (jamais un chiffre
# recalculé). ``etude-params`` (garde la plus stricte : module ventes) est la
# PREMIÈRE valeur — c'est elle que relit la parité catalogue ↔ route.
EXPLIQUER_DEVIS = AgentAction(
    key='ventes.devis.expliquer',
    label="Expliquer un chiffre du devis",
    description=(
        "Sert à : dire d'où vient un chiffre du devis (production, économie, "
        "retour) en lisant l'étude du serveur : bloc economie (résidentiel), "
        "economie-ci (commercial/industriel), economie-pompage (agricole), "
        "etude-params (paramètres saisis). Ne pas utiliser pour : recalculer "
        "un chiffre ni citer un prix d'achat. Exemple : « Pourquoi 9 ans de "
        "retour sur le devis 12 ? » → id=12, bloc=economie. Résultat : les "
        "chiffres et hypothèses servis par la route, rien n'est écrit."
    ),
    endpoint='/api/django/ventes/devis/{id}/{bloc}/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'description': 'Identifiant du devis.'},
            'bloc': {'type': 'string', 'enum': [
                'etude-params', 'economie', 'economie-ci', 'economie-pompage']},
        },
        'required': ['id', 'bloc'],
    },
    required_permission='ventes_voir',
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
    objets={'id': 'devis'},
)


# AIC99 — l'envoi par e-mail de l'écran (même route), en proposition À
# CONFIRMER ; aucun texte d'e-mail écrit par le modèle (gabarit société).
ENVOYER_EMAIL_DEVIS = AgentAction(
    key='ventes.devis.envoyer_email',
    label='Envoyer le devis par e-mail',
    description=(
        "Sert à : envoyer au client, par e-mail, la proposition d'un devis "
        "(PDF /proposal et lien, texte du modèle de la société). Envoi réel : "
        "proposition puis confirmation obligatoire. Ne pas utiliser pour : "
        "rédiger un e-mail ni l'envoyer par WhatsApp. Exemple : « Envoie-le "
        "par e-mail » → id du devis. Résultat : journal d'envoi et statut du "
        "devis ; un refus (e-mail absent, envoi non configuré) est expliqué."
    ),
    endpoint='/api/django/ventes/devis/{id}/envoyer-email/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'description': 'Identifiant du devis.'},
            'pdf_mode': {'type': 'string', 'enum': ['full', 'onepage']},
        },
        'required': ['id'],
    },
    required_permission=_PERM_MODIFIER,
    risk=RISK_OUTWARD,
    confirm_summary='Envoyer la proposition de ce devis au client par e-mail.',
    lot=LOT_COPILOTE,
    objets={'id': 'devis'},
)


#: COP2 — l'exemple commun des actions de composition : la phrase du fondateur.
_EXEMPLE_FONDATEUR = (
    "« prépare-lui un devis : 10 panneaux solaires avec onduleur triphasé de "
    "10kw et une batterie de 5kwh »")

# COP2-V2 — lire le catalogue vendable (route ``ventes/assistant/catalogue/``,
# garde ``LectureVentes`` = ``ventes_voir``) : même classement que la
# composition imposée, jamais de prix d'achat, de marge ni de stock chiffré.
CHERCHER_CATALOGUE = AgentAction(
    key='ventes.catalogue.chercher',
    label='Chercher dans le catalogue',
    description=(
        "Sert à : lire le catalogue vendable (panneaux, onduleurs, batteries) "
        "avec prix TTC ; un genre et une taille donnent un verdict unique, "
        "ambigu ou aucun. Ne pas utiliser pour : créer un devis ni demander "
        "une puissance au client. Exemple : " + _EXEMPLE_FONDATEUR + " → "
        "genre=onduleur, kw=10, phase=triphase, famille=hybride ; puis "
        "genre=batterie, kwh=5. Résultat : produits (produit_id, nom, "
        "marque, prix TTC), statut et raison."
    ),
    endpoint='/api/django/ventes/assistant/catalogue/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'q': {'type': 'string', 'description': 'Texte cherché (nom ou marque).'},
            'genre': {'type': 'string', 'enum': ['panneau', 'onduleur', 'batterie']},
            'kw': {'type': 'number', 'description': "Puissance d'onduleur en kW (0,5 à 100)."},
            'kwh': {'type': 'number', 'description': 'Capacité de batterie en kWh (0,5 à 100).'},
            'wc': {'type': 'number', 'description': 'Puissance de panneau en Wc (100 à 1000).'},
            'phase': {'type': 'string', 'enum': ['monophase', 'triphase']},
            'famille': {'type': 'string', 'enum': ['hybride', 'reseau', 'offgrid'],
                        'description': 'Famille d\'onduleur (hybride = avec batterie).'},
            'limite': {'type': 'integer', 'description': 'Lignes rendues (1 à 25, défaut 10).'},
        },
    },
    required_permission='ventes_voir',
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)


def _entier(description):
    return {'type': 'integer', 'description': description}


# COP2-V4 — composer un devis au kit IMPOSÉ (route ``POST ventes/devis/auto/``,
# garde ``ventes_creer``) : un brouillon est une écriture INTERNE (précédent
# ``creer_auto``). Entrées = sous-ensemble de ``DevisAutoRequest`` ; ni remise
# globale (montant), ni puissance cible (refusée en mode imposé).
COMPOSER_DEVIS = AgentAction(
    key='ventes.devis.composer',
    label='Composer un devis (kit imposé)',
    description=(
        "Sert à : créer un devis brouillon résidentiel au kit demandé "
        "(nombre de panneaux, onduleur, batterie), même sans facture sur le "
        "lead. Ne pas utiliser pour : une V2 ni la correction d'un devis "
        "existant (il crée TOUJOURS un devis séparé), dimensionner depuis la "
        "facture (creer_auto) ni un lead commercial ou agricole. Exemple : "
        + _EXEMPLE_FONDATEUR + " → lead, nb_panneaux=10, onduleur_kw=10, "
        "onduleur_phase=triphase, batterie_kwh=5. Résultat : devis "
        "brouillon et ses lignes TTC ; 409 choix si un produit est ambigu."
    ),
    endpoint='/api/django/ventes/devis/auto/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'lead': _entier('Identifiant du lead (résidentiel).'),
            'client': _entier('Identifiant du client — on remonte à son lead '
                              'le plus récent.'),
            'nb_panneaux': _entier('Nombre de panneaux (1 à 200), obligatoire.'),
            'panneau_produit_id': _entier('Produit panneau (catalogue) ; '
                                          'absent : 710 Wc du catalogue.'),
            'onduleur_produit_id': _entier('Produit onduleur, OU onduleur_kw '
                                           '+ onduleur_phase.'),
            'onduleur_kw': {'type': 'number',
                            'description': "Puissance de l'onduleur (0,5 à 100 kW)."},
            'onduleur_phase': {'type': 'string',
                               'enum': ['monophase', 'triphase']},
            'batterie_produit_id': _entier('Produit batterie, OU batterie_kwh.'),
            'batterie_kwh': {'type': 'number',
                             'description': 'Capacité de batterie (0,5 à 100 kWh).'},
            'scenario': {'type': 'string', 'enum': ['sans', 'avec'],
                         'description': 'Avec ou sans batterie (une batterie '
                                        'donnée vaut « avec »).'},
            'taux_tva': {'type': 'number',
                         'description': 'Taux de TVA en % (défaut : taux '
                                        'standard de la société).'},
        },
        'required': ['nb_panneaux'],
    },
    required_permission=_PERM_CREER,
    risk=RISK_INTERNAL,
    carte='devis_cree',
    lot=LOT_COPILOTE,
    objets={'lead': 'lead', 'client': 'client'},
)


# COP2-V5 — lire les lignes d'UN devis (``GET devis/{id}/lignes-assistant/``,
# garde ``LectureVentes`` = ``ventes_voir``) : l'id de ligne que
# ``ligne_modifier`` / ``ligne_supprimer`` demandent. Prix TTC seulement.
LIGNES_DEVIS = AgentAction(
    key='ventes.devis.lignes',
    label='Lire les lignes du devis',
    description=(
        "Sert à : lire les lignes d'un devis (ligne_id, produit, quantité, "
        "prix TTC) avant de modifier ou retirer une ligne. Ne pas utiliser "
        "pour : modifier le devis ni lire un prix d'achat (jamais servi). "
        "Exemple : « passe la batterie du devis 451 à 2 » → id=451, puis "
        "ligne_modifier avec le ligne_id lu. Résultat : référence, statut, "
        "total TTC et lignes du devis."
    ),
    endpoint='/api/django/ventes/devis/{id}/lignes-assistant/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {'id': _entier('Identifiant du devis.')},
        'required': ['id'],
    },
    required_permission='ventes_voir',
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
    objets={'id': 'devis'},
)


# AIC99 — lot « copilote » (copilote allumé seulement), hors ``VENTES_ACTIONS``.
VENTES_ACTIONS_COPILOTE = (EXPLIQUER_DEVIS, ENVOYER_EMAIL_DEVIS,
                           CHERCHER_CATALOGUE, COMPOSER_DEVIS, LIGNES_DEVIS)


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
    for action in VENTES_ACTIONS + VENTES_ACTIONS_COPILOTE:
        try:
            register(action)
        except ValueError:
            # Déjà enregistrée — registre déterministe, rien à faire.
            pass
