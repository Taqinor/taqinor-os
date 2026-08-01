"""AOF61/AOF62 — l'API de calepinage : calcul borné, job de fond, cache tenant,
actions de variante IDEMPOTENTES.

Trois refus assumés, tous portés par le code et pas par la discipline :

* **jamais de calcul non borné en synchrone.** ``perf.estimer_cout`` chiffre le
  travail AVANT de le lancer ; au-delà du budget, l'endpoint renvoie **202** et
  la consigne d'appel asynchrone au lieu de faire attendre l'utilisateur devant
  un écran gelé ;
* **jamais de file maison.** Le calcul lourd part par
  ``core.jobs.submit(kind, task, company=…, user=…)`` et se suit par
  ``BackgroundJob`` — la progression et l'échec sont ceux de la plateforme ;
* **jamais un cache global.** ``core.cache`` préfixe toute clé par la société
  (``t:{company_id}:…``) et la clé porte l'empreinte de l'entrée ET la version
  du moteur : deux sociétés ne peuvent pas se lire, et un bump de version rend
  l'ancien cache inatteignable sans purge à ne pas oublier.

Le CRUD des variantes n'est PAS redoublé ici : il vit sur
``/api/django/ao/variantes-calepinage/`` (AOF28). ``CalepinageVarianteViewSet``
est un ``GenericViewSet`` SANS mixin — il n'expose que ses quatre actions, si
bien qu'aucune seconde surface d'écriture n'apparaît sur la même table.
"""
from __future__ import annotations

import json

from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from core.idempotency import (
    IDEMPOTENCY_KEY_HEADER, IdempotencyConflict, IdempotencyRecord,
    _fingerprint,
)
from core.models import BackgroundJob
from core.permissions import ScopedPermission, declared_action_permissions

from . import calepinage_io, calepinage_service
from .calepinage_serializers import (
    ComparaisonVariantesSerializer, DemandeCalepinageSerializer,
    DemandeJobCalepinageSerializer, JobCalepinageSerializer,
    ResultatCalepinageSerializer,
)
from .calepinage_service import (
    EntreeInvalide, MoteurCalepinage, VariantePerimee,
)
from .calepinage_tasks import calculer_calepinage
from .models import ToitureAO, VarianteCalepinage
from .permissions import AO_GERER, AO_VOIR
from .serializers import VarianteCalepinageSerializer
from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.perf import BudgetCalcul

__all__ = [
    'BUDGET', 'CalculerCalepinageView', 'LancerCalepinageView',
    'ResultatCalepinageView', 'CalepinageVarianteViewSet',
]

#: Budget de calcul de l'API. Module-level DÉLIBÉRÉMENT : les tests le
#: remplacent pour prouver la bascule asynchrone sans fabriquer une toiture
#: monstrueuse (un test qui doit être lent pour prouver une borne est un test
#: qu'on finit par désactiver).
BUDGET = BudgetCalcul()

#: Type logique du job de fond (``BackgroundJob.kind``).
KIND_CALEPINAGE = 'ao_calepinage'


def _societe(request):
    return getattr(request.user, 'company', None)


class _BaseCalepinageView(GenericAPIView):
    """Socle commun : garde ``ao_voir``/``ao_gerer`` + scoping société."""

    permission_classes = [ScopedPermission]
    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get_queryset(self):
        """Toitures de la SOCIÉTÉ de l'appelant — jamais plus large.

        Une toiture d'une autre société n'existe pas pour cet appelant : la
        recherche par identifiant rend 404, pas 403 (un 403 confirmerait
        l'existence de l'objet).
        """
        return ToitureAO.objects.filter(company=_societe(self.request))

    def _toiture(self, identifiant):
        toiture = self.get_queryset().select_related(
            'batiment', 'batiment__appel_offre').filter(
                pk=identifiant).first()
        if toiture is None:
            raise Http404("Toiture introuvable dans cette société.")
        return toiture

    def _document(self, donnees):
        if donnees.get('toiture') is not None:
            return calepinage_io.document_entree(
                self._toiture(donnees['toiture']),
                params=donnees.get('params'))
        return dict(donnees['entree'])


def _erreur(champ, message):
    return Response({champ: [message]}, status=status.HTTP_400_BAD_REQUEST)


class CalculerCalepinageView(_BaseCalepinageView):
    """``POST /api/django/ao/calepinage/calculer/`` — calcul SYNCHRONE borné.

    Réponses :

    * **200** — le résultat (du cache si l'entrée a déjà été calculée pour
      cette société avec ce moteur) ;
    * **202** — le travail dépasse le budget synchrone : le corps porte le coût
      estimé et la consigne d'appel asynchrone (``.../lancer/``) ;
    * **400** — document invalide (champ nommé) ou plan incohérent (le
      contrôle d'AOF51 qui a échoué est NOMMÉ) ;
    * **404** — la toiture n'appartient pas à la société de l'appelant.
    """

    serializer_class = DemandeCalepinageSerializer

    @extend_schema(request=DemandeCalepinageSerializer,
                   responses=ResultatCalepinageSerializer)
    def post(self, request, *args, **kwargs):
        demande = self.get_serializer(data=request.data)
        demande.is_valid(raise_exception=True)
        company = _societe(request)
        try:
            document = self._document(demande.validated_data)
            empreinte = calepinage_service.empreinte_document(document)
        except EntreeInvalide as erreur:
            return _erreur('entree', str(erreur))

        depuis_cache = calepinage_service.resultat_en_cache(
            getattr(company, 'id', None), empreinte)
        if depuis_cache is not None:
            depuis_cache = dict(depuis_cache, depuis_cache=True)
            return Response(depuis_cache)

        try:
            cout = calepinage_service.cout_estime(document, budget=BUDGET)
        except EntreeInvalide as erreur:
            return _erreur('entree', str(erreur))
        if not cout.synchrone:
            return Response({
                'detail': (
                    "Ce calepinage dépasse le budget de calcul synchrone : "
                    "lancez-le en tâche de fond via "
                    "/api/django/ao/calepinage/lancer/, puis suivez-le sur "
                    "/api/django/ao/calepinage/resultat/<job_id>/."),
                'cout_estime': {
                    'positions': cout.positions, 'kits': cout.kits,
                    'appels': cout.appels,
                    'millisecondes': round(cout.millisecondes, 1),
                    'motif': cout.motif},
                'asynchrone': '/api/django/ao/calepinage/lancer/',
            }, status=status.HTTP_202_ACCEPTED)

        try:
            resultat = calepinage_service.calepiner(
                document, company=company, user=request.user,
                moteur=MoteurCalepinage())
        except EntreeInvalide as erreur:
            return _erreur('entree', str(erreur))
        except CalepinageIncoherent as erreur:
            return Response(
                {'calepinage': [str(erreur)], 'controle': erreur.controle,
                 'repere': erreur.repere},
                status=status.HTTP_400_BAD_REQUEST)

        calepinage_service.mettre_en_cache(getattr(company, 'id', None),
                                           resultat)
        return Response(dict(resultat, depuis_cache=False))


class LancerCalepinageView(_BaseCalepinageView):
    """``POST /api/django/ao/calepinage/lancer/`` — calcul en TÂCHE DE FOND.

    Dispatch par ``core.jobs.submit`` — jamais une file maison. Renvoie **202**
    avec l'identifiant du ``BackgroundJob`` à suivre.
    """

    serializer_class = DemandeJobCalepinageSerializer

    @extend_schema(request=DemandeJobCalepinageSerializer,
                   responses=JobCalepinageSerializer)
    def post(self, request, *args, **kwargs):
        from core.jobs import submit

        demande = self.get_serializer(data=request.data)
        demande.is_valid(raise_exception=True)
        donnees = demande.validated_data
        company = _societe(request)

        if donnees.get('toiture') is not None:
            # 404 IMMÉDIAT plutôt qu'un job qui échouera dans 30 s : l'erreur
            # d'appartenance doit se voir à l'appel, pas dans un journal.
            self._toiture(donnees['toiture'])

        job = submit(
            KIND_CALEPINAGE, calculer_calepinage, company=company,
            user=request.user, toiture_id=donnees.get('toiture'),
            params=donnees.get('params'), entree=donnees.get('entree'),
            persister=bool(donnees.get('persister')),
            nom=donnees.get('nom', ''), role=donnees.get('role', ''),
            user_id=request.user.pk)
        return Response(
            {'id': job.pk, 'kind': job.kind, 'statut': job.statut,
             'progress_pct': job.progress_pct, 'message_erreur': '',
             'resultat': None, 'variante': None},
            status=status.HTTP_202_ACCEPTED)


class ResultatCalepinageView(_BaseCalepinageView):
    """``GET /api/django/ao/calepinage/resultat/<job_id>/`` — suivi + résultat.

    Le job d'une AUTRE société est introuvable (404), jamais « interdit » :
    la réponse ne doit pas confirmer son existence.
    """

    serializer_class = JobCalepinageSerializer

    def get_queryset(self):
        return BackgroundJob.objects.filter(company=_societe(self.request),
                                            kind=KIND_CALEPINAGE)

    @extend_schema(responses=JobCalepinageSerializer)
    def get(self, request, job_id=None, *args, **kwargs):
        job = self.get_queryset().filter(pk=job_id).first()
        if job is None:
            raise Http404("Calcul de calepinage introuvable.")
        resultat = None
        if job.statut == BackgroundJob.STATUT_DONE and job.result_file_key:
            from core import cache as cache_tenant

            resultat = cache_tenant.get(job.company_id, job.result_file_key)
        variante = VarianteCalepinage.objects.filter(
            company=job.company_id, job=job).values_list('pk', flat=True
                                                         ).first()
        return Response({
            'id': job.pk, 'kind': job.kind, 'statut': job.statut,
            'progress_pct': job.progress_pct,
            'message_erreur': job.message_erreur,
            'resultat': resultat, 'variante': variante,
        })


# ─────────────────────────────────── AOF62 — actions de variante idempotentes
class IdempotentActionMixin:
    """Étend le contrat ``Idempotency-Key`` de ``core.idempotency`` aux
    ``@action``.

    ``IdempotentCreateMixin`` ne couvre que ``create`` ; les actions métier
    d'AOF62 en ont autant besoin — un double-clic ou un rejeu réseau ne doit
    ni relancer un calcul ni basculer deux fois une retenue.

    L'EMPREINTE inclut la CIBLE (``pk``) et le nom de l'action, pas seulement
    le corps : sans cela, deux ``retenir`` sur DEUX variantes différentes,
    envoyés avec la même clé et un corps vide, auraient la même empreinte et le
    second rejouerait la réponse du premier — il aurait retenu la mauvaise
    variante en silence.
    """

    def _cle_idempotence(self, request):
        brut = (request.META.get(IDEMPOTENCY_KEY_HEADER)
                or request.headers.get('Idempotency-Key'))
        return brut.strip()[:255] if brut else None

    def _empreinte(self, request):
        return _fingerprint({
            'action': getattr(self, 'action', ''),
            'cible': str(self.kwargs.get('pk', '')),
            'corps': json.loads(json.dumps(request.data, default=str)),
        })

    def executer_idempotent(self, request, calcul):
        cle = self._cle_idempotence(request)
        if not cle:
            return calcul()
        company = _societe(request)
        endpoint = '%s.%s' % (type(self).__qualname__,
                              getattr(self, 'action', ''))
        empreinte = self._empreinte(request)
        memorise = IdempotencyRecord.objects.filter(
            company=company, endpoint=endpoint, key=cle).first()
        if memorise is not None:
            if memorise.request_fingerprint != empreinte:
                raise IdempotencyConflict()
            return Response(memorise.response_body,
                            status=memorise.response_status)
        reponse = calcul()
        try:
            IdempotencyRecord.objects.get_or_create(
                company=company, endpoint=endpoint, key=cle,
                defaults={'request_fingerprint': empreinte,
                          'response_status': reponse.status_code,
                          'response_body': reponse.data})
        except Exception:  # noqa: BLE001 — l'idempotence est un CONFORT : elle
            # ne doit jamais faire échouer une action qui a déjà réussi.
            pass
        return reponse


class CalepinageVarianteViewSet(IdempotentActionMixin, viewsets.GenericViewSet):
    """AOF62 — ``retenir`` / ``comparer`` / ``sensibilites`` / ``marches``.

    ``GenericViewSet`` sans mixin : AUCUNE route de CRUD n'est générée. Le
    CRUD des variantes reste sur ``/variantes-calepinage/`` (AOF28) — deux
    surfaces d'écriture sur la même table divergeraient tôt ou tard.
    """

    serializer_class = VarianteCalepinageSerializer
    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get_permissions(self):
        """Garde du DOMAINE en plancher, garde de l'action en plafond.

        Même composition que ``AoBaseViewSet`` : une ``@action`` qui déclare sa
        propre garde la voit AJOUTÉE, jamais substituée — aucune déclaration
        n'est perdue en silence.
        """
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            permissions.extend(declared)
        return permissions

    def get_queryset(self):
        return VarianteCalepinage.objects.filter(
            company=_societe(self.request)).select_related('toiture')

    @extend_schema(responses=VarianteCalepinageSerializer)
    @action(detail=True, methods=['post'], url_path='retenir')
    def retenir(self, request, pk=None):
        """Désigne LA variante retenue de la toiture — idempotent, 409 si périmée."""
        variante = self.get_object()

        def calcul():
            try:
                retenue = calepinage_service.retenir_variante(
                    variante, user=request.user)
            except VariantePerimee as erreur:
                return Response({'statut': [str(erreur)]},
                                status=status.HTTP_409_CONFLICT)
            return Response(self.get_serializer(retenue).data)

        return self.executer_idempotent(request, calcul)

    @extend_schema(parameters=[ComparaisonVariantesSerializer],
                   responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=['get'], url_path='comparer')
    def comparer(self, request):
        """Compare N variantes EN UN APPEL (``?ids=1,2,3``)."""
        demande = ComparaisonVariantesSerializer(data=request.query_params)
        demande.is_valid(raise_exception=True)
        return Response(calepinage_service.comparer_variantes(
            _societe(request), demande.validated_data['ids']))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['post'], url_path='sensibilites')
    def sensibilites(self, request, pk=None):
        """Rejoue la batterie défavorable et publie le PLANCHER."""
        variante = self.get_object()

        def calcul():
            try:
                return Response(calepinage_service.calculer_sensibilites(
                    variante, user=request.user))
            except EntreeInvalide as erreur:
                return _erreur('entree', str(erreur))
            except CalepinageIncoherent as erreur:
                return Response({'calepinage': [str(erreur)]},
                                status=status.HTTP_400_BAD_REQUEST)

        return self.executer_idempotent(request, calcul)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'], url_path='marches')
    def marches(self, request, pk=None):
        """L'échelle de décomposition, deltas SIGNÉS et contrôle d'honnêteté."""
        return Response(calepinage_service.calculer_marches(self.get_object()))
