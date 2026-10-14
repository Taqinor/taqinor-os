"""ENF6 — briques OpenAPI partagées du CRM (paramètres, corps, réponses).

Le schéma d'une opération doit être EXACT : tout paramètre de requête lu par la
vue est déclaré, tout corps attendu est décrit, toute réponse qui n'est pas le
``serializer_class`` de la vue le dit. Ces briques évitent de répéter les mêmes
``inline_serializer`` / ``OpenApiParameter`` dans ``views.py``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

#: Réponse « objet libre » (dict dont la forme dépend de la situation).
OBJ = OpenApiTypes.OBJECT

XLSX_TYPE = ('application/vnd.openxmlformats-officedocument.'
             'spreadsheetml.sheet')
#: Réponse binaire .xlsx.
EXPORT_XLSX = {(200, XLSX_TYPE): OpenApiTypes.BINARY}
#: Réponse binaire .ics (calendrier).
EXPORT_ICS = {(200, 'text/calendar'): OpenApiTypes.BINARY}


def liste(nom):
    """Réponse « liste d'objets » (tableau JSON, pas d'enveloppe)."""
    return inline_serializer(nom, {}, many=True)


def param(nom, typ=OpenApiTypes.STR, *, required=False, enum=None,
          description=None):
    """Paramètre de REQUÊTE (query string) déclaré."""
    return OpenApiParameter(
        nom, typ, OpenApiParameter.QUERY, required=required, enum=enum,
        description=description)


def corps(nom, **champs):
    """Corps de requête / réponse décrit en ligne (champs DRF nommés)."""
    return inline_serializer(nom, champs)


def ids_requis(**kw):
    """Liste d'identifiants entiers NON vide (sélection d'une action de masse)."""
    # ``min_length=1`` : le schéma publie ``minItems: 1`` (avant, ``[]``
    # semblait valide et le serveur répondait « Sélectionnez au moins un… »).
    return serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, min_length=1, **kw)


# ── Paramètres de requête réutilisés ────────────────────────────────────────

P_Q = param('q', description='Texte recherché.')
#: ``jours`` des agrégats KPI (MRY19/MRY21/CAD87) : contrat TOLÉRANT —
#: entier borné à [1, 365] ; une valeur non entière retombe sur le défaut
#: (``params_requete.entier_param(tolerant=True)``). Déclaré entier OU texte,
#: pour que le schéma dise ce que le serveur fait.
P_JOURS = OpenApiParameter(
    'jours', {'anyOf': [{'type': 'integer'}, {'type': 'string'}]},
    OpenApiParameter.QUERY, required=False,
    description='Fenêtre en jours (1 à 365, bornée) ; une valeur non entière '
                'retombe sur le défaut de la vue.')
P_OWNER = param('owner', OpenApiTypes.INT,
                description='Identifiant du responsable.')
#: ``owner`` : identifiant entier OU le mot « null » (responsable vide).
P_OWNER_OU_NULL = OpenApiParameter(
    'owner',
    {'anyOf': [{'type': 'integer'}, {'type': 'string', 'enum': ['null']}]},
    OpenApiParameter.QUERY, required=False,
    description='Identifiant du responsable, ou « null » (sans responsable).')
P_LEAD = param('lead', OpenApiTypes.INT, description='Identifiant du lead.')
P_LEAD_REQ = param('lead', OpenApiTypes.INT, required=True,
                   description='Identifiant du lead.')
P_CLE = param('cle', description='Clé du message.')
P_LANGUE = param('langue', description='Langue du message (fr, darija…).')
P_SCOPE = param('scope', description='Portée de la liste (today, lead…).')
P_ARCHIVED = param('archived', enum=['only', 'all'],
                   description='only = archivés seulement, all = tous.')
P_ARCHIVED_FLAG = param(
    'archived', description="1/true pour inclure les éléments archivés.")
#: ERR-ENF11-FUZZ-CRM — date de requête facultative : ``params_requete.
#: date_param`` lit une valeur VIDE (``?fin=``) comme « non renseignée ». Le
#: schéma publie donc « date OU chaîne vide », ce que le serveur accepte.
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}


def param_date(nom, description=None):
    """Paramètre de requête date facultatif (vide = non renseigné)."""
    return OpenApiParameter(nom, DATE_OU_VIDE, OpenApiParameter.QUERY,
                            required=False, description=description)


P_DEBUT = param_date('debut', description='Début (AAAA-MM-JJ).')
P_FIN = param_date('fin', description='Fin (AAAA-MM-JJ).')
#: ``entite`` : contrat TOLÉRANT (NTADM2, ``core.entite_scoping``) — une
#: valeur non numérique vaut « pas de filtre » (jamais un 400) : déclaré entier
#: OU texte pour que le schéma dise ce que le serveur fait.
P_ENTITE = OpenApiParameter(
    'entite', {'anyOf': [{'type': 'integer'}, {'type': 'string'}]},
    OpenApiParameter.QUERY, required=False,
    description="Filtre par entité (société juridique) ; une valeur non "
                "numérique est ignorée.")


#: ENF11 — ``{activite_id}`` des actions ``epingler``/``desepingler`` du lead :
#: PK entière d'une entrée du chatter (``LeadActivity``), que drf-spectacular
#: ne peut pas typer depuis le modèle ``Lead``.
P_ACTIVITE_ID = OpenApiParameter(
    'activite_id', OpenApiTypes.INT, OpenApiParameter.PATH,
    description="Identifiant de l'entrée du chatter du lead.")


def _cible_unique(a, b):
    """Exactement UN de ``a`` / ``b`` (entier) — l'autre absent ou nul."""
    return {'oneOf': [
        {'required': [a], 'properties': {a: {'type': 'integer'}}},
        {'required': [b], 'properties': {b: {'type': 'integer'}}},
    ]}


#: ERR-ENF11-FUZZ-CRM — une salle de vente référence exactement un lead OU un
#: client (``SalleVenteSerializer.validate``), à la création.
SALLE_CIBLE_UNIQUE = {EXTENSION_CORPS_RESSERRE: _cible_unique('lead', 'client')}

#: ERR-ENF11-FUZZ-CRM — un objectif mensuel (défaut) porte son mois, un
#: trimestriel son trimestre (``ObjectifCommercialSerializer.validate``) ;
#: création et remplacement (PUT), jamais le PATCH (repli sur la ligne).
OBJECTIF_PERIODE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['period_type'],
     'properties': {'period_type': {'enum': ['year']}}},
    {'required': ['period_month'],
     'properties': {'period_type': {'enum': ['month']},
                    'period_month': {'type': 'integer'}}},
    {'required': ['period_type', 'period_quarter'],
     'properties': {'period_type': {'enum': ['quarter']},
                    'period_quarter': {'type': 'integer'}}},
]}}

#: ERR-ENF11-FUZZ-CRM — conversion lead → client : le mode « lier » exige
#: ``client_id`` (``clients_identite.convertir_lead_en_client``).
CONVERSION_LIER_CLIENT = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'properties': {'mode': {'enum': ['nouveau', 'aucun']}}},
    {'required': ['client_id'], 'properties': {
        'mode': {'enum': ['lier']}, 'client_id': {'type': 'integer'}}},
]}}


def _texte_avec(motif):
    return {'type': 'string', 'pattern': motif}


#: ERR-ENF11-FUZZ-CRM — « locataire » (``cadence_reponses.refus_proprietaire``) :
#: ``proprietaire_inconnu: true`` OU les coordonnées du propriétaire — un nom
#: non blanc et un numéro joignable (au moins un chiffre non nul ; le
#: téléphone prime sur le WhatsApp quand il est renseigné). Textes sans NUL.
_SANS_NUL = r'^[^\x00]*$'
_NUMERO = r'^[^\x00]*[1-9][^\x00]*$'
LOCATAIRE_SUITE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['proprietaire_inconnu'],
     'properties': {'proprietaire_inconnu': {'enum': [True]}}},
    {'required': ['proprietaire'], 'properties': {'proprietaire': {
        'type': 'object', 'required': ['nom'],
        'properties': {'nom': _texte_avec(r'^[^\x00]*\S[^\x00]*$'),
                       'prenom': _texte_avec(_SANS_NUL)},
        'anyOf': [
            {'required': ['telephone'],
             'properties': {'telephone': _texte_avec(_NUMERO),
                            'whatsapp': _texte_avec(_SANS_NUL)}},
            {'required': ['whatsapp'],
             'properties': {'whatsapp': _texte_avec(_NUMERO),
                            'telephone': {'type': 'string', 'maxLength': 0}}},
        ]}}},
]}}
