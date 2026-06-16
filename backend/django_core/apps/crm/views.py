from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from .models import Client, Lead, LeadTag, MotifPerte, CanalSource
from .serializers import (
    ClientSerializer, LeadSerializer, LeadActivitySerializer,
    LeadTagSerializer, MotifPerteSerializer, CanalSourceSerializer,
)
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
@permission_classes([IsAnyRole])
def global_search_view(request):
    """Recherche globale multi-modèles (leads, clients, devis, factures,
    chantiers, équipements, tickets SAV) — tout scopé société. Résultats
    groupés par type avec id + libellé + route."""
    from .discovery import global_search
    q = request.query_params.get('q', '')
    return Response({'q': q, 'groups': global_search(request.user, q)})


@api_view(['GET'])
@permission_classes([IsAnyRole])
def notifications_view(request):
    """Notifications in-app calculées à la volée (activités en retard,
    garanties bientôt expirées, factures impayées) — scopé société."""
    from .discovery import notifications
    return Response(notifications(request.user))


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
        if self.action in READ_ACTIONS + ['historique', 'duplicates',
                                          'doublons']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'devis_auto', 'archiver', 'restaurer', 'merge',
            'whatsapp_devis', 'bulk',
        ]:
            # L'archivage réversible est ouvert à la Commerciale. Les actions
            # en masse aussi (la suppression en masse est gardée à l'intérieur).
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

    @action(detail=True, methods=['post'], url_path='whatsapp-devis',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_devis(self, request, pk=None):
        """Construit un lien wa.me prêt à envoyer pour un/plusieurs devis du lead.

        N'envoie RIEN : ouvre WhatsApp avec le message pré-rempli (le commercial
        appuie lui-même sur Envoyer). Chaque {lien} est un lien public tokenisé
        (30 j) vers le PDF CLIENT — jamais de prix d'achat ni de marge.
        """
        from apps.ventes.models import Devis
        from apps.ventes.utils.phone import normalize_ma_phone
        from apps.ventes.utils.whatsapp import (
            build_devis_whatsapp, build_wa_url,
        )

        lead = self.get_object()
        ids = request.data.get('devis_ids') or []
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'Sélectionnez au moins un devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Devis du lead, dans la société courante uniquement.
        devis_list = list(
            Devis.objects.filter(id__in=ids, lead=lead, company=lead.company)
            .order_by('id'))
        if len(devis_list) != len(set(ids)):
            return Response(
                {'detail': 'Un devis sélectionné est introuvable pour ce lead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phone = lead.whatsapp or lead.telephone
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        langue = request.data.get('langue', 'fr')
        message, links = build_devis_whatsapp(request, lead, devis_list, langue)
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'links': links,
        })

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

    @action(detail=False, methods=['get'], url_path='doublons',
            permission_classes=[IsAnyRole])
    def doublons(self, request):
        """Atelier doublons : scanne TOUS les leads de la société et renvoie les
        clusters de doublons probables (téléphone / email / nom normalisé), avec
        pour chacun un survivant suggéré (le plus complet, puis le plus récent)."""
        from .services import find_duplicate_clusters, _completeness
        include_archived = request.query_params.get('archived') in ('1', 'true')
        clusters, _ = find_duplicate_clusters(
            request.user.company, include_archived=include_archived)
        out = []
        for group in clusters:
            suggested = max(
                group, key=lambda le: (_completeness(le), le.date_creation))
            out.append({
                'suggested_survivor_id': suggested.id,
                'members': [
                    {
                        'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                        'societe': d.societe, 'telephone': d.telephone,
                        'email': d.email, 'ville': d.ville, 'stage': d.stage,
                        'is_archived': d.is_archived,
                        'nb_devis': d.devis.count(),
                        'completeness': _completeness(d),
                        'date_creation': d.date_creation.isoformat(),
                    }
                    for d in group
                ],
            })
        return Response(out)

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

    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsResponsableOrAdmin])
    def bulk(self, request):
        """Actions « en masse » sur une sélection de leads.

        Corps : {action, ids:[...], params:{...}}. Tout est scopé société (les
        ids étrangers sont ignorés), chaque changement est journalisé dans
        l'Historique avec le marqueur « en masse ». L'export renvoie un fichier
        .xlsx ; la suppression est admin-only et bloquée si elle orphelinerait
        des devis."""
        from . import bulk as bulk_ops
        from django.http import HttpResponse

        action_name = request.data.get('action')
        ids = request.data.get('ids') or []
        params = request.data.get('params') or {}
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Aucun lead sélectionné.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Leads de la société courante uniquement — les ids étrangers sont
        # silencieusement ignorés (get_queryset applique déjà le scope).
        base = Lead.objects.filter(company=request.user.company)
        leads = list(base.filter(pk__in=ids))

        if action_name == 'export':
            content = bulk_ops.export_leads_xlsx(leads)
            resp = HttpResponse(
                content,
                content_type=('application/vnd.openxmlformats-officedocument'
                              '.spreadsheetml.sheet'))
            resp['Content-Disposition'] = (
                'attachment; filename="leads.xlsx"')
            return resp

        if action_name == 'delete':
            if not getattr(request.user, 'is_admin_role', False):
                return Response(
                    {'detail': "Suppression réservée à l'administrateur."},
                    status=status.HTTP_403_FORBIDDEN)
            ok, result = bulk_ops.delete_leads(leads, request.user)
            if not ok:
                return Response({'detail': result},
                                status=status.HTTP_409_CONFLICT)
            return Response({'deleted': result})

        if action_name not in bulk_ops.MUTATING_ACTIONS:
            return Response({'detail': 'Action inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)

        summary = bulk_ops.run_mutating_action(
            action_name, leads, request.user, params)
        summary['requested'] = len(ids)
        summary['matched'] = len(leads)
        return Response(summary)


class LeadTagViewSet(TenantMixin, viewsets.ModelViewSet):
    """Étiquettes de lead gérées (Paramètres → CRM). Lecture tout rôle,
    écriture admin."""
    queryset = LeadTag.objects.all()
    serializer_class = LeadTagSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]


class MotifPerteViewSet(TenantMixin, viewsets.ModelViewSet):
    """Motifs de perte gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin."""
    queryset = MotifPerte.objects.all()
    serializer_class = MotifPerteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]


def _slugify_canal_key(label):
    """Clé stable (a-z0-9_) dérivée d'un libellé, pour un nouveau canal."""
    import re
    import unicodedata
    norm = unicodedata.normalize('NFKD', label or '')
    norm = norm.encode('ascii', 'ignore').decode('ascii').lower()
    norm = re.sub(r'[^a-z0-9]+', '_', norm).strip('_')
    return norm or 'canal'


class CanalSourceViewSet(TenantMixin, viewsets.ModelViewSet):
    """Canaux / sources de lead gérés (Paramètres → CRM).

    Lecture tout rôle, écriture admin. La clé `site_web` est protégée (non
    renommable, non supprimable) ; un canal utilisé par un lead ne peut pas
    être supprimé (message français clair).
    """
    queryset = CanalSource.objects.all()
    serializer_class = CanalSourceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        # Clé posée côté serveur (slug du libellé), unique par société.
        company = self.request.user.company
        label = serializer.validated_data.get('label', '')
        base = _slugify_canal_key(label)
        key = base
        i = 2
        while CanalSource.objects.filter(company=company, key=key).exists():
            key = f'{base}_{i}'
            i += 1
        serializer.save(company=company, key=key)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # La clé n'est jamais modifiable (stabilité du lien Lead.canal).
        if 'key' in request.data and request.data.get('key') != instance.key:
            return Response(
                {'detail': "La clé d'un canal ne peut pas être modifiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Le canal « Site web » est protégé : libellé verrouillé (utilisé par
        # le webhook du site public). On autorise seulement l'ordre/archivage.
        if instance.is_protected:
            new_label = request.data.get('label')
            if new_label is not None and str(new_label).strip() != instance.label:
                return Response(
                    {'detail': "Le canal « Site web » est protégé et ne peut "
                               "pas être renommé."},
                    status=status.HTTP_409_CONFLICT,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_protected:
            return Response(
                {'detail': "Le canal « Site web » est protégé et ne peut pas "
                           "être supprimé."},
                status=status.HTTP_409_CONFLICT,
            )
        # Bloque la suppression d'un canal encore utilisé par un lead.
        in_use = Lead.objects.filter(
            company=instance.company, canal=instance.key).exists()
        if in_use:
            return Response(
                {'detail': "Ce canal est utilisé par des leads — il ne peut "
                           "pas être supprimé. Archivez-le plutôt."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)
