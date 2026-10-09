"""NTUX7 — endpoint `corbeille/` (écran `/parametres/corbeille`)."""
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier
from core.permissions import declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .models import ElementSupprime
from .permissions import PeutConsulterCorbeille, PeutRestaurerCorbeille
from .serializers import ElementSupprimeSerializer
from .services import RestaurationImpossible, restaurer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from django.utils.dateparse import parse_date, parse_datetime


_FILTRES = [
    OpenApiParameter('type', OpenApiTypes.STR, required=False),
    OpenApiParameter('depuis', OpenApiTypes.DATETIME, required=False),
    OpenApiParameter('jusqua', OpenApiTypes.DATETIME, required=False),
    OpenApiParameter('restaures', OpenApiTypes.STR, required=False,
                     enum=['1', 'true', 'True', '0', 'false']),
]


def _borne_temporelle(valeur, nom):
    """Date ou date-heure ISO ; sinon 400 nommant le paramètre (jamais 500)."""
    if parse_datetime(valeur) is not None or parse_date(valeur) is not None:
        return valeur
    raise ValidationError({nom: 'Date ou date-heure ISO attendue.'})


@extend_schema_view(list=extend_schema(parameters=_FILTRES))
class CorbeilleViewSet(CompanyScopedModelViewSet):
    """Corbeille transverse : liste paginée filtrable + restauration.

    Réservée Directeur/Admin (l'écran `/parametres/corbeille` est un écran de
    gouvernance : il expose les suppressions de TOUTE la société). La société
    est bornée par `TenantMixin.get_queryset` — jamais lue du corps.

    Le journal est en LECTURE SEULE : `create`/`update`/`destroy` sont refusés
    (une entrée naît de l'événement `record_soft_deleted`, se ferme par
    `restaurer/`, et disparaît par la purge de rétention `purger_corbeille`).
    """

    queryset = ElementSupprime.objects.select_related(
        'content_type', 'supprime_par').all()
    serializer_class = ElementSupprimeSerializer
    # Pas de PUT/PATCH/DELETE ; POST sert UNIQUEMENT à l'action `restaurer/`.
    http_method_names = ['get', 'post', 'head', 'options']
    parser_classes = [JSONParser]

    def get_permissions(self):
        # Une garde déclarée par l'@action PRIME (sinon le `permission_classes=`
        # du décorateur serait silencieusement jeté — cf. core.permissions).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        # NTUX31 — `ux.corbeille.consulter` s'ajoute EN PLUS du palier existant
        # (jamais à sa place) : administrable dans l'éditeur de rôles, sans
        # retirer l'accès d'un compte hérité (repli légacy).
        return [IsAdminOrResponsableTier(), PeutConsulterCorbeille()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        # Par défaut : seules les entrées ENCORE dans la corbeille. Le journal
        # complet (audit de rétention, NTUX24) s'obtient avec `?restaures=1`.
        #
        # UNIQUEMENT sur la LISTE : ce filtre est une commodité d'affichage, pas
        # une règle de visibilité. Appliqué aussi au détail, il faisait
        # DISPARAÎTRE une entrée déjà restaurée, si bien qu'un second
        # `POST {id}/restaurer/` renvoyait 404 (« ça n'existe pas ») au lieu du
        # 400 explicite « déjà restauré » — et que `GET {id}/` d'une entrée
        # restaurée mentait de la même façon. La borne SOCIÉTÉ, elle, reste
        # posée par `TenantMixin.get_queryset` en amont : rien n'est élargi
        # côté multi-société.
        # NTUX24 — `export_xlsx` reflète EXACTEMENT le même filtre par défaut
        # que `list` (même bascule « Inclure les éléments restaurés »).
        if (getattr(self, 'action', None) in ('list', 'export_xlsx')
                and params.get('restaures') not in ('1', 'true', 'True')):
            qs = qs.filter(restaure_le__isnull=True)
        type_libelle = params.get('type')
        if type_libelle:
            qs = qs.filter(type_libelle__iexact=type_libelle)
        depuis = params.get('depuis')
        if depuis:
            qs = qs.filter(
                supprime_le__gte=_borne_temporelle(depuis, 'depuis'))
        jusqua = params.get('jusqua')
        if jusqua:
            qs = qs.filter(
                supprime_le__lte=_borne_temporelle(jusqua, 'jusqua'))
        return qs

    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        # Le journal n'est jamais alimenté depuis l'API (seulement par le bus
        # d'événements) — POST reste ouvert pour l'action `restaurer/`.
        raise MethodNotAllowed('POST')

    @extend_schema(request=None, responses=inline_serializer('CorbeilleRestauration', {
        'restaure': serializers.BooleanField(),
        'element': ElementSupprimeSerializer()}))
    @action(detail=True, methods=['post'], url_path='restaurer',
            permission_classes=[IsAdminOrResponsableTier, PeutRestaurerCorbeille])
    def restaurer(self, request, pk=None):
        """Restaure la cible via le `services.py` de l'app cible (registre
        NTUX7), jamais par un accès direct à son modèle."""
        element = self.get_object()
        if element.restaure_le is not None:
            raise ValidationError({'detail': 'Cet élément a déjà été restauré.'})
        try:
            obj = restaurer(element, user=request.user)
        except RestaurationImpossible as exc:
            raise ValidationError({'detail': str(exc)})
        # NTUX38 — traçabilité audit d'une action UX sensible (modèle
        # `audit.AuditLog` existant, jamais un nouveau journal ; import
        # fonction-local, même patron qu'ailleurs dans le dépôt).
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record as audit_record
        audit_record(
            AuditLog.Action.UPDATE, instance=element, user=request.user,
            company=element.company,
            detail=(
                f'Restauré depuis la corbeille : {element.type_libelle or "élément"} '
                f'« {element.libelle_snapshot} ».'))
        return Response({
            'restaure': obj is not None,
            'element': ElementSupprimeSerializer(element).data,
        })

    @extend_schema(
        parameters=_FILTRES,
        responses={(200, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): OpenApiTypes.BINARY})
    @action(detail=False, methods=['get'], url_path='export-xlsx')
    def export_xlsx(self, request):
        """NTUX24 — export .xlsx du journal de corbeille (audit de rétention
        RGPD/CNDP), sur les MÊMES filtres que `list` (`?type=`/`?depuis=`/
        `?jusqua=`/`?restaures=`) — jamais une seconde source de vérité.
        Moteur .xlsx PARTAGÉ `apps.records.xlsx` (foundation app, exempte de
        la frontière inter-apps), jamais le moteur `quote_engine` (règle #4,
        hors périmètre). Aucune donnée sensible au-delà de `libelle_snapshot`
        (jamais `donnees_snapshot`, best-effort affichage seul)."""
        from django.utils import timezone

        from apps.records.xlsx import build_xlsx_response

        elements = self.get_queryset()
        headers = [
            'Type', 'Libellé', 'Supprimé par', 'Supprimé le', 'Expire le',
            'Statut',
        ]
        now = timezone.now()
        rows = []
        for el in elements:
            if el.restaure_le:
                statut = 'Restauré'
            elif el.expire_le and el.expire_le < now:
                statut = 'Expiré (purge planifiée imminente)'
            else:
                statut = 'Actif'
            supprime_par = el.supprime_par
            nom_supprime_par = ''
            if supprime_par:
                full = f'{getattr(supprime_par, "first_name", "")} {getattr(supprime_par, "last_name", "")}'.strip()
                nom_supprime_par = full or getattr(supprime_par, 'username', '') or ''
            rows.append([
                el.type_libelle or '',
                el.libelle_snapshot or '',
                nom_supprime_par,
                el.supprime_le,
                el.expire_le,
                statut,
            ])
        return build_xlsx_response(
            'journal-corbeille.xlsx', headers, rows, sheet_title='Journal corbeille')
