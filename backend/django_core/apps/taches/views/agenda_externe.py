"""Agendas externes (reference/api.md §3.4, §4 ; A18-M4) : au plus 3 adresses ICS, lues côté serveur.

Le schéma OpenAPI de chaque route est celui de son échantillon de `contract_samples/`. Aucune
écriture ici ne rend de `geste_id` (api.md §0). L'URL n'est JAMAIS rendue ni journalisée : la forme
ne sert que `hote`. Toute écriture efface l'index en cache des agendas du compte.
"""
import datetime

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.publicapi.validators import UnsafeWebhookURL
from apps.taches import agenda_externe as lecteur
from apps.taches.models.agenda import AgendaExterne
from apps.taches.views.base import PERMISSIONS, corps, forme_echantillon, reponses
from apps.taches.views.journee import maintenant, par_compte
from core.idempotency import IdempotentCreateMixin

AGENDA_EXTERNE = forme_echantillon('agenda_externe')
MESSAGE_URL = 'Adresse https publique attendue.'
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


class AgendaCorps(serializers.Serializer):
    url = serializers.CharField(max_length=500)
    libelle = serializers.CharField(max_length=60, required=False, allow_blank=True, default='')


class AgendaPatchCorps(serializers.Serializer):
    libelle = serializers.CharField(max_length=60, required=False, allow_blank=True)
    actif = serializers.BooleanField(required=False)
    rang = serializers.IntegerField(required=False)


def _url_acceptee(user, brute):
    """L'URL normalisée (`webcal://` → `https://`) ; 400 au champ `url` sinon."""
    url = lecteur.normaliser_url(brute)
    try:
        lecteur.verifier_adresse(url)
    except UnsafeWebhookURL:
        raise ValidationError({'url': [MESSAGE_URL]})
    if agendas_de(user).filter(url=url).exists():
        raise ValidationError({'url': [MESSAGE_DOUBLON]})
    if agendas_de(user).count() >= lecteur.AGENDAS_MAX:
        raise ValidationError({'url': [MESSAGE_PLAFOND]})
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
        raise ValidationError({'url': [MESSAGE_DOUBLON]})
    lecteur.oublier_index(user)
    return lire_maintenant(agenda)


class AgendasExternesVue(IdempotentCreateMixin, APIView):
    """GET agendas-externes/ (`{"results":[…]}`, ≤ 3) · POST (une adresse ICS, lue aussitôt)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('agendas_externes')))
    def get(self, request):
        return Response({'results': [forme(a) for a in agendas_de(request.user).order_by('rang', 'pk')]})

    @extend_schema(request=corps('AgendaExterne', {
        'url': 'https://outlook.office365.com/owa/calendar/abc/reachcalendar.ics', 'libelle': 'Microsoft 365',
    }, requis=('url',)), responses=reponses(AGENDA_EXTERNE, statut=201, erreurs=(400,)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._ajouter(request), suffixe=par_compte(request))

    def _ajouter(self, request):
        serializer = AgendaCorps(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(forme(ajouter(request.user, serializer.validated_data)), status=201)


class AgendaExterneVue(APIView):
    """PATCH (libellé, actif, rang) · DELETE agendas-externes/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('AgendaExternePatch', {'libelle': 'Bureau', 'actif': False, 'rang': 2048}),
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

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(AGENDA_EXTERNE, erreurs=(404,)))
    def post(self, request, id):
        return Response(forme(lire_maintenant(_du_compte(request.user, id))))
