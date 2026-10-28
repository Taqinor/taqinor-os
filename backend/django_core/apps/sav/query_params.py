"""ENF11 — lecture VALIDÉE des paramètres de requête entiers du SAV.

Une valeur non numérique ou hors bornes répond 400 en nommant le paramètre —
jamais 500 (``int('abc')``, dépassement ``timedelta``/entier PostgreSQL).
"""
import re
from datetime import date

from rest_framework.exceptions import ValidationError

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

# Borne haute d'une clé primaire PostgreSQL (integer).
ID_MAX = 2147483647


def ou_vide(schema):
    """ENF11 (api-fuzz-full) — ``entier_param``/``nombre_param`` lisent un
    paramètre VIDE comme « absent » : le schéma le dit (valeur ou chaîne vide)
    au lieu d'annoncer le seul type, que ``?produit=`` contredisait."""
    return {'oneOf': [schema, {'type': 'string', 'enum': ['']}]}


def valeur_param(request, nom):
    """Valeur brute du paramètre ``nom`` (``None`` si absent) ; un paramètre
    RÉPÉTÉ est un tableau, que le schéma (scalaire) ne publie pas -> 400."""
    valeurs = request.query_params.getlist(nom)
    if len(valeurs) > 1:
        raise ValidationError(
            {nom: f"Le paramètre « {nom} » ne doit figurer qu'une fois."})
    return valeurs[0] if valeurs else None


#: CI #956 (api-fuzz « rejected schema-compliant », sav/equipements/?produit=0) —
#: schéma OpenAPI d'un paramètre d'identifiant lu par ``entier_param`` : les
#: bornes PUBLIÉES sont celles que la vue applique (``0`` n'est pas un id).
ENTIER_ID = ou_vide({'type': 'integer', 'minimum': 1, 'maximum': ID_MAX})

#: Plafond de ``?limit=`` (classements de fiabilité du parc).
LIMITE_MAX = 1000
LIMITE = ou_vide({'type': 'integer', 'minimum': 1, 'maximum': LIMITE_MAX})


def entier_param(request, nom, defaut=None, *, mini=1, maxi=ID_MAX):
    """Entier du paramètre ``nom`` (``defaut`` si absent ou vide), borné à
    ``[mini, maxi]`` ; sinon 400."""
    brut = valeur_param(request, nom)
    if brut is None or str(brut).strip() == '':
        return defaut
    try:
        valeur = int(str(brut).strip())
    except ValueError:
        raise ValidationError({nom: 'Entier attendu.'})
    if not mini <= valeur <= maxi:
        raise ValidationError(
            {nom: f'Valeur attendue entre {mini} et {maxi}.'})
    return valeur


#: Date ISO ou chaîne vide : ``date_param`` lit « vide » comme « borne non
#: posée » ; le schéma le DIT au lieu d'annoncer une date seule.
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}

#: ``?export=xlsx`` (ou vide = JSON) — ``choix_param`` refuse toute autre valeur.
EXPORT_XLSX = {'type': 'string', 'enum': ['xlsx', '']}

_ISO_STRICT = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def date_param(request, nom):
    """Date ``AAAA-MM-JJ`` du paramètre ``nom`` (``None`` si absent ou vide) ;
    toute autre forme → 400 nommant le paramètre, jamais ignorée en silence."""
    brut = (valeur_param(request, nom) or '').strip()
    if not brut:
        return None
    try:
        if not _ISO_STRICT.match(brut):
            raise ValueError(brut)
        return date.fromisoformat(brut)
    except ValueError:
        raise ValidationError(
            {nom: 'Date invalide (format attendu : AAAA-MM-JJ).'})


def periode_param(request, jours=30):
    """XSAV16 — ``(debut, fin)`` (datetimes aware, minuit local) des
    paramètres ``debut``/``fin`` ; défaut : ``fin`` = maintenant, ``debut`` =
    ``fin`` − ``jours`` jours. api-fuzz-full 27/10 (ENF11) : ``fin=0001-01-01``
    faisait déborder ``fin − 30 j`` (``OverflowError`` → 500, même avec un
    ``debut`` fourni : le défaut était calculé d'avance) — le défaut n'est plus
    calculé qu'en l'absence de ``debut``, et borné au premier jour du
    calendrier ; la requête (deux dates valides) est servie."""
    from datetime import datetime, timedelta

    from django.utils import timezone

    def _borne(nom):
        jour = date_param(request, nom)
        if jour is None:
            return None
        return datetime(jour.year, jour.month, jour.day,
                        tzinfo=timezone.get_current_timezone())

    fin = _borne('fin') or timezone.now()
    debut = _borne('debut')
    if debut is None:
        try:
            debut = fin - timedelta(days=jours)
        except OverflowError:
            debut = timezone.make_aware(datetime.min)
    return debut, fin


def choix_param(request, nom, choix, defaut=None):
    """Valeur du paramètre ``nom`` parmi ``choix`` (``defaut`` si absent ou
    vide) ; toute autre valeur → 400 nommant le paramètre."""
    brut = valeur_param(request, nom)
    if brut is None or brut == '':
        return defaut
    if brut not in choix:
        raise ValidationError(
            {nom: f"Valeur attendue parmi : {', '.join(choix)}."})
    return brut


def nombre_param(request, nom, mini, maxi):
    """Nombre décimal fini du paramètre ``nom`` dans ``[mini, maxi]`` (``None``
    si absent ou vide) ; sinon 400 nommant le paramètre."""
    brut = (valeur_param(request, nom) or '').strip()
    if not brut:
        return None
    try:
        valeur = float(brut)
    except ValueError:
        valeur = float('nan')
    if not mini <= valeur <= maxi:
        raise ValidationError(
            {nom: f'Nombre attendu entre {mini} et {maxi}.'})
    return valeur


# ── ERR-ENF11-FUZZ-SAV — règles de corps publiées sur UNE opération ─────────
# (``extend_schema(extensions=…)``, combinées en ``allOf`` au corps publié par
# ``core.openapi_erreurs`` ; aucun composant ne change de nom ni de forme).

#: La création d'un ticket exige un ``client`` OU un ``equipement`` (dont le
#: client est repris, ``TicketViewSet.perform_create``) : un ``{}`` était
#: « conforme » puis refusé « client obligatoire ».
CORPS_TICKET_CLIENT_OU_EQUIPEMENT = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'required': ['client'], 'properties': {'client': {'type': 'integer'}}},
    {'required': ['equipement'],
     'properties': {'equipement': {'type': 'integer'}}},
]}}

#: Chaque opération groupée exige SA valeur : ``priorite`` pour « priorite »,
#: ``statut`` pour « statut » (``TicketViewSet.actions_groupees``).
CORPS_ACTIONS_GROUPEES_VALEUR_REQUISE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'properties': {'operation': {'enum': ['priorite']}},
     'required': ['priorite']},
    {'properties': {'operation': {'enum': ['statut']}},
     'required': ['statut']},
    {'properties': {'operation': {'enum': ['technicien', 'annuler']}}},
]}}


#: ``?ordering=`` de la liste des problèmes : le tri par impact (calculé) et les
#: tris simples du filtre de tri ; toute autre valeur → 400, vide = ordre par défaut.
ORDRES_PROBLEME = tuple(
    signe + nom for nom in ('impact', 'reference', 'titre', 'statut', 'created_at')
    for signe in ('', '-'))
ORDRES_PROBLEME_SCHEMA = {'type': 'string', 'enum': [*ORDRES_PROBLEME, '']}


def archives_incluses(request):
    """``?archived=`` publié ``enum: ['1']`` : ``True`` pour ``1``, ``False``
    absent ; toute autre valeur, vide comprise, → 400 nommant le paramètre
    (CI #993, api-fuzz « accepted schema-violating » : ``?archived=AAA``
    filtrait en silence)."""
    brut = request.query_params.get('archived')
    if brut is not None and brut != '1':
        raise ValidationError({'archived': 'Valeur attendue : 1.'})
    return brut == '1'
