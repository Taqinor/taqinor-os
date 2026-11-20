"""Agendas externes (reference/api.md §3.4, §4 ; A18-M4) : au plus 3 adresses ICS, lues côté serveur.

Le schéma OpenAPI de chaque route est celui de son échantillon de `contract_samples/`. Aucune
écriture ici ne rend de `geste_id` (api.md §0). L'URL n'est JAMAIS rendue ni journalisée : la forme
ne sert que `hote`. Toute écriture efface l'index en cache des agendas du compte.
"""
import datetime
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.publicapi.validators import UnsafeWebhookURL
from apps.taches import agenda_externe as lecteur
from apps.taches.models.agenda import AgendaExterne
from apps.taches.entrees import MotifPublie, refus_etat
from apps.taches.views.base import PARSEURS, PERMISSIONS, forme_echantillon, reponses
from apps.taches.views.journee import maintenant, par_compte
from apps.taches.views.presence import HorsAssistant
from core.champs_stricts import BooleenStrict, ChaineStricte, EntierStrict
from core.idempotency import IdempotentCreateMixin

AGENDA_EXTERNE = forme_echantillon('agenda_externe')
#: Trois refus, trois phrases (R2-127, F2 n°18) : ce n'est pas une adresse · il faut https · le serveur ne peut
#: pas l'atteindre (hôte introuvable, ou adresse interne).
MESSAGE_PAS_UNE_ADRESSE = "Ce n'est pas une adresse : colle le lien de ton agenda."
MESSAGE_HTTPS = "L'adresse doit commencer par https."
MESSAGE_INJOIGNABLE = 'Adresse injoignable : vérifie le lien.'
MESSAGE_PLAFOND = '3 agendas au plus.'
MESSAGE_DOUBLON = 'Cet agenda est déjà ajouté.'
PAS_RANG = 1024
#: Fenêtre lue à l'ajout et au rafraîchissement (regles.md §11) : [J − 1, J + 42].
JOURS_AVANT, JOURS_APRES = 1, 42


def agendas_de(user):
    if getattr(user, 'company_id', None) is None:
        return AgendaExterne.objects.none()
    return AgendaExterne.objects.filter(company_id=user.company_id, proprietaire=user)


def _instant(valeur):
    return timezone.localtime(valeur).replace(microsecond=0).isoformat() if valeur else None


def forme(agenda):
    """Forme `agenda_externe.json` : jamais l'URL."""
    return {'id': agenda.pk, 'hote': agenda.hote, 'libelle': agenda.libelle, 'actif': agenda.actif,
            'rang': agenda.rang, 'dernier_chargement_le': _instant(agenda.dernier_chargement_le),
            'dernier_etat': agenda.dernier_etat}


def _du_compte(user, id):
    agenda = agendas_de(user).filter(pk=id).first()
    if agenda is None:
        raise Http404('Introuvable.')
    return agenda


def lire_maintenant(agenda):
    """Lecture immédiate (ignore le cache) : `dernier_etat` dit l'issue."""
    jour = maintenant().date()
    lecteur.lire_agenda_externe(agenda, jour - datetime.timedelta(days=JOURS_AVANT),
                                jour + datetime.timedelta(days=JOURS_APRES), rafraichir=True)
    agenda.refresh_from_db()
    return agenda


#: Une adresse d'agenda telle que le serveur la lit : `https://` ou `webcal://` (casse indifférente, ECMA n'a pas de
#: drapeau en ligne), un `user@` facultatif, un hôte ASCII (`_` et punycode compris), un port, puis `/`, `?` ou `#` ;
#: un espace collé autour est toléré (`normaliser_url` le retire). Qu'elle soit publique et joignable dépend du DNS,
#: pas du corps : refus d'ÉTAT (409), comme `publicapi` (ERR46) — critique serveur n° 6.
MOTIF_URL_AGENDA = (r"^\s*(?:[Hh][Tt][Tt][Pp][Ss]|[Ww][Ee][Bb][Cc][Aa][Ll])://"
                    r"(?:[A-Za-z0-9._~%!$&'()*+,;=:-]+@)?[A-Za-z0-9._~%-]+(?::[0-9]{1,5})?(?:[/?#]\S*)?\s*$")
#: `AgendaExterne.rang` est un `IntegerField` (au-delà : 500 « integer out of range »).
RANG_MIN, RANG_MAX = -2 ** 31, 2 ** 31 - 1


class MotifUrlAgenda(MotifPublie):
    """`MOTIF_URL_AGENDA` publié ; un autre schéma d'adresse (« http:// », « ftp:// ») garde SON message (R2-127)."""

    def __init__(self):
        super().__init__(MOTIF_URL_AGENDA, MESSAGE_PAS_UNE_ADRESSE)

    def __call__(self, valeur):
        try:
            super().__call__(valeur)
        except DjangoValidationError:
            schema = re.match(r'^([A-Za-z][A-Za-z0-9+.-]*)://\S', valeur.strip()) if isinstance(valeur, str) else None
            # « http:// », « ftp:// » : il faut https ; une adresse https / webcal mal formée n'est pas une adresse
            if schema and schema.group(1).lower() not in (lecteur.SCHEMA, 'webcal'):
                raise DjangoValidationError(MESSAGE_HTTPS, code='invalid')
            raise


@extend_schema_serializer(component_name='TachesCorpsAgendaExterne')
class AgendaCorps(serializers.Serializer):
    url = ChaineStricte(max_length=500, trim_whitespace=False,
                        validators=[MotifUrlAgenda()],
                        error_messages={'blank': MESSAGE_PAS_UNE_ADRESSE, 'invalid': MESSAGE_PAS_UNE_ADRESSE})
    libelle = ChaineStricte(max_length=60, required=False, allow_blank=True, default='')


@extend_schema_serializer(component_name='TachesCorpsAgendaExternePatch')
class AgendaPatchCorps(serializers.Serializer):
    libelle = ChaineStricte(max_length=60, required=False, allow_blank=True)
    actif = BooleenStrict(required=False)
    rang = EntierStrict(required=False, min_value=RANG_MIN, max_value=RANG_MAX)


def _url_acceptee(user, brute):
    """L'URL normalisée (`webcal://` → `https://`) ; 400 au champ `url` sinon."""
    url = lecteur.normaliser_url(brute)
    try:
        morceaux = urlsplit(url)
        hote = morceaux.hostname
    except ValueError:
        raise ValidationError({'url': [MESSAGE_PAS_UNE_ADRESSE]})
    if not morceaux.scheme or not hote:
        raise ValidationError({'url': [MESSAGE_PAS_UNE_ADRESSE]})
    if morceaux.scheme.lower() != lecteur.SCHEMA:
        raise ValidationError({'url': [MESSAGE_HTTPS]})
    # Refus d'ÉTAT (409, même corps) : l'hôte (DNS), un agenda déjà ajouté, les 3 déjà posés (api-fuzz r2).
    try:
        lecteur.verifier_adresse(url)
    except UnsafeWebhookURL:
        raise refus_etat({'url': [MESSAGE_INJOIGNABLE]})
    if agendas_de(user).filter(url=url).exists():
        raise refus_etat({'url': [MESSAGE_DOUBLON]})
    if agendas_de(user).count() >= lecteur.AGENDAS_MAX:
        raise refus_etat({'url': [MESSAGE_PLAFOND]})
    return url


def ajouter(user, donnees):
    """POST : au plus 3 adresses par compte, lue aussitôt."""
    url = _url_acceptee(user, donnees['url'])
    dernier = agendas_de(user).aggregate(m=Max('rang'))['m'] or 0
    try:
        with transaction.atomic():
            agenda = AgendaExterne.objects.create(company_id=user.company_id, proprietaire=user, url=url,
                                                  libelle=donnees.get('libelle', ''), rang=dernier + PAS_RANG)
    except IntegrityError:
        raise refus_etat({'url': [MESSAGE_DOUBLON]})
    lecteur.oublier_index(user)
    return lire_maintenant(agenda)


class AgendasHorsAssistant(HorsAssistant):
    """403 sous l'assistant (api.md §0) : le relais du Copilote ne lit ni ne change l'adresse d'un agenda."""

    message = "L'assistant ne gère pas tes agendas."


class AgendasExternesVue(IdempotentCreateMixin, APIView):
    """GET agendas-externes/ (`{"results":[…]}`, ≤ 3) · POST (une adresse ICS, lue aussitôt)."""

    permission_classes = [*PERMISSIONS, AgendasHorsAssistant]
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('agendas_externes')))
    def get(self, request):
        return Response({'results': [forme(a) for a in agendas_de(request.user).order_by('rang', 'pk')]})

    @extend_schema(request=AgendaCorps, responses=reponses(AGENDA_EXTERNE, statut=201, erreurs=(400, 409)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._ajouter(request), suffixe=par_compte(request))

    def _ajouter(self, request):
        serializer = AgendaCorps(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(forme(ajouter(request.user, serializer.validated_data)), status=201)


class AgendaExterneVue(APIView):
    """PATCH (libellé, actif, rang) · DELETE agendas-externes/{id}/."""

    permission_classes = [*PERMISSIONS, AgendasHorsAssistant]
    parser_classes = PARSEURS

    @extend_schema(request=AgendaPatchCorps,
                   responses=reponses(AGENDA_EXTERNE, erreurs=(400, 404)))
    def patch(self, request, id):
        agenda = _du_compte(request.user, id)
        serializer = AgendaPatchCorps(data=request.data)
        serializer.is_valid(raise_exception=True)
        champs = dict(serializer.validated_data)
        for champ, valeur in champs.items():
            setattr(agenda, champ, valeur)
        if champs:
            agenda.save(update_fields=[*champs, 'updated_at'])
        if champs.get('actif') is False:
            lecteur.oublier(agenda)
        lecteur.oublier_index(request.user)
        return Response(forme(agenda))

    @extend_schema(request=None, responses=reponses(None, statut=204, erreurs=(404,)))
    def delete(self, request, id):
        agenda = _du_compte(request.user, id)
        lecteur.oublier(agenda)
        agenda.delete()
        lecteur.oublier_index(request.user)
        return Response(status=204)


class AgendaExterneRafraichirVue(APIView):
    """POST agendas-externes/{id}/rafraichir/ — relire maintenant (ignore le cache)."""

    permission_classes = [*PERMISSIONS, AgendasHorsAssistant]
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=reponses(AGENDA_EXTERNE, erreurs=(404,)))
    def post(self, request, id):
        return Response(forme(lire_maintenant(_du_compte(request.user, id))))
