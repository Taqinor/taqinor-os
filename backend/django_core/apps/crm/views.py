from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from core.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet
from apps.core.destroy_mixins import UsageGuardedDestroyMixin
from authentication.scoping import scope_queryset, scope_client_queryset
from .models import (
    Appointment, Client, ConcurrentPerte, EquipeCommerciale,
    ForecastEntry, ForecastSnapshot, Lead, LeadPlaybookProgress, LeadTag,
    MotifPerte, Canal, Parrainage, MessageTemplate, ObjectifCommercial,
    PlanActivite, PlanCompte, Playbook, PlaybookEtape,
    PlaybookTache, PointContact, RevueCompte, SiteProfile, WebsiteLeadPayload,
)
from .serializers import (
    AppointmentSerializer, ClientSerializer, ConcurrentPerteSerializer,
    LeadSerializer, LeadActivitySerializer,
    LeadTagSerializer, MotifPerteSerializer, CanalSerializer,
    ParrainageSerializer, MessageTemplateSerializer, _tag_en_usage, _motif_en_usage,
    ObjectifCommercialSerializer, ObjectifAttainmentSerializer,
    PlanActiviteSerializer, PointContactSerializer, SiteProfileSerializer,
    EquipeCommercialeSerializer, WebsiteLeadPayloadSerializer,
    ForecastEntrySerializer, ForecastSnapshotSerializer,
    PlanCompteSerializer, RevueCompteSerializer,
    PlaybookSerializer, PlaybookEtapeSerializer, PlaybookTacheSerializer,
    LeadPlaybookProgressSerializer,
)
from apps.records.views import ChatterViewSetMixin
from . import activity
from .services import default_responsable_for
from .devis_auto import champs_manquants, message_manquants
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)

# ODX13 — ré-export TRANSITOIRE des ViewSets partenaires/territoires (FG234–
# 237) qui vivent encore dans ``apps.compta.views`` (adossés à
# ``_ComptaBaseViewSet`` = ``TenantMixin`` + ``ModelViewSet``, scoping
# ``request.user.company`` + assignation forcée de ``company``). Ce module
# donne aux nouvelles routes ``/api/django/crm/…`` un point d'entrée
# ``apps.crm.views`` stable ; les anciennes routes ``/api/django/compta/…``
# continuent de servir les MÊMES classes. ODX22 re-logera le corps ici.
from apps.compta.views import (  # noqa: F401
    CommissionPartenaireViewSet,
    PartenaireViewSet,
    SoumissionLeadPartenaireViewSet,
    TerritoireCommercialViewSet,
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


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def equipes_statistiques(request):
    """ZSAL3 — Tableau de bord « Mes équipes » : pipeline ouvert/pondéré,
    activités en retard, CA signé du mois vs cible, par équipe commerciale
    active de la société courante."""
    user = request.user
    if not user.company_id:
        if not user.is_superuser:
            return Response({'equipes': []})
        return Response({'equipes': []})
    from .selectors import stats_equipe
    return Response({'equipes': stats_equipe(user.company)})


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def rapport_attribution(request):
    """ZSAL6 — Rapport d'attribution des leads par commercial + par source,
    croisé avec le résultat (conversion, CA signé). ?debut=&fin= (YYYY-MM-DD,
    optionnels) filtrent la période. Lecture seule."""
    user = request.user
    if not user.company_id:
        return Response({'par_commercial': [], 'par_source': []})
    from django.utils.dateparse import parse_date
    debut = parse_date(request.query_params.get('debut') or '') or None
    fin = parse_date(request.query_params.get('fin') or '') or None
    from .selectors import attribution_leads
    return Response(attribution_leads(user.company, debut=debut, fin=fin))


class ClientViewSet(CompanyScopedModelViewSet):
    # ARC2 — pilote : base transverse unique (TenantMixin + ModelViewSet). Le
    # get_queryset (portée de visibilité) et perform_create (company +
    # created_by forcés serveur) SURCHARGENT la base : réponses inchangées.
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
        # QC1 — `search` est une LECTURE scopée société (autocomplete des
        # données propres) : ouverte à tout rôle authentifié, comme `list`.
        # Ce get_permissions prime sur le permission_classes de l'action.
        if self.action in READ_ACTIONS + ['export_xlsx', 'documents', 'search']:
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

    @action(detail=False, methods=['get'], url_path='search',
            permission_classes=[IsAnyRole])
    def search(self, request):
        """QC1 — Autocomplete entreprise sur les DONNÉES PROPRES de la société
        (clients + fournisseurs + leads), recherche floue sur nom/ICE, scopée
        société côté serveur. Passe par le provider seam ``search_companies``
        (QC2 pourra brancher un registre licencié derrière un flag). LECTURE
        SEULE — ne crée jamais rien.

        Paramètre : ``q`` (texte). Renvoie ``{results: [{source, id, nom, ice,
        if_fiscal, rc, adresse, telephone, email}, …]}`` (≤ 12)."""
        from .company_search import search_companies
        q = (request.query_params.get('q') or '').strip()
        results = search_companies(request.user.company, q) if q else []
        return Response({'results': results})

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
                # VX245(c) — clé RAW (additive, jamais lue par les autres
                # consommateurs de `statut`) : « Relancer par WhatsApp »
                # n'apparaît QUE sur une facture réellement en retard, sans
                # dépendre du libellé FR affiché (fragile/localisé).
                'statut_key': f.statut,
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

    @action(detail=True, methods=['get'], url_path='consolidation',
            permission_classes=[IsAnyRole])
    def consolidation(self, request, pk=None):
        """XSAL9 — Rollup CA groupe (société mère + toutes ses filiales,
        récursif) — voir ``selectors.consolidation_client``. Lecture seule,
        bornée à la société courante (get_object passe par TenantMixin)."""
        from .selectors import consolidation_client
        client = self.get_object()
        rollup = consolidation_client(client)
        return Response({
            'filiales': [
                {'id': f.id, 'nom': str(f), 'parent_id': f.parent_id}
                for f in rollup['filiales']
            ],
            'ca_devis_total': str(rollup['ca_devis_total']),
            'ca_factures_total': str(rollup['ca_factures_total']),
            'nb_devis_total': rollup['nb_devis_total'],
            'nb_factures_total': rollup['nb_factures_total'],
        })

    @action(detail=True, methods=['get'], url_path='data-export',
            permission_classes=[IsResponsableOrAdmin])
    def data_export(self, request, pk=None):
        """FG26 — bundle d'accès du sujet (RGPD) : toutes les données
        personnelles détenues sur un client + la liste de ses documents liés.

        Lecture seule, company-scopée (get_object passe par TenantMixin +
        visibilité). Destiné à satisfaire une demande d'accès du sujet."""
        client = self.get_object()
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT, instance=client,
               detail='Export RGPD (accès du sujet)')
        identite = {
            'id': client.id,
            'nom': client.nom, 'prenom': client.prenom,
            'email': client.email, 'telephone': client.telephone,
            'adresse': client.adresse, 'type_client': client.type_client,
            'cin': client.cin, 'ice': client.ice,
            'if_fiscal': client.if_fiscal, 'rc': client.rc,
            'custom_data': client.custom_data,
            'date_creation': client.date_creation.isoformat()
            if client.date_creation else None,
            'is_anonymized': client.is_anonymized,
        }
        documents = {
            'devis': [
                {'reference': d.reference, 'statut': getattr(d, 'statut', None),
                 'total_ttc': str(d.total_ttc)}
                for d in client.devis.all().order_by('-date_creation')
            ],
            'factures': [
                {'reference': f.reference, 'statut': getattr(f, 'statut', None),
                 'total_ttc': str(f.total_ttc)}
                for f in client.factures.all().order_by('-date_emission')
            ],
        }
        return Response({'identite': identite, 'documents': documents})

    @action(detail=True, methods=['post'], url_path='anonymize',
            permission_classes=[IsAdminRole])
    def anonymize(self, request, pk=None):
        """FG26 — droit à l'effacement : scrube les PII du client tout en
        PRÉSERVANT l'intégrité comptable (devis/factures conservés, liés à une
        identité neutralisée). Admin uniquement, irréversible, idempotent."""
        from django.utils import timezone
        client = self.get_object()
        if client.is_anonymized:
            return Response(
                {'detail': 'Ce client est déjà anonymisé.'},
                status=status.HTTP_400_BAD_REQUEST)
        client.nom = f'Client anonymisé #{client.id}'
        client.prenom = None
        client.email = None
        client.telephone = None
        client.adresse = None
        client.cin = None
        client.ice = None
        client.if_fiscal = None
        client.rc = None
        client.custom_data = None
        client.is_anonymized = True
        client.anonymized_at = timezone.now()
        client.save()
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.UPDATE, instance=client,
               detail='Anonymisation RGPD (effacement des données personnelles)')
        return Response(ClientSerializer(
            client, context={'request': request}).data)

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

    # FG32 — Segmentation clients ────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='segments',
            permission_classes=[IsAnyRole])
    def segments(self, request):
        """Segmentation client : top clients, sans devis récent, à recontacter.

        ?segment= top | sans_devis | a_recontacter | dormants
        Calculs basés sur les totaux facturés et dates de devis existants.
        """
        from django.utils import timezone
        import datetime
        segment = request.query_params.get('segment', 'top')
        qs = self.get_queryset()
        now = timezone.now()
        cutoff_12m = now - datetime.timedelta(days=365)
        cutoff_18m = now - datetime.timedelta(days=548)

        result = []

        if segment == 'top':
            # Top 20 clients par valeur facturée TTC (toutes factures non annulées)
            from decimal import Decimal
            scored = []
            for c in qs:
                total = sum(
                    f.total_ttc for f in c.factures.all() if f.statut != 'annulee'
                ) or Decimal('0')
                scored.append((float(total), c))
            scored.sort(key=lambda x: x[0], reverse=True)
            result = [
                {
                    'id': c.id, 'nom': str(c),
                    'total_facture_ttc': round(t, 2),
                    'segment': 'top',
                }
                for t, c in scored[:20]
            ]

        elif segment == 'sans_devis':
            # Clients sans devis depuis plus de 12 mois (ou jamais)
            for c in qs:
                last = c.devis.order_by('-date_creation').first()
                if last is None or last.date_creation < cutoff_12m:
                    result.append({
                        'id': c.id, 'nom': str(c),
                        'last_devis': last.date_creation.isoformat() if last else None,
                        'segment': 'sans_devis',
                    })

        elif segment == 'a_recontacter':
            # Clients avec au moins un devis mais aucun signé dans les 12 derniers mois
            for c in qs:
                if not c.devis.exists():
                    continue
                signed_recent = c.devis.filter(
                    statut='accepte', date_creation__gte=cutoff_12m
                ).exists()
                if not signed_recent:
                    result.append({
                        'id': c.id, 'nom': str(c),
                        'nb_devis': c.devis.count(),
                        'segment': 'a_recontacter',
                    })

        elif segment == 'dormants':
            # Clients sans aucune activité (devis/facture) depuis 18 mois
            for c in qs:
                last_devis = c.devis.order_by('-date_creation').first()
                last_facture = c.factures.order_by('-date_emission').first()
                last_date = None
                if last_devis:
                    last_date = last_devis.date_creation
                if last_facture and (last_date is None or
                                     last_facture.date_emission > last_date):
                    last_date = last_facture.date_emission
                if last_date is None or last_date < cutoff_18m:
                    result.append({
                        'id': c.id, 'nom': str(c),
                        'last_activity': last_date.isoformat() if last_date else None,
                        'segment': 'dormants',
                    })

        return Response({'segment': segment, 'count': len(result), 'results': result})


class LeadViewSet(CompanyScopedModelViewSet):
    """Leads + historique « chatter » (journal automatique + notes manuelles).

    L'utilisateur acteur et la société viennent toujours de la requête côté
    serveur — jamais du corps envoyé par le navigateur.
    """
    # YOPSB13 — LeadSerializer expose owner_nom/owner_poste/owner_avatar
    # (SerializerMethodField sur obj.owner), client_nom (obj.client) et devis
    # (obj.devis, reverse FK) : sans select_related/prefetch_related, la
    # liste des leads exécute 1 requête PAR LIGNE pour chacune (N+1 réel,
    # capturé par core.tests.test_utils.AssertQueryBudgetMixin dans
    # apps/crm/tests/test_lead_query_budget.py).
    queryset = Lead.objects.select_related('owner', 'client').prefetch_related(
        # 'devis__lignes' — get_devis expose d.total_ttc (propriété qui somme
        # les LIGNES du devis) : sans ce prefetch imbriqué, chaque devis
        # requêtait ses lignes (N+1, ~2 requêtes/devis). String-FK cross-app.
        'devis', 'devis__lignes').all()
    serializer_class = LeadSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'prenom', 'societe', 'email', 'telephone', 'ville']
    ordering_fields = ['nom', 'date_creation', 'stage', 'score']
    ordering = ['-date_creation']

    def list(self, request, *args, **kwargs):
        # YOPSB13 — LeadSerializer.get_next_activity() et get_devis() (via
        # installation_summaries_for_devis) exécutaient chacun 1 requête PAR
        # LIGNE (N+1 réel : le nombre de requêtes grandissait avec le nombre
        # de leads — apps/crm/tests_yopsb13_lead_query_budget.py /
        # tests_perf_n1_leads.py). On précharge ici les deux cartes {lead_id
        # / devis_id: ...} en UNE SEULE requête chacune, pour TOUTE la page
        # (après pagination), et on les pose dans le contexte serializer —
        # le serializer les préfère à son fallback requête-par-ligne.
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else list(queryset)

        extra_context = {
            'next_activity_map': self._next_activity_map(objects),
            'chantier_map': self._chantier_map(objects),
            'stage_since_map': self._stage_since_map(objects),
        }
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={
                    **self.get_serializer_context(), **extra_context})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(
            objects, many=True, context={
                **self.get_serializer_context(), **extra_context})
        return Response(serializer.data)

    @staticmethod
    def _next_activity_map(leads):
        """{lead_id: Activity} — l'activité ouverte la plus proche par lead,
        en UNE requête pour tout le lot (au lieu d'une par lead)."""
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        ids = [lead.id for lead in leads]
        if not ids:
            return {}
        ct = ContentType.objects.get_for_model(Lead)
        out = {}
        acts = (Activity.objects
                .filter(content_type=ct, object_id__in=ids, done=False,
                        due_date__isnull=False)
                .select_related('activity_type')
                .order_by('object_id', 'due_date'))
        for act in acts:
            # order_by garantit due_date croissant par lead — on ne garde
            # que la PREMIÈRE (la plus proche) rencontrée par lead.
            out.setdefault(act.object_id, act)
        return out

    @staticmethod
    def _chantier_map(leads):
        """{devis_id: chantier-summary} pour TOUS les devis de TOUS les leads
        du lot, en UNE requête (au lieu d'une par lead via get_devis)."""
        from apps.installations.selectors import (
            installation_summaries_for_devis,
        )
        devis_ids = [d.id for lead in leads for d in lead.devis.all()]
        if not devis_ids:
            return {}
        from apps.ventes.models import Devis
        rows = Devis.objects.filter(id__in=devis_ids)
        return installation_summaries_for_devis(rows)

    @staticmethod
    def _stage_since_map(leads):
        """{lead_id: datetime du dernier changement d'étape} pour tout le lot
        en UNE requête (au lieu d'une par lead via get_stage_since_days)."""
        from .models import LeadActivity
        ids = [lead.id for lead in leads]
        if not ids:
            return {}
        out = {}
        rows = (LeadActivity.objects
                .filter(lead_id__in=ids,
                        kind=LeadActivity.Kind.MODIFICATION, field='stage')
                .order_by('lead_id', '-created_at')
                .values('lead_id', 'created_at'))
        for r in rows:
            # -created_at → on garde la PREMIÈRE (la plus récente) par lead.
            out.setdefault(r['lead_id'], r['created_at'])
        return out

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
                # NTCRM1 — territoire consulté en premier, repli XSAL11.
                default = default_responsable_for(
                    user.company, lead_attrs=serializer.validated_data)
                if default is not None:
                    extra['owner'] = default
        serializer.save(**extra)
        activity.log_creation(serializer.instance, user)
        from .services import sync_relance_activity, recompute_lead_score
        sync_relance_activity(serializer.instance, user)
        recompute_lead_score(serializer.instance)

    def perform_update(self, serializer):
        # Snapshot avant écriture pour journaliser ancien → nouveau.
        old = Lead.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        new_lead = serializer.instance
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern archived_by.
        new_lead.updated_by = self.request.user
        new_lead.save(update_fields=['updated_by'])
        activity.log_changes(old, new_lead, self.request.user)
        from .services import (
            _emit_stage_changed, maybe_set_first_contacted_at,
            recompute_lead_score, sync_relance_activity,
        )
        sync_relance_activity(new_lead, self.request.user)
        # FG28 — Pose first_contacted_at à la première sortie de l'étape NEW.
        maybe_set_first_contacted_at(old, new_lead)
        # QJ6 — Recalcule et persiste le score après chaque mise à jour.
        recompute_lead_score(new_lead)
        # NTCRM12 — édition manuelle de l'étape depuis l'écran lead.
        _emit_stage_changed(new_lead, old.stage, new_lead.stage, self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique', 'duplicates',
                                          'check_duplicates', 'doublons',
                                          'export_xlsx', 'relances',
                                          'roi_sources', 'sla_breach',
                                          'client_match', 'points_contact',
                                          'scan_carte']:
            return [IsAnyRole()]
        elif self.action in ('merge', 'convertir_client'):
            # VX199 — fusion / conversion de lead : permission ERP FINE
            # (crm_modifier), pas le grossier IsResponsableOrAdmin. get_permissions
            # PRIME sur le permission_classes de l'@action, donc la garde fine
            # doit être ICI.
            return [HasPermissionOrLegacy('crm_modifier')()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'devis_auto', 'archiver', 'restaurer',
            'whatsapp_devis', 'bulk', 'log_interaction',
            'appliquer_plan',
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
        from apps.ventes.selectors import devis_for_lead
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
        devis_list = devis_for_lead(lead, ids)
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
        # U4 — partager un devis au client le marque « envoyé » et fait avancer
        # le funnel (→ QUOTE_SENT). On passe par le service ventes (jamais une
        # écriture brute de statut) pour préserver la sémantique (règle #4) + le
        # chatter du devis ; l'avance du lead se fait via l'événement domaine
        # ``devis_sent``, comme ``devis_accepted``. Idempotent et ne dégrade
        # jamais un devis déjà accepté/refusé/envoyé.
        from apps.ventes.services import mark_devis_sent
        for d in devis_list:
            mark_devis_sent(devis=d, user=request.user)
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
        """Suppression RÉVERSIBLE (admin) — VX96 : soft-delete + undo 30 min.

        Le lead n'est plus détruit : ``soft_delete`` le masque des querysets par
        défaut (``Lead.objects``) et journalise une entrée de corbeille
        (``DeletionRecord``) restaurable pendant 30 min via ``/core/corbeille/``.
        Toujours bloqué si des devis sont liés (on n'orpheline jamais de pièces
        financières). L'événement est journalisé (qui/quand) côté serveur ; la
        réponse porte l'``corbeille_id`` pour l'undo-toast du front."""
        import logging
        lead = self.get_object()
        if lead.devis.exists():
            return Response(
                {'detail': "Ce lead a des devis liés. Supprimer le lead "
                           "détacherait ces pièces — archivez-le plutôt."},
                status=status.HTTP_409_CONFLICT,
            )
        logging.getLogger('crm.audit').warning(
            'SOFT DELETE lead id=%s "%s" par user=%s (company=%s)',
            lead.id, lead, getattr(request.user, 'username', '?'),
            getattr(lead, 'company_id', None),
        )
        lead.soft_delete(request.user)
        # Entrée de corbeille tout juste créée (undo dans la fenêtre de 30 min).
        from django.contrib.contenttypes.models import ContentType
        from core.models import DeletionRecord
        ct = ContentType.objects.get_for_model(Lead)
        record = (DeletionRecord.objects
                  .filter(content_type=ct, object_id=lead.pk,
                          restored_at__isnull=True)
                  .order_by('-id').first())
        return Response(
            {'corbeille_id': getattr(record, 'id', None), 'id': lead.id},
            status=status.HTTP_200_OK,
        )

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

    @action(detail=False, methods=['post'], url_path='scan-carte',
            permission_classes=[IsAnyRole],
            parser_classes=[MultiPartParser],
            throttle_classes=[ScopedRateThrottle])
    def scan_carte(self, request):
        """XSAL8 — Scan de carte de visite (photo) → pré-remplissage du modal
        « Lead express ». NE CRÉE JAMAIS de lead — renvoie les champs
        reconnus + un pré-check de doublons ; l'utilisateur valide avant
        toute création. Sans clé OCR configurée : 503 douce, aucun appel
        réseau. Aucune image persistée au-delà du traitement (en mémoire)."""
        from .services import CarteVisiteScanUnavailable, scan_carte_visite

        upload = request.FILES.get('file')
        if not upload:
            return Response(
                {'detail': 'Aucune image fournie.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            content = upload.read()
        finally:
            upload.close()

        try:
            result = scan_carte_visite(
                company=request.user.company, file_bytes=content)
        except CarteVisiteScanUnavailable as exc:
            message = str(exc)
            unavailable = 'configuré' in message
            return Response(
                {'detail': message},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE if unavailable
                        else status.HTTP_400_BAD_REQUEST))
        return Response(result)

    scan_carte.throttle_scope = 'crm_ocr_scan'

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
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
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

    @action(detail=True, methods=['post'], url_path='appliquer-plan',
            permission_classes=[IsResponsableOrAdmin])
    def appliquer_plan(self, request, pk=None):
        """ZSAL2 — applique un PlanActivite (body {plan_id}) au lead : crée
        une activité par étape, échéance = aujourd'hui + délai. Idempotent :
        ré-appliquer le même plan ne duplique rien."""
        lead = self.get_object()
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({'plan_id': 'Requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        plan = PlanActivite.objects.filter(
            id=plan_id, company=request.user.company).first()
        if plan is None:
            return Response({'detail': 'Plan introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        from .services import appliquer_plan_activite
        try:
            activites = appliquer_plan_activite(
                lead=lead, plan=plan, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.records.serializers import ActivitySerializer
        return Response(
            ActivitySerializer(activites, many=True).data,
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='convertir-client',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def convertir_client(self, request, pk=None):
        """ZSAL4 — assistant de conversion EXPLICITE lead → client (body
        {mode: nouveau|lier|aucun, client_id?}). Journalisé dans le chatter."""
        lead = self.get_object()
        mode = (request.data.get('mode') or '').strip()
        client_id = request.data.get('client_id')
        from .services import convertir_lead_en_client
        try:
            client = convertir_lead_en_client(
                lead=lead, user=request.user, mode=mode, client_id=client_id)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'mode': mode,
            'client': ClientSerializer(client).data if client else None,
        })

    @action(detail=True, methods=['get'], url_path='points-contact',
            permission_classes=[IsAnyRole])
    def points_contact(self, request, pk=None):
        """FG204 — journal multi-touch ordonné + résumé d'attribution du lead
        (first-touch vs last-touch). get_object() borne déjà à la société."""
        from .selectors import lead_touchpoints_attribution
        lead = self.get_object()
        summary = lead_touchpoints_attribution(
            lead, company=request.user.company)
        return Response({
            'lead_id': summary['lead_id'],
            'count': summary['count'],
            'first_touch': summary['first_touch'],
            'last_touch': summary['last_touch'],
            'cout_total': summary['cout_total'],
            'timeline': PointContactSerializer(
                summary['timeline'], many=True).data,
        })

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

    # ── FG31 — File de relance du jour ───────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='relances',
            permission_classes=[IsAnyRole])
    def relances(self, request):
        """File de relance consolidée.

        scope= overdue (en retard) | today (aujourd'hui) | week (cette semaine)
        Portée de visibilité de l'utilisateur respectée (scope_queryset).

        VX83 — la logique de sélection vit désormais dans
        ``crm.selectors.relances_du_jour`` (consommée aussi par « Ma file »
        cross-module) ; cette vue ne fait que la présenter (convention
        selectors — jamais deux implémentations divergentes).
        """
        from .selectors import relances_du_jour
        scope = request.query_params.get('scope', 'today')
        company = request.user.company if request.user.company_id else None
        qs = relances_du_jour(company, request.user, scope=scope)
        serializer = LeadSerializer(qs, many=True, context={'request': request})
        return Response({'count': qs.count(), 'results': serializer.data})

    # ── FG34 — ROI par source / campagne ────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='roi-sources',
            permission_classes=[IsAnyRole])
    def roi_sources(self, request):
        """Agrégation ROI par canal et par campagne UTM.

        Renvoie pour chaque groupe :
          canal, utm_campaign (optionnel), lead_count, signed_count,
          win_rate (%), signed_value_ttc (somme des devis acceptés TTC).
        Filtres : ?from=YYYY-MM-DD &to=YYYY-MM-DD &canal=<key>
        """
        import datetime

        qs = self.get_queryset().filter(is_archived=False)

        # Filtres date optionnels
        from_ = request.query_params.get('from')
        to_ = request.query_params.get('to')
        if from_:
            try:
                qs = qs.filter(date_creation__date__gte=datetime.date.fromisoformat(from_))
            except ValueError:
                pass
        if to_:
            try:
                qs = qs.filter(date_creation__date__lte=datetime.date.fromisoformat(to_))
            except ValueError:
                pass
        canal_filter = request.query_params.get('canal')
        if canal_filter:
            qs = qs.filter(canal=canal_filter)

        # Grouper par canal puis par campagne
        result = []
        for canal_key in (qs.values_list('canal', flat=True)
                          .order_by('canal').distinct()):
            canal_qs = qs.filter(canal=canal_key)
            # Par campagne UTM (None = pas de campagne)
            campaigns = (canal_qs.values_list('utm_campaign', flat=True)
                         .order_by('utm_campaign').distinct())
            for campaign in campaigns:
                grp = canal_qs.filter(utm_campaign=campaign)
                lead_count = grp.count()
                signed = grp.filter(stage='SIGNED')
                signed_count = signed.count()
                # Somme des devis TTC des leads signés
                signed_value = 0
                for lead in signed.prefetch_related('devis'):
                    for d in lead.devis.filter(statut='accepte'):
                        try:
                            signed_value += float(d.total_ttc)
                        except Exception:
                            pass
                result.append({
                    'canal': canal_key,
                    'utm_campaign': campaign,
                    'lead_count': lead_count,
                    'signed_count': signed_count,
                    'win_rate': round(signed_count / lead_count * 100, 1)
                              if lead_count else 0,
                              'signed_value_ttc': round(signed_value, 2),
                              })
        return Response(result)

    # ── FG38 — Correspondance Lead↔Client (doublon retour client) ────────────
    @action(detail=True, methods=['get'], url_path='client-match',
            permission_classes=[IsAnyRole])
    def client_match(self, request, pk=None):
        """Cherche si le lead correspond à un Client existant de la société.

        Normalise téléphone et email, puis cherche dans Client (pas dans Lead).
        Retourne [] si aucune correspondance ou {id, nom, nb_devis, nb_chantiers}
        pour chaque client correspondant.
        """
        lead = self.get_object()
        company = request.user.company
        from .models import Client as ClientModel
        from apps.ventes.utils.phone import normalize_ma_phone

        conditions = []
        phone_norm = normalize_ma_phone(lead.telephone or '') if lead.telephone else None
        email_norm = (lead.email or '').strip().lower() or None
        if phone_norm:
            conditions.append(
                Lead._meta.model.objects.none()  # placeholder — on fait direct
            )

        # Recherche directe sur Client
        client_qs = ClientModel.objects.filter(company=company)
        found = []
        pks_seen = set()
        if phone_norm:
            for c in client_qs:
                norm = normalize_ma_phone(c.telephone or '') if c.telephone else None
                if norm and norm == phone_norm and c.pk not in pks_seen:
                    found.append(c)
                    pks_seen.add(c.pk)
        if email_norm:
            for c in client_qs.filter(email__iexact=email_norm):
                if c.pk not in pks_seen:
                    found.append(c)
                    pks_seen.add(c.pk)

        result = []
        for c in found:
            result.append({
                'id': c.id,
                'nom': f"{c.nom} {c.prenom or ''}".strip(),
                'email': c.email,
                'telephone': c.telephone,
                'nb_devis': c.devis.count(),
                'nb_chantiers': c.installations.count() if hasattr(c, 'installations') else 0,
            })
        return Response(result)

    # ── FG28 — Filtre SLA non contactés ──────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='sla-breach',
            permission_classes=[IsAnyRole])
    def sla_breach(self, request):
        """Leads NEW non contactés depuis plus de lead_sla_hours (filtre SLA).

        Retourne les leads dont first_contacted_at est NULL, stage=NEW,
        créés il y a plus de lead_sla_hours heures (selon le profil société).
        """
        from django.utils import timezone
        import datetime
        from .services import lead_sla_hours as get_sla_hours
        sla = get_sla_hours(request.user.company)
        if sla == 0:
            return Response({'sla_hours': 0, 'count': 0, 'results': []})
        cutoff = timezone.now() - datetime.timedelta(hours=sla)
        qs = self.get_queryset().filter(
            is_archived=False,
            stage='NEW',
            first_contacted_at__isnull=True,
            date_creation__lte=cutoff,
        ).order_by('date_creation')
        serializer = LeadSerializer(qs, many=True, context={'request': request})
        return Response({
            'sla_hours': sla,
            'count': qs.count(),
            'results': serializer.data,
        })

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin],
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def noter(self, request, pk=None):
        """Note manuelle (appel, commentaire…) — auteur pris de la requête.

        FG28 : si le lead est encore en NEW et n'a jamais été contacté, cette
        note constitue la première prise de contact → first_contacted_at est posé.

        VX111 — accepte en plus un fichier multipart optionnel (`file`, ex.
        photo prise depuis mobile pendant une visite) : réutilise le magasin
        `records.Attachment` EXISTANT (déjà whitelisté ('crm','lead')) — la
        pièce jointe créée cible directement le LEAD (visible aussi dans
        AttachmentsPanel) et est liée à cette note. Jamais un second magasin.
        """
        lead = self.get_object()
        body = (request.data.get('body') or '').strip()
        file = request.FILES.get('file')
        if not body and not file:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        attachment = None
        if file:
            from apps.records.storage import store_attachment
            from apps.records.models import Attachment
            from django.contrib.contenttypes.models import ContentType
            meta, err = store_attachment(file, company=request.user.company)
            if err:
                return Response({'file': err}, status=status.HTTP_400_BAD_REQUEST)
            ct = ContentType.objects.get(app_label='crm', model='lead')
            attachment = Attachment.objects.create(
                company=request.user.company, content_type=ct, object_id=lead.id,
                uploaded_by=request.user, **meta)
        act = activity.log_note(lead, request.user, body or '📎 Pièce jointe')
        if attachment:
            act.attachment = attachment
            act.save(update_fields=['attachment'])
        # FG28 — première note = premier contact (même sans changer d'étape)
        if lead.stage == 'NEW' and lead.first_contacted_at is None:
            from django.utils import timezone
            lead.first_contacted_at = timezone.now()
            lead.save(update_fields=['first_contacted_at'])
        return Response(LeadActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    # FG30 — Interaction typée (appel/e-mail) dans le chatter ─────────────────
    @action(detail=True, methods=['post'], url_path='log-interaction',
            permission_classes=[IsResponsableOrAdmin])
    def log_interaction(self, request, pk=None):
        """Enregistre un appel ou un e-mail dans le chatter du lead.

        Corps requis :
          - kind : 'appel' | 'email'
          - body : texte libre (résumé de l'échange), facultatif
          - outcome : parmi les choix LeadActivity.OUTCOMES, facultatif

        L'auteur et la société sont toujours pris côté serveur.
        """
        from .models import LeadActivity
        lead = self.get_object()
        kind = (request.data.get('kind') or '').strip()
        valid_kinds = {LeadActivity.Kind.APPEL, LeadActivity.Kind.EMAIL}
        if kind not in valid_kinds:
            return Response(
                {'kind': f"Valeur invalide. Choisir parmi : {', '.join(valid_kinds)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = (request.data.get('body') or '').strip()
        outcome = (request.data.get('outcome') or '').strip()
        valid_outcomes = {k for k, _ in LeadActivity.OUTCOMES}
        if outcome and outcome not in valid_outcomes:
            return Response(
                {'outcome': f"Valeur invalide. Choisir parmi : {', '.join(valid_outcomes)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        act = LeadActivity.objects.create(
            lead=lead,
            company=lead.company,
            kind=kind,
            body=body or None,
            outcome=outcome,
            user=request.user,
        )
        # FG28 — tout contact direct = première prise de contact
        if lead.stage == 'NEW' and lead.first_contacted_at is None:
            from django.utils import timezone
            lead.first_contacted_at = timezone.now()
            lead.save(update_fields=['first_contacted_at'])
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


class LeadTagViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """Étiquettes de lead gérées (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L780) : une étiquette référencée par des leads
    ne se supprime pas — l'admin l'archive plutôt (l'historique est préservé).
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : LeadTag n'est pas dans TRACKED_MODELS."""
    queryset = LeadTag.objects.all()
    serializer_class = LeadTagSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy_guard_message(self, tag):
        if _tag_en_usage(tag.company, tag.nom) > 0:
            return ("Cette étiquette est utilisée par des leads — "
                    "archivez-la plutôt que de la supprimer.")
        return None


class MotifPerteViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """Motifs de perte gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L779) : un motif utilisé par des leads ne se
    supprime pas — l'admin l'archive plutôt (comme pour les canaux).
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : MotifPerte n'est pas dans TRACKED_MODELS."""
    queryset = MotifPerte.objects.all()
    serializer_class = MotifPerteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy_guard_message(self, motif):
        if _motif_en_usage(motif.company, motif.nom) > 0:
            return ("Ce motif est utilisé par des leads — archivez-le "
                    "plutôt que de le supprimer.")
        return None


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


class CanalViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """Canaux / sources de lead gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fous : un canal protégé ('site_web') ne se supprime
    pas, et aucun canal utilisé par des leads ne se supprime.
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : Canal n'est pas dans TRACKED_MODELS."""
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

    def destroy_guard_message(self, canal):
        if canal.protege:
            return ("Ce canal est protégé (utilisé par le site web) et "
                    "ne peut pas être supprimé.")
        if Lead.objects.filter(company=canal.company, canal=canal.cle).exists():
            return ("Ce canal est utilisé par des leads — archivez-le "
                    "plutôt que de le supprimer.")
        return None


class ParrainageViewSet(CompanyScopedModelViewSet):
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


# ── QX16 — Surface de rejeu des payloads leads site web ──────────────────────

class WebsiteLeadPayloadViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """QX16 — « Jamais perdre un lead » (webhooks.py) devient opérationnel :
    liste des payloads bruts, avec un filtre par défaut sur ceux qui méritent
    une action (mapping en erreur OU sans lead rattaché). ``?all=1`` renvoie
    la liste complète (comportement admin). LECTURE SEULE — la seule écriture
    possible est l'action ``replay``, qui rejoue EXACTEMENT le même mapping
    que le webhook (jamais une seconde implémentation)."""
    queryset = WebsiteLeadPayload.objects.select_related('lead').all()
    serializer_class = WebsiteLeadPayloadSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('all'):
            return qs
        # Défaut : ce qui mérite une action — erreur de mapping OU jamais
        # rattaché à un lead (payload traité mais orphelin, ex. ping
        # d'engagement QW7 sans lead correspondant — n'est pas une PERTE,
        # mais reste utile à voir).
        from django.db.models import Q
        return qs.filter(Q(error__gt='') | Q(lead__isnull=True))

    @action(detail=True, methods=['post'], url_path='replay',
            permission_classes=[IsResponsableOrAdmin])
    def replay(self, request, pk=None):
        """QX16 — rejoue ce payload à travers le mapping webhook standard.

        Renvoie 200 avec le lead résultant en cas de succès, 422 si le rejeu
        échoue encore (le payload reste rejouable — jamais supprimé)."""
        from .webhooks import replay_website_lead_payload

        payload = self.get_object()
        ok, detail, lead = replay_website_lead_payload(payload)
        payload.refresh_from_db()
        data = WebsiteLeadPayloadSerializer(payload).data
        if not ok:
            return Response({'detail': detail, 'payload': data}, status=422)
        return Response({'detail': detail, 'payload': data}, status=200)


# ── DC12 — Profil site/énergie réutilisable par client ───────────────────────

class SiteProfileViewSet(CompanyScopedModelViewSet):
    """DC12 — profil site/énergie réutilisable, attaché au client.

    Saisi une fois par client, le générateur de devis le pré-remplit ensuite
    (y compris pour les devis sans lead). Société ET créateur forcés côté
    serveur (jamais lus du corps de requête). Lecture tout rôle, écriture
    responsable/admin. Filtrable par ?client=<id>."""
    queryset = SiteProfile.objects.select_related('client').all()
    serializer_class = SiteProfileSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )


# ── ZSAL2 — Plans d'activité ──────────────────────────────────────────────────

class PlanActiviteViewSet(CompanyScopedModelViewSet):
    """Plans d'activité (checklists de tâches commerciales) : lecture tout
    rôle, écriture responsable/admin. Société forcée côté serveur."""
    queryset = PlanActivite.objects.prefetch_related(
        'etapes', 'etapes__activity_type').all()
    serializer_class = PlanActiviteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class EquipeCommercialeViewSet(CompanyScopedModelViewSet):
    """ZSAL3 — Équipes commerciales (admin CRUD, Paramètres → CRM). Lecture
    tout rôle (le dashboard « Mes équipes » y référence des noms), écriture
    responsable/admin. Société forcée côté serveur (TenantMixin)."""
    queryset = EquipeCommerciale.objects.prefetch_related('membres').all()
    serializer_class = EquipeCommercialeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


# ── FG36 — Modèles de messages WhatsApp/SMS ───────────────────────────────────

class MessageTemplateViewSet(CompanyScopedModelViewSet):
    """Modèles de messages CRM (WhatsApp/SMS). Lecture tout rôle, écriture admin.

    La société est toujours posée côté serveur (TenantMixin). Un modèle archivé
    reste accessible en détail mais n'apparaît plus dans la liste par défaut
    (?archived=true pour les voir).
    """
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'corps']
    ordering_fields = ['nom', 'date_creation']
    ordering = ['nom']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            archived = self.request.query_params.get('archived')
            if archived not in ('1', 'true'):
                qs = qs.filter(archived=False)
        return qs

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'render_template']:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    @action(detail=True, methods=['post'], url_path='render',
            permission_classes=[IsAnyRole])
    def render_template(self, request, pk=None):
        """Applique les variables {prenom}/{ville}/{lien}/{lien_rdv} et
        retourne le texte.

        Corps : {prenom, ville, lien, lead_id} (tous optionnels). XSAL17 —
        ``lead_id`` (scopé société) résout {lien_rdv} en un lien de
        réservation réel ; sans lead_id (ou template sans le placeholder),
        aucun BookingLink n'est créé (no-op — le placeholder disparaît
        simplement s'il est présent sans lead_id fourni).
        """
        tmpl = self.get_object()
        prenom = request.data.get('prenom', '')
        ville = request.data.get('ville', '')
        lien = request.data.get('lien', '')
        lien_rdv = ''
        lead_id = request.data.get('lead_id')
        if lead_id and '{lien_rdv}' in (tmpl.corps or ''):
            from .services import public_booking_url
            lead = Lead.objects.filter(
                pk=lead_id, company=request.user.company).first()
            if lead is not None:
                try:
                    lien_rdv = public_booking_url(lead, request=request)
                except Exception:  # noqa: BLE001 — jamais bloquer l'aperçu
                    lien_rdv = ''
        return Response({'texte': tmpl.render(
            prenom=prenom, ville=ville, lien=lien, lien_rdv=lien_rdv)})


# ── QJ20 — Rendez-vous (visites commerciales/techniques) ──────────────────────

class AppointmentViewSet(CompanyScopedModelViewSet):
    """QJ20 — Rendez-vous planifiés sur les leads (visites commerciales/techniques).

    Lecture tout rôle, écriture responsable/admin.
    Toujours scopé par société (TenantMixin). La société est posée côté serveur
    depuis l'utilisateur actif (jamais lue du corps de requête — multi-tenant).
    Filtre ?lead=<id> pour n'avoir que les RDV d'un lead donné.
    """
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.select_related('lead', 'company').all()
    filterset_fields = ['lead', 'statut']
    ordering_fields = ['scheduled_at', 'date_creation']
    ordering = ['scheduled_at']

    def get_permissions(self):
        # VX245(a) — `ics` (téléchargement, lecture seule) rejoint les
        # READ_ACTIONS : tout rôle peut télécharger le `.ics` d'un RDV qu'il
        # peut déjà VOIR (queryset scopé société, jamais un nouveau droit).
        if self.action in READ_ACTIONS or self.action == 'ics':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Company et created_by toujours posés côté serveur."""
        from .services import book_appointment
        lead = serializer.validated_data['lead']
        scheduled_at = serializer.validated_data['scheduled_at']
        notes = serializer.validated_data.get('notes') or ''
        appt = book_appointment(
            lead=lead,
            scheduled_at=scheduled_at,
            notes=notes,
            user=self.request.user,
        )
        # The serializer's save() would create a duplicate — we bypass it here
        # and return the already-created appointment via the serializer for the
        # response. Patch self so the serializer picks up the instance.
        serializer.instance = appt

    @action(detail=True, methods=['get'], url_path='ics')
    def ics(self, request, pk=None):
        """VX245(a) — `.ics` d'ÉVÉNEMENT UNIQUE pour CE rendez-vous (RFC 5545,
        1 VEVENT horodaté) — distinct du flux d'ABONNEMENT complet de
        `reporting.calendar.calendar_ics`. Réutilise la MÊME fonction pure
        `build_ics` (extraite pour être réutilisable, jamais une 2ᵉ
        implémentation ICS).

        Scopé société via `get_object()` (`CompanyScopedModelViewSet` — le
        RDV d'une autre société renvoie 404, jamais fabriqué)."""
        appt = self.get_object()
        from datetime import timedelta

        from django.http import HttpResponse

        from apps.reporting.calendar import build_ics

        lead_nom = f'{appt.lead.nom} {appt.lead.prenom or ""}'.strip()
        titre = f'RDV — {lead_nom}' if lead_nom else f'RDV #{appt.pk}'
        events = [{
            'uid': f'appointment-{appt.pk}',
            'start_dt': appt.scheduled_at,
            'end_dt': appt.scheduled_at + timedelta(hours=1),
            'summary': titre,
            'description': appt.notes or '',
        }]
        body = build_ics(request.user, events, calname=titre)
        resp = HttpResponse(body, content_type='text/calendar; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="rdv-{appt.pk}.ics"'
        return resp

    @action(detail=True, methods=['post'], url_path='confirmer-whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_whatsapp(self, request, pk=None):
        """VX245(b) — aperçu du message de CONFIRMATION WhatsApp post-RDV
        (date/heure + lien `.ics`). N'ENVOIE RIEN : le commercial ouvre
        WhatsApp lui-même après avoir vérifié l'aperçu (même convention que
        `LeadViewSet.whatsapp_devis`)."""
        appt = self.get_object()
        from .services import build_appointment_confirmation_whatsapp

        message, wa_url, ics_url = build_appointment_confirmation_whatsapp(
            request, appt)
        if wa_url is None:
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'message': message, 'wa_url': wa_url, 'ics_url': ics_url,
        })


# ── FG39 — ObjectifCommercial / KPI Target ────────────────────────────────────

class ObjectifCommercialViewSet(CompanyScopedModelViewSet):
    """CRUD objectifs commerciaux + endpoint d'atteinte (réalisé vs cible).

    Routes :
      GET/POST  /crm/objectifs/
      GET/PATCH /crm/objectifs/{id}/
      DELETE    /crm/objectifs/{id}/
      GET       /crm/objectifs/attainment/?year=&metric=&period_type=&owner=
      GET       /crm/objectifs/{id}/attainment/
    """
    queryset = ObjectifCommercial.objects.all()
    serializer_class = ObjectifCommercialSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related('owner')
        # Filtres optionnels.
        metric = self.request.query_params.get('metric')
        if metric:
            qs = qs.filter(metric=metric)
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(period_year=year)
        period_type = self.request.query_params.get('period_type')
        if period_type:
            qs = qs.filter(period_type=period_type)
        owner = self.request.query_params.get('owner')
        if owner == 'null':
            qs = qs.filter(owner__isnull=True)
        elif owner:
            qs = qs.filter(owner_id=owner)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['attainment', 'attainment_list']:
            return [IsAnyRole()]
        return [IsAdminRole()]

    @action(detail=True, methods=['get'], url_path='attainment',
            permission_classes=[IsAnyRole])
    def attainment(self, request, pk=None):
        """Réalisé vs cible pour un objectif unique."""
        from .selectors import compute_attainment
        obj = self.get_object()
        data = compute_attainment(obj)
        payload = {
            'id': obj.pk,
            'metric': obj.metric,
            'metric_display': obj.get_metric_display(),
            'period_type': obj.period_type,
            'period_year': obj.period_year,
            'period_month': obj.period_month,
            'period_quarter': obj.period_quarter,
            'cible': obj.cible,
            'owner': obj.owner_id,
            'owner_nom': getattr(obj.owner, 'username', None),
            **data,
        }
        s = ObjectifAttainmentSerializer(payload)
        return Response(s.data)

    @action(detail=False, methods=['get'], url_path='attainment',
            permission_classes=[IsAnyRole])
    def attainment_list(self, request):
        """Réalisé vs cible pour tous les objectifs du filtre courant."""
        from .selectors import compute_attainment
        qs = self.get_queryset()
        result = []
        for obj in qs:
            data = compute_attainment(obj)
            result.append({
                'id': obj.pk,
                'metric': obj.metric,
                'metric_display': obj.get_metric_display(),
                'period_type': obj.period_type,
                'period_year': obj.period_year,
                'period_month': obj.period_month,
                'period_quarter': obj.period_quarter,
                'cible': obj.cible,
                'owner': obj.owner_id,
                'owner_nom': getattr(obj.owner, 'username', None),
                **data,
            })
        s = ObjectifAttainmentSerializer(result, many=True)
        return Response(s.data)


# ── FG242 — Suivi des concurrents sur deals perdus ────────────────────────────

class ConcurrentPerteViewSet(CompanyScopedModelViewSet):
    """FG242 — concurrent gagnant + prix saisis sur un lead perdu.

    Intelligence concurrentielle : sur un lead PERDU (drapeau ``Lead.perdu`` —
    « Perdu » est un lost-flag, pas une étape STAGES.py), on capture qui nous a
    battu et à quel prix.

    Routes :
      GET/POST  /crm/concurrents-perte/        (filtre ?lead=<id>)
      GET/PATCH /crm/concurrents-perte/{id}/
      DELETE    /crm/concurrents-perte/{id}/

    Lecture tout rôle, écriture responsable/admin. Toujours scopé par société
    (TenantMixin) : la société et ``saisi_par`` sont posés côté serveur depuis
    l'utilisateur actif — jamais lus du corps de requête (multi-tenant).
    """
    serializer_class = ConcurrentPerteSerializer
    queryset = ConcurrentPerte.objects.select_related(
        'lead', 'company', 'saisi_par').all()
    filterset_fields = ['lead']
    ordering_fields = ['saisi_le', 'concurrent_prix']
    ordering = ['-saisi_le']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Société et saisi_par toujours posés côté serveur ; trace chatter."""
        obj = serializer.save(
            company=self.request.user.company,
            saisi_par=self.request.user,
        )
        # Trace l'info dans le chatter du lead (best-effort, ne casse jamais
        # la création si le log échoue).
        try:
            from . import activity
            prix = ''
            if obj.concurrent_prix is not None:
                prix = f' à {obj.concurrent_prix} {obj.devise or ""}'.rstrip()
            activity.log_note(
                obj.lead, self.request.user,
                f"Concurrent gagnant saisi : {obj.concurrent_nom}{prix}.",
            )
        except Exception:
            pass


class PointContactViewSet(CompanyScopedModelViewSet):
    """FG204 — journal multi-touch des points de contact d'un lead.

    Au-delà du first-touch (``Lead.canal``), on consigne chaque point de contact
    du parcours (Meta → site → WhatsApp → signature) pour une attribution
    multi-touch.

    Routes :
      GET/POST  /crm/points-contact/                    (filtre ?lead=<id>)
      GET/PATCH /crm/points-contact/{id}/
      DELETE    /crm/points-contact/{id}/
      GET       /crm/points-contact/attribution/?lead=  (résumé first/last-touch)

    Lecture tout rôle, écriture responsable/admin. Toujours scopé par société
    (TenantMixin) : la société et ``saisi_par`` sont posés côté serveur depuis
    l'utilisateur actif — jamais lus du corps de requête (multi-tenant).
    """
    serializer_class = PointContactSerializer
    queryset = PointContact.objects.select_related(
        'lead', 'company', 'saisi_par').all()
    filterset_fields = ['lead', 'canal']
    ordering_fields = ['ordre', 'date_contact', 'saisi_le', 'cout']
    ordering = ['ordre', 'date_contact', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'attribution':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Société et saisi_par toujours posés côté serveur ; date par défaut
        et ordre auto-incrémenté quand non fourni ; trace chatter."""
        from django.utils import timezone
        from django.db.models import Max
        lead = serializer.validated_data.get('lead')
        # date_contact par défaut : maintenant (le journal pose l'horodatage).
        date_contact = serializer.validated_data.get('date_contact')
        save_kwargs = {
            'company': self.request.user.company,
            'saisi_par': self.request.user,
        }
        if date_contact is None:
            save_kwargs['date_contact'] = timezone.now()
        # Ordre auto : si le client n'a pas posé d'ordre (>0), prend le max+1 du
        # journal de ce lead (chaque point de contact suit le précédent).
        ordre = serializer.validated_data.get('ordre') or 0
        if ordre == 0 and lead is not None:
            current_max = (
                PointContact.objects.filter(
                    company=self.request.user.company, lead=lead)
                .aggregate(m=Max('ordre'))['m'] or 0
            )
            save_kwargs['ordre'] = current_max + 1
        obj = serializer.save(**save_kwargs)
        # Trace dans le chatter du lead (best-effort, ne casse jamais la création).
        try:
            from . import activity
            activity.log_note(
                obj.lead, self.request.user,
                f"Point de contact ajouté : {obj.get_canal_display()}"
                + (f" ({obj.source})" if obj.source else "")
                + ".",
            )
        except Exception:
            pass

    @action(detail=False, methods=['get'], url_path='attribution',
            permission_classes=[IsAnyRole])
    def attribution(self, request):
        """Résumé d'attribution multi-touch d'un lead : timeline ordonnée +
        first-touch vs last-touch. Requiert ``?lead=<id>`` (borné société)."""
        from .selectors import lead_touchpoints_attribution
        lead_id = request.query_params.get('lead')
        if not lead_id:
            return Response(
                {'detail': 'Paramètre ?lead=<id> requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        lead = Lead.objects.filter(
            pk=lead_id, company=request.user.company).first()
        if lead is None:
            return Response(
                {'detail': 'Lead inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        summary = lead_touchpoints_attribution(
            lead, company=request.user.company)
        return Response({
            'lead_id': summary['lead_id'],
            'count': summary['count'],
            'first_touch': summary['first_touch'],
            'last_touch': summary['last_touch'],
            'cout_total': summary['cout_total'],
            'timeline': PointContactSerializer(
                summary['timeline'], many=True).data,
        })


# ── NTCRM4 — Catégories de forecast ──────────────────────────────────────────

class ForecastEntryViewSet(CompanyScopedModelViewSet):
    """CRUD des catégorisations forecast (commit/best-case/pipeline/omis).

    Routes :
      GET/POST  /crm/forecast-entries/?owner=&categorie=&periode=
      GET/PATCH /crm/forecast-entries/{id}/
    La réponse liste inclut ``totaux_par_categorie`` (somme des montants
    effectifs des lignes filtrées, par catégorie)."""
    queryset = ForecastEntry.objects.select_related('lead', 'lead__owner')
    serializer_class = ForecastEntrySerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        owner = self.request.query_params.get('owner')
        if owner:
            qs = qs.filter(lead__owner_id=owner)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        periode = self.request.query_params.get('periode')  # 'YYYY-MM'
        if periode and '-' in periode:
            year, month = periode.split('-', 1)
            try:
                qs = qs.filter(
                    lead__date_cloture_prevue__year=int(year),
                    lead__date_cloture_prevue__month=int(month))
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            mis_a_jour_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(mis_a_jour_par=self.request.user)

    def list(self, request, *args, **kwargs):
        from decimal import Decimal
        response = super().list(request, *args, **kwargs)
        totaux = {}
        for entry in self.filter_queryset(self.get_queryset()):
            totaux[entry.categorie] = (
                totaux.get(entry.categorie, Decimal('0'))
                + (entry.montant_effectif or Decimal('0')))
        if isinstance(response.data, dict) and 'results' in response.data:
            response.data['totaux_par_categorie'] = totaux
        else:
            response.data = {
                'results': response.data, 'totaux_par_categorie': totaux}
        return response


@api_view(['GET'])
@permission_classes([IsAnyRole])
def forecast_rollup_view(request):
    """NTCRM5 — Roll-up hiérarchique du forecast : ``?periode=YYYY-MM&
    equipe=<id>``. Un Responsable/manager (non Admin) ne voit QUE les équipes
    qu'il dirige (``EquipeCommerciale.responsable``) ; un Admin/Directeur voit
    tout. ``?equipe=<id>`` restreint la réponse à cette équipe précise."""
    user = request.user
    if not user.company_id:
        return Response({'equipes': [], 'total_societe': {}})
    periode = None
    periode_param = request.query_params.get('periode')
    if periode_param and '-' in periode_param:
        year, month = periode_param.split('-', 1)
        try:
            periode = {
                'period_type': 'month', 'period_year': int(year),
                'period_month': int(month),
            }
        except ValueError:
            periode = None
    manager = None if getattr(user, 'is_admin_role', False) else user
    from .selectors import forecast_rollup
    data = forecast_rollup(user.company, periode=periode, manager=manager)
    equipe_id = request.query_params.get('equipe')
    if equipe_id:
        try:
            equipe_id = int(equipe_id)
        except ValueError:
            equipe_id = None
        data = {
            **data,
            'equipes': [e for e in data['equipes'] if e['equipe_id'] == equipe_id],
        }
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def forecast_historique_view(request):
    """NTCRM6 — Série de snapshots hebdomadaires : ``?owner=&semaines=12``.
    ``owner`` vide = snapshots SOCIÉTÉ (owner=None) ; sinon un commercial
    donné. Renvoie la série ordonnée chronologiquement pour un graphe
    d'évolution (glissement visible)."""
    user = request.user
    if not user.company_id:
        return Response({'series': []})
    owner = request.query_params.get('owner')
    try:
        semaines = int(request.query_params.get('semaines') or 12)
    except ValueError:
        semaines = 12
    qs = ForecastSnapshot.objects.filter(company=user.company)
    qs = qs.filter(owner_id=owner) if owner else qs.filter(owner__isnull=True)
    qs = qs.order_by('-semaine_iso')[:max(1, semaines)]
    data = list(reversed(ForecastSnapshotSerializer(qs, many=True).data))
    return Response({'series': data})


# ── NTCRM10 — Plan de compte ─────────────────────────────────────────────────

class PlanCompteViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """NTCRM10 — Plan de compte. ARC8 : l'historique (chatter) converge sur
    ``records.Activity`` — création + changements de champ suivis journalisés
    via ``records.services`` (le « mail.thread » maison), jamais un modèle
    ``*Activity`` local. Le mixin ``ChatterViewSetMixin`` ajoute en plus les
    actions génériques ``chatter/historique`` (GET) et ``chatter/noter`` (POST)."""
    queryset = PlanCompte.objects.select_related('client')
    serializer_class = PlanCompteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        from apps.records.models import Activity
        from apps.records.services import log_activity
        instance = serializer.save(
            company=self.request.user.company, created_by=self.request.user,
            mis_a_jour_par=self.request.user)
        log_activity(
            instance, Activity.Kind.CREATION, user=self.request.user,
            body=f'Plan de compte créé pour {instance.client}.')

    def perform_update(self, serializer):
        from apps.records.services import log_field_change
        old = PlanCompte.objects.get(pk=serializer.instance.pk)
        instance = serializer.save(mis_a_jour_par=self.request.user)
        tracked = [
            'objectifs_strategiques', 'potentiel_estime', 'concurrents_presents',
            'prochaine_revue', 'statut',
        ]
        for field in tracked:
            old_val, new_val = getattr(old, field), getattr(instance, field)
            if old_val != new_val:
                log_field_change(
                    instance, field,
                    str(old_val) if old_val is not None else '',
                    str(new_val) if new_val is not None else '',
                    user=self.request.user)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs
        plan = self.get_object()
        qs = chatter_qs(plan, company=request.user.company)
        return Response(ChatterActivitySerializer(qs, many=True).data)


class RevueCompteViewSet(CompanyScopedModelViewSet):
    queryset = RevueCompte.objects.select_related('plan')
    serializer_class = RevueCompteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(plan__company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── NTCRM12 — Playbooks de vente par étape ───────────────────────────────────

class PlaybookViewSet(CompanyScopedModelViewSet):
    queryset = Playbook.objects.prefetch_related('etapes__taches')
    serializer_class = PlaybookSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class PlaybookEtapeViewSet(CompanyScopedModelViewSet):
    queryset = PlaybookEtape.objects.select_related('playbook').prefetch_related('taches')
    serializer_class = PlaybookEtapeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(
            playbook__company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save()


class PlaybookTacheViewSet(CompanyScopedModelViewSet):
    queryset = PlaybookTache.objects.select_related('etape__playbook')
    serializer_class = PlaybookTacheSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(
            etape__playbook__company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save()


@api_view(['GET', 'POST'])
@permission_classes([IsAnyRole])
def lead_playbook_view(request, lead_id):
    """NTCRM12 — ``GET`` : progression playbook du lead (toutes les tâches
    générées pour son étape courante ou une étape antérieure). ``POST``
    ``{'tache': <id>, 'fait': true}`` : coche/décoche UNE tâche, pose
    l'acteur+la date côté serveur (jamais silencieux)."""
    lead = Lead.objects.filter(pk=lead_id, company=request.user.company).first()
    if lead is None:
        return Response({'detail': 'Lead introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        progress = lead.playbook_progress.select_related(
            'tache', 'tache__etape', 'fait_par').all()
        return Response(LeadPlaybookProgressSerializer(progress, many=True).data)

    tache_id = request.data.get('tache')
    fait = bool(request.data.get('fait', True))
    progress = LeadPlaybookProgress.objects.filter(
        lead=lead, tache_id=tache_id).first()
    if progress is None:
        return Response(
            {'detail': 'Tâche de playbook introuvable pour ce lead.'},
            status=status.HTTP_404_NOT_FOUND)
    from django.utils import timezone as _tz
    progress.fait = fait
    progress.fait_par = request.user if fait else None
    progress.fait_le = _tz.now() if fait else None
    progress.save(update_fields=['fait', 'fait_par', 'fait_le'])
    return Response(LeadPlaybookProgressSerializer(progress).data)
