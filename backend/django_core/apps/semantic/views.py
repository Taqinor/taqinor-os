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
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import company_qs
from core.viewsets import CompanyScopedModelViewSet

from . import portabilite, selectors, services
from .models import MetricDefinition
from .serializers import ImportMetriquesSerializer, MetricDefinitionSerializer


class MetricDefinitionViewSet(CompanyScopedModelViewSet):
    """NTDATA10 — CRUD des métriques nommées de la société.

    ``GET semantic/metriques/`` est le CATALOGUE que lit le picker front
    (filtres ``?actif=true|false`` et ``?q=`` sur clé/libellé). La société est
    forcée côté serveur (``CompanyScopedModelViewSet``), jamais lue du corps ;
    une clé déjà prise dans la société répond 409 (``unique_conflict``).

    ÉDITER signe la version figée (NTDATA9) du nom de l'acteur : le signal
    ``post_save`` fige sans auteur, la vue — qui connaît l'acteur — la signe
    juste après (``services.attribuer_auteur``).

    JAMAIS SUPPRIMÉE : on la DÉSACTIVE (``PATCH {"actif": false}`` ; le DELETE
    qui désactivait est retiré, ENF48). Une métrique est référencée PAR
    CLÉ par des widgets, des alertes et des rapports, et son historique de
    versions explique les chiffres passés : l'effacer casserait les uns et
    rendrait les autres inexplicables. Une métrique désactivée n'est plus
    résolue (404 sur ``valeur``) mais reste lisible et réactivable.
    """

    serializer_class = MetricDefinitionSerializer
    permission_classes = [IsResponsableOrAdmin]
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    # ENF48 — jamais de suppression : désactiver = ``PATCH {"actif": false}``.
    # Un DELETE 2xx suivi d'un GET 200 était un « use after free » (api-fuzz-full
    # 42074433075) ; aucun écran ne l'appelait (précédent ``entites``, NTADM1).
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    queryset = MetricDefinition.objects.all()
    # Identifiant NUMÉRIQUE seulement : `metriques/<cle>/…` (valeur, lignage)
    # et les actions de liste (`export`, `glossaire`…) ne doivent jamais être
    # lus comme un détail.
    lookup_value_regex = r'\d+'
    # YAPIC2 / YAPIC11 — tri et recherche DÉCLARÉS (liste blanche) : la
    # recherche historique ``?q=`` reste lue par ``get_queryset``.
    ordering_fields = ('cle', 'libelle', 'actif', 'updated_at')
    search_fields = ('cle', 'libelle')

    # Lecture du catalogue par l'agent : tout rôle interne ; tout le reste
    # (CRUD, export, import) reste Responsable/Admin.
    ACTIONS_LECTURE_AGENT = ('pour_agent',)
    ACTIONS_RESPONSABLE = ('export', 'importer')

    def get_permissions(self):
        if self.action in self.ACTIONS_LECTURE_AGENT:
            return [IsAnyRole()]
        if self.action in self.ACTIONS_RESPONSABLE:
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

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

    @extend_schema(
        responses=inline_serializer('MetriquesPourAgentReponse', {
            'metriques': inline_serializer('MetriquePourAgent', {
                'cle': serializers.CharField(),
                'libelle': serializers.CharField(),
                'description': serializers.CharField(),
                'unite': serializers.CharField(),
            }, many=True),
        }))
    @action(detail=False, methods=['get'], url_path='pour-agent',
            permission_classes=[IsAnyRole])
    def pour_agent(self, request):
        """NTDATA12 — le catalogue des métriques GOUVERNÉES pour l'agent IA.

        Lu par le service FastAPI (jeton de l'appelant relayé) pour que
        l'agent NL→SQL préfère une métrique nommée à un SQL ad-hoc quand
        l'intention correspond (« quel est notre DSO » → ``dso``). LECTURE
        SEULE, métriques ACTIVES de la société de l'appelant, et rien que
        clé + libellé + définition + unité : ni dataset, ni mesure, ni
        filtres (la recette reste côté serveur, la valeur se lit par
        ``metriques/<cle>/valeur/``).
        """
        definitions = company_qs(
            MetricDefinition.objects.filter(actif=True),
            request.user).order_by('cle')
        return Response({'metriques': [
            {'cle': d.cle, 'libelle': d.libelle,
             'description': d.description, 'unite': d.unite}
            for d in definitions
        ]})

    @extend_schema(responses=inline_serializer('MetriquesExportReponse', {
        'format': serializers.CharField(),
        'version': serializers.IntegerField(),
        'metriques': serializers.ListField(child=serializers.DictField()),
    }))
    @action(detail=False, methods=['get'], url_path='export',
            permission_classes=[IsResponsableOrAdmin])
    def export(self, request):
        """NTDATA48 — les métriques de la société en JSON vendor-neutre."""
        if not request.user.company_id:
            return Response({'format': portabilite.FORMAT,
                             'version': portabilite.VERSION_FORMAT,
                             'metriques': []})
        return Response(portabilite.exporter_metriques(request.user.company))

    _RAPPORT_IMPORT = inline_serializer('MetriquesImportReponse', {
        'commit': serializers.BooleanField(),
        'applique': serializers.BooleanField(),
        'resultats': serializers.ListField(child=serializers.DictField()),
    })

    @extend_schema(
        request=ImportMetriquesSerializer,
        responses={200: _RAPPORT_IMPORT, 409: OpenApiResponse(
            response=_RAPPORT_IMPORT, description=(
                "Mode commit : une entrée est refusée par l'ÉTAT (création "
                "incomplète, doublon dans le document) — rien n'est écrit, "
                "le rapport nomme chaque refus."))})
    @action(detail=False, methods=['post'], url_path='import',
            permission_classes=[IsResponsableOrAdmin])
    def importer(self, request):
        """NTDATA48 — import symétrique : dry-run par défaut, ``commit`` tout
        ou rien. Une entrée de forme invalide = 400 (ENF48, même en dry-run) ;
        une entrée refusée par l'état en mode ``commit`` = 409 (était 400)."""
        corps = ImportMetriquesSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        if not request.user.company_id:
            raise ValidationError(
                {'detail': 'Aucune société rattachée : import impossible.'})
        donnees = corps.validated_data
        if (donnees.get('format')
                and donnees['format'] != portabilite.FORMAT):
            raise ValidationError(
                {'format': 'Document étranger : format « %s » attendu.'
                           % portabilite.FORMAT})
        rapport = portabilite.importer_metriques(
            request.user.company, donnees['metriques'],
            commit=donnees.get('commit', False), auteur=request.user,
            contexte={'request': request})
        refus = any(r['action'] == 'refusee' for r in rapport['resultats'])
        code = (status.HTTP_409_CONFLICT if rapport['commit'] and refus
                else status.HTTP_200_OK)
        return Response(rapport, status=code)


#: ENF45 c (api-fuzz-full 41958593088) — paramètres de requête qui portent un
#: OBJET JSON (``?filters={"statut":"ouvert"}``) : publiés ``type: string``, le
#: fuzz y envoyait « 2 » ou un texte libre, conformes au schéma et refusés
#: (400). Ils sont publiés tels que la vue les lit : ``content:
#: application/json`` + schéma objet (OpenAPI 3, « parameter content »). La
#: validation serveur (``_json_param``, liste blanche du moteur) est inchangée ;
#: ``period`` accepte toujours aussi « debut,fin » en texte.
_OBJET_JSON = {'type': 'object'}
_PERIODE_JSON = {
    'type': 'object',
    'properties': {
        'debut': {'type': 'string', 'format': 'date'},
        'fin': {'type': 'string', 'format': 'date'},
        'champ': {'type': 'string', 'minLength': 1},
    },
}


class _SchemaParametresJson(AutoSchema):
    """AutoSchema qui publie les paramètres de ``parametres_json`` en
    ``content: application/json`` (drf-spectacular 0.30 n'expose pas
    ``content`` sur ``OpenApiParameter``). Déclaration de schéma UNIQUEMENT :
    aucune route, aucune lecture ni réponse ne change."""

    parametres_json = {'period': _PERIODE_JSON, 'filters': _OBJET_JSON,
                       'cellule': _OBJET_JSON}

    def get_operation(self, *args, **kwargs):
        operation = super().get_operation(*args, **kwargs)
        for parametre in (operation or {}).get('parameters', []):
            schema = self.parametres_json.get(parametre.get('name'))
            if parametre.get('in') != 'query' or schema is None:
                continue
            for cle in ('schema', 'style', 'explode'):
                parametre.pop(cle, None)
            parametre['content'] = {'application/json': {'schema': dict(schema)}}
        return operation


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


#: ENF50 — la métrique existe mais est désactivée (``actif`` faux).
_METRIQUE_DESACTIVEE = OpenApiResponse(
    description='Métrique désactivée : la réactiver pour la lire.')


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
    schema = _SchemaParametresJson()

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
        responses={
            200: inline_serializer('MetriqueValeurReponse', {
                'cle': serializers.CharField(),
                'libelle': serializers.CharField(),
                'unite': serializers.CharField(),
                'format': serializers.IntegerField(),
                'dataset': serializers.CharField(),
                'group_by': serializers.ListField(
                    child=serializers.CharField()),
                'valeur': serializers.JSONField(allow_null=True),
                'lignes': serializers.JSONField(),
            }),
            409: OpenApiResponse(
                description='Métrique désactivée, ou adaptateur/dataset de la '
                            'métrique absent de ce serveur (module désactivé).'),
        })
    def get(self, request, cle=None):
        group_by, period, filters = parametres_de_resolution(
            request.query_params)
        try:
            resultat = services.resolve_metric(
                request.user.company, request.user, cle, filters=filters,
                group_by=group_by, period=period)
        except services.MetriqueInactive as exc:
            # ENF50 — la métrique EXISTE mais est désactivée : état (409),
            # 404 gardé pour une clé que la société n'a pas.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        except services.MetriqueInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except services.MetriqueIndisponible as exc:
            # ENF49 (api-fuzz-full 42128456456, UDnVtL) — adaptateur/dataset
            # ENREGISTRÉ mais absent de ce serveur : état de la métrique (409),
            # la requête « GET sans paramètre » était conforme.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
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
        responses={200: inline_serializer('MetriqueLignageReponse', {
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
        }), 409: _METRIQUE_DESACTIVEE})
    def get(self, request, cle=None):
        try:
            lignage = selectors.lineage(request.user.company, cle,
                                        user=request.user)
        except services.MetriqueInactive as exc:
            # ENF50 — la métrique EXISTE mais est désactivée : état (409),
            # 404 gardé pour une clé que la société n'a pas.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        except services.MetriqueInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(lignage)


class GlossaireView(APIView):
    """NTDATA49 — ``GET semantic/glossaire/`` : le dictionnaire de données.

    Chaque métrique ACTIVE de la société avec sa définition française, son
    unité, son propriétaire et sa date de dernière modification — lisible par
    TOUT utilisateur interne (un commercial lit ce que signifie
    « marge_brute » sans coder). Aucune recette n'y figure.
    """

    permission_classes = [IsAnyRole]

    @extend_schema(responses=inline_serializer('GlossaireReponse', {
        'nb_metriques': serializers.IntegerField(),
        'metriques': inline_serializer('GlossaireEntree', {
            'cle': serializers.CharField(),
            'libelle': serializers.CharField(),
            'definition': serializers.CharField(),
            'unite': serializers.CharField(),
            'unite_libelle': serializers.CharField(),
            'proprietaire': serializers.CharField(),
            'derniere_modification': serializers.DateTimeField(),
        }, many=True),
    }))
    def get(self, request):
        entrees = (selectors.glossaire(request.user.company)
                   if request.user.company_id else [])
        return Response({'nb_metriques': len(entrees), 'metriques': entrees})


class MetriqueExpliquerView(APIView):
    """NTDATA44 — ``GET semantic/metriques/<cle>/expliquer/`` : « expliquer ce
    chiffre » d'un widget.

    UNE réponse : le lignage NTDATA43 (définition, dataset, app, filtres,
    version) + le drill-down NTDATA33 (identifiants et liens profonds des
    lignes sources). ``filters`` = filtres effectifs du widget (JSON),
    ``cellule`` = valeurs de regroupement du point cliqué (JSON), ``limite``
    borne la liste (1..1000, défaut 200).
    """

    permission_classes = [IsResponsableOrAdmin]
    schema = _SchemaParametresJson()

    @extend_schema(
        parameters=[
            OpenApiParameter('filters', str, required=False,
                             description='Objet JSON des filtres du widget.'),
            OpenApiParameter('cellule', str, required=False,
                             description='Objet JSON des valeurs de '
                                         'regroupement du point cliqué.'),
            OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                        'maximum': 1000, 'default': 200},
                             required=False,
                             description='Nombre maximal de lignes (1..1000).'),
        ],
        responses={200: inline_serializer('MetriqueExpliquerReponse', {
            'lignage': serializers.JSONField(),
            'filtres_appliques': serializers.JSONField(),
            'cellule': serializers.JSONField(),
            'enregistrements': serializers.JSONField(allow_null=True),
            'raison': serializers.CharField(),
        }), 409: _METRIQUE_DESACTIVEE})
    def get(self, request, cle=None):
        params = request.query_params
        filters = _json_param(params.get('filters'), 'filters', dict)
        cellule = _json_param(params.get('cellule'), 'cellule', dict)
        try:
            limite = int(params.get('limite') or 200)
        except (TypeError, ValueError):
            raise ValidationError({'limite': 'Entier attendu.'})
        if not 1 <= limite <= 1000:
            raise ValidationError({'limite': 'Entre 1 et 1000.'})
        try:
            explication = selectors.expliquer(
                request.user.company, request.user, cle, filters=filters,
                cellule=cellule, limite=limite)
        except services.MetriqueInactive as exc:
            # ENF50 — la métrique EXISTE mais est désactivée : état (409),
            # 404 gardé pour une clé que la société n'a pas.
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        except services.MetriqueInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError, DjangoValidationError):
            return Response(
                {'detail': 'Valeurs de filtre ou de cellule illisibles.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(explication)
