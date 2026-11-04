"""Surface HTTP de la couche sémantique.

  * ``semantic/metriques/`` (NTDATA10) — CRUD des définitions (catalogue du
    picker front en ``GET``), ``IsResponsableOrAdmin``, société forcée serveur ;
  * ``GET semantic/metriques/<cle>/valeur/`` (NTDATA10) — la valeur d'une
    métrique par sa CLÉ, via le résolveur NTDATA8 ;
  * ``GET semantic/metriques/<id>/versions/`` (NTDATA9) — l'historique figé
    des définitions successives d'une métrique ;
  * ``GET semantic/metriques/<cle>/lignage/`` (NTDATA43) — « d'où vient ce
    chiffre » : dataset source, app propriétaire, filtres appliqués, nombre de
    lignes agrégées et version de définition en vigueur.

CHAQUE ROUTE A SA PROPRE CLASSE : deux routes branchées sur la MÊME vue
produisent le même ``operationId`` dans le schéma OpenAPI, et la collision fait
échouer la génération (précédent NTDATA5).

Toutes les lectures sont bornées à ``request.user.company`` : une métrique est
company-scopée, son historique l'est donc aussi.
"""
import json

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin
from core.mixins import TenantMixin

from . import selectors, services
from .models import MetricDefinition
from .serializers import MetricDefinitionSerializer


class MetricDefinitionViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTDATA10 — CRUD des métriques nommées de la société.

    ``GET semantic/metriques/`` est le CATALOGUE que lit le picker front
    (filtres ``?actif=true|false`` et ``?q=`` sur clé/libellé). La société est
    forcée côté serveur (``TenantMixin``), jamais lue du corps ; une clé déjà
    prise dans la société répond 409 (``unique_conflict``).

    ÉDITER signe la version figée (NTDATA9) du nom de l'acteur : le signal
    ``post_save`` fige sans auteur, la vue — qui connaît l'acteur — la signe
    juste après (``services.attribuer_auteur``).

    SUPPRIMER = DÉSACTIVER (``actif=False``). Une métrique est référencée PAR
    CLÉ par des widgets, des alertes et des rapports, et son historique de
    versions explique les chiffres passés : l'effacer casserait les uns et
    rendrait les autres inexplicables. Une métrique désactivée n'est plus
    résolue (404 sur ``valeur``) mais reste lisible et réactivable.
    """

    serializer_class = MetricDefinitionSerializer
    permission_classes = [IsResponsableOrAdmin]
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    queryset = MetricDefinition.objects.all()
    # Identifiant NUMÉRIQUE seulement : `metriques/<cle>/…` (valeur, lignage)
    # et les actions de liste (`export`, `glossaire`…) ne doivent jamais être
    # lus comme un détail.
    lookup_value_regex = r'\d+'

    def get_queryset(self):
        qs = super().get_queryset().order_by('cle')
        params = self.request.query_params
        actif = (params.get('actif') or '').strip().lower()
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        elif actif in ('false', '0'):
            qs = qs.filter(actif=False)
        recherche = (params.get('q') or '').strip()
        if recherche:
            from django.db.models import Q
            qs = qs.filter(Q(cle__icontains=recherche)
                           | Q(libelle__icontains=recherche))
        return qs

    def perform_create(self, serializer):
        if not self.request.user.company_id:
            raise ValidationError(
                {'detail': 'Aucune société rattachée : impossible de créer '
                           'une métrique.'})
        with transaction.atomic():
            definition = serializer.save(company=self.request.user.company)
            services.attribuer_auteur(definition, None, self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            avant = services.derniere_version_id(serializer.instance)
            super().perform_update(serializer)
            services.attribuer_auteur(serializer.instance, avant,
                                      self.request.user)

    def perform_destroy(self, instance):
        if instance.actif:
            instance.actif = False
            instance.save(update_fields=['actif', 'updated_at'])


def _json_param(brut, nom, attendu):
    """Un paramètre de requête JSON, du type ``attendu`` (400 sinon)."""
    if brut in (None, ''):
        return None
    try:
        valeur = json.loads(brut)
    except (TypeError, ValueError):
        raise ValidationError({nom: 'JSON invalide.'})
    if not isinstance(valeur, attendu):
        raise ValidationError(
            {nom: 'Objet JSON attendu.' if attendu is dict
             else 'Valeur JSON invalide.'})
    return valeur


def parametres_de_resolution(query_params):
    """``group_by`` / ``period`` / ``filters`` lus de la query-string.

    * ``group_by`` — noms de champs séparés par des virgules (absent ⇒ les
      dimensions par défaut de la définition ; ``group_by=`` VIDE ⇒ une
      valeur globale) ;
    * ``period`` — ``AAAA-MM-JJ,AAAA-MM-JJ`` ou un objet JSON
      ``{"debut": …, "fin": …, "champ": …}`` ;
    * ``filters`` — objet JSON ``{"champ": valeur}`` (liste blanche du dataset
      revérifiée par le moteur).
    """
    group_by = None
    if 'group_by' in query_params:
        group_by = [c.strip() for c in query_params.get('group_by', '').split(',')
                    if c.strip()]
    brut_periode = (query_params.get('period') or '').strip()
    period = None
    if brut_periode.startswith('{'):
        period = _json_param(brut_periode, 'period', dict)
        period = {k: v for k, v in period.items()
                  if k in ('debut', 'fin', 'champ') and v not in (None, '')}
    elif brut_periode:
        morceaux = [m.strip() or None for m in brut_periode.split(',')]
        if len(morceaux) != 2:
            raise ValidationError(
                {'period': 'Format attendu : « debut,fin » ou un objet JSON.'})
        period = {'debut': morceaux[0], 'fin': morceaux[1]}
    filters = _json_param(query_params.get('filters'), 'filters', dict)
    return group_by, period, filters


class MetriqueValeurView(APIView):
    """NTDATA10 — ``GET semantic/metriques/<cle>/valeur/`` : la valeur PAR CLÉ.

    Appelle le résolveur NTDATA8 (``services.resolve_metric``) : une métrique
    définie une fois est appelable par sa clé partout. Inconnue ou inactive ⇒
    404 ; définition non exécutable (dataset désenregistré, champ hors liste
    blanche, formule fautive) ⇒ 400 au message français. ``valeur`` à ``null``
    n'est jamais un zéro déguisé (population vide, division par zéro, champ
    que ce lecteur n'a pas le droit de voir).
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter('group_by', str, required=False,
                             description='Champs de regroupement, séparés '
                                         'par des virgules.'),
            OpenApiParameter('period', str, required=False,
                             description='« debut,fin » ou objet JSON '
                                         '{debut, fin, champ}.'),
            OpenApiParameter('filters', str, required=False,
                             description='Objet JSON de filtres.'),
        ],
        responses=inline_serializer('MetriqueValeurReponse', {
            'cle': serializers.CharField(),
            'libelle': serializers.CharField(),
            'unite': serializers.CharField(),
            'format': serializers.IntegerField(),
            'dataset': serializers.CharField(),
            'group_by': serializers.ListField(child=serializers.CharField()),
            'valeur': serializers.JSONField(allow_null=True),
            'lignes': serializers.JSONField(),
        }))
    def get(self, request, cle=None):
        group_by, period, filters = parametres_de_resolution(
            request.query_params)
        try:
            resultat = services.resolve_metric(
                request.user.company, request.user, cle, filters=filters,
                group_by=group_by, period=period)
        except services.MetriqueInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except services.MetriqueNonResolvable as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError, DjangoValidationError):
            # Une valeur de filtre/période illisible pour la base (date mal
            # formée, nombre attendu) : la requête est fautive, pas le serveur.
            return Response(
                {'detail': 'Paramètres de filtre ou de période illisibles.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)


class MetriqueVersionsView(APIView):
    """NTDATA9 — l'historique FIGÉ des définitions d'une métrique.

    ``GET /semantic/metriques/<id>/versions/`` rend les versions de la plus
    récente à la plus ancienne : ce que valait la définition, quand elle a été
    figée, et par qui (vide quand l'édition est venue d'un chemin sans acteur
    identifié — le seeder, l'admin, un script).

    Une métrique d'une AUTRE société est un 404, jamais un 403 : répondre
    « interdit » confirmerait son existence.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('MetriqueVersionsReponse', {
            'metrique': serializers.CharField(),
            'libelle': serializers.CharField(),
            'nb_versions': serializers.IntegerField(),
            'versions': serializers.JSONField(),
        }))
    def get(self, request, pk=None):
        definition = MetricDefinition.objects.filter(
            pk=pk, company=request.user.company).first()
        if definition is None:
            return Response({'detail': 'Métrique introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        versions = [
            {
                'version': version.version,
                'libelle': version.libelle,
                'dataset': version.dataset,
                'mesure': version.mesure,
                'filtres': version.filtres,
                'unite': version.unite,
                'auteur': (getattr(version.auteur, 'username', '')
                           if version.auteur_id else ''),
                'figee_le': version.date_creation.isoformat(),
            }
            for version in services.versions_metrique(definition)
        ]
        return Response({
            'metrique': definition.cle,
            'libelle': definition.libelle,
            'nb_versions': len(versions),
            'versions': versions,
        })


class MetriqueLignageView(APIView):
    """NTDATA43 — « d'où vient ce chiffre » pour une métrique nommée.

    ``GET /semantic/metriques/<cle>/lignage/`` rend l'arbre : métrique →
    dataset source → app propriétaire → filtres appliqués → nombre de lignes
    agrégées, plus la version de définition en vigueur (NTDATA9).

    Le lecteur est transmis au moteur : un champ sous permission (AUD801)
    qu'il ne peut pas voir ne lui est pas décrit non plus, et le nombre de
    lignes agrégées rend alors VIDE plutôt que de divulguer.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('MetriqueLignageReponse', {
            'metrique': serializers.CharField(),
            'libelle': serializers.CharField(),
            'description': serializers.CharField(),
            'unite': serializers.CharField(),
            'format': serializers.IntegerField(),
            'calcul': serializers.JSONField(),
            'sources': serializers.JSONField(),
            'filtres': serializers.JSONField(),
            'nb_lignes_agregees': serializers.IntegerField(allow_null=True),
            'version': serializers.JSONField(allow_null=True),
        }))
    def get(self, request, cle=None):
        try:
            lignage = selectors.lineage(request.user.company, cle,
                                        user=request.user)
        except services.MetriqueInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(lignage)
