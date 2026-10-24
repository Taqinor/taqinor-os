"""ENF6 — briques OpenAPI partagées du CRM (paramètres, corps, réponses).

Le schéma d'une opération doit être EXACT : tout paramètre de requête lu par la
vue est déclaré, tout corps attendu est décrit, toute réponse qui n'est pas le
``serializer_class`` de la vue le dit. Ces briques évitent de répéter les mêmes
``inline_serializer`` / ``OpenApiParameter`` dans ``views.py``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema_field, inline_serializer
from rest_framework import serializers

from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE, MOTIF_QUERY_SANS_NUL

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
#: pour que le schéma dise ce que le serveur fait. Le texte reste « sans
#: caractère nul » : le serveur refuse un nul partout en 400
#: (``core.parametres_requete.verifier_caractere_nul``) — api-fuzz-full 24/10.
P_JOURS = OpenApiParameter(
    'jours', {'anyOf': [{'type': 'integer'},
                        {'type': 'string', 'pattern': MOTIF_QUERY_SANS_NUL}]},
    OpenApiParameter.QUERY, required=False,
    description='Fenêtre en jours (1 à 365, bornée) ; une valeur non entière '
                'retombe sur le défaut de la vue.')
P_OWNER = param('owner', OpenApiTypes.INT,
                description='Identifiant du responsable.')
#: ERR-ENF11-FUZZ-CRM — ``owner`` de ``relance-etapes/suivi`` et ``/controle`` :
#: identifiant ENTIER d'un responsable (≥ 1) ; un texte non numérique reste un
#: 400, un entier inconnu / hors portée un 404 (``controle``) ou une liste vide.
P_OWNER_ID = OpenApiParameter(
    'owner', {'type': 'integer', 'minimum': 1}, OpenApiParameter.QUERY,
    required=False, description='Identifiant du responsable (entier >= 1).')
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


def param_entier_ou_vide(nom, description=None, minimum=None):
    """Paramètre de requête ENTIER facultatif dont la valeur VIDE (``?nom=``)
    veut dire « sans filtre » : le schéma publie « entier OU chaîne vide »,
    exactement ce que ``params_requete.entier_param`` accepte (le serveur
    refuse tout le reste en 400)."""
    entier = {'type': 'integer'}
    if minimum is not None:
        entier['minimum'] = minimum
    return OpenApiParameter(
        nom, {'anyOf': [entier, {'type': 'string', 'maxLength': 0}]},
        OpenApiParameter.QUERY, required=False, description=description)


def param_texte_sans_nul(nom, description=None):
    """Paramètre de requête TEXTE sans caractère nul (Postgres le refuse dans
    tout littéral : le serveur répond 400 — le schéma ne le génère plus)."""
    return OpenApiParameter(
        nom, {'type': 'string', 'pattern': MOTIF_SANS_NUL},
        OpenApiParameter.QUERY, required=False, description=description)


def param_enum_ou_vide(nom, valeurs, description=None):
    """Paramètre de requête à vocabulaire dont la valeur vide = « tous »."""
    return OpenApiParameter(
        nom, {'type': 'string', 'enum': [*valeurs, '']},
        OpenApiParameter.QUERY, required=False, description=description)


P_LANGUE = param('langue', description='Langue du message (fr, darija…).')


def parametres_message(cles, langues):
    """ENF11 nocturne — ``relance-etapes/{id}/message/`` : ``cle`` et ``langue``
    sont des VOCABULAIRES (le serveur répond 400 hors liste) ; publiés en
    ``enum`` tirés des constantes du serveur, jamais recopiés."""
    return [param('cle', enum=[*cles], description='Texte de réponse convenu.'),
            param('langue', enum=[*langues], description='Langue du message.')]


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
    'entite', {'anyOf': [{'type': 'integer', 'minimum': 1},
                         {'type': 'string', 'maxLength': 0}]},
    OpenApiParameter.QUERY, required=False,
    description="Filtre par entité (société juridique) : entier, ou vide "
                "(= sans filtre) ; une valeur non numérique répond 400 "
                "(CI #997, core.entite_scoping.entite_id_demandee).")


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


def _texte_avec(motif, longueur_max=None):
    schema = {'type': 'string', 'pattern': motif}
    if longueur_max:
        schema['maxLength'] = longueur_max
    return schema


#: ERR-ENF11-FUZZ-CRM — « locataire » (``cadence_reponses.refus_proprietaire``) :
#: ``proprietaire_inconnu: true`` OU les coordonnées du propriétaire — un nom
#: non blanc et un numéro joignable. Textes sans NUL, bornés comme les colonnes
#: de ``crm.Lead`` (nom/prénom 255, téléphone/WhatsApp 50 : au-delà, Postgres
#: refusait l'écriture).
#: 3e drainage 24/10 : le motif du nom était ``\S`` (qui MATCHE le NUL : un nom
#: « abc\0 » passait pour conforme) — c'est ``MOTIF_NON_BLANC_SANS_NUL``. Le
#: numéro exige un chiffre 3-9 : ``normalize_phone`` retire l'indicatif ``212``
#: et les zéros de tête, donc « 2120 » (chiffres 0-2 seuls) devient vide et le
#: serveur répond 400 ; un chiffre 3-9 survit à toute normalisation.
_SANS_NUL = r'^[^\x00]*$'
_NUMERO = r'^[^\x00]*[3-9][^\x00]*$'
LOCATAIRE_SUITE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['proprietaire_inconnu'],
     'properties': {'proprietaire_inconnu': {'enum': [True]}}},
    {'required': ['proprietaire'], 'properties': {'proprietaire': {
        'type': 'object', 'required': ['nom'],
        'properties': {'nom': _texte_avec(MOTIF_NON_BLANC_SANS_NUL, 255),
                       'prenom': _texte_avec(_SANS_NUL, 255)},
        'anyOf': [
            {'required': ['telephone'],
             'properties': {'telephone': _texte_avec(_NUMERO, 50),
                            'whatsapp': _texte_avec(_SANS_NUL, 50)}},
            {'required': ['whatsapp'],
             'properties': {'whatsapp': _texte_avec(_NUMERO, 50),
                            'telephone': {'type': 'string', 'maxLength': 0}}},
        ]}}},
]}}


#: Nocturne 24/10 — ``relance-etapes/{id}/reporter/`` : une ÉCHÉANCE est
#: obligatoire — ``due_at`` non vide, OU ``rappel_le`` (jour AAAA-MM-JJ, heure
#: facultative) ; un corps vide est refusé (400 « Échéance invalide »).
MOTIF_JOUR = r'^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
MOTIF_HEURE = r'^([01][0-9]|2[0-3]):[0-5][0-9]$'
#: Jour PUBLIÉ de ``rappel_le`` : un jour du calendrier de l'an 0001 à 9999
#: (``date.fromisoformat`` refuse l'an 0000 et les jours inexistants). Le
#: 29 février est exclu du motif publié (année bissextile non connue) ; le
#: serveur, lui, l'accepte les années bissextiles.
MOTIF_JOUR_PUBLIE = (
    r'^(?:0(?:00[1-9]|0[1-9][0-9]|[1-9][0-9]{2})|[1-9][0-9]{3})-'
    r'(?:(?:0[13578]|1[02])-(?:0[1-9]|[12][0-9]|3[01])'
    r'|(?:0[469]|11)-(?:0[1-9]|[12][0-9]|30)'
    r'|02-(?:0[1-9]|1[0-9]|2[0-8]))$')


class ChampJour(serializers.RegexField):
    """``rappel_le`` : le serveur valide la forme (``MOTIF_JOUR``) puis le
    calendrier (400 nommé) ; le schéma publie le motif calendaire exact.
    (Le surcharge est posée dans ``__init__`` : un champ copié par DRF la
    perd sinon.)"""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override
        super().__init__(MOTIF_JOUR, **kwargs)
        set_override(self, 'field', {'type': 'string', 'pattern': MOTIF_JOUR_PUBLIE})


REPORTER_ECHEANCE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['due_at'], 'properties': {'due_at': {'minLength': 1}}},
    {'required': ['rappel_le']},
]}}


def _schema_questions():
    from .models import QuestionnaireLien
    return {'type': 'object', 'additionalProperties': False,
            'properties': {cle: {'type': 'boolean'} for cle in QuestionnaireLien.SECTIONS_CLES}}


@extend_schema_field(_schema_questions())
class QuestionsQuestionnaire(serializers.DictField):
    """ENF11 (nocturne 15/10) — ``questions`` du lien questionnaire :
    ``{section: booléen}``, sections de la whitelist SEULEMENT (une clé
    inconnue était « conforme » au schéma puis refusée en 400)."""


#: ENF11 (nocturne 15/10) — ``?periode=AAAA-MM`` du roll-up forecast : année
#: 0001-9999, mois 01-12 — le motif PUBLIÉ est celui que la vue applique.
MOTIF_PERIODE_MOIS = r'^(?!0000)[0-9]{4}-(0[1-9]|1[0-2])$'


def param_periode_ou_vide(nom='periode'):
    """``?periode=AAAA-MM`` facultatif ; vide = non renseignée."""
    return OpenApiParameter(
        nom, {'anyOf': [{'type': 'string', 'pattern': MOTIF_PERIODE_MOIS},
                        {'type': 'string', 'maxLength': 0}]},
        OpenApiParameter.QUERY, required=False, description='AAAA-MM')


#: ENF11 (nocturne 15/10) — réponse du POST ``leads/{id}/locataire/`` : l'issue
#: (``proprietaire_cree`` 201, ``proprietaire_relie`` / ``perdu_locataire`` 200),
#: la fiche propriétaire (null quand le propriétaire est inconnu) et le locataire.
LOCATAIRE_ISSUE = inline_serializer('CrmLeadLocataireIssue', {
    'issue': serializers.CharField(),
    'lead_proprietaire': serializers.DictField(allow_null=True),
    'locataire': serializers.DictField(),
})


def corps_bulk(actions):
    """CI #997 (2) — paramètres PROPRES À CHAQUE action de ``leads/bulk/``.

    Le composant ne déclare que ``action`` + ``ids`` ; or ``fiche_bulk.
    apply_bulk_action`` valide, AVANT tout traitement, le paramètre dont
    l'action a besoin (``tag``, ``stage``, ``canal``, ``priorite``,
    ``relance_date``, ``motif``, ``due_date`` + ``summary``). Le schéma disait
    « ``add_tag`` sans ``tag`` » conforme et le serveur répondait 400. Une
    branche par famille d'actions ; les actions sans paramètre sont groupées."""
    from . import stages
    non_blanc = {'type': 'string', 'pattern': r'\S'}
    avec_parametre = {
        ('add_tag', 'remove_tag'): {'tag': non_blanc},
        ('set_stage',): {'stage': {'type': 'string', 'enum': list(stages.STAGES)}},
        ('set_canal',): {'canal': non_blanc},
        ('set_priorite',): {'priorite': {
            'type': 'string', 'enum': ['basse', 'normale', 'haute']}},
        ('set_relance',): {'relance_date': {'type': 'string', 'format': 'date'}},
        ('set_perdu',): {'motif': non_blanc},
        ('plan_activity',): {'due_date': {'type': 'string', 'format': 'date'},
                             'summary': non_blanc},
    }
    sans_parametre = sorted(
        set(actions) - {a for noms in avec_parametre for a in noms})
    branches = [{'properties': {'action': {'enum': sans_parametre}}}]
    for noms, proprietes in avec_parametre.items():
        branches.append({
            'required': sorted(proprietes),
            'properties': {'action': {'enum': list(noms)}, **proprietes}})
    return {EXTENSION_CORPS_RESSERRE: {'anyOf': branches}}
