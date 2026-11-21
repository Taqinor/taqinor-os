"""AG9 — Actions agentiques de l'app installations (chantiers / interventions).

Déclare en code, via le registre AG1 (:mod:`apps.agent.registry`), les deux
actions que l'agent (relais FastAPI + JWT utilisateur) peut proposer sur le
module chantiers/installations. Ce sont les remplaçantes-catalogue des deux
outils LangChain aujourd'hui codés en dur dans
``backend/fastapi_ia/app/services/action_tools.py`` :

* ``planifier_visite_maintenance`` → ``POST /api/django/installations/interventions/``
  (intervention de type ``controle`` planifiée sur un chantier à une date) ;
* ``brouillon_commande_chantier`` → ``POST
  /api/django/installations/chantiers/{id}/commander-besoin/`` (bon de commande
  fournisseur BROUILLON pour les manques d'un chantier).

Le module est PUREMENT des métadonnées : aucune exécution ici. L'exécution
garde le motif existant — FastAPI relaie le JWT de l'utilisateur vers
l'``endpoint`` nommé, et Django re-vérifie la permission + la société à ce
moment-là. Le ``company`` n'apparaît JAMAIS dans les ``inputs`` (forcé côté
serveur). Pour ``commander-besoin``, le ``<id>`` du chantier est modélisé comme
un input requis que le gabarit de chemin consomme.

Permissions (copilote vague 2) : chacune est le code que la ROUTE exige
(``get_permissions`` des viewsets) — ``achats_commander`` pour
``commander-besoin`` (REP3), ``intervention_gerer`` pour la création
d'intervention (REP4). Les deux écrivent sur des données existantes ou dans
la journée de quelqu'un : propositions À CONFIRMER.

Enregistré (idempotent) au démarrage par :func:`register_installation_actions`,
appelée depuis ``InstallationsConfig.ready()``.
"""
from __future__ import annotations

from apps.agent.registry import (
    AgentAction, LOT_COPILOTE, RISK_INTERNAL, RISK_OUTWARD, register,
)


# Type d'intervention d'une visite de maintenance : valeur exacte de
# ``Intervention.Type.CONTROLE`` (apps/installations/models_intervention.py).
_VISITE_TYPE = 'controle'


#: REP4 — garde RÉELLE de la création d'intervention : ``IsResponsableOrAdmin``
#: + ``DroitDeLaGrille('intervention_gerer')`` (ASEC72), et
#: ``technicien_assign`` en plus quand le corps porte ``technicien``
#: (``InterventionViewSet.get_permissions``, ASEC50).
_PERM_INTERVENTION = 'intervention_gerer'


# REP4 — une intervention datée entre dans la journée d'un technicien : une
# écriture sur l'agenda de quelqu'un → proposition À CONFIRMER. Le relais
# n'applique pas un ``default`` du schéma alors que ``type_intervention`` est
# obligatoire au modèle : il est REQUIS, à valeur unique (contrôle).
PLANIFIER_VISITE_MAINTENANCE = AgentAction(
    key='installations.intervention.planifier_visite',
    label='Visite de maintenance : entre dans la journée du technicien désigné, notifié',
    description=(
        "Sert à : planifier une visite de maintenance "
        "(intervention de type contrôle) sur un chantier à une date. Le "
        "technicien désigné est notifié ; sans technicien, la visite n'est "
        "dans la journée de personne (l'installateur du chantier est mis "
        "dans l'équipe). Ne pas utiliser pour : une pose ni la visite "
        "technique d'un lead avant devis (fiche du lead). Exemple : "
        "« contrôle du "
        "chantier 12 le 2026-12-03 par le technicien 9 » → installation=12, "
        "type_intervention=controle, date_prevue, technicien=9. Résultat : "
        "l'intervention créée ; 409 si le chantier est annulé."
    ),
    endpoint='/api/django/installations/interventions/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'installation': {
                'type': 'integer',
                'title': 'Chantier (id)',
                'description': 'Chantier à visiter.',
            },
            'type_intervention': {
                'type': 'string',
                'title': "Type d'intervention",
                'enum': [_VISITE_TYPE],
                'description': 'Toujours controle.',
            },
            'date_prevue': {
                'type': 'string',
                'format': 'date',
                'title': 'Date prévue',
                'description': 'Date prévue (AAAA-MM-JJ).',
            },
            'technicien': {
                'type': 'integer',
                'title': 'Technicien (id)',
                'description': ('Qui fait la visite (demande-le) ; '
                                "l'affecter exige le droit technicien_assign."),
            },
        },
        'required': ['installation', 'type_intervention', 'date_prevue'],
    },
    required_permission=_PERM_INTERVENTION,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Planifier une visite de maintenance (contrôle) sur le chantier, à "
        "cette date ; le technicien désigné est notifié."),
    # Vague 2 — l'aperçu NOMME le chantier et le technicien
    # (`selectors_libelles.libelles_installations`, compte résolu par l'agent).
    objets={'installation': 'chantier', 'technicien': 'utilisateur'},
)


#: REP3 — garde RÉELLE de ``commander-besoin`` : ``IsResponsableOrAdmin`` +
#: ``HasPermissionOrLegacy('achats_commander')`` (branche dédiée de
#: ``InstallationViewSet.get_permissions``, ACHT54) — jamais
#: ``installation_gerer`` (le Technicien voyait l'outil et recevait 403).
_PERM_COMMANDER = 'achats_commander'


# REP3 — la route crée des BCF BROUILLONS (un par fournisseur) ET tente de
# faire passer un chantier « Signé » à « Matériel commandé »
# (``_avancer_materiel_commande``, ``exiger_couverture=False``) : deux effets
# sur des données existantes → proposition À CONFIRMER dont l'aperçu dit les
# deux. Corps de la route (``CommanderBesoinRequete``) : ``fournisseur``,
# ``fournisseurs`` {produit_id: fournisseur_id}, ``produits`` [ids].
BROUILLON_COMMANDE_CHANTIER = AgentAction(
    key='installations.chantier.commander_besoin',
    label="Manques en BCF BROUILLONS (rien n'est envoyé) ; Signé → Matériel commandé",
    description=(
        "Sert à : créer, après confirmation, les bons de commande "
        "fournisseur BROUILLONS des manques de matériel d'un chantier (un "
        "par fournisseur) ; rien n'est envoyé au fournisseur. Un chantier "
        "« Signé » passe aussi à « Matériel commandé » quand ses étapes le "
        "permettent. Ne pas utiliser pour : envoyer une commande ni une "
        "commande hors chantier. Exemple : « commande ce qui manque pour le "
        "chantier 12 » → id=12. Résultat : les BCF brouillons et le statut du "
        "chantier ; 409 si rien ne manque, si un BCF ouvert couvre déjà ou "
        "sans fournisseur."
    ),
    endpoint='/api/django/installations/chantiers/{id}/commander-besoin/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {
                'type': 'integer',
                'title': 'Chantier (id)',
                'description': 'Chantier dont on commande les manques '
                               '(consommé par le gabarit de chemin).',
            },
            'fournisseur': {
                'type': 'integer',
                'title': 'Fournisseur (id)',
                'description': ('Fournisseur imposé aux lignes ; absent : '
                                'celui du produit.'),
            },
            'fournisseurs': {
                'type': 'object',
                'title': 'Fournisseur par produit',
                'additionalProperties': {'type': 'integer'},
                'description': '{"<produit_id>": <fournisseur_id>}.',
            },
            'produits': {
                'type': 'array',
                'title': 'Produits à commander (ids)',
                'items': {'type': 'integer'},
                'description': 'Absent : tous les manques.',
            },
        },
        'required': ['id'],
    },
    required_permission=_PERM_COMMANDER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Créer les bons de commande fournisseur BROUILLONS des manques du "
        "chantier (rien n'est envoyé) ; un chantier « Signé » peut passer à "
        "« Matériel commandé »."),
    objets={'id': 'chantier', 'fournisseur': 'fournisseur'},
)


#: Copilote vague 2 — lecture du module : ``LectureDuModule`` (installations)
#: des routes de l'assistant (``InstallationViewSet.get_permissions``).
_PERM_LIRE = 'installation_voir'


# CHTA2 — la fiche compacte d'UN chantier (GET chantiers/{id}/etat-assistant/,
# contrat `assistant_chantier_etat.json`). Lecture : exécutée sans proposition.
ETAT_CHANTIER = AgentAction(
    key='installations.chantier.etat',
    label="État d'un chantier : prêt à poser ?",
    description=(
        "Sert à : dire où en est UN chantier — prêt à poser ou non et "
        "pourquoi (manques de matériel en quantités, date de pose, "
        "technicien, acompte exigé et encaissé, intervention de pose, étape "
        "suivante), la prochaine chose à faire (`a_faire`) et les liens des "
        "écrans. Ne pas utiliser pour : changer le statut (jamais par "
        "l'assistant : lien de la fiche) ni chercher un chantier "
        "(installations.chantiers.liste). Exemple : « le chantier 12 est-il "
        "prêt ? » → id=12. Résultat : la fiche, sans aucun prix ni coût ; "
        "404 si le chantier est hors de ta portée."
    ),
    endpoint='/api/django/installations/chantiers/{id}/etat-assistant/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'title': 'Chantier (id)',
                   'description': 'Chantier lu (consommé par le chemin).'},
        },
        'required': ['id'],
    },
    required_permission=_PERM_LIRE,
    risk=RISK_INTERNAL,
    carte='fiche_chantier',
    lot=LOT_COPILOTE,
    objets={'id': 'chantier'},
)


#: Statuts filtrables de la liste (canoniques, sauf « Clôturé »).
_STATUTS_LISTE = ['signe', 'materiel_commande', 'planifie', 'en_cours',
                  'installe', 'receptionne']


# CHTA3 — la liste compacte (GET chantiers/assistant/, contrat
# `assistant_chantiers.json`). Lecture : exécutée sans proposition.
LISTE_CHANTIERS = AgentAction(
    key='installations.chantiers.liste',
    label='Chantiers en cours, bloqués ou posés cette semaine',
    description=(
        "Sert à : lister les chantiers de ta portée — vue en_cours, bloques "
        "(sans date, sans technicien, date sans intervention de pose, date "
        "dépassée, acompte exigé non encaissé) ou poses_semaine — ou "
        "retrouver un chantier par référence, nom du client (q) ou lead. Le "
        "matériel n'y est PAS calculé : lis installations.chantier.etat sur "
        "une ligne. Ne pas utiliser pour : l'état détaillé d'un chantier. "
        "Exemple : « quels chantiers sont bloqués ? » → vue=bloques. "
        "Résultat : {vue, total, limite, lignes[], note, lien}, sans prix."
    ),
    endpoint='/api/django/installations/chantiers/assistant/',
    method='GET',
    inputs={
        'type': 'object',
        'properties': {
            'vue': {'type': 'string', 'title': 'Vue',
                    'enum': ['en_cours', 'bloques', 'poses_semaine'],
                    'description': 'Défaut en_cours.'},
            'q': {'type': 'string', 'title': 'Recherche', 'maxLength': 100,
                  'description': 'Référence du chantier ou nom du client.'},
            'lead': {'type': 'integer', 'title': 'Lead (id)',
                     'description': "Lead d'origine du chantier."},
            'statut': {'type': 'string', 'title': 'Statut du chantier',
                       'enum': _STATUTS_LISTE},
            'technicien': {'type': 'integer', 'title': 'Technicien (id)',
                           'description': 'Technicien responsable.'},
            'debut': {'type': 'string', 'format': 'date', 'title': 'Semaine du',
                      'description': 'poses_semaine : un jour de la semaine voulue.'},
            'limite': {'type': 'integer', 'title': 'Nombre de lignes',
                       'minimum': 1, 'maximum': 25, 'description': 'Défaut 10.'},
        },
        'required': [],
    },
    required_permission=_PERM_LIRE,
    risk=RISK_INTERNAL,
    carte='liste_chantiers',
    lot=LOT_COPILOTE,
    objets={'technicien': 'utilisateur', 'lead': 'lead'},
)


# CHTA4 — POST interventions/suggerer-creneau/ (XFSM2) : une route de LECTURE
# (LectureDuModule ; « NE MUTE RIEN ») servie en POST — `lecture=True` : ni
# proposition, ni décompte dans le plafond des écritures silencieuses.
SUGGERER_CRENEAU = AgentAction(
    key='installations.planning.suggerer',
    label='Créneaux proposés (technicien, jour) pour une intervention',
    description=(
        "Sert à : proposer 3 créneaux (technicien, jour) pour une "
        "intervention d'un chantier — jour sans autre intervention ni "
        "indisponibilité, charge la plus faible, puis distance. Seuls les "
        "comptes déjà affectés à une intervention sont proposés ; les "
        "visites techniques ne comptent pas ; rien n'est réservé. Ne pas "
        "utiliser pour : planifier (installations.chantier.planifier, à "
        "part) ni une visite de lead. Exemple : « quand poser le chantier "
        "12 ? » → chantier=12, type_intervention=pose. Résultat : "
        "{chantier_id, propositions[]}."
    ),
    endpoint='/api/django/installations/interventions/suggerer-creneau/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'chantier': {'type': 'integer', 'title': 'Chantier (id)'},
            'type_intervention': {
                'type': 'string', 'title': "Type d'intervention",
                'enum': ['pose', 'raccordement', 'mise_en_service',
                         'controle', 'depannage']},
            'duree_jours': {'type': 'integer', 'title': 'Durée (jours)',
                            'minimum': 1, 'maximum': 30,
                            'description': 'Défaut 1.'},
            'date_cible': {'type': 'string', 'format': 'date',
                           'title': 'À partir du',
                           'description': "Défaut aujourd'hui."},
        },
        'required': ['chantier'],
    },
    required_permission=_PERM_LIRE,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
    lecture=True,
    objets={'chantier': 'chantier'},
)


#: CHTA5 — garde de ``planifier-pose`` (``InstallationViewSet.get_permissions``) :
#: ``installation_gerer`` + ``intervention_gerer`` toujours, ``technicien_assign``
#: quand le corps porte ``technicien``.
_PERM_PLANIFIER = 'installation_gerer'


# CHTA5 (B-18, D-W2-CHT-1) — UNE confirmation qui pose la date et le technicien
# du chantier ET l'intervention de pose (sans elle, la pose n'est dans la
# journée de personne). Jamais le statut, jamais un passe-outre d'acompte.
PLANIFIER_POSE = AgentAction(
    key='installations.chantier.planifier',
    label='Pose : date et technicien du chantier + intervention dans sa journée, notifié',
    description=(
        "Sert à : planifier la POSE d'un chantier en un "
        "geste : date de pose (et de fin), technicien du chantier, ET "
        "l'intervention de pose créée ou déplacée — c'est elle qui entre dans "
        "la journée du technicien (notifié). Le statut ne change pas. Ne pas "
        "utiliser pour : une visite de maintenance ni changer le statut. "
        "Exemple : « pose du chantier 12 le 2026-11-24 avec le technicien 9 "
        "» → id=12, date_pose_prevue, technicien=9. Résultat : la fiche du "
        "chantier relue ; 409 nommé si annulé, clôturé, date passée, pose "
        "commencée ou acompte exigé non encaissé (aucun passe-outre)."
    ),
    endpoint='/api/django/installations/chantiers/{id}/planifier-pose/',
    method='POST',
    inputs={
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'title': 'Chantier (id)',
                   'description': 'Chantier dont on planifie la pose.'},
            'date_pose_prevue': {'type': 'string', 'format': 'date',
                                 'title': 'Date de pose',
                                 'description': "AAAA-MM-JJ, aujourd'hui ou plus tard."},
            'date_pose_fin_prevue': {'type': 'string', 'format': 'date',
                                     'title': 'Fin de pose prévue',
                                     'description': 'Facultative, pas avant la date de pose.'},
            'technicien': {'type': 'integer', 'title': 'Technicien (id)',
                           'description': ('Qui pose (demande-le) ; absent : celui '
                                           "du chantier. L'affecter exige le droit "
                                           'technicien_assign.')},
            'creer_intervention': {'type': 'boolean',
                                   'title': 'Intervention de pose',
                                   'description': ('Défaut vrai : crée ou déplace '
                                                   "l'intervention de pose.")},
        },
        'required': ['id', 'date_pose_prevue'],
    },
    required_permission=_PERM_PLANIFIER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Planifier la pose du chantier à cette date : date et technicien du "
        "chantier, intervention de pose créée ou déplacée dans la journée du "
        "technicien (notifié) ; le statut du chantier ne change pas."),
    carte='fiche_chantier',
    lot=LOT_COPILOTE,
    objets={'id': 'chantier', 'technicien': 'utilisateur'},
)


# Catalogue déclaré par cette app (ordre stable).
INSTALLATIONS_ACTIONS = (
    PLANIFIER_VISITE_MAINTENANCE,
    BROUILLON_COMMANDE_CHANTIER,
    ETAT_CHANTIER,
    LISTE_CHANTIERS,
    SUGGERER_CRENEAU,
    PLANIFIER_POSE,
)


def register_installation_actions() -> None:
    """Enregistre les actions de l'app installations dans le registre AG1.

    Idempotent : une action déjà présente (même ``key``) n'est pas
    ré-enregistrée — sûr si le module est importé plusieurs fois (tests,
    rechargement du serveur de dev).
    """
    from apps.agent import registry as _registry

    for action in INSTALLATIONS_ACTIONS:
        if action.key not in _registry._REGISTRY:
            register(action)
