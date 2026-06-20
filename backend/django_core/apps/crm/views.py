from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.scoping import scope_queryset, scope_client_queryset
from .models import Client, Lead, LeadTag, MotifPerte, Canal, Parrainage
from .serializers import (
    ClientSerializer, LeadSerializer, LeadActivitySerializer,
    LeadTagSerializer, MotifPerteSerializer, CanalSerializer,
    ParrainageSerializer, _tag_en_usage, _motif_en_usage,
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
    search_fields = [
        'nom', 'prenom', 'email', 'telephone',
        'ice', 'if_fiscal', 'rc', 'cin',
    ]
    ordering_fields = ['nom', 'date_creation']
    ordering = ['-date_creation']

    def get_queryset(self):
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # clients rattachés à ses documents/leads visibles. 'all' → inchangé.
        return scope_client_queryset(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        # Traçabilité (L16) : société ET créateur forcés côté serveur — jamais
        # acceptés du corps de la requête.
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['export_xlsx', 'documents']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de clients en .xlsx (société courante)."""
        from .exports import export_clients_xlsx
        ids = request.data.get('ids') or []
        qs = self.get_queryset()
        if ids:
            qs = qs.filter(id__in=ids)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT, detail='Export clients (.xlsx)')
        return export_clients_xlsx(qs.order_by('nom'))

    @action(detail=True, methods=['get'], url_path='documents',
            permission_classes=[IsAnyRole])
    def documents(self, request, pk=None):
        """Panneau détail (L4) : devis, factures et chantiers liés à un client.

        Lecture seule, bornée à la société courante (get_object passe par la
        portée TenantMixin + visibilité). Référence / statut / total uniquement
        — aucun prix d'achat ni marge n'apparaît (sortie client-facing)."""
        client = self.get_object()

        def _statut(obj):
            try:
                return obj.get_statut_display()
            except Exception:
                return getattr(obj, 'statut', None)

        def _date(obj):
            # Devis → date_creation ; Facture → date_emission.
            d = getattr(obj, 'date_creation', None) \
                or getattr(obj, 'date_emission', None)
            return d.isoformat() if d else None

        devis = [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': _statut(d),
                'total_ttc': str(d.total_ttc),
                'date': _date(d),
            }
            for d in client.devis.all().order_by('-date_creation')
        ]
        factures = [
            {
                'id': f.id,
                'reference': f.reference,
                'statut': _statut(f),
                'total_ttc': str(f.total_ttc),
                'date': _date(f),
            }
            for f in client.factures.all().order_by('-date_emission')
        ]
        chantiers = [
            {
                'id': i.id,
                'reference': i.reference,
                'statut': _statut(i),
            }
            for i in client.installations.all().order_by('-id')
        ]
        return Response({
            'devis': devis,
            'factures': factures,
            'chantiers': chantiers,
        })

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
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que ses
        # leads (responsable). 'all' → inchangé. Un utilisateur voit toujours
        # ses propres leads (son id est inclus dans la portée).
        qs = scope_queryset(qs, self.request.user, ['owner'])
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
            # Un utilisateur à portée restreinte (Feature F) garde la propriété
            # de ce qu'il crée — sinon il perdrait de vue son propre lead. Les
            # comptes « voit tout » conservent l'assignation au responsable par
            # défaut de la société (comportement historique).
            if user.record_scope() != 'all':
                extra['owner'] = user
            else:
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
                                          'check_duplicates', 'doublons',
                                          'export_xlsx']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'devis_auto', 'archiver', 'restaurer', 'merge',
            'whatsapp_devis', 'bulk',
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

        from .services import coerce_id_list

        lead = self.get_object()
        raw_ids = request.data.get('devis_ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {'detail': 'Sélectionnez au moins un devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ids = coerce_id_list(raw_ids)
        except ValueError:
            return Response(
                {'detail': 'Identifiant de devis invalide.'},
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
        # Langue du message : la valeur explicite de la requête l'emporte ;
        # sinon on retombe sur la langue préférée du lead, puis sur le FR.
        langue = request.data.get('langue')
        if langue is None:
            langue = lead.langue_preferee or 'fr'
        message, links = build_devis_whatsapp(request, lead, devis_list, langue)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.WHATSAPP, instance=lead,
               detail=f'Lien WhatsApp devis préparé ({len(devis_list)})')
        # L856 — trace l'action dans le chatter du lead (Historique). Acteur et
        # société posés côté serveur, jamais lus du corps de la requête.
        refs = ', '.join(d.reference for d in devis_list)
        activity.log_note(
            lead, request.user,
            f'Lien WhatsApp généré pour {refs} '
            f'par {getattr(request.user, "username", "?")}.')
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

    @action(detail=False, methods=['get'], url_path='check-duplicates',
            permission_classes=[IsAnyRole])
    def check_duplicates(self, request):
        """Contrôle PRÉ-CRÉATION (et édition) : un téléphone/email saisi
        correspond-il déjà à un lead de la société ? Avertissement NON bloquant
        côté formulaire — la société vient du serveur, jamais du corps. Saisie
        libre acceptée (mêmes normaliseurs que la détection de doublons).
        ?exclude=<id> retire le lead en cours d'édition de ses propres doublons."""
        from .services import find_duplicates_by_contact
        phone = request.query_params.get('telephone') or \
            request.query_params.get('phone')
        email = request.query_params.get('email')
        exclude = request.query_params.get('exclude')
        exclude_pk = exclude if (exclude or '').isdigit() else None
        dups = find_duplicates_by_contact(
            request.user.company, phone=phone, email=email,
            exclude_pk=exclude_pk)
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
        from .services import (
            find_duplicate_clusters, _completeness, cluster_match_keys,
            _MERGE_FILL_FIELDS,
        )
        from .models import LeadActivity
        include_archived = request.query_params.get('archived') in ('1', 'true')
        clusters, _ = find_duplicate_clusters(
            request.user.company, include_archived=include_archived)
        # Libellés FR des champs comblés à la fusion (aperçu avant confirmation).
        field_labels = activity.TRACKED_FIELDS
        out = []
        for group in clusters:
            suggested = max(
                group, key=lambda le: (_completeness(le), le.date_creation))
            others = [d for d in group if d.id != suggested.id]
            # Aperçu de fusion : devis + activités migrés, et champs vides du
            # survivant que les absorbés viendraient combler.
            devis_migres = sum(d.devis.count() for d in others)
            activites_migrees = sum(
                LeadActivity.objects.filter(lead=d).count() for d in others)
            champs_combles = []
            for field in _MERGE_FILL_FIELDS:
                cur = getattr(suggested, field, None)
                if cur in (None, '', False):
                    if any(getattr(d, field, None) not in (None, '', False)
                           for d in others):
                        champs_combles.append(field_labels.get(field, field))
            out.append({
                'suggested_survivor_id': suggested.id,
                'match_keys': cluster_match_keys(group),
                'merge_preview': {
                    'devis': devis_migres,
                    'activites': activites_migrees,
                    'fiches_archivees': len(others),
                    'champs_combles': champs_combles,
                },
                'members': [
                    {
                        'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                        'societe': d.societe, 'telephone': d.telephone,
                        'email': d.email, 'ville': d.ville, 'stage': d.stage,
                        'is_archived': d.is_archived,
                        'nb_devis': d.devis.count(),
                        'nb_activites': LeadActivity.objects.filter(lead=d).count(),
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
        """Actions EN MASSE sur une sélection de leads (liste + kanban).

        Corps : {ids: [...], action: 'reassign'|'add_tag'|'remove_tag'|
        'set_stage'|'set_relance'|'clear_relance'|'set_perdu'|'unset_perdu'|
        'archive'|'unarchive'|'delete', + paramètres de l'action}. La société et
        l'acteur viennent du serveur ; la règle métier (funnel, garde-fous,
        Historique « en masse ») vit dans services.apply_bulk_action."""
        from .services import BULK_ACTIONS, BULK_ADMIN_ONLY, apply_bulk_action
        op = request.data.get('action')
        ids = request.data.get('ids') or []
        if op not in BULK_ACTIONS:
            return Response({'detail': 'Action en masse inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins un lead.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if op in BULK_ADMIN_ONLY and not request.user.is_admin_role:
            return Response(
                {'detail': "Action réservée à l'administrateur."},
                status=status.HTTP_403_FORBIDDEN)
        try:
            result = apply_bulk_action(
                company=request.user.company, user=request.user,
                lead_ids=ids, op=op, params=request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de leads en .xlsx (société courante).

        Corps : {ids: [...]} — la sélection. Vide → 400 (l'UI exporte une
        sélection). Borné à la société de l'utilisateur."""
        from .exports import export_leads_xlsx
        from .services import coerce_id_list
        raw_ids = request.data.get('ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response({'detail': 'Sélectionnez au moins un lead.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = coerce_id_list(raw_ids)
        except ValueError:
            return Response({'detail': 'Identifiant de lead invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        leads = (Lead.objects.filter(company=request.user.company, id__in=ids)
                 .select_related('owner').order_by('id'))
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT,
               detail=f'Export leads (.xlsx) — {len(ids)} ligne(s)')
        return export_leads_xlsx(leads)


class LeadTagViewSet(TenantMixin, viewsets.ModelViewSet):
    """Étiquettes de lead gérées (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L780) : une étiquette référencée par des leads
    ne se supprime pas — l'admin l'archive plutôt (l'historique est préservé)."""
    queryset = LeadTag.objects.all()
    serializer_class = LeadTagSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        tag = self.get_object()
        if _tag_en_usage(tag.company, tag.nom) > 0:
            return Response(
                {'detail': "Cette étiquette est utilisée par des leads — "
                           "archivez-la plutôt que de la supprimer."},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)


class MotifPerteViewSet(TenantMixin, viewsets.ModelViewSet):
    """Motifs de perte gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L779) : un motif utilisé par des leads ne se
    supprime pas — l'admin l'archive plutôt (comme pour les canaux)."""
    queryset = MotifPerte.objects.all()
    serializer_class = MotifPerteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        motif = self.get_object()
        if _motif_en_usage(motif.company, motif.nom) > 0:
            return Response(
                {'detail': "Ce motif est utilisé par des leads — archivez-le "
                           "plutôt que de le supprimer."},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)


# Canaux par défaut (clés = Lead.Canal) — 'site_web' est PROTÉGÉ (webhook site).
_DEFAULT_CANAUX = [
    ('meta_ads', 'Publicité Meta', False),
    ('whatsapp_ctwa', 'WhatsApp/CTWA', False),
    ('site_web', 'Site web', True),
    ('reference', 'Référence', False),
    ('telephone', 'Téléphone', False),
    ('walk_in', 'Visite/Walk-in', False),
    ('autre', 'Autre', False),
]


def seed_canaux(company):
    """Crée les canaux par défaut pour une société qui n'en a aucun (idempotent,
    additif). 'site_web' est marqué protégé."""
    if company is None or Canal.objects.filter(company=company).exists():
        return
    for i, (cle, libelle, protege) in enumerate(_DEFAULT_CANAUX):
        Canal.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'ordre': i, 'protege': protege})


class CanalViewSet(TenantMixin, viewsets.ModelViewSet):
    """Canaux / sources de lead gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fous : un canal protégé ('site_web') ne se supprime
    pas, et aucun canal utilisé par des leads ne se supprime."""
    queryset = Canal.objects.all()
    serializer_class = CanalSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        # Amorçage paresseux : à la 1re consultation, on peuple les canaux par
        # défaut de la société (préserve le comportement existant).
        if request.user.company_id:
            seed_canaux(request.user.company)
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        canal = self.get_object()
        if canal.protege:
            return Response(
                {'detail': "Ce canal est protégé (utilisé par le site web) et "
                           "ne peut pas être supprimé."},
                status=status.HTTP_409_CONFLICT)
        if Lead.objects.filter(company=canal.company, canal=canal.cle).exists():
            return Response(
                {'detail': "Ce canal est utilisé par des leads — archivez-le "
                           "plutôt que de le supprimer."},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)


class ParrainageViewSet(TenantMixin, viewsets.ModelViewSet):
    """N98 — parrainages. Lecture tout rôle, écriture responsable/admin.

    À la création, la récompense est pré-remplie depuis Paramètres
    (referral_reward) quand elle n'est pas fournie. ?stats=1 ajoute un petit
    tableau de bord (totaux par statut + récompenses)."""
    queryset = Parrainage.objects.select_related(
        'parrain', 'filleul_lead', 'filleul_client').all()
    serializer_class = ParrainageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['stats']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        company = self.request.user.company
        extra = {'created_by': self.request.user}
        if serializer.validated_data.get('recompense') in (None, ''):
            try:
                from apps.parametres.models import CompanyProfile
                prof = CompanyProfile.get(company)
                if prof and prof.referral_reward is not None:
                    extra['recompense'] = prof.referral_reward
            except Exception:
                pass
        serializer.save(**extra)

    @action(detail=False, methods=['get'], url_path='stats',
            permission_classes=[IsAnyRole])
    def stats(self, request):
        """Tableau de bord parrainage : compte par statut + récompenses."""
        from decimal import Decimal
        qs = self.get_queryset()
        total = qs.count()
        par_statut = {}
        rec_total = Decimal('0')
        rec_versee = Decimal('0')
        for p in qs:
            par_statut[p.statut] = par_statut.get(p.statut, 0) + 1
            if p.recompense:
                rec_total += p.recompense
                if p.statut == Parrainage.Statut.RECOMPENSE_VERSEE:
                    rec_versee += p.recompense
        return Response({
            'total': total,
            'par_statut': par_statut,
            'recompenses_total': str(rec_total),
            'recompenses_versees': str(rec_versee),
        })
