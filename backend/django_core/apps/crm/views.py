from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from .models import Client, Lead
from .serializers import ClientSerializer, LeadSerializer, LeadActivitySerializer
from . import activity
from .services import default_responsable_for
from .devis_auto import champs_manquants, message_manquants
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def assignable_users(request):
    """Employés assignables comme responsable d'un lead (société courante).

    Léger et accessible à la Commerciale (le sélecteur de responsable doit
    fonctionner pour elle, pas seulement pour l'admin) — contrairement à
    /users/ réservé à l'admin. Renvoie de quoi peindre un avatar Odoo
    (initiales/photo) + nom + poste.
    """
    from authentication.models import CustomUser
    from authentication.avatars import presign_avatar
    user = request.user
    qs = CustomUser.objects.filter(is_active=True)
    if user.company_id:
        qs = qs.filter(company=user.company)
    elif not user.is_superuser:
        qs = qs.none()
    qs = qs.order_by('username')
    return Response([
        {
            'id': u.id,
            'username': u.username,
            'poste': u.poste or None,
            'avatar_url': presign_avatar(u.avatar_key),
        }
        for u in qs
    ])


class ClientViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'prenom', 'email', 'telephone']
    ordering_fields = ['nom', 'date_creation']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        # Un client avec des devis est PROTÉGÉ (pas de cascade) : message
        # français clair au lieu d'un 500 silencieux.
        from django.db.models import ProtectedError
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': "Ce client a des devis liés — supprimez ou "
                           "réassignez ses devis d'abord."},
                status=status.HTTP_409_CONFLICT,
            )


class LeadViewSet(TenantMixin, viewsets.ModelViewSet):
    """Leads + historique « chatter » (journal automatique + notes manuelles).

    L'utilisateur acteur et la société viennent toujours de la requête côté
    serveur — jamais du corps envoyé par le navigateur.
    """
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'prenom', 'societe', 'email', 'telephone', 'ville']
    ordering_fields = ['nom', 'date_creation', 'stage']
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # Optional filters: ?stage=NEW  &  ?source=odoo_import_test
        stage = self.request.query_params.get('stage')
        source = self.request.query_params.get('source')
        if stage:
            qs = qs.filter(stage=stage)
        if source:
            qs = qs.filter(source=source)
        # Archivage : par défaut on CACHE les leads archivés. ?archived=all
        # montre tout ; ?archived=only ne montre que les archivés (filtre UI
        # « Archivés »). Les actions detail (retrieve/archiver/restaurer/
        # destroy) doivent atteindre un lead archivé → pas de filtre alors.
        archived = self.request.query_params.get('archived')
        if self.action == 'list':
            if archived == 'only':
                qs = qs.filter(is_archived=True)
            elif archived != 'all':
                qs = qs.filter(is_archived=False)
        return qs

    def perform_create(self, serializer):
        # Société toujours côté serveur (TenantMixin). Si aucun responsable
        # n'est choisi à la création, on applique le responsable par défaut
        # de la société (Paramètres). Un responsable explicite est respecté.
        user = self.request.user
        extra = {'company': user.company}
        if not serializer.validated_data.get('owner'):
            default = default_responsable_for(user.company)
            if default is not None:
                extra['owner'] = default
        serializer.save(**extra)
        activity.log_creation(serializer.instance, user)
        from .services import sync_relance_activity
        sync_relance_activity(serializer.instance, user)

    def perform_update(self, serializer):
        # Snapshot avant écriture pour journaliser ancien → nouveau.
        old = Lead.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        activity.log_changes(old, serializer.instance, self.request.user)
        from .services import sync_relance_activity
        sync_relance_activity(serializer.instance, self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique', 'duplicates']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'devis_auto', 'archiver', 'restaurer', 'merge',
        ]:
            # L'archivage réversible est ouvert à la Commerciale.
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            # La suppression DÉFINITIVE reste réservée à l'admin/propriétaire.
            return [IsAdminRole()]
        return [IsAdminRole()]

    @action(detail=True, methods=['post'], url_path='archiver',
            permission_classes=[IsResponsableOrAdmin])
    def archiver(self, request, pk=None):
        """Archive un lead (réversible). Le retire des vues par défaut."""
        from django.utils import timezone
        lead = self.get_object()
        if not lead.is_archived:
            lead.is_archived = True
            lead.archived_by = request.user
            lead.archived_at = timezone.now()
            lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
            activity.log_archive(lead, request.user)
        return Response(LeadSerializer(lead, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='restaurer',
            permission_classes=[IsResponsableOrAdmin])
    def restaurer(self, request, pk=None):
        """Restaure un lead archivé (le ramène dans les vues par défaut)."""
        lead = self.get_object()
        if lead.is_archived:
            lead.is_archived = False
            lead.archived_by = None
            lead.archived_at = None
            lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
            activity.log_restore(lead, request.user)
        return Response(LeadSerializer(lead, context={'request': request}).data)

    def destroy(self, request, *args, **kwargs):
        """Suppression DÉFINITIVE (admin). Bloquée si des devis sont liés —
        on n'orpheline jamais de pièces financières : message clair, archiver
        à la place. L'événement est journalisé (qui/quand) côté serveur."""
        import logging
        lead = self.get_object()
        if lead.devis.exists():
            return Response(
                {'detail': "Ce lead a des devis liés. Supprimer le lead "
                           "détacherait ces pièces — archivez-le plutôt."},
                status=status.HTTP_409_CONFLICT,
            )
        logging.getLogger('crm.audit').warning(
            'HARD DELETE lead id=%s "%s" par user=%s (company=%s)',
            lead.id, lead, getattr(request.user, 'username', '?'),
            getattr(lead, 'company_id', None),
        )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='duplicates',
            permission_classes=[IsAnyRole])
    def duplicates(self, request, pk=None):
        """Doublons probables (même téléphone/email normalisé, même société)."""
        from .services import find_duplicate_leads
        lead = self.get_object()
        dups = find_duplicate_leads(lead)
        return Response([
            {
                'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                'societe': d.societe, 'telephone': d.telephone,
                'email': d.email, 'stage': d.stage,
                'is_archived': d.is_archived,
                'nb_devis': d.devis.count(),
            }
            for d in dups
        ])

    @action(detail=True, methods=['post'], url_path='merge',
            permission_classes=[IsResponsableOrAdmin])
    def merge(self, request, pk=None):
        """Fusionne d'autres leads DANS celui-ci (survivant). Sans perte :
        devis, chantiers, activités, pièces jointes et historique sont déplacés ;
        les leads absorbés sont archivés (jamais supprimés)."""
        from .services import merge_leads
        survivor = self.get_object()
        ids = request.data.get('others') or []
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Aucun lead à fusionner.'},
                            status=status.HTTP_400_BAD_REQUEST)
        others = list(self.get_queryset().filter(pk__in=ids).exclude(pk=survivor.pk))
        if not others:
            return Response({'detail': 'Leads à fusionner introuvables.'},
                            status=status.HTTP_400_BAD_REQUEST)
        merge_leads(survivor, others, request.user)
        survivor.refresh_from_db()
        return Response(
            LeadSerializer(survivor, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Timeline chatter du lead (auto + notes), du plus récent au plus ancien."""
        lead = self.get_object()
        return Response(
            LeadActivitySerializer(lead.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='devis-auto',
            permission_classes=[IsResponsableOrAdmin])
    def devis_auto(self, request, pk=None):
        """Garde serveur du devis automatique : le lead a-t-il les champs
        requis pour son mode ? Aucun effet de bord — la création du devis
        reste le flux générateur existant. Toute entrée UI appelle cette
        règle AVANT de lancer le générateur."""
        lead = self.get_object()
        manquants = champs_manquants(lead)
        if manquants:
            return Response({'detail': message_manquants(manquants)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'ok': True, 'detail': 'Lead prêt pour le devis automatique.'})

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """Note manuelle (appel, commentaire…) — auteur pris de la requête."""
        lead = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(lead, request.user, body)
        return Response(LeadActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)
