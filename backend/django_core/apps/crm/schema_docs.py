"""ENF6 — briques OpenAPI partagées du CRM (paramètres, corps, réponses).

Le schéma d'une opération doit être EXACT : tout paramètre de requête lu par la
vue est déclaré, tout corps attendu est décrit, toute réponse qui n'est pas le
``serializer_class`` de la vue le dit. Ces briques évitent de répéter les mêmes
``inline_serializer`` / ``OpenApiParameter`` dans ``views.py``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

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
    return serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, **kw)


# ── Paramètres de requête réutilisés ────────────────────────────────────────

P_Q = param('q', description='Texte recherché.')
P_JOURS = param('jours', OpenApiTypes.INT,
                description='Fenêtre en jours (1 à 365).')
P_OWNER = param('owner', OpenApiTypes.INT,
                description='Identifiant du responsable.')
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
P_DEBUT = param('debut', OpenApiTypes.DATE, description='Début (AAAA-MM-JJ).')
P_FIN = param('fin', OpenApiTypes.DATE, description='Fin (AAAA-MM-JJ).')
P_ENTITE = param('entite', OpenApiTypes.INT,
                 description="Filtre par entité (société juridique).")
