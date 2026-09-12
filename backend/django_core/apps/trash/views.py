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
        if (getattr(self, 'action', None) == 'list'
                and params.get('restaures') not in ('1', 'true', 'True')):
            qs = qs.filter(restaure_le__isnull=True)
        type_libelle = params.get('type')
        if type_libelle:
            qs = qs.filter(type_libelle__iexact=type_libelle)
        depuis = params.get('depuis')
        if depuis:
            qs = qs.filter(supprime_le__gte=depuis)
        jusqua = params.get('jusqua')
        if jusqua:
            qs = qs.filter(supprime_le__lte=jusqua)
        return qs

    def create(self, request, *args, **kwargs):
        # Le journal n'est jamais alimenté depuis l'API (seulement par le bus
        # d'événements) — POST reste ouvert pour l'action `restaurer/`.
        raise MethodNotAllowed('POST')

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
