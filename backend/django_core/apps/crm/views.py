import logging
from contextlib import contextmanager

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from core.entite_scoping import EntiteScopeMixin
from core.mixins import TenantMixin
from core.permissions import declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet
from apps.core.destroy_mixins import UsageGuardedDestroyMixin
from authentication.scoping import scope_queryset, scope_client_queryset
from .models import (
    LeadActivity, Appointment, Client, ConcurrentPerte, EquipeCommerciale,
    ForecastEntry, ForecastSnapshot, Lead, LeadPlaybookProgress, LeadTag, MotifPerte,
    Canal, Parrainage, ObjectifCommercial, PlanActivite, PlanCompte, Playbook,
    PlaybookEtape, PlaybookTache, RelanceEtape, RevueCompte, SavedView, SiteProfile,
    WebsiteLeadPayload,
)
from .serializers import (
    AppointmentSerializer, ClientSerializer, ConcurrentPerteSerializer, LeadSerializer,
    LeadActivitySerializer, LeadTagSerializer, MotifPerteSerializer, CanalSerializer,
    ParrainageSerializer, _tag_en_usage, _motif_en_usage, ObjectifCommercialSerializer,
    ObjectifAttainmentSerializer, PlanActiviteSerializer, SiteProfileSerializer,
    EquipeCommercialeSerializer, WebsiteLeadPayloadSerializer, ForecastEntrySerializer,
    ForecastSnapshotSerializer, PlanCompteSerializer, RevueCompteSerializer,
    PlaybookSerializer, PlaybookEtapeSerializer, PlaybookTacheSerializer,
    LeadPlaybookProgressSerializer, SavedViewSerializer, masquer_pii_dict,
)
from .actions_crud import READ_ACTIONS, WRITE_ACTIONS, _PorteeEnfantsMixin
from .leads_views import LeadIntakeActionsMixin
from .cadence_views import (
    LeadCadenceActionsMixin,
    _best_effort, _geste_atomique, _parse_rappel, _prochaine_touche_publique,
)
from apps.records.views import ChatterViewSetMixin
from . import activity, stages
from .fiche_bulk import BULK_ACTIONS  # SPL3 (main) : déplacé de services ; ENF6 l'expose au schéma
from .leads_attribution import default_responsable_for
from . import schema_docs as sd
from .devis_auto import champs_manquants, message_manquants
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)

logger = logging.getLogger(__name__)


class ReportToucheEchoue(APIException):
    """ALEA30 — le report de la prochaine touche a échoué : la transaction
    (écriture du lead + chatter + report) est annulée, RIEN n'est écrit, et la
    réponse le dit explicitement (jamais un 200 sur un état divergent)."""
    status_code = 500
    default_detail = ('Le report de la prochaine touche a échoué : rien n’a '
                      'été enregistré. Réessayez.')
    default_code = 'report_touche_echoue'


class SortieSigneRefusee(APIException):
    """Décision fondateur (08/10/2026) — le lead ne peut pas sortir de
    « Signé » : son devis accepté a déjà une suite réelle. 409, RIEN n'est
    écrit (ni étape, ni dés-acceptation) et ``detail`` nomme ce qui bloque."""
    status_code = 409
    default_detail = 'Impossible de sortir ce lead de cette étape.'
    default_code = 'sortie_signe_bloquee'


#: ACRM3 — les LECTURES de l'annuaire clients (en plus de ``READ_ACTIONS``) :
#: elles exigent ``crm_voir`` ou le code de lecture d'un module consommateur.
CLIENT_LECTURE_ACTIONS = [
    'documents', 'search', 'dormants', 'engagement', 'engagement_bulk',
    'mon_portefeuille',
]


def _voit_le_crm(user):
    """ACRM3 — vrai si ``user`` lit le CRM (``crm_voir``), même règle que
    ``HasPermissionOrLegacy('crm_voir')`` : superuser, rôle fin portant le
    code, ou compte historique responsable sans rôle fin."""
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None):
        return user.has_erp_permission('crm_voir')
    return bool(getattr(user, 'is_responsable', False))


def _refus_pii_whatsapp(request):
    """ACRM4 — le partage WhatsApp d'un devis rend le NUMÉRO du client
    (``phone``, ``wa_url``) : refusé 403 ``droit_manquant`` sans
    ``client_pii_voir``, exactement comme ``resume_associe``. ``None`` si
    l'appelant a le droit."""
    from .serializers import pii_masquee_pour
    if not pii_masquee_pour(request.user):
        return None
    return Response(
        {'detail': "Vous n'avez pas la permission de voir les coordonnées "
                   'du client.',
         'code': 'droit_manquant'},
        status=status.HTTP_403_FORBIDDEN)


@contextmanager
def _save_borne_aux_champs(instance, champs):
    """CRX25 — force ``update_fields`` sur le prochain ``instance.save()``.

    ``ModelSerializer.update()`` termine par un ``instance.save()`` NU, qui
    réécrit TOUTES les colonnes depuis la copie en mémoire : deux requêtes
    concurrentes touchant des champs DISJOINTS se révertent alors l'une
    l'autre (lost update). DRF n'expose aucun crochet pour borner cette
    écriture ; on remplace donc la méthode LIÉE le temps de l'appel, puis on la
    restaure — le sérialiseur n'est pas modifié, les M2M (posés APRÈS le save
    par DRF) ne sont pas concernés, et un appelant qui passerait déjà un
    ``update_fields`` explicite garde le sien.

    ``champs`` vide ⇒ aucune borne (un ``update_fields=[]`` ne ferait
    strictement rien et perdrait l'écriture).
    """
    if not champs:
        yield
        return
    original = instance.save

    def _save(*args, **kwargs):
        kwargs.setdefault('update_fields', champs)
        return original(*args, **kwargs)

    instance.save = _save
    try:
        yield
    finally:
        try:
            del instance.save
        except AttributeError:  # pragma: no cover — défense en profondeur
            instance.save = original


@extend_schema(responses=sd.liste('CrmAssignableUser'))
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


@extend_schema(responses=sd.OBJ)
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


class ClientViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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
        # APRF17 (C-APRF-006) — ce que ``ClientSerializer`` lit PAR LIGNE
        # (créateur, nombre de devis, totaux facturé/payé : lignes, paiements
        # et ventilations d'avances) est chargé EN LOT : la liste coûte le
        # même nombre de requêtes à 5 et à 15 clients. Chemins en chaînes —
        # aucun import des modèles ventes/facturation.
        return (scope_client_queryset(super().get_queryset(),
                                      self.request.user)
                .select_related('created_by')
                .prefetch_related(
                    'devis', 'factures__lignes', 'factures__paiements',
                    'factures__affectations_paiement__paiement'))

    def perform_create(self, serializer):
        # Traçabilité (L16) : société ET créateur forcés côté serveur — jamais
        # acceptés du corps de la requête.
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        # NTI18N49 — snapshot de la langue documentaire AVANT écriture, pour
        # journaliser le changement dans le chatter (lead rattaché) une fois
        # la sauvegarde faite. Aucun autre comportement de perform_update
        # n'est touché (comportement DRF par défaut préservé).
        old_langue = serializer.instance.langue_document
        super().perform_update(serializer)
        new_client = serializer.instance
        if new_client.langue_document != old_langue:
            activity.log_client_langue_document_change(
                new_client, self.request.user,
                old_value=old_langue, new_value=new_client.langue_document,
            )
            # CRM-LANGUE-EVENT — comble le seam NTI18N43 (jusqu'ici sans
            # émetteur) : une intégration tierce (webhook publicapi
            # `langue_changed`) doit savoir que ce client a changé de langue
            # documentaire. `emettre_langue_changed` porte déjà sa propre
            # garde « ça a vraiment changé » — le if ci-dessus la double,
            # sans risque (idempotent).
            from core.events import emettre_langue_changed
            emettre_langue_changed(
                new_client.company,
                ancienne_langue=old_langue,
                nouvelle_langue=new_client.langue_document,
                client_id=new_client.pk,
                user=self.request.user,
            )

    def get_permissions(self):
        # QC1 — `search` est une LECTURE scopée société (autocomplete des
        # données propres) : ouverte à tout rôle authentifié, comme `list`.
        # Ce get_permissions prime sur le permission_classes de l'action —
        # NTCRM14/15/16/29 : `dormants`/`relancer_dormance`/`engagement`/
        # `engagement_bulk`/`mon_portefeuille` sont des LECTURES (ou une
        # relance légère) déjà ouvertes via `permission_classes=[IsAnyRole]`
        # sur leur @action, mais get_permissions() PRIME dessus — sans les
        # lister ICI elles retombaient sur le défaut `IsAdminRole` (403 pour
        # tout rôle Commercial/Responsable non-admin).
        #
        # ACRM3 (C-ACRM-001) — « tout rôle authentifié » laissait le
        # Commercial terrain (app Visites seule) et l'Admin RH lire
        # l'annuaire clients et chercher des leads avec leur téléphone : les
        # LECTURES exigent désormais un code fin de lecture — ``crm_voir``,
        # ou celui d'un module qui CONSOMME l'annuaire clients (``sav_voir``
        # pour le SAV, ``installation_voir`` pour les chantiers) — et la
        # relance (une écriture au chatter du lead) ``crm_modifier``.
        # ``OrLegacy`` préserve les comptes historiques sans rôle fin.
        if self.action in READ_ACTIONS + CLIENT_LECTURE_ACTIONS:
            return [(HasPermissionOrLegacy('crm_voir')
                     | HasPermissionOrLegacy('sav_voir')
                     | HasPermissionOrLegacy('installation_voir'))()]
        elif self.action == 'relancer_dormance':
            return [HasPermissionOrLegacy('crm_modifier')()]
        elif self.action == 'export_xlsx':
            # Export : garde propre (ASEC50, code ``crm_export``) — hors
            # périmètre d'ACRM3.
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['dupliquer']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        # ACRM21 (C-ACRM-014) — les autres @action (consolidation,
        # data-export, anonymize, segments) sont gardées par CE QUE LEUR
        # DÉCORATEUR DÉCLARE (patron ``declared_action_permissions``) : le
        # repli brut ``IsAdminRole`` refusait au Commercial le bloc « CA
        # groupe » (déclaré ``IsAnyRole``) et l'export RGPD (déclaré
        # ``IsResponsableOrAdmin``).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        return [IsAdminRole()]

    @extend_schema(request=None, responses={201: ClientSerializer})
    @action(detail=True, methods=['post'], url_path='dupliquer',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer(self, request, pk=None):
        """NTUX13 — Duplique cette fiche client (suffixe « (copie) », email/
        ICE vidés — voir ``services.dupliquer_client``)."""
        source = self.get_object()
        from .clients_identite import dupliquer_client
        copie = dupliquer_client(source, user=request.user)
        return Response(
            ClientSerializer(copie, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @extend_schema(request=sd.corps('CrmClientsExportRequest', ids=serializers.ListField(child=serializers.IntegerField(), required=False)), responses=sd.EXPORT_XLSX)
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
        # ACRM4 — sans ``client_pii_voir`` : export sans colonnes PII.
        from .serializers import pii_masquee_pour
        return export_clients_xlsx(
            qs.order_by('nom'), masquer_pii=pii_masquee_pour(request.user))

    @extend_schema(parameters=[sd.P_Q], responses=sd.corps('CrmClientSearch', results=serializers.ListField(child=serializers.DictField())))
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
        # CRX16 — la portée de visibilité du rôle s'applique à l'autocomplete
        # comme à la liste (``scope_client_queryset`` côté clients) : sans
        # elle, un rôle restreint lisait ici les coordonnées d'enregistrements
        # que sa propre liste lui masque.
        results = (search_companies(request.user.company, q,
                                    user=request.user)
                   if q else [])
        # ACRM3 — un module consommateur (SAV, chantiers) cherche des
        # CLIENTS : sans ``crm_voir``, aucun lead (ni son téléphone) ne sort
        # de l'autocomplete.
        if not _voit_le_crm(request.user):
            results = [r for r in results if r.get('source') != 'lead']
        return Response({'results': results})

    @extend_schema(responses=sd.OBJ)
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

    @extend_schema(responses=sd.OBJ)
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

    @extend_schema(responses=sd.OBJ)
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
        # ACRM53 — même règle que ``ClientSerializer`` : un rôle sans
        # ``client_pii_voir`` reçoit l'export sans téléphone/email/adresse.
        from .serializers import masquer_pii_dict
        masquer_pii_dict(identite, request.user)
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

    @extend_schema(request=None, responses=ClientSerializer)
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
    # ACRM21 — déclaration EXPLICITE (admin) : c'est la garde qui
    # s'appliquait déjà par le repli ; elle est désormais lue sur l'@action.
    @extend_schema(parameters=[sd.param('segment', enum=['top', 'sans_devis', 'a_recontacter', 'dormants'])], responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='segments',
            permission_classes=[IsAdminRole])
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

    @extend_schema(parameters=[sd.param('seuil', OpenApiTypes.INT)], responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='dormants',
            permission_classes=[IsAnyRole])
    def dormants(self, request):
        """NTCRM14 — Comptes dormants : au moins un devis/facture passé mais
        aucune activité (devis/facture/LeadActivity/PointContact) depuis
        `?seuil=` jours (défaut 90). Distinct de `segments?segment=dormants`
        (seuil fixe 18 mois, sans LeadActivity/PointContact) — celui-ci
        alimente aussi la commande de notification `detecter_comptes_dormants`.
        """
        from .selectors import comptes_dormants
        try:
            seuil = int(request.query_params.get('seuil', 90))
        except (TypeError, ValueError):
            seuil = 90
        company = request.user.company if request.user.company_id else None
        # ALEA27 — bornée par la portée du viewset (société + équipe).
        entries = comptes_dormants(
            company, seuil_jours=seuil, clients=self.get_queryset())
        results = [{
            'id': e['client'].id,
            'nom': str(e['client']),
            'derniere_activite': (
                e['derniere_activite'].isoformat()
                if e['derniere_activite'] else None),
            'jours_inactivite': e['jours_inactivite'],
        } for e in entries]
        return Response({'seuil': seuil, 'count': len(results), 'results': results})

    @extend_schema(request=None, responses={201: LeadActivitySerializer})
    @action(detail=True, methods=['post'], url_path='relancer-dormance',
            permission_classes=[IsAnyRole])
    def relancer_dormance(self, request, pk=None):
        """NTCRM15 — Bouton one-click « créer une activité de relance » du
        widget Comptes dormants : journalise une note sur le lead le plus
        récent lié à ce client. 404 si le client n'a aucun lead (rien à
        relancer via le chatter — cas rare, clients importés sans lead)."""
        from . import activity
        from .models import Lead
        client = self.get_object()
        # ACRM7 — le lead relancé est choisi parmi ceux de la PORTÉE de
        # l'appelant : jamais une note chez un collègue hors portée.
        lead = (scope_queryset(
                    Lead.objects.filter(company=client.company,
                                        client=client),
                    request.user, ['owner'])
                .order_by('-date_creation').first())
        if lead is None:
            return Response(
                {'detail': "Aucun lead lié à ce client — relance impossible."},
                status=status.HTTP_404_NOT_FOUND)
        act = activity.log_note(
            lead, request.user,
            f'Relance dormance — compte {client} réactivé manuellement.')
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='engagement',
            permission_classes=[IsAnyRole])
    def engagement(self, request, pk=None):
        """NTCRM16 — Score d'engagement multi-signaux (0-100) de CE client."""
        from .engagement import engagement_for_client
        client = self.get_object()
        return Response(engagement_for_client(client))

    @extend_schema(responses=sd.liste('CrmEngagementClient'))
    @action(detail=False, methods=['get'], url_path='engagement-bulk',
            permission_classes=[IsAnyRole])
    def engagement_bulk(self, request):
        """NTCRM16 — Score d'engagement multi-signaux pour la liste (bulk)."""
        from .engagement import engagement_bulk as _engagement_bulk
        qs = self.get_queryset()
        return Response(_engagement_bulk(list(qs)))

    @extend_schema(responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='mon-portefeuille',
            permission_classes=[IsAnyRole])
    def mon_portefeuille(self, request):
        """NTCRM29 — Widget « portefeuille de comptes » : les comptes du
        commercial CONNECTÉ (owner via leads liés), triés par score
        d'engagement croissant (les plus froids en premier). Jamais scopé
        depuis la query string — toujours ``request.user``/``request.user.
        company``."""
        from .selectors import portefeuille_commercial
        results = portefeuille_commercial(request.user.company, request.user)
        return Response({'count': len(results), 'results': results})


class _RepliIsAdminMixin:
    """SPL75 — fin de la chaîne des ``get_permissions`` coopératifs de
    LeadViewSet : toute action qu'aucun mixin ni LeadViewSet ne garde
    retombe sur ``[IsAdminRole()]`` (repli final, prouvé par l'action
    absente du golden SPL70). Placé AVANT ``EntiteScopeMixin`` dans les
    bases."""

    def get_permissions(self):
        return [IsAdminRole()]


@extend_schema_view(list=extend_schema(parameters=[sd.param('stage'), sd.param('source'), sd.P_ARCHIVED, sd.P_ENTITE]))
class LeadViewSet(LeadCadenceActionsMixin, LeadIntakeActionsMixin,
                  _RepliIsAdminMixin, EntiteScopeMixin,
                  CompanyScopedModelViewSet):
    """Leads + historique « chatter » (journal automatique + notes manuelles).

    L'utilisateur acteur et la société viennent toujours de la requête côté
    serveur — jamais du corps envoyé par le navigateur.
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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
    # VTA4 (12/09/2026) — la frontière « pas d'accès CRM » est SERVEUR : la
    # liste/lecture des leads exige désormais le code fin `crm_voir`. Sans
    # cette ligne, ScopedPermission sans code = « authentifié suffit », et le
    # rôle « Commercial terrain » (app Visites seule) lisait tout l'annuaire
    # leads en appelant l'API directement — exactement ce que le fondateur a
    # exclu. Les rôles legacy (sans Role fin) gardent leur accès historique
    # (comportement OrLegacy de la garde).
    read_permission = 'crm_voir'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    # WREF (fondateur 21/08) — client_ref = la référence remise au client :
    # stockée mais introuvable (3 recherches, 0 index). Depuis WREF2 c'est la
    # référence « NOM-N » attribuée par le serveur (les fiches d'avant portent
    # encore le « TQ-XXXX » du navigateur) — les deux formats se cherchent
    # ici de la même façon. NB :
    # code_parrainage vit sur crm.Client, PAS sur Lead — ne pas l'ajouter ici.
    search_fields = ['nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
                     'client_ref', 'client_ref_provisoire']
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
        donnees = self._serialiser_leads_en_lot(objects)
        if page is not None:
            return self.get_paginated_response(donnees)
        return Response(donnees)

    def _serialiser_leads_en_lot(self, objects):
        """APRF18 (C-APRF-009) — LA sérialisation EN LOT d'une liste de
        leads : les cartes ``{lead_id/devis_id: …}`` (prochaine activité,
        chantiers, ancienneté d'étape, liens de partage, lectures) sont
        calculées UNE fois pour tout le lot et posées dans le contexte, que le
        sérialiseur préfère à son repli requête-par-ligne. Partagée par
        ``list``, ``relances`` et ``sla_breach`` : aucune des trois ne paie
        une requête par lead."""
        objects = list(objects)
        extra_context = {
            'next_activity_map': self._next_activity_map(objects),
            'chantier_map': self._chantier_map(objects),
            'stage_since_map': self._stage_since_map(objects),
            'share_link_map': self._share_link_map(objects),
            'lecture_map': self._lecture_map(objects),
        }
        serializer = self.get_serializer(
            objects, many=True, context={
                **self.get_serializer_context(), **extra_context})
        return serializer.data

    def retrieve(self, request, *args, **kwargs):
        """LW30 — pose ``include_chatter_recent`` dans le contexte pour que
        ``LeadSerializer`` embarque les 50 dernières activités du chatter
        (``get_fields()`` ne garde le champ QUE quand ce flag est présent) —
        jamais sur list() (payload), l'ouverture de la fiche passe de 4
        requêtes (detail + historique/ + …) à 3."""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, context={
                **self.get_serializer_context(),
                'include_chatter_recent': True,
            })
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
    def _share_link_map(leads):
        """{devis_id: {niveau, otp_lecture, sections}} pour TOUS les devis de
        TOUS les leads du lot, en UNE requête (au lieu d'une par lead via
        ``get_devis``). Sans ce préchargement, L-NIV-UI ré-interrogeait
        ``ShareLink`` pour CHAQUE ligne de la liste (N+1 réel : le budget de
        requêtes passait de 17 à 22 entre 5 et 10 leads). Lecture cross-app
        par ``apps.ventes.selectors`` uniquement."""
        from apps.ventes.selectors import share_link_niveau_map
        devis_ids = [d.id for lead in leads for d in lead.devis.all()]
        if not devis_ids:
            return {}
        return share_link_niveau_map(devis_ids)

    @staticmethod
    def _lecture_map(leads):
        """QJ-VUES — {devis_id: {nombre_vues, premiere/derniere_consultation}}
        pour TOUS les devis du lot en UNE requête (même garde N+1 que
        ``_share_link_map`` juste au-dessus). Lecture cross-app par
        ``apps.ventes.selectors`` uniquement."""
        from apps.ventes.selectors import share_link_lecture_map
        devis_ids = [d.id for lead in leads for d in lead.devis.all()]
        if not devis_ids:
            return {}
        return share_link_lecture_map(devis_ids)

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
        qs = self._annoter_prochaine_touche(qs, self.request.user.company)
        # CAD133 (correctif de budget) — le score d'une ligne lit désormais
        # des signaux de COMPORTEMENT (proposition ouverte/rouverte/lue,
        # questionnaire répondu, client joint) et la fraîcheur de la DERNIÈRE
        # interaction. Lus lead par lead, ils coûtaient 16 requêtes PAR LIGNE
        # (415 pour 25 leads). Posés ici en sous-requêtes, ils arrivent avec
        # la ligne : le budget de la liste ET de la fiche redevient fixe.
        # Seules les deux lectures les portent — aucune autre action n'en a
        # besoin, et un queryset annoté ne doit pas servir à un `update()`.
        if getattr(self, 'action', None) in ('list', 'retrieve'):
            from .signaux import annotations_signaux
            qs = qs.annotate(**annotations_signaux())
        return qs

    def _leads_en_portee(self):
        """ALEA27 — les leads que CET utilisateur peut voir (société + portée
        équipe/sous-arbre + entité), SANS les annotations de liste : la base
        de toute action annexe (bulk, doublons, contrôle de doublons). Une
        seule source de vérité : ``get_queryset()``.

        ACRM8 — la règle vit désormais dans ``selectors.leads_en_portee``
        (une seule définition, partagée avec les viewsets enfants) ; seul le
        filtre optionnel ``?entite=`` de la requête s'y ajoute ici."""
        from core.entite_scoping import filtre_entite_demandee

        from .selectors import leads_en_portee
        return filtre_entite_demandee(
            leads_en_portee(self.request.user), self.request)

    @staticmethod
    def _annoter_prochaine_touche(qs, company):
        """MRY5 — la prochaine touche de cadence, EN UNE requête.

        Le badge « touche due » et la chip « À relancer » (MRY16) doivent
        s'afficher sur 50 cartes sans coûter 50 requêtes : ces trois valeurs
        arrivent donc par Subquery/Exists dans le queryset, jamais par un
        `SerializerMethodField` qui interrogerait la base par lead.
        """
        from django.db.models import (
            Count, DateTimeField, F, IntegerField, OuterRef, Subquery)
        from django.db.models.functions import Coalesce

        from .models import LeadActivity, RelanceEtape

        ouvertes = RelanceEtape.objects.filter(
            lead=OuterRef('pk'), statut=RelanceEtape.Statut.A_FAIRE)
        prochaines = ouvertes.order_by(
            F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
        return qs.annotate(
            prochaine_touche_at=Subquery(
                prochaines.values('due_at')[:1],
                output_field=DateTimeField()),
            prochaine_touche_canal=Subquery(
                prochaines.values('canal')[:1]),
            # ALEA32 — « en retard » = au moins un jour COMPTÉ (calendrier
            # de la société) depuis l'échéance. Le queryset ne porte que la
            # PLUS ANCIENNE échéance ouverte (même requête) ; le sérialiseur
            # la compare au seuil unique ``seuil_retard``, lu UNE fois par
            # requête et SEULEMENT si une échéance est déjà passée :
            # « ∃ échéance < seuil » ⇔ « min(échéances) < seuil ». Une action
            # qui ne sérialise pas le lead (historique…) ne lit plus le
            # calendrier pour rien.
            plus_ancienne_touche_ouverte=Subquery(
                ouvertes.filter(due_date__isnull=False)
                .order_by('due_date').values('due_date')[:1]),
            # MRY20 — combien de fois a-t-on VRAIMENT essayé ? Seules les
            # tentatives HUMAINES comptent (appel / WhatsApp / e-mail avec un
            # auteur) : compter les lignes système gonflerait le chiffre
            # jusqu'à le rendre inutilisable, et c'est lui qui décide quand
            # un dossier a été assez travaillé pour être classé.
            # APRF20 — sous-requête CORRÉLÉE (et non un ``Count`` joint) : la
            # page de leads ne joint plus ``crm_leadactivity`` au niveau
            # principal, le tri/limite ne porte plus sur leads × activités.
            nb_tentatives=Coalesce(
                Subquery(
                    LeadActivity.objects
                    .filter(lead=OuterRef('pk'), user__isnull=False,
                            kind__in=[
                                LeadActivity.Kind.APPEL,
                                LeadActivity.Kind.WHATSAPP,
                                LeadActivity.Kind.EMAIL,
                            ])
                    .order_by()
                    .values('lead')
                    .annotate(n=Count('pk'))
                    .values('n')[:1],
                    output_field=IntegerField()),
                0),
        )

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
        from .leads_score import recompute_lead_score
        from .cadence_plan import demarrer_cadence_contact, sync_relance_activity
        # CAD90 — un lead saisi à la main entre dans la cadence comme ceux du
        # site : il doit donc, comme eux, exister au registre de consentement.
        # La personne a elle-même sollicité le contact (appel entrant,
        # message reçu, demande au salon) : c'est la base légale tracée ici.
        from .leads_consentement import (
            BASE_LEGALE_SOLLICITATION,
            CONSENT_SOURCE_SAISIE_MANUELLE,
            enregistrer_base_legale_lead,
        )
        enregistrer_base_legale_lead(
            serializer.instance, source=CONSENT_SOURCE_SAISIE_MANUELLE,
            base_legale=BASE_LEGALE_SOLLICITATION)
        sync_relance_activity(serializer.instance, user)
        recompute_lead_score(serializer.instance)
        # MRY6 — un lead saisi à la main est une demande réelle : il entre
        # dans la cadence comme ceux du site. Best-effort intégral — la
        # création répond 201 même si la cadence échoue.
        demarrer_cadence_contact(
            serializer.instance, user=user, origine='saisie manuelle')

    #: CRX25 — colonnes DÉRIVÉES recalculées par ``Lead.save()`` (QW10) : sans
    #: elles dans ``update_fields``, un changement de téléphone/email ne serait
    #: pas répercuté sur les colonnes indexées de dédup. On ne les écrit QUE
    #: quand leur source est dans le corps : les inclure systématiquement
    #: réécrirait la dédup depuis une copie périmée.
    COLONNES_DERIVEES = {'telephone': 'phone_normalise',
                         'email': 'email_normalise',
                         'whatsapp': 'whatsapp_normalise'}  # ACRM32

    @staticmethod
    def _champs_ecrivables(noms):
        """Restreint ``noms`` aux champs LOCAUX CONCRETS de ``Lead``, en y
        ajoutant TOUJOURS les horodatages ``auto_now``.

        Deux pièges de ``update_fields`` :

        * il refuse un M2M, une relation inverse ou un nom inconnu
          (``ValueError``) — on filtre donc sur le méta du modèle plutôt que de
          faire confiance aux clés du corps ;
        * Django ne rafraîchit un champ ``auto_now`` que s'il figure DANS
          ``update_fields``. Sans cet ajout, ``date_modification`` cesserait
          d'avancer à chaque PATCH — la fraîcheur affichée mentirait.
        """
        concrets = set()
        horodatages = set()
        for f in Lead._meta.get_fields():
            if (not getattr(f, 'concrete', False)
                    or getattr(f, 'many_to_many', False)
                    or getattr(f, 'primary_key', False)):
                continue
            concrets.add(f.name)
            if getattr(f, 'auto_now', False):
                horodatages.add(f.name)
        return sorted({n for n in noms if n in concrets} | horodatages)

    @staticmethod
    def _a_un_changement(old, vd):
        """ALEA29 — vrai si au moins une valeur validée diffère de la base.
        Prudent : une valeur non comparable (M2M, type inconnu) compte comme
        un changement."""
        for nom, valeur in vd.items():
            try:
                champ = Lead._meta.get_field(nom)
            except Exception:  # noqa: BLE001 — champ non modèle
                return True
            if getattr(champ, 'many_to_many', False):
                actuel = set(getattr(old, nom).values_list('pk', flat=True))
                voulu = {getattr(v, 'pk', v) for v in (valeur or [])}
                if actuel != voulu:
                    return True
                continue
            if getattr(old, nom) != valeur:
                return True
        return False

    def perform_update(self, serializer):
        # CAD156 — « Je vous rappelle jeudi à 18 h » : l'HEURE promise au
        # téléphone n'avait aucun champ (`relance_date` est une date). Elle
        # passe par le MÊME chemin que le report d'une touche (date + heure →
        # `reporter_prochaine_touche`), sans second champ ni second système de
        # rappel (MRY10). `relance_heure` (HH:MM) n'est pas une colonne : lue
        # dans le corps, validée AVANT toute écriture, refus qui NOMME le champ.
        quand_rappel = None
        brut_heure = self.request.data.get('relance_heure') \
            if hasattr(self.request.data, 'get') else None
        brut_heure = (str(brut_heure or '')).strip()
        if brut_heure:
            date_rappel = serializer.validated_data.get('relance_date')
            if not date_rappel:
                raise DRFValidationError({'relance_heure': [(
                    '« Heure du rappel » : choisissez d’abord la date de '
                    'relance.')]})
            quand_rappel = _parse_rappel(date_rappel.isoformat(), brut_heure)
            if quand_rappel is None:
                raise DRFValidationError({'relance_heure': [(
                    f'« Heure du rappel » : « {brut_heure} » n’est pas une '
                    'heure (HH:MM attendu).')]})
        # Snapshot avant écriture pour journaliser ancien → nouveau.
        old = Lead.objects.get(pk=serializer.instance.pk)
        instance = serializer.instance

        # ALEA29 — un PATCH SANS changement réel (corps vide ou valeurs
        # identiques) n’écrit rien : ni date_modification ni updated_by
        # n'avancent (sinon l'autre onglet affichait un faux « modifié par
        # ailleurs »). Une heure de rappel dans le corps est un changement.
        if not brut_heure and not self._a_un_changement(
                old, serializer.validated_data):
            return

        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern archived_by. CRX25 : posé
        # AVANT l'écriture et inclus dans update_fields, au lieu d'un second
        # save() (une écriture de moins, et jamais un lead sauvé deux fois).
        instance.updated_by = self.request.user

        # CRX25 — l'écriture est BORNÉE aux champs réellement touchés. Avant,
        # DRF faisait un ``instance.save()`` COMPLET : deux PATCH concurrents
        # sur des champs DISJOINTS (le commercial change la ville pendant que
        # l'assistante corrige le nom) se révertaient l'un l'autre — le second
        # save réécrivait TOUTES les colonnes depuis sa copie périmée.
        vd = serializer.validated_data
        # QJR583 — corriger la ville efface la ville de rattachement devenue
        # périmée (sinon l'ancienne ville continue de piloter productible,
        # PDF, transport). Une ville de rattachement envoyée avec la nouvelle
        # ville est gardée telle quelle.
        if ('ville' in vd and (vd['ville'] or '') != (old.ville or '')
                and old.ville_reference
                and ('ville_reference' not in vd
                     or vd['ville_reference'] == old.ville_reference)):
            vd['ville_reference'] = ''
        # QJR584 — le WhatsApp qui n'était qu'une copie du téléphone suit la
        # correction du téléphone ; un WhatsApp distinct n'est jamais touché.
        if 'telephone' in vd and 'whatsapp' not in vd:
            from .leads_doublons import normalize_phone
            if (old.whatsapp and normalize_phone(old.whatsapp)
                    == normalize_phone(old.telephone)
                    and normalize_phone(vd['telephone'])
                    != normalize_phone(old.telephone)):
                vd['whatsapp'] = vd['telephone']
        ecrits = set(vd.keys())
        if self.request.user.company_id:
            ecrits.add('company')  # forcée côté serveur (TenantMixin)
        ecrits.add('updated_by')
        for source, derivee in self.COLONNES_DERIVEES.items():
            if source in ecrits:
                ecrits.add(derivee)
        # ALEA30 — l'écriture, son chatter et le report de la prochaine touche
        # forment UNE transaction : un report en panne n'écrit RIEN (avant, la
        # `relance_date` du lead était persistée et la touche restait à son
        # ancienne date — deux dates divergentes, sonde LCAD-6). Les effets
        # secondaires non critiques (score, premier contact, émission d'étape)
        # sont best-effort, chacun dans son point de sauvegarde : leur panne
        # est journalisée et n'échoue plus un PATCH déjà écrit (LFICHE-5).
        from django.db import transaction
        from .leads_score import recompute_lead_score
        from .cadence_plan import reporter_prochaine_touche, sync_relance_activity
        from .fiche_funnel import _emit_stage_changed
        from .leads_premier_contact import maybe_set_first_contacted_at
        with transaction.atomic():
            # Décision fondateur 08/10/2026 — SORTIR de « Signé » par une
            # action utilisateur dés-accepte le(s) devis du lead (retour à
            # « envoyé », chantier auto-créé annulé…), dans CETTE transaction
            # et AVANT l'écriture : un blocage (facture émise, chantier
            # avancé…) rend un 409 qui nomme la cause, rien n'est écrit.
            if (old.stage == stages.SIGNED and 'stage' in vd
                    and vd['stage'] != stages.SIGNED):
                from .fiche_funnel import SortieSigneBloquee, desaccepter_devis_du_lead
                try:
                    desaccepter_devis_du_lead(old, self.request.user)
                except SortieSigneBloquee as exc:
                    raise SortieSigneRefusee(exc.message) from exc
            with _save_borne_aux_champs(
                    instance, self._champs_ecrivables(ecrits)):
                super().perform_update(serializer)

            new_lead = serializer.instance
            # CRX25 — l'instance en mémoire peut porter des valeurs PÉRIMÉES
            # sur les champs NON écrits (une requête concurrente les a changés
            # entre la lecture et l'écriture) : on relit avant de journaliser,
            # sinon le chatter annoncerait un changement qui n'a jamais été
            # persisté — et la réponse renverrait au client un état qui n'est
            # pas celui de la base.
            new_lead.refresh_from_db()
            activity.log_changes(old, new_lead, self.request.user)
            _best_effort('relance', sync_relance_activity,
                         new_lead, self.request.user)
            # FG28 — Pose first_contacted_at à la première sortie de NEW.
            _best_effort('premier contact', maybe_set_first_contacted_at,
                         old, new_lead)
            # QJ6 — Recalcule et persiste le score après chaque mise à jour.
            _best_effort('score', recompute_lead_score, new_lead)
            # NTCRM12 — édition manuelle de l'étape depuis l'écran lead.
            _best_effort('étape', _emit_stage_changed, new_lead, old.stage,
                         new_lead.stage, self.request.user)
            # MRY10 — UN SEUL système de rappel. Le rival historique
            # (`CallLogPopover`, qui PATCHe `relance_date` seul) reste
            # fonctionnel : sur un lead à cadence active, ce PATCH est traité
            # comme un report de la prochaine touche, sinon les deux dates
            # divergeraient dès le premier appel — exactement ce que
            # l'invariant de `sync_relance_activity` interdit.
            # CAD156 — une HEURE saisie reporte la touche même si la date ne
            # change pas (« toujours jeudi, mais à 18 h »).
            if quand_rappel is not None or (
                    'relance_date' in serializer.validated_data
                    and new_lead.relance_date
                    and new_lead.relance_date != old.relance_date):
                try:
                    reporter_prochaine_touche(
                        new_lead, self.request.user,
                        quand_rappel or new_lead.relance_date)
                except Exception as exc:  # noqa: BLE001 — tout est annulé
                    logger.warning(
                        'ALEA30: report de touche échoué sur le lead #%s — '
                        'PATCH annulé', new_lead.pk, exc_info=True)
                    raise ReportToucheEchoue() from exc
        # AGR522 — au passage à « accordé » (approbation préalable FDA), une
        # étape MANUELLE datée rappelle le délai de 3 mois (interne, hors
        # gabarit). Best-effort : jamais bloquant pour l'enregistrement.
        # ACRM45 — et quand le statut QUITTE « accordé », l'étape est
        # annulée (même point d'entrée, clé stable ``rappel_fda``).
        accorde = Lead.DossierSubvention.ACCORDE
        if ((new_lead.dossier_subvention == accorde
             and (old.dossier_subvention != new_lead.dossier_subvention
                  or old.dossier_subvention_le
                  != new_lead.dossier_subvention_le))
                or (old.dossier_subvention == accorde
                    and new_lead.dossier_subvention != accorde)):
            from .cadence_filet import poser_rappel_subvention
            try:
                poser_rappel_subvention(new_lead, self.request.user)
            except Exception:  # noqa: BLE001 — jamais bloquant pour le lead
                logger.warning('AGR522: rappel FDA non posé (lead #%s)',
                               new_lead.pk, exc_info=True)
        # CIQ513 — « Qui décide » noté au téléphone (conjoint/famille,
        # associé/direction, propriétaire tiers) pose l'étiquette « Décision à
        # plusieurs » (même effet que les réponses de touche). Idempotent ;
        # repasser à « seul » ne retire rien. Jamais bloquant.
        if old.decideur != new_lead.decideur:
            from .cadence_reponses import poser_decision_a_plusieurs_depuis_decideur
            try:
                poser_decision_a_plusieurs_depuis_decideur(
                    new_lead, self.request.user)
            except Exception:  # noqa: BLE001 — jamais bloquant pour le lead
                logger.warning('CIQ513: étiquette non posée (lead #%s)',
                               new_lead.pk, exc_info=True)
        # AGR525 — la pompe passe au butane sur un agricole déjà contacté :
        # la tâche FDA apparaît pour les étapes atteintes (idempotent).
        if (old.pompe_alim_actuelle != new_lead.pompe_alim_actuelle
                and new_lead.pompe_alim_actuelle == 'butane'):
            from .fiche_funnel import rattraper_playbooks_pompe
            try:
                rattraper_playbooks_pompe(new_lead)
            except Exception:  # noqa: BLE001 — jamais bloquant pour le lead
                logger.warning('AGR525: tâche FDA non générée (lead #%s)',
                               new_lead.pk, exc_info=True)
        # CIQ517 — un commercial/industriel déjà contacté passe en MT, en
        # régularisation 82-21 ou veut revendre : la tâche « raccordement et
        # autorisations du site » apparaît (idempotent, comme AGR525).
        if any(getattr(old, champ) != getattr(new_lead, champ)
               for champ in ('tension_raccordement', 'regularisation_8221',
                             'objectif_projet')):
            from .fiche_funnel import rattraper_playbooks_8221
            try:
                rattraper_playbooks_8221(new_lead)
            except Exception:  # noqa: BLE001 — jamais bloquant pour le lead
                logger.warning('CIQ517: tâche 82-21 non générée (lead #%s)',
                               new_lead.pk, exc_info=True)
        # QJR590 — une correction d'identité du lead suit sur SA fiche Client
        # (imprimée sur le PDF) tant que celle-ci n'a pas divergé à la main.
        # CIQ403 — un client ENTREPRISE suit aussi son identité légale.
        if ecrits & {'nom', 'prenom', 'email', 'telephone', 'adresse',
                     'ville', 'societe', 'fonction_contact', 'ice', 'rc',
                     'if_fiscal', 'adresse_siege', 'tva_recuperable'}:
            from .clients_identite import synchroniser_identite_client
            try:
                synchroniser_identite_client(new_lead, old, self.request.user)
            except Exception:  # noqa: BLE001 — jamais bloquant pour le lead
                logger.warning(
                    'QJR590: synchronisation client échouée (lead #%s)',
                    new_lead.pk, exc_info=True)
        # MRY9 (c)(d) — deux bascules ARRÊTENT les relances. Le passage
        # d'étape est déjà couvert par le receiver `lead_stage_changed`.
        # SUIVI E21 (30/09/2026) — et le rendez-vous de visite EN ATTENTE
        # s'annule avec elles (best-effort, note au chatter quand un
        # rendez-vous est réellement annulé) : le technicien ne se déplace
        # pas chez un client perdu ou qui ne veut plus être contacté.
        from .cadence_visite import (
            CAUSE_RDV_NE_PLUS_CONTACTER,
            annuler_rendez_vous_sur_arret,
            cause_rdv_perdu,
        )
        from .cadence_plan import arreter_cadence
        try:
            if not old.perdu and new_lead.perdu:
                arreter_cadence(
                    new_lead, user=self.request.user,
                    motif=(new_lead.motif_perte or 'lead perdu'))
                annuler_rendez_vous_sur_arret(
                    new_lead, self.request.user,
                    cause=cause_rdv_perdu(new_lead.motif_perte))
            if not old.ne_plus_contacter and new_lead.ne_plus_contacter:
                arreter_cadence(new_lead, user=self.request.user,
                                motif='ne plus contacter')
                annuler_rendez_vous_sur_arret(
                    new_lead, self.request.user,
                    cause=CAUSE_RDV_NE_PLUS_CONTACTER)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'MRY9: arrêt de cadence échoué sur le lead #%s',
                new_lead.pk, exc_info=True)
        # CAD91 — l'opposition cochée sur la fiche est inscrite au REGISTRE
        # (``ConsentRecord`` granted=False, daté), indépendamment de l'arrêt
        # de cadence ci-dessus : sans elle, rien ne prouverait qu'elle a été
        # honorée. Aucun motif exigé (loi 09-08 art. 9 al. 2).
        if not old.ne_plus_contacter and new_lead.ne_plus_contacter:
            from .cadence_reponses import (
                CONSENT_SOURCE_OPPOSITION_FICHE,
                tracer_opposition_registre,
            )
            tracer_opposition_registre(
                new_lead, source=CONSENT_SOURCE_OPPOSITION_FICHE)
        # ACRM59 — la DÉCOCHE est tracée elle aussi : une ligne accordée par
        # finalité de contact, dont la source nomme l'utilisateur.
        if old.ne_plus_contacter and not new_lead.ne_plus_contacter:
            from .leads_consentement import tracer_levee_opposition_registre
            tracer_levee_opposition_registre(new_lead, self.request.user)
        # CAD107 — la bascule INVERSE n'était traitée nulle part : décocher
        # « Perdu » ne déclenchait rien, alors qu'un client perdu qui revient
        # est le meilleur signal d'achat qui existe. Les trois chemins de
        # réouverture (ce PATCH, le lot `unset_perdu`, la nouvelle touche
        # entrante) posent désormais la MÊME cadence de reprise.
        from .cadence_touche import reprendre_cadence_apres_reouverture
        try:
            if old.perdu and not new_lead.perdu:
                reprendre_cadence_apres_reouverture(
                    new_lead, self.request.user, origine='fiche rouverte')
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'CAD107: reprise non posée sur le lead #%s',
                new_lead.pk, exc_info=True)

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['export_xlsx',
                                          'client_match',
                                          'salle_vente_analytics_view']:
            # VTA4 (12/09/2026, bug CI #25 en sens inverse) — la lecture des
            # leads exige le code fin ``crm_voir`` : ce get_permissions PRIME
            # sur tout, donc l'attribut ``read_permission`` posé sur la classe
            # était MORT et le rôle « Commercial terrain » (app Visites seule)
            # listait l'annuaire leads en 200. ``OrLegacy`` préserve les
            # comptes historiques sans Role fin ; tous les rôles métier seedés
            # (Responsable :509, Commercial resp :641, Commercial :682,
            # Viewer :807) portent déjà crm_voir.
            return [HasPermissionOrLegacy('crm_voir')()]
        elif self.action in ('historique', 'jalons_devis',
                             # VISITE-CADENCE — les deux LECTURES de la visite
                             # depuis la fiche lead. Listées ICI parce que
                             # get_permissions() PRIME sur le
                             # permission_classes de l'@action : posée
                             # seulement là-bas, la garde `crm_voir` serait
                             # MORTE et les deux actions retomberaient sur le
                             # `return [IsAdminRole()]` final — 403 pour la
                             # Commerciale, qui est justement celle qui lit.
                             'visites', 'message_visite',
                             # AGR516 — les réalisations proches sont une
                             # LECTURE de la fiche : même garde fine que
                             # l'@action (sinon `[IsAdminRole()]` final).
                             'references_proches'):
            # CRX19/CRX37 — l'historique COMPLET d'un lead (et ses jalons
            # devis, qui sont le même historique vu côté ventes) exige
            # ``crm_voir``. get_permissions() PRIME sur le permission_classes
            # de l'@action : posée seulement là-bas, la garde fine était morte
            # — `historique` retombait sur IsAnyRole (ouvert à TOUT porteur de
            # rôle) et `jalons_devis`, absent de toutes les listes, sur le
            # `return [IsAdminRole()]` final (403 pour la Commerciale).
            return [HasPermissionOrLegacy('crm_voir')()]
        elif self.action == 'resume_associe':
            # AGR534 — la permission DÉCLARÉE sur l'@action (responsable ou
            # admin) ; get_permissions() PRIME sur elle (bug CI #25), d'où
            # cette branche explicite plutôt que le `[IsAdminRole()]` final.
            return [IsResponsableOrAdmin()]
        elif self.action == 'locataire':
            # CAD164 — LIRE la proposition « locataire » est une lecture de la
            # fiche (`crm_voir`) ; créer la fiche du propriétaire ou clore
            # « Perdu — Locataire » est une écriture commerciale ordinaire
            # (`crm_modifier`). Listé ICI : get_permissions() PRIME sur
            # l'@action (bug CI #25).
            code = ('crm_voir' if self.request.method in ('GET', 'HEAD',
                                                          'OPTIONS')
                    else 'crm_modifier')
            return [HasPermissionOrLegacy(code)()]
        elif self.action in (
                'convertir_client', 'epingler', 'desepingler',
                # VISITE-CADENCE — POSER un rendez-vous de visite est une
                # ÉCRITURE commerciale ordinaire (`crm_modifier`), pas un
                # geste d'administration : sans cette ligne l'action
                # retomberait sur IsAdminRole et la Commerciale — qui est
                # justement celle qui cale la visite après l'envoi du devis —
                # serait refusée.
                'planifier_visite'):
            # VX199 — fusion / conversion de lead : permission ERP FINE
            # (crm_modifier), pas le grossier IsResponsableOrAdmin. get_permissions
            # PRIME sur le permission_classes de l'@action, donc la garde fine
            # doit être ICI. LW28 — épingler/désépingler suivent la même règle.
            return [HasPermissionOrLegacy('crm_modifier')()]
        elif self.action in WRITE_ACTIONS + [
            'noter', 'devis_auto', 'archiver', 'restaurer',
            'whatsapp_devis', 'whatsapp_devis_apercu', 'synchroniser_client',
            'bulk',
            'log_interaction',
            # GPS7 — même motif : sans cette ligne, resoudre-gps
            # retomberait sur IsAdminRole et la Commerciale serait
            # refusée alors que l'@action déclare crm_modifier.
            'resoudre_gps',
            # VREF — même motif (bug CI #25) pour « Vérifier la ville ».
            'ville_statut',
            # CAD111 — journaliser l'ouverture du message de visite : une
            # ÉCRITURE commerciale (chatter), même garde que `whatsapp_devis`
            # — listée ICI parce que get_permissions() PRIME (bug CI #25).
            'message_visite_ouvert',
        ]:
            # L'archivage réversible est ouvert à la Commerciale.
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            # La suppression DÉFINITIVE reste réservée à l'admin/propriétaire.
            return [IsAdminRole()]
        # SPL75 — les actions des mixins (cadence…) se gardent elles-mêmes ;
        # la chaîne finit sur _RepliIsAdminMixin ([IsAdminRole()]).
        return super().get_permissions()

    @extend_schema(request=None, responses=LeadSerializer)
    @action(detail=True, methods=['post'], url_path='archiver',
            permission_classes=[IsResponsableOrAdmin])
    def archiver(self, request, pk=None):
        """Archive un lead (réversible). Le retire des vues par défaut."""
        from django.db import transaction
        from django.utils import timezone
        lead = self.get_object()
        if not lead.is_archived:
            lead.is_archived = True
            lead.archived_by = request.user
            lead.archived_at = timezone.now()
            # ALEA30 — écriture et chatter dans la MÊME transaction.
            with transaction.atomic():
                lead.save(update_fields=['is_archived', 'archived_by',
                                         'archived_at'])
                activity.log_archive(lead, request.user)
        return Response(LeadSerializer(lead, context={'request': request}).data)

    @extend_schema(request=None, responses=LeadSerializer)
    @action(detail=True, methods=['post'], url_path='restaurer',
            permission_classes=[IsResponsableOrAdmin])
    def restaurer(self, request, pk=None):
        """Restaure un lead archivé (le ramène dans les vues par défaut)."""
        from django.db import transaction
        lead = self.get_object()
        if lead.is_archived:
            lead.is_archived = False
            lead.archived_by = None
            lead.archived_at = None
            # ALEA30 — écriture et chatter dans la MÊME transaction.
            with transaction.atomic():
                lead.save(update_fields=['is_archived', 'archived_by',
                                         'archived_at'])
                activity.log_restore(lead, request.user)
        return Response(LeadSerializer(lead, context={'request': request}).data)

    def _whatsapp_devis_message(self, request, lead, *, enregistrer):
        """Valide la sélection et construit le message multi-devis du lead.

        QJR538 — partagé par l'APERÇU (`whatsapp-devis-apercu`, sans aucun
        effet) et le COMMIT (`whatsapp-devis`). ``ShareLink.for_devis``
        réutilise le jeton : aperçu et commit portent le MÊME lien. Renvoie
        ``(Response d'erreur, None)`` ou ``(None, (devis_list, phone, message,
        links))``.
        """
        from apps.ventes.selectors import devis_for_lead
        from apps.ventes.utils.phone import normalize_phone_e164
        from apps.ventes.utils.whatsapp import build_devis_whatsapp

        from .fiche_bulk import coerce_id_list

        raw_ids = request.data.get('devis_ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {'detail': 'Sélectionnez au moins un devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        try:
            ids = coerce_id_list(raw_ids)
        except ValueError:
            return Response(
                {'detail': 'Identifiant de devis invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        # Devis du lead, dans la société courante uniquement.
        devis_list = devis_for_lead(lead, ids)
        if len(devis_list) != len(set(ids)):
            return Response(
                {'detail': 'Un devis sélectionné est introuvable pour ce lead.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        phone = lead.whatsapp or lead.telephone
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            ), None
        # QJR539 — garde de remise T17 (ventes.services) AVANT tout effet,
        # lien compris : un seul devis refusé refuse toute la sélection. Un
        # aperçu (``enregistrer=False``) n'écrit pas l'approbation implicite.
        from apps.ventes.services import (
            RemiseNonApprouvee, exiger_approbation_remise)
        for d in devis_list:
            if d.statut not in ('brouillon', 'envoye'):
                continue
            try:
                exiger_approbation_remise(
                    d, request.user, enregistrer=enregistrer)
            except RemiseNonApprouvee as erreur:
                return Response({'detail': erreur.message},
                                status=status.HTTP_400_BAD_REQUEST), None
        # Langue du message : la valeur explicite de la requête l'emporte ;
        # sinon on retombe sur la langue préférée du lead, puis sur le FR.
        langue = request.data.get('langue')
        if langue is None:
            langue = lead.langue_preferee or 'fr'
        message, links = build_devis_whatsapp(request, lead, devis_list, langue)
        return None, (devis_list, phone, message, links)

    @extend_schema(request=sd.corps('CrmWhatsappDevisApercuRequest', devis_ids=sd.ids_requis(), langue=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='whatsapp-devis-apercu',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_devis_apercu(self, request, pk=None):
        """QJR538 (contrat ``whatsapp_devis_apercu.json``) — APERÇU du message
        WhatsApp multi-devis, SANS AUCUN EFFET : ni ``mark_devis_sent``, ni
        AuditLog, ni note. Remplir le dialogue d'aperçu puis « Annuler » ne
        change donc ni le statut, ni la date d'envoi, ni le funnel."""
        from apps.ventes.utils.whatsapp import build_wa_url

        refus = _refus_pii_whatsapp(request)
        if refus is not None:
            return refus
        lead = self.get_object()
        erreur, built = self._whatsapp_devis_message(
            request, lead, enregistrer=False)
        if erreur is not None:
            return erreur
        _devis_list, phone, message, links = built
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'links': links,
        })

    @extend_schema(request=sd.corps('CrmResumeAssocieRequest', accord_client=serializers.BooleanField(), devis_id=serializers.IntegerField(required=False), langue=serializers.CharField(required=False)), responses=inline_serializer('CrmResumeAssocie', {
        'wa_url': serializers.CharField(),
        'phone': serializers.CharField(),
        'message': serializers.CharField(),
    }))
    @action(detail=True, methods=['post'], url_path='resume-associe',
            permission_classes=[IsResponsableOrAdmin])
    def resume_associe(self, request, pk=None):
        """AGR534 (contrat ``lead_resume_associe.json``, AGR504) — PRÉPARE le
        lien WhatsApp vers l'ASSOCIÉ (contact secondaire) avec le résumé de la
        proposition déjà envoyée. N'ENVOIE rien (décision D5) : le commercial
        ouvre ``wa_url``. Corps ``{devis_id, accord_client: true, langue?}``.

        Refus 403 sans ``client_pii_voir`` (le numéro est une PII) ; 400
        nommant ``accord_client`` (accord non coché),
        ``contact_secondaire_telephone`` (vide ou invalide) ou ``devis_id``
        (devis absent, d'un autre lead, ou jamais envoyé). Effet : UNE ligne
        d'historique ; aucun statut, aucune date d'envoi, aucune cadence
        touchés (CAD144, règle #4 : le lien est la proposition existante)."""
        from apps.parametres.models_messages import MessageTemplate
        from apps.ventes.selectors import devis_for_lead
        from apps.ventes.utils.client_links import url_proposition
        from apps.ventes.utils.phone import normalize_phone_e164
        from apps.ventes.utils.whatsapp import build_wa_url, render_message_template

        from .models import LeadActivity
        from .serializers import pii_masquee_pour
        from .cadence_messages import (
            _corps_pour_segment,
            _nom_affiche_conseiller,
            _nom_affiche_marque,
            _omettre_phrases_incompletes,
            _societe_du_lead,
        )

        if pii_masquee_pour(request.user):
            return Response(
                {'detail': "Vous n'avez pas la permission de voir les "
                           'coordonnées du client.'},
                status=status.HTTP_403_FORBIDDEN)
        lead = self.get_object()
        accord = request.data.get('accord_client')
        if not (accord is True or str(accord).strip().lower() == 'true'):
            return Response(
                {'accord_client': [
                    "Cochez l'accord du client avant de partager le résumé "
                    'avec son associé.']},
                status=status.HTTP_400_BAD_REQUEST)
        phone = (lead.contact_secondaire_telephone or '').strip()
        if not phone or not normalize_phone_e164(phone):
            return Response(
                {'contact_secondaire_telephone': [
                    'Aucun numéro valide pour le contact secondaire : '
                    'renseignez-le sur la fiche.']},
                status=status.HTTP_400_BAD_REQUEST)
        brut = str(request.data.get('devis_id') or '').strip()
        devis = (devis_for_lead(lead, [int(brut)]) if brut.isdigit() else [])
        if not devis or devis[0].statut == 'brouillon':
            return Response(
                {'devis_id': [
                    "Ce devis n'a jamais été envoyé au client : rien à "
                    'partager.']},
                status=status.HTTP_400_BAD_REQUEST)
        devis = devis[0]
        langue = (request.data.get('langue') or lead.langue_preferee
                  or 'fr').strip()
        if langue not in ('fr', 'darija'):
            langue = 'fr'
        corps = MessageTemplate.get_corps(
            lead.company, 'resume_associe', langue) or ''
        # CIQ503 — variante B2B (« pour votre direction ou votre comité ») par
        # le mécanisme CAD126 : jamais sur un texte personnalisé, jamais pour
        # un agricole ou un résidentiel.
        corps = _corps_pour_segment(corps, 'resume_associe', lead, langue)
        contexte = {
            'conseiller': _nom_affiche_conseiller(lead, request.user),
            'marque': _nom_affiche_marque(lead),
            'lien': url_proposition(devis) or '',
            # CIQ503 — raison sociale ; vide ⇒ sa phrase est OMISE (MRY13).
            'societe': _societe_du_lead(lead),
        }
        manquants = [cle for cle, valeur in contexte.items()
                     if '{' + cle + '}' in corps and not str(valeur).strip()]
        message = render_message_template(
            _omettre_phrases_incompletes(corps, manquants), contexte)
        nom = (lead.contact_secondaire_nom or '').strip() or 'l’associé'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=request.user,
            kind=LeadActivity.Kind.NOTE,
            body=f'Résumé transmis à {nom} — accord du client noté '
                 f'(proposition {devis.reference}).')
        return Response({'wa_url': build_wa_url(phone, message),
                         'phone': phone, 'message': message})

    @extend_schema(request=sd.corps('CrmWhatsappDevisRequest', devis_ids=sd.ids_requis(), langue=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='whatsapp-devis',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_devis(self, request, pk=None):
        """COMMIT du partage WhatsApp d'un/plusieurs devis du lead.

        Appelé par « Ouvrir WhatsApp » (QJR538) — jamais pour remplir
        l'aperçu (voir `whatsapp_devis_apercu`). N'envoie RIEN lui-même : le
        commercial appuie sur Envoyer dans WhatsApp. Chaque {lien} est un lien
        public tokenisé (30 j) vers le PDF CLIENT — jamais de prix d'achat ni
        de marge.
        """
        from apps.ventes.utils.whatsapp import build_wa_url

        refus = _refus_pii_whatsapp(request)
        if refus is not None:
            return refus
        lead = self.get_object()
        erreur, built = self._whatsapp_devis_message(
            request, lead, enregistrer=True)
        if erreur is not None:
            return erreur
        devis_list, phone, message, links = built
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

    @extend_schema(request=None, responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='synchroniser-client',
            permission_classes=[IsResponsableOrAdmin])
    def synchroniser_client(self, request, pk=None):
        """QJR590 (contrat ``lead_client_ecart.json``) — « Mettre à jour la
        fiche client » : recopie TOUT l'écart d'identité du lead vers SA fiche
        Client (``lead.client`` seulement, jamais un id du corps). 200
        ``{client_ecart, champs_mis_a_jour}`` | 400 ``{detail}``."""
        from .clients_identite import client_ecart, synchroniser_identite_client

        lead = self.get_object()
        if not lead.client_id:
            return Response(
                {'detail': "Ce lead n'est lié à aucune fiche client."},
                status=status.HTTP_400_BAD_REQUEST)
        if getattr(lead.client, 'is_anonymized', False):
            return Response(
                {'detail': 'La fiche client est anonymisée : elle ne se '
                           'met plus à jour.'},
                status=status.HTTP_400_BAD_REQUEST)
        champs, _message = synchroniser_identite_client(
            lead, None, request.user, force=True)
        lead.client.refresh_from_db()
        return Response({
            'client_ecart': client_ecart(lead),
            'champs_mis_a_jour': champs,
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
        from .leads_fusion import raison_refus_suppression
        lead = self.get_object()
        # ACAL177 — UNE garde (devis liés + calepinage ouvert), partagée avec
        # l'opération en masse ``delete``.
        refus = raison_refus_suppression(lead)
        if refus is not None:
            return Response(refus, status=status.HTTP_409_CONFLICT)
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

    @extend_schema(responses=LeadActivitySerializer(many=True))
    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def historique(self, request, pk=None):
        """Timeline chatter du lead (auto + notes), du plus récent au plus ancien.

        LW8 — ``select_related('user','attachment')`` : sans lui,
        ``LeadActivitySerializer.get_user_nom``/``get_attachment_*`` retouchent
        chacune une FK PAR LIGNE (N+1 réel, recon 02 §5). ``order_by`` explicite
        (au lieu du tri implicite ``Meta.ordering`` du modèle) — LW28 : les
        notes ÉPINGLÉES remontent en tête, hors chronologie.

        CRX19 — deux corrections : la lecture exige ``crm_voir`` (elle était
        ouverte à TOUT porteur de rôle, alors qu'elle sert l'historique
        complet d'un lead), et le CONTEXTE est propagé au sérialiseur, sans
        quoi le masquage PII du chatter ne s'appliquerait pas ici."""
        lead = self.get_object()
        activites = (
            lead.activites
            .select_related('user', 'attachment')
            .order_by('-pinned', '-created_at')
        )
        return Response(LeadActivitySerializer(
            activites, many=True, context={'request': request}).data)

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='references-proches',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def references_proches(self, request, pk=None):
        """AGR516 — les réalisations RÉELLES proches de ce lead (« allez voir
        chez un voisin »). Lecture seule, bornée à la société (``get_object``
        → 404 pour un lead d'une autre société). Le choix, le filtre de
        segment (AGR513) et le tri par distance vivent dans la fondation
        ``parametres`` (``selectors.realisations_proches``) ; forme du contrat
        ``lead_references_proches.json``. Aucune écriture."""
        from apps.parametres.selectors import realisations_proches
        lead = self.get_object()
        return Response({
            'segment': lead.type_installation or '',
            'references': realisations_proches(lead, limite=5),
        })

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='jalons-devis',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def jalons_devis(self, request, pk=None):
        """CRX37 — jalons du cycle de vie des devis du lead (envoyé / ouvert /
        signé / refusé), pour fusion dans la timeline côté écran.

        Surface HTTP MINIMALE du sélecteur ``selectors.lead_jalons_devis``, qui
        lit ``apps.ventes.selectors.devis_events_for_lead`` (jamais un import
        de ``apps.ventes.models``). Additive : ``historique`` garde sa forme à
        l'octet, aucun mock existant n'est invalidé. Même permission que
        ``historique`` (``crm_voir``) — c'est le même historique de lead.

        Contrat : ``apps/crm/contract_samples/lead_jalons_devis.json``.
        """
        from .selectors import lead_jalons_devis

        lead = self.get_object()
        return Response({'results': lead_jalons_devis(lead)})

    @extend_schema(request=None, responses=LeadActivitySerializer)
    @action(detail=True, methods=['post'],
            url_path=r'activites/(?P<activite_id>[^/.]+)/epingler',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def epingler(self, request, pk=None, activite_id=None):
        """LW28 — Épingle une entrée du chatter (mise en avant en tête,
        hors chronologie). Scopée au lead courant (déjà company-scopé via
        ``get_object()``) : un ``activite_id`` d'un AUTRE lead — même dans la
        même société — ou d'une autre société renvoie 404, jamais une fuite."""
        lead = self.get_object()
        from .models import LeadActivity
        try:
            act = lead.activites.get(pk=activite_id)
        except (LeadActivity.DoesNotExist, ValueError):
            return Response({'detail': 'Activité introuvable.'}, status=404)
        if not act.pinned:
            act.pinned = True
            act.save(update_fields=['pinned'])
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data)

    @extend_schema(request=None, responses=LeadActivitySerializer)
    @action(detail=True, methods=['post'],
            url_path=r'activites/(?P<activite_id>[^/.]+)/desepingler',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def desepingler(self, request, pk=None, activite_id=None):
        """LW28 — Désépingle une entrée du chatter (retour dans la
        chronologie normale). Même garde 404 hors-tenant que ``epingler``."""
        lead = self.get_object()
        from .models import LeadActivity
        try:
            act = lead.activites.get(pk=activite_id)
        except (LeadActivity.DoesNotExist, ValueError):
            return Response({'detail': 'Activité introuvable.'}, status=404)
        if act.pinned:
            act.pinned = False
            act.save(update_fields=['pinned'])
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data)

    @extend_schema(request=sd.corps('CrmResoudreGpsRequest', adresse=serializers.CharField(required=False), lien=serializers.CharField(required=False), ville=serializers.CharField(required=False)), responses=sd.OBJ)
    @action(detail=False, methods=['post'], url_path='resoudre-gps',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def resoudre_gps(self, request):
        """GPS7 — résout des coordonnées GPS, SANS RIEN ÉCRIRE.

        Corps : ``{lien}`` (lien Google Maps, y compris lien court) OU
        ``{adresse, ville}``. L'écran remplit ``gps_lat``/``gps_lng`` (et
        ``lien_maps``) avec la réponse ; l'enregistrement normal du lead
        persiste et journalise — ce résolveur reste PUR, utilisable aussi
        en création avant tout enregistrement. ``precision`` dit d'où vient
        le point : ``lien`` (exact, choisi par le client), ``adresse``
        (géocodeur), ``ville`` (centre-ville approximatif)."""
        from .geolocalisation import (
            coords_depuis_adresse, coords_depuis_lien_maps)
        lien = (request.data.get('lien') or '').strip()
        if lien:
            coords = coords_depuis_lien_maps(lien)
            if coords is None:
                return Response(
                    {'detail': 'Aucune coordonnée trouvée dans ce lien '
                               'Google Maps.'},
                    status=status.HTTP_400_BAD_REQUEST)
            lat, lng, precision = (*coords, 'lien')
        else:
            resultat = coords_depuis_adresse(
                request.data.get('adresse'), request.data.get('ville'))
            if resultat is None:
                return Response(
                    {'detail': "Adresse introuvable (ni géocodable, ni une "
                               'ville connue du gazetier).'},
                    status=status.HTTP_400_BAD_REQUEST)
            lat, lng, precision = resultat
        return Response({
            'gps_lat': str(lat), 'gps_lng': str(lng),
            'precision': precision,
        })

    @extend_schema(request=sd.corps('CrmVilleStatutRequest', ville=serializers.CharField(required=False, allow_blank=True), gps_lat=serializers.FloatField(required=False), gps_lng=serializers.FloatField(required=False), proches=serializers.BooleanField(required=False)), responses=sd.OBJ)
    @action(detail=False, methods=['post'], url_path='ville-statut',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def ville_statut(self, request):
        """VREF — statut d'une ville tapée + villes ERP proches, SANS RIEN
        ÉCRIRE (l'écran « Vérifier la ville » décide, l'enregistrement
        normal persiste).

        Corps : ``{ville, gps_lat?, gps_lng?}``. La position pour les villes
        proches vient du GPS fourni (le repère du lead — le plus fiable),
        sinon du géocodage de la ville tapée (Nominatim, repli gazetier).
        ``statut`` ∈ exacte/corrigee/ambigue/inconnue ; ``proches`` liste
        les villes ERP triées par distance (vide sans position)."""
        from apps.parametres.villes_resolution import (
            resoudre_ville, villes_proches)
        ville = (request.data.get('ville') or '').strip()
        resultat = resoudre_ville(ville)
        position = None
        proches = []
        gps_hors_zone = False
        # ``proches: true`` = l'écran-carte (dialogue) ; le simple contrôle
        # de statut (débouncé à la frappe) reste PUR — aucun géocodage réseau.
        if bool(request.data.get('proches')):
            try:
                lat = float(request.data.get('gps_lat'))
                lng = float(request.data.get('gps_lng'))
                # Garde de PLAUSIBILITÉ (incident 08/09 : un GPS de test à
                # 19.59/-30.61 — plein Atlantique — rendait « Bir Ghandouz,
                # 1 466 km » comme ville la plus proche). Hors de l'emprise
                # Maroc + Sahara, le repère est IGNORÉ et signalé — jamais
                # une liste de villes calculée depuis un point absurde.
                if 20.0 <= lat <= 36.5 and -17.5 <= lng <= -0.9:
                    position = (lat, lng)
                elif -90 <= lat <= 90 and -180 <= lng <= 180:
                    gps_hors_zone = True
            except (TypeError, ValueError):
                position = None
            if position is None and resultat['coords']:
                position = (float(resultat['coords'][0]),
                            float(resultat['coords'][1]))
            if position is None and ville:
                from .geolocalisation import coords_depuis_adresse
                geo = coords_depuis_adresse(ville)
                if geo:
                    position = (float(geo[0]), float(geo[1]))
            if position:
                proches = villes_proches(position[0], position[1])
        return Response({
            'statut': resultat['statut'],
            'ville_canonique': resultat['ville'],
            'candidats': resultat['candidats'],
            'position': ({'lat': position[0], 'lng': position[1]}
                         if position else None),
            'proches': proches,
            'gps_hors_zone': gps_hors_zone,
        })

    @extend_schema(request=sd.corps('CrmConvertirClientRequest', mode=serializers.ChoiceField(choices=['nouveau', 'lier', 'aucun']), client_id=serializers.IntegerField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='convertir-client',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def convertir_client(self, request, pk=None):
        """ZSAL4 — assistant de conversion EXPLICITE lead → client (body
        {mode: nouveau|lier|aucun, client_id?}). Journalisé dans le chatter."""
        lead = self.get_object()
        mode = (request.data.get('mode') or '').strip()
        client_id = request.data.get('client_id')
        from .clients_identite import ClientIntrouvable, convertir_lead_en_client
        try:
            # ACRM7 — le client à lier est cherché dans la PORTÉE de
            # l'appelant (même règle que ``ClientViewSet.get_queryset``).
            client = convertir_lead_en_client(
                lead=lead, user=request.user, mode=mode, client_id=client_id,
                clients=scope_client_queryset(
                    Client.objects.filter(company=lead.company),
                    request.user))
        except ClientIntrouvable as exc:
            # LEVÉ, pas renvoyé (même motif que `placement_cadences`) : le
            # contrat de la vue reste la forme de son 200 ; DRF rend le 400
            # ``{client_id: [...]}``.
            raise DRFValidationError({'client_id': [str(exc)]})
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'mode': mode,
            # ACRM4 — contexte transmis : la PII du client suit la règle
            # unique du masquage (``client_pii_voir``).
            'client': (ClientSerializer(
                client, context={'request': request}).data
                if client else None),
        })

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='salle-vente-analytics',
            permission_classes=[IsAnyRole])
    def salle_vente_analytics_view(self, request, pk=None):
        """NTCRM19 — résumé de consultation de la salle de vente la plus
        récente de ce lead, pour le widget « le client a consulté N fois,
        dernière fois <date> » de la fiche lead. `null` si aucune salle."""
        from .selectors import salle_vente_summary_for_lead
        lead = self.get_object()
        summary = salle_vente_summary_for_lead(request.user.company, lead.pk)
        return Response(summary)

    @extend_schema(request=None, responses=sd.OBJ)
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

    # ── FG38 — Correspondance Lead↔Client (doublon retour client) ────────────
    @extend_schema(responses=sd.OBJ)
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
        # 25/08/2026 — LANE NUMÉROS INTERNATIONAUX : bascule depuis
        # `apps.ventes.utils.phone.normalize_ma_phone` (forçait un préfixe
        # '212', ne rapprochait jamais un lead à numéro étranger) vers la
        # même clé QW10 que `selectors.find_client_by_phone` juste au-dessus.
        from .leads_doublons import normalize_phone

        conditions = []
        phone_norm = normalize_phone(lead.telephone or '') if lead.telephone else None
        email_norm = (lead.email or '').strip().lower() or None
        if phone_norm:
            conditions.append(
                Lead._meta.model.objects.none()  # placeholder — on fait direct
            )

        # Recherche directe sur Client
        # ALEA27 (jumeau) — bornée par la portée client de l'utilisateur
        # (même règle que ``ClientViewSet.get_queryset``) : un client hors
        # portée n'est jamais rendu.
        client_qs = scope_client_queryset(
            ClientModel.objects.filter(company=company), request.user)
        found = []
        pks_seen = set()
        if phone_norm:
            for c in client_qs:
                norm = normalize_phone(c.telephone or '') if c.telephone else None
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
            # ACRM4 — PII vidée pour un rôle sans ``client_pii_voir``.
            result.append(masquer_pii_dict({
                'id': c.id,
                'nom': f"{c.nom} {c.prenom or ''}".strip(),
                'email': c.email,
                'telephone': c.telephone,
                'nb_devis': c.devis.count(),
                'nb_chantiers': c.installations.count() if hasattr(c, 'installations') else 0,
            }, request.user))
        return Response(result)

    # ── VISITE-CADENCE — LA VISITE TECHNIQUE, VUE DEPUIS LA FICHE LEAD ───────
    #
    # Ordre fondateur du 15/09/2026 : la visite est une ÉTAPE DU SUIVI
    # COMMERCIAL, proposée APRÈS l'envoi du devis. Elle doit donc se lire et se
    # PLANIFIER depuis la fiche du lead, pas seulement depuis l'app terrain.
    #
    # Ces trois routes appartiennent au CRM et portent SA portée de visibilité
    # (``crm_voir`` / ``crm_modifier``) — délibérément PAS la portée dure « mes
    # visites » de l'app terrain (VTA6), qui reste intacte sur SES routes : la
    # recopier ici cacherait à un responsable CRM les visites de son propre
    # dossier. La lecture des visites passe par le SÉLECTEUR de ``apps.visites``
    # (frontière M3) : ce module n'importe jamais ses modèles.

    @extend_schema(responses=inline_serializer('CrmLeadVisites', {
        'visites': serializers.ListField(child=serializers.DictField()),
        'avertissement_sans_devis': serializers.CharField(),
        'rappel_juridique': serializers.CharField(),
    }))
    @action(detail=True, methods=['get'], url_path='visites',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def visites(self, request, pk=None):
        """Les visites techniques du lead, de la plus récente à la plus ancienne.

        CAD123 — plus l'AVERTISSEMENT (jamais un blocage) quand aucun devis
        n'est encore parti : la règle « la visite se propose après le devis »
        et son effet de bord juridique (CAD122), textes du serveur — deux
        chaînes vides sinon."""
        from apps.visites.selectors import visites_pour_lead

        from .cadence_visite import avertissement_visite

        lead = self.get_object()
        avertissement = avertissement_visite(lead)
        return Response({
            'visites': visites_pour_lead(lead),
            'avertissement_sans_devis': avertissement[
                'avertissement_sans_devis'],
            'rappel_juridique': avertissement['rappel_juridique'],
        })

    @extend_schema(request=sd.corps('CrmPlanifierVisiteRequest', commercial=serializers.IntegerField(required=False), date_prevue=serializers.CharField(), etape=serializers.CharField(required=False), note_etape=serializers.CharField(required=False), notes=serializers.CharField(required=False), replanifier=serializers.BooleanField(required=False)), responses=inline_serializer('CrmLeadVisitePlanifiee', {
        'visite': serializers.DictField(),
        'prochaine_touche': serializers.DictField(allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='visites/planifier',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def planifier_visite(self, request, pk=None):
        """POSE un rendez-vous de visite technique sur ce lead.

        Corps : ``{date_prevue: 'AAAA-MM-JJ', commercial?: <id>, notes?,
        replanifier?, etape?, note_etape?}``. Chaque refus NOMME son champ
        (règle fondateur 08/09/2026) : jamais un « non enregistré » générique.

        L'écriture elle-même vit dans ``apps.visites.services.planifier_visite``
        — la visite appartient à cette app, le CRM ne fait que la lui demander.
        Les effets de bord (cadence recalée, chatter, notification à l'assigné)
        naissent de l'événement ``visite_planifiee``, pas d'ici.

        SUIVI E18 (30/09/2026) — la planification CLÔT la touche qui l'a
        demandée : ``etape`` (une touche de CE lead) et ``note_etape`` ; après
        la planification réussie, la touche encore à faire est close
        « visite acceptée » (``services.clore_etape_apres_planification``).
        ``replanifier`` DÉPLACE le rendez-vous en attente (SUIVI E5). La
        réponse porte aussi ``prochaine_touche`` (forme E9, ou ``null``).
        """
        from django.utils.dateparse import parse_date

        from apps.visites.selectors import ligne_visite_pour_lead
        from apps.visites.services import planifier_visite

        from .cadence_visite import clore_etape_apres_planification
        from .cadence_plan import _prochaine_touche_a_faire

        lead = self.get_object()
        brut = (request.data.get('date_prevue') or '').strip()
        date_prevue = parse_date(brut) if brut else None
        if brut and date_prevue is None:
            return Response(
                {'date_prevue': ['Date illisible (format AAAA-MM-JJ '
                                 'attendu).']},
                status=status.HTTP_400_BAD_REQUEST)

        commercial = None
        brut_commercial = request.data.get('commercial')
        if brut_commercial not in (None, '', 0):
            from django.contrib.auth import get_user_model
            # Borné à la SOCIÉTÉ de l'appelant : un id d'un autre locataire est
            # indiscernable d'un id inconnu (on ne confirme pas son existence).
            commercial = (get_user_model().objects
                          .filter(pk=brut_commercial,
                                  company=request.user.company)
                          .first())
            if commercial is None:
                return Response(
                    {'commercial': ['Utilisateur inconnu dans votre '
                                    'société.']},
                    status=status.HTTP_400_BAD_REQUEST)

        # SUIVI E18 — la touche qui a demandé la planification : une touche
        # de CE lead (donc de la société de l'appelant, ``get_object`` étant
        # borné), vérifiée AVANT toute écriture.
        etape = None
        brut_etape = request.data.get('etape')
        if brut_etape not in (None, '', 0):
            if str(brut_etape).isdigit():
                etape = lead.relance_etapes.filter(pk=int(brut_etape)).first()
            if etape is None:
                return Response(
                    {'etape': ['Étape de relance inconnue sur ce lead.']},
                    status=status.HTTP_400_BAD_REQUEST)
        replanifier = request.data.get('replanifier') in (
            True, 'true', 'True', '1', 1)
        # COCKPIT-CONTRÔLE B8 — l'échéance que la touche avait au moment où on
        # la TRAITE, lue AVANT la planification : celle-ci décale le suivi
        # pendant (donc cette touche) jusqu'après la visite.
        echeance_avant = (None if etape is None else
                          (etape.due_at, etape.due_date, etape.due_initial_at))

        visite, erreurs = planifier_visite(
            lead, request.user, date_prevue, commercial=commercial,
            notes=(request.data.get('notes') or ''), replanifier=replanifier)
        if erreurs:
            return Response(erreurs, status=status.HTTP_400_BAD_REQUEST)
        if etape is not None:
            clore_etape_apres_planification(
                etape, request.user,
                note=(request.data.get('note_etape') or ''),
                echeance_avant=echeance_avant)
        return Response({'visite': ligne_visite_pour_lead(visite),
                         'prochaine_touche': _prochaine_touche_publique(
                             _prochaine_touche_a_faire(lead))},
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=sd.corps('CrmLocataireRequest', proprietaire=serializers.DictField(required=False), proprietaire_inconnu=serializers.BooleanField(required=False)), responses=inline_serializer('CrmLeadLocataire', {
        'locataire': serializers.BooleanField(),
        'propose': serializers.ListField(child=serializers.CharField()),
        'motif_perte': serializers.CharField(),
    }))
    @action(detail=True, methods=['get', 'post'], url_path='locataire')
    def locataire(self, request, pk=None):
        """CAD164 — [TRANCHÉ 21/09/2026] le client est LOCATAIRE.

        ``GET`` : ce que l'écran propose — les deux suites (créer la fiche du
        propriétaire, ou « Perdu — Locataire ») quand la réponse est
        « locataire ».

        ``POST`` : ``{proprietaire: {nom, prenom?, telephone|whatsapp}}`` crée
        (ou relie, s'il est déjà connu) la fiche du propriétaire, liée au
        locataire — 201 ; ``{proprietaire_inconnu: true}`` clôt la fiche du
        locataire avec le motif EXISTANT « Locataire » — 200. Chaque refus
        NOMME son champ. Aucune valeur d'énumération neuve (contrat
        ``lead_locataire``)."""
        from .cadence_reponses import (
            clore_locataire_sans_proprietaire,
            creer_lead_proprietaire,
            proposition_locataire,
            refus_proprietaire,
        )

        lead = self.get_object()
        if request.method == 'GET':
            return Response(proposition_locataire(lead))

        if request.data.get('proprietaire_inconnu') is True:
            clore_locataire_sans_proprietaire(lead, request.user)
            lead.refresh_from_db()
            return Response({
                'issue': 'perdu_locataire',
                'lead_proprietaire': None,
                'locataire': {'id': lead.pk, 'ownership': lead.ownership,
                              'perdu': lead.perdu,
                              'motif_perte': lead.motif_perte or ''},
            })

        donnees = request.data.get('proprietaire')
        if donnees is None:
            return Response(
                {'proprietaire': ['« Propriétaire » : ses coordonnées, ou '
                                  '« propriétaire inconnu » pour clore la '
                                  'fiche avec le motif « Locataire ».']},
                status=status.HTTP_400_BAD_REQUEST)
        refus = refus_proprietaire(donnees)
        if refus:
            # Les erreurs de CHAMP vivent sous `proprietaire` (même forme que
            # le corps) ; une charge illisible est refusée sur `proprietaire`.
            corps = refus if 'proprietaire' in refus else {'proprietaire': refus}
            return Response(corps, status=status.HTTP_400_BAD_REQUEST)
        # ACRM7 — rapprochement borné aux leads en portée (D-ACRM-1).
        proprietaire, cree = creer_lead_proprietaire(
            lead, request.user, donnees, queryset=self._leads_en_portee())
        lead.refresh_from_db()
        return Response({
            'issue': 'proprietaire_cree' if cree else 'proprietaire_relie',
            'lead_proprietaire': {'id': proprietaire.pk,
                                  'nom': proprietaire.nom,
                                  'prenom': proprietaire.prenom or ''},
            'locataire': {'id': lead.pk, 'ownership': lead.ownership,
                          'perdu': lead.perdu,
                          'motif_perte': lead.motif_perte or ''},
        }, status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK)

    @extend_schema(parameters=[sd.P_CLE], responses=inline_serializer('CrmLeadMessageVisite', {
        'corps_fr': serializers.CharField(),
        'corps_darija': serializers.CharField(),
    }))
    @action(detail=True, methods=['get'], url_path='message-visite',
            permission_classes=[HasPermissionOrLegacy('crm_voir')])
    def message_visite(self, request, pk=None):
        """Le message de visite à copier-coller, rendu côté serveur.

        ``?cle=visite_proposition|visite_confirmation``. MÊME machinerie que
        les messages de cadence : ``{conseiller}`` est le RESPONSABLE du lead
        (jamais un prénom codé en dur), et une phrase dont le placeholder n'a
        pas de valeur réelle est OMISE — un lead sans date de visite ne reçoit
        donc pas « la visite prévue  chez vous ».

        LECTURE PURE : le serveur REND, il n'ENVOIE pas (décision D5).
        """
        from .serializers import pii_masquee_pour
        from .cadence_messages import cles_message_visite_du_lead, message_visite_pour_lead

        cle = (request.query_params.get('cle') or '').strip()
        lead = self.get_object()
        # CAD111 — les liens wa.me sont construits ICI (E.164) ; un rôle sans
        # `client_pii_voir` ne reçoit aucun numéro (liens nuls, `phone` vide).
        # AGR526 — `dossier_fda` / `dossier_8221` seulement pour le lead dont
        # le playbook de segment les confirme.
        rendu = message_visite_pour_lead(
            lead, cle, user=request.user,
            masquer_numero=pii_masquee_pour(request.user))
        if rendu is None:
            return Response(
                {'cle': ['Message de visite inconnu « ' + cle + ' ». Clés '
                         'connues : '
                         + ', '.join(cles_message_visite_du_lead(lead)) + '.']},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(rendu)

    @extend_schema(request=sd.corps('CrmMessageVisiteOuvertRequest', cle=serializers.CharField(), etape=serializers.CharField(required=False), langue=serializers.CharField(required=False)), responses=inline_serializer('CrmMessageVisiteOuvert', {
        'journalise': serializers.BooleanField(),
        'cle': serializers.CharField(),
        'langue': serializers.CharField(),
        'etape': serializers.IntegerField(allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='message-visite/ouvert',
            permission_classes=[IsResponsableOrAdmin])
    def message_visite_ouvert(self, request, pk=None):
        """CAD111 — le message de VISITE vient d'être OUVERT dans WhatsApp.

        Jumeau POST de la lecture ``message-visite`` (même patron que la
        touche : ``window.open`` d'abord, puis cet appel best-effort). Corps :
        ``{cle, langue, etape?}``. Journalise « WhatsApp ouvert » au chatter
        (tentative + premier contact + AuditLog) — JAMAIS « fait » : aucune
        issue, aucune touche avancée. ``etape`` (une touche à faire de CE lead)
        rattache l'ouverture à la touche, que son panneau « Fait » reconnaît.
        Refus 400 nommant le champ (``cle``, ``langue``, ``etape``)."""
        from .cadence_messages import (
            LANGUES_MESSAGE_VISITE,
            cle_message_visite_autorisee,
            cles_message_visite_du_lead,
            journaliser_message_visite_ouvert,
        )
        lead = self.get_object()
        cle = (request.data.get('cle') or '').strip()
        # AGR526 — mêmes clés que la lecture `message-visite` pour CE lead.
        if not cle_message_visite_autorisee(lead, cle):
            raise DRFValidationError({'erreurs': {'cle': (
                f'« Message de visite » inconnu : « {cle} ». Clés connues : '
                + ', '.join(cles_message_visite_du_lead(lead)) + '.')}})
        langue = (request.data.get('langue') or 'fr').strip()
        if langue not in LANGUES_MESSAGE_VISITE:
            raise DRFValidationError({'erreurs': {'langue': (
                f'« Langue du message » inconnue : « {langue} ». Langues : '
                + ', '.join(LANGUES_MESSAGE_VISITE) + '.')}})
        etape = None
        brut = str(request.data.get('etape') or '').strip()
        if brut:
            if brut.isdigit():
                etape = (RelanceEtape.objects
                         .filter(pk=int(brut), lead=lead, company=lead.company,
                                 statut=RelanceEtape.Statut.A_FAIRE)
                         .first())
            if etape is None:
                raise DRFValidationError({'erreurs': {'etape': (
                    '« Touche » : aucune touche à faire de ce lead ne porte '
                    f'l’identifiant « {brut} ».')}})
        journaliser_message_visite_ouvert(
            lead, request.user, cle=cle, langue=langue, etape=etape)
        try:
            from apps.audit.models import AuditLog
            from apps.audit.recorder import record
            record(AuditLog.Action.WHATSAPP, instance=lead,
                   detail=f'Message de visite ouvert ({cle})')
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('CAD111: AuditLog non écrit (lead #%s)', lead.pk,
                           exc_info=True)
        return Response({'journalise': True, 'cle': cle, 'langue': langue,
                         'etape': etape.pk if etape is not None else None})

    @extend_schema(request={'application/json': sd.corps('CrmNoterRequest', body=serializers.CharField()), 'multipart/form-data': sd.corps('CrmNoterMultipartRequest', body=serializers.CharField(), file=serializers.FileField(required=False))}, responses={201: LeadActivitySerializer})
    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin],
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    @_geste_atomique
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
            # ACRM22 — supprimée du stockage si le geste échoue ensuite.
            request._acrm22_cles.append(meta.get('file_key'))
            ct = ContentType.objects.get(app_label='crm', model='lead')
            attachment = Attachment.objects.create(
                company=request.user.company, content_type=ct, object_id=lead.id,
                uploaded_by=request.user, **meta)
        act = activity.log_note(lead, request.user, body or '📎 Pièce jointe')
        if attachment:
            act.attachment = attachment
            act.save(update_fields=['attachment'])
        # FG28/MRY19 — première note = premier contact. La condition
        # « lead encore en NEW » a DISPARU : un lead saisi à la main, déjà
        # CONTACTED, ne recevait jamais d'horodatage et sortait du KPI.
        from .leads_premier_contact import marquer_premier_contact
        marquer_premier_contact(lead)
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    # FG30 — Interaction typée (appel/e-mail) dans le chatter ─────────────────
    @extend_schema(request=sd.corps('CrmLogInteractionRequest', kind=serializers.ChoiceField(choices=[LeadActivity.Kind.APPEL, LeadActivity.Kind.EMAIL, LeadActivity.Kind.WHATSAPP]), body=serializers.CharField(required=False, allow_blank=True), outcome=serializers.ChoiceField(choices=[k for k, _ in LeadActivity.OUTCOMES if k], required=False), rappel_le=serializers.CharField(required=False), rappel_heure=serializers.CharField(required=False)), responses={201: LeadActivitySerializer})
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
        # MRY10 — le WhatsApp est le canal PRINCIPAL de Meryem : il devait
        # être journalisable comme un appel, pas noyé dans une note libre.
        valid_kinds = {LeadActivity.Kind.APPEL, LeadActivity.Kind.EMAIL,
                       LeadActivity.Kind.WHATSAPP}
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
        # MRY10 — « rappelez-moi jeudi » : le rappel demandé au téléphone
        # DÉPLACE la touche de cadence au lieu d'ouvrir un second système de
        # rappel à côté d'elle.
        rappel_le = (request.data.get('rappel_le') or '').strip()
        rappel_heure = (request.data.get('rappel_heure') or '').strip()
        quand = None
        if outcome == 'rappel' and rappel_le:
            quand = _parse_rappel(rappel_le, rappel_heure)
            if quand is None:
                return Response(
                    {'rappel_le': 'Date invalide (AAAA-MM-JJ attendu, '
                                  'heure HH:MM optionnelle).'},
                    status=status.HTTP_400_BAD_REQUEST)
        # ALEA30 — l'interaction, le premier contact et le report de la
        # touche forment UNE transaction : un report en panne n'écrit rien
        # (avant : chatter écrit puis 500, touche jamais déplacée).
        from django.db import transaction
        from .cadence_plan import reporter_prochaine_touche
        from .leads_premier_contact import marquer_premier_contact
        with transaction.atomic():
            act = LeadActivity.objects.create(
                lead=lead,
                company=lead.company,
                kind=kind,
                body=body or None,
                outcome=outcome,
                user=request.user,
            )
            # FG28/MRY19 — tout contact direct = première prise de contact,
            # posée par LA source unique. Aucune chaîne d'étape ici.
            marquer_premier_contact(lead)
            if quand is not None:
                try:
                    reporter_prochaine_touche(lead, request.user, quand)
                except Exception as exc:  # noqa: BLE001 — tout est annulé
                    logger.warning(
                        'ALEA30: report de touche échoué sur le lead #%s — '
                        'interaction annulée', lead.pk, exc_info=True)
                    raise ReportToucheEchoue() from exc
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=sd.corps('CrmBulkLeadsRequest', action=serializers.ChoiceField(choices=sorted(BULK_ACTIONS)), ids=sd.ids_requis()), responses=sd.OBJ)
    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsResponsableOrAdmin])
    def bulk(self, request):
        """Actions EN MASSE sur une sélection de leads (liste + kanban).

        Corps : {ids: [...], action: 'reassign'|'add_tag'|'remove_tag'|
        'set_stage'|'set_relance'|'clear_relance'|'set_perdu'|'unset_perdu'|
        'archive'|'unarchive'|'delete', + paramètres de l'action}. La société et
        l'acteur viennent du serveur ; la règle métier (funnel, garde-fous,
        Historique « en masse ») vit dans services.apply_bulk_action."""
        from .fiche_bulk import BULK_ACTIONS, BULK_ADMIN_ONLY, apply_bulk_action
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
            # ALEA27 — la sélection est bornée par la portée du viewset : un
            # id hors portée (lead d'un collègue hors équipe) est ignoré.
            result = apply_bulk_action(
                company=request.user.company, user=request.user,
                lead_ids=ids, op=op, params=request.data,
                queryset=self._leads_en_portee())
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @extend_schema(request=sd.corps('CrmLeadsExportRequest', ids=sd.ids_requis()), responses=sd.EXPORT_XLSX)
    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de leads en .xlsx (société courante).

        Corps : {ids: [...]} — la sélection. Vide → 400 (l'UI exporte une
        sélection). Borné à la société de l'utilisateur."""
        from .exports import export_leads_xlsx
        from .fiche_bulk import coerce_id_list
        raw_ids = request.data.get('ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response({'detail': 'Sélectionnez au moins un lead.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = coerce_id_list(raw_ids)
        except ValueError:
            return Response({'detail': 'Identifiant de lead invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # CRX16 — l'export passe par ``self.get_queryset()`` (parité
        # ClientViewSet.export_xlsx) : la PORTÉE DE VISIBILITÉ du rôle
        # s'applique enfin. Le filtre société brut d'origine exportait tous
        # les leads de la société, y compris ceux qu'un rôle restreint ne peut
        # même pas ouvrir dans la liste.
        from django.db.models import Prefetch
        from apps.ventes.models import Devis
        leads = (
            self.get_queryset()
            .filter(id__in=ids)
            # On remplace les prefetch de la LISTE par un prefetch ORDONNÉ :
            # ``lead_row`` a besoin du DERNIER devis. Un prefetch nu ne suffit
            # pas — ``lead.devis.order_by(...).first()`` re-requête et ignore
            # le cache (1 requête PAR LIGNE, plus 1 par devis pour ses lignes
            # via ``total_ttc``). Le tri vit donc DANS le prefetch, exposé sous
            # ``devis_ordonnes`` (lu par ``exports.lead_row``) : O(1) requêtes
            # quelle que soit la taille de la sélection.
            .prefetch_related(None)
            .select_related('owner')
            .prefetch_related(Prefetch(
                'devis',
                queryset=Devis.objects.order_by(
                    '-date_creation').prefetch_related('lignes'),
                to_attr='devis_ordonnes'))
            .order_by('id'))
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT,
               detail=f'Export leads (.xlsx) — {len(ids)} ligne(s)')
        # ACRM4 — sans ``client_pii_voir`` : export sans colonnes PII.
        from .serializers import pii_masquee_pour
        return export_leads_xlsx(
            leads, masquer_pii=pii_masquee_pour(request.user))


class LeadTagViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """Étiquettes de lead gérées (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L780) : une étiquette référencée par des leads
    ne se supprime pas — l'admin l'archive plutôt (l'historique est préservé).
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : LeadTag n'est pas dans TRACKED_MODELS."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = LeadTag.objects.all()
    serializer_class = LeadTagSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        # MRY2 — amorçage paresseux des étiquettes standard. ACRM25 — UNE
        # fois par société, quand la liste est VIDE (patron ``seed_canaux``) :
        # à chaque GET, une étiquette standard supprimée ou renommée
        # ressuscitait.
        if (request.user.company_id and not LeadTag.objects.filter(
                company=request.user.company).exists()):
            seed_tags(request.user.company)
        return super().list(request, *args, **kwargs)

    def perform_update(self, serializer):
        """ACRM25 — renommer une étiquette EN USAGE renomme aussi le jeton
        dans ``Lead.tags`` (une ligne « en masse » au chatter de chaque
        lead) : sinon l'étiquette renommée comptait 0 lead et les fiches
        gardaient l'ancien libellé."""
        ancien = serializer.instance.nom
        tag = serializer.save()
        if tag.nom != ancien:
            _renommer_tag_sur_leads(tag.company, ancien, tag.nom,
                                    self.request.user)

    def destroy_guard_message(self, tag):
        if _tag_en_usage(tag.company, tag.nom) > 0:
            return ("Cette étiquette est utilisée par des leads — "
                    "archivez-la plutôt que de la supprimer.")
        return None


# PUB28 — motifs de perte standards, seedés au premier chargement (idempotent,
# additive-only — même patron que ``seed_canaux`` ci-dessous). ``est_junk=True``
# = le lead n'était jamais un vrai prospect ; ``False`` = perte commerciale
# réelle. Vocabulaire pris tel quel dans le texte de la tâche fondateur.
_DEFAULT_MOTIFS_PERTE = [
    ('Numéro invalide', True),
    ('Spam/bot', True),
    ('Hors zone', True),
    ('Jamais répondu', True),
    ('Prix', False),
    ('Concurrent', False),
    ('Reporté', False),
    # MRY2 — les cinq motifs que Meryem utilise réellement au téléphone et qui
    # manquaient : sans eux, « Autre » avalait les vraies raisons et le KPI
    # « perdus avec motif » (MRY21) ne disait plus rien. Aucun n'est « junk » :
    # ce sont des pertes commerciales réelles, pas des faux prospects.
    ('Locataire', False),
    ('Consommation trop faible', False),
    ('Déjà équipé', False),
    ('Ne plus contacter', False),
    ('Devis refusé', False),
    # AGR521 (05/10/2026) — pompage : un accord refusé (subvention FDA, DPA)
    # ou un forage trop faible finissait en « Autre » / « Reporté », et rien
    # n'était appris. Pertes commerciales réelles, jamais « junk ».
    ('Subvention non obtenue', False),
    ('Eau insuffisante / forage', False),
    # CIQ514 (06/10/2026) — pertes d'une affaire PRO (commerce, industrie) : la
    # banque a refusé, la direction a reporté, le bailleur des murs a dit non,
    # le budget passe à l'exercice suivant… Jusqu'ici tout finissait en
    # « Reporté » ou « Autre » et rien n'était appris. Pertes commerciales
    # réelles, jamais « junk » ; ajoutées SANS migration par
    # `completer_motifs_perte`. Libellés ✎ à valider par Reda.
    ('Financement refusé (banque / organisme)', False),
    ('Décision interne reportée', False),
    ('Refus du bailleur des murs', False),
    ("Budget reporté à l'exercice suivant", False),
    ('Contrainte de raccordement au réseau', False),
    ('Toiture ou structure inadaptée (visite)', False),
    ('Consultation : autre prestataire retenu', False),
]

# MRY2 — étiquettes standard. `Lead.tags` reste un TEXTE LIBRE : cette liste
# n'est qu'une source de suggestions et de couleurs, jamais une contrainte.
# Les deux dernières sont celles que `poser_tag_lead` écrit à la clôture d'une
# cadence (MRY11) : les seeder évite qu'elles arrivent sans couleur ni libellé
# dans l'écran Paramètres → CRM.
_DEFAULT_TAGS = [
    'Compare les devis',
    'Facilité de paiement',
    'Décision à plusieurs',
    "Client à l'étranger",
    'En construction',
    'Déjà équipé',
    'Attente facture',
    'Injoignable 6 appels',
    'Devis sans suite',
    # MRY30 — l'étiquette du dormant JAMAIS CHIFFRÉ, posée par
    # `services.placer_anciens_leads` : seedée pour la même raison que les
    # deux précédentes (arriver sans couleur ni libellé dans Paramètres → CRM
    # ferait croire à une saisie libre).
    'Jamais chiffré',
    # SUIVI E26 (30/09/2026) — l'étiquette de clôture de la cadence courte
    # « deuxième affaire » (`services._CLOTURE_TAG_DEUXIEME_AFFAIRE`), seedée
    # comme les autres étiquettes de clôture ; un test garde les deux libellés
    # identiques.
    'Deuxième affaire sans réponse',
    # AGR520 (05/10/2026) — l'étiquette posée par la réponse « En attente
    # d'un accord (DPA / banque) » (`services.TAG_ATTENTE_ACCORD`).
    'Attend un accord (DPA / banque)',
    # CIQ508 (06/10/2026) — une étiquette par RAISON de l'attente B2B
    # (`services.RAISONS_ATTENTE`) ; `administration` pose celle d'AGR520.
    'Attend la direction / le comité',
    "Attend la banque / l'organisme de financement",
    'Attend le bailleur des murs',
    "Budget de l'exercice suivant",
    'Consultation en cours',
]


def seed_tags(company):
    """MRY2 — pose les étiquettes standard manquantes (idempotent, ADDITIF).

    `LeadTag` n'avait aucun seeder : chaque société démarrait avec une liste
    vide. `get_or_create` par `(company, nom)` — jamais de doublon, jamais de
    modification d'une étiquette existante (couleur ou archivage compris),
    jamais de suppression."""
    if company is None:
        return
    for nom in _DEFAULT_TAGS:
        LeadTag.objects.get_or_create(company=company, nom=nom,
                                      defaults={'couleur': ''})


def completer_motifs_perte(company):
    """MRY2 — ajoute les motifs standard MANQUANTS d'une société.

    `seed_motifs_perte` ne seede QUE les sociétés qui n'ont AUCUN motif : une
    société déjà personnalisée n'a donc jamais reçu les cinq motifs de MRY2.
    Cette fonction complète, sans jamais toucher un motif existant (libellé,
    `est_junk`, archivage) ni en supprimer un.

    ACRM25 — chaque motif standard n'est proposé qu'UNE fois par société
    (``MotifPerteStandardPropose``) : un motif standard renommé ou supprimé
    par la société ne ressuscite jamais ; un motif standard ajouté plus tard
    au référentiel est proposé une fois."""
    from .models import MotifPerteStandardPropose

    if company is None:
        return
    deja = set(MotifPerteStandardPropose.objects.filter(
        company=company).values_list('nom', flat=True))
    for nom, est_junk in _DEFAULT_MOTIFS_PERTE:
        if nom in deja:
            continue
        MotifPerte.objects.get_or_create(
            company=company, nom=nom, defaults={'est_junk': est_junk})
        MotifPerteStandardPropose.objects.get_or_create(
            company=company, nom=nom)


def _renommer_motif_sur_leads(company, ancien, nouveau, user):
    """ACRM25 — ``Lead.motif_perte`` suit le renommage du motif, avec une
    ligne « modification en masse » au chatter de chaque lead."""
    for lead in Lead.objects.filter(company=company,
                                    motif_perte__iexact=ancien):
        activity.log_bulk_change(lead, user, 'motif_perte',
                                 lead.motif_perte, nouveau)
        Lead.objects.filter(pk=lead.pk).update(motif_perte=nouveau)


def _renommer_tag_sur_leads(company, ancien, nouveau, user):
    """ACRM25 — le JETON ``ancien`` de ``Lead.tags`` (texte libre séparé
    par des virgules, comparaison insensible à la casse) devient
    ``nouveau`` ; une ligne « modification en masse » au chatter de chaque
    lead touché."""
    cible = (ancien or '').strip().casefold()
    if not cible:
        return
    for lead in Lead.objects.filter(company=company, tags__icontains=ancien):
        jetons = [(t or '').strip() for t in (lead.tags or '').split(',')]
        if not any(j.casefold() == cible for j in jetons):
            continue
        nouveaux = [nouveau if j.casefold() == cible else j
                    for j in jetons if j]
        valeur = ', '.join(nouveaux)[:500]
        activity.log_bulk_change(lead, user, 'tags', lead.tags, valeur)
        Lead.objects.filter(pk=lead.pk).update(tags=valeur)


def seed_motifs_perte(company):
    """Crée les motifs de perte standards pour une société qui n'en a AUCUN
    (idempotent, additif) — mêmes garanties que ``seed_canaux`` : ne touche
    jamais une liste déjà personnalisée par le fondateur, jamais de doublon
    (``get_or_create`` par nom), jamais de modification d'un motif existant."""
    from .models import MotifPerteStandardPropose

    if company is None or MotifPerte.objects.filter(company=company).exists():
        return
    for nom, est_junk in _DEFAULT_MOTIFS_PERTE:
        MotifPerte.objects.get_or_create(
            company=company, nom=nom, defaults={'est_junk': est_junk})
        # ACRM25 — mémoire : proposé une fois, jamais ressuscité.
        MotifPerteStandardPropose.objects.get_or_create(
            company=company, nom=nom)


class MotifPerteViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """Motifs de perte gérés (Paramètres → CRM). Lecture tout rôle,
    écriture admin. Garde-fou (L779) : un motif utilisé par des leads ne se
    supprime pas — l'admin l'archive plutôt (comme pour les canaux).
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : MotifPerte n'est pas dans TRACKED_MODELS."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = MotifPerte.objects.all()
    serializer_class = MotifPerteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        # PUB28 — amorçage paresseux : à la 1re consultation, on peuple les
        # motifs de perte standards de la société (même patron que
        # CanalViewSet.list — préserve le comportement existant : une société
        # ayant déjà des motifs n'est jamais touchée).
        if request.user.company_id:
            seed_motifs_perte(request.user.company)
            # MRY2 — `seed_motifs_perte` ne sert QUE les sociétés sans aucun
            # motif : une liste déjà personnalisée n'avait donc jamais reçu
            # les motifs standard ajoutés après coup. On COMPLÈTE ici, sans
            # jamais modifier ni supprimer un motif existant. ACRM25 — chaque
            # motif standard n'est proposé qu'UNE fois (mémoire
            # ``MotifPerteStandardPropose``) : renommé ou supprimé, il ne
            # ressuscite plus.
            completer_motifs_perte(request.user.company)
        return super().list(request, *args, **kwargs)

    def perform_update(self, serializer):
        """ACRM25 — renommer un motif EN USAGE renomme aussi
        ``Lead.motif_perte`` des leads qui le portent (une ligne « en masse »
        au chatter de chacun)."""
        ancien = serializer.instance.nom
        motif = serializer.save()
        if motif.nom != ancien:
            _renommer_motif_sur_leads(motif.company, ancien, motif.nom,
                                      self.request.user)

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
    ('google_ads', 'Google Ads', False),
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
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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


class ParrainageViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """N98 — parrainages. Lecture tout rôle, écriture responsable/admin.

    À la création, la récompense est pré-remplie depuis Paramètres
    (referral_reward) quand elle n'est pas fournie. ?stats=1 ajoute un petit
    tableau de bord (totaux par statut + récompenses)."""
    # ACRM9 — lectures bornées à la portée (leads : filleul_lead ;

    # clients : parrain, filleul_client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('filleul_lead',)

    portee_clients = ('parrain', 'filleul_client')
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

    @extend_schema(responses=sd.OBJ)
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

@extend_schema_view(list=extend_schema(parameters=[sd.param('all', description='Inclure aussi les payloads déjà rattachés.')]))
class WebsiteLeadPayloadViewSet(_PorteeEnfantsMixin, TenantMixin, viewsets.ReadOnlyModelViewSet):
    """QX16 — « Jamais perdre un lead » (webhooks.py) devient opérationnel :
    liste des payloads bruts, avec un filtre par défaut sur ceux qui méritent
    une action (mapping en erreur OU sans lead rattaché). ``?all=1`` renvoie
    la liste complète (comportement admin). LECTURE SEULE — la seule écriture
    possible est l'action ``replay``, qui rejoue EXACTEMENT le même mapping
    que le webhook (jamais une seconde implémentation)."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    # ACRM52 — détail/rejeu désormais adressables hors filtre « à traiter » :
    # bornés à la portée du lead rattaché (sans lead : visible, comme avant).
    portee_leads = ('lead',)
    portee_clients = ()
    queryset = WebsiteLeadPayload.objects.select_related('lead').all()
    serializer_class = WebsiteLeadPayloadSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        # AACQ30 — le filtre « à traiter » ne vaut que pour la LISTE : un
        # payload déjà rattaché reste adressable en détail et rejouable
        # (« Déjà rattaché au lead #… », jamais 404 ni second lead).
        if self.action != 'list' or self.request.query_params.get('all'):
            return qs
        # Défaut : ce qui mérite une action — erreur de mapping OU jamais
        # rattaché à un lead (payload traité mais orphelin, ex. ping
        # d'engagement QW7 sans lead correspondant — n'est pas une PERTE,
        # mais reste utile à voir).
        from django.db.models import Q
        return qs.filter(Q(error__gt='') | Q(lead__isnull=True))

    @extend_schema(request=None, responses={200: sd.OBJ, 422: sd.OBJ})
    @action(detail=True, methods=['post'], url_path='replay',
            permission_classes=[IsResponsableOrAdmin])
    def replay(self, request, pk=None):
        """QX16 — rejoue ce payload à travers le mapping webhook standard.

        CRX2 — le chemin de rejeu suit la SOURCE de la ligne : site web →
        ``replay_website_lead_payload``, Meta Lead Ads →
        ``replay_meta_lead_payload``. Chacun réutilise le mapping de SON
        webhook (jamais une seconde implémentation).

        Renvoie 200 avec le lead résultant en cas de succès, 422 si le rejeu
        échoue encore (le payload reste rejouable — jamais supprimé)."""
        from .webhooks import (
            replay_meta_lead_payload, replay_website_lead_payload)

        payload = self.get_object()
        if payload.source == WebsiteLeadPayload.Source.META_LEAD_ADS:
            ok, detail, lead = replay_meta_lead_payload(payload)
        else:
            ok, detail, lead = replay_website_lead_payload(payload)
        payload.refresh_from_db()
        data = WebsiteLeadPayloadSerializer(payload).data
        if not ok:
            return Response({'detail': detail, 'payload': data}, status=422)
        return Response({'detail': detail, 'payload': data}, status=200)


# ── DC12 — Profil site/énergie réutilisable par client ───────────────────────

@extend_schema_view(list=extend_schema(parameters=[sd.param('client', OpenApiTypes.INT)]))
class SiteProfileViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """DC12 — profil site/énergie réutilisable, attaché au client.

    Saisi une fois par client, le générateur de devis le pré-remplit ensuite
    (y compris pour les devis sans lead). Société ET créateur forcés côté
    serveur (jamais lus du corps de requête). Lecture tout rôle, écriture
    responsable/admin. Filtrable par ?client=<id>."""
    # ACRM9 — lectures bornées à la portée (leads : — ;

    # clients : client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ()

    portee_clients = ('client',)
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
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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
    ADMIN. Société forcée côté serveur (TenantMixin).

    ACRM26 (C-ACRM-021) — l'écriture (création, modification dont
    ``responsable``, suppression) passe au palier ADMIN : une équipe pilote
    une PORTÉE (le rollup du forecast, les cartes « Mes équipes ») — un
    Commercial pouvait se nommer responsable d'une équipe et lire son
    pipeline."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = EquipeCommerciale.objects.prefetch_related('membres').all()
    serializer_class = EquipeCommercialeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]


# ── FG36 — Modèles de messages WhatsApp/SMS ───────────────────────────────────


# ── QJ20 — Rendez-vous (visites commerciales/techniques) ──────────────────────

def _libelle_statut_rdv(statut):
    """ACRM23 — le libellé FR d'un statut de rendez-vous."""
    return dict(Appointment.Statut.choices).get(statut, statut or '—')


def _quand_rdv(quand):
    """ACRM23 — « JJ/MM/AAAA à HH:MM » (heure de Casablanca)."""
    if quand is None:
        return '—'
    from . import horaires
    return quand.astimezone(horaires.CASABLANCA).strftime('%d/%m/%Y à %H:%M')


def _noter_rdv(lead, user, corps):
    """ACRM23 — une ligne de chatter du lead pour un geste sur un RDV,
    l'acteur nommé (jamais un prénom en dur)."""
    if lead is None:
        return
    qui = getattr(user, 'username', '') or 'système'
    activity.log_note(lead, user, f'{corps} (par {qui}).')


@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD]))
class AppointmentViewSet(CompanyScopedModelViewSet):
    """QJ20 — Rendez-vous planifiés sur les leads (visites commerciales/techniques).

    Lecture tout rôle, écriture responsable/admin.
    Toujours scopé par société (TenantMixin). La société est posée côté serveur
    depuis l'utilisateur actif (jamais lue du corps de requête — multi-tenant).
    Filtre ?lead=<id> pour n'avoir que les RDV d'un lead donné.
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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
        # ALEA27 — portée équipe/sous-arbre : seuls les RDV d'un lead dans la
        # portée (responsable visible) ou créés par un utilisateur visible.
        # Portée 'all' (admin) → inchangé.
        qs = scope_queryset(qs, self.request.user, ['lead__owner', 'created_by'])
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Company et created_by toujours posés côté serveur."""
        from .visites_rdv import book_appointment
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

    def perform_update(self, serializer):
        """ACRM23 (C-ACRM-016) — l'annulation, le changement de statut et le
        DÉPLACEMENT d'un rendez-vous sont journalisés au chatter du lead
        (acteur + ancien → nouveau) ; un déplacement RÉARME le rappel
        (``reminder_sent=False``). Un PATCH qui ne change rien reste muet."""
        avant = serializer.instance
        ancien_statut = avant.statut
        ancien_quand = avant.scheduled_at
        ancien_lead_id = avant.lead_id
        rdv = serializer.save()
        changements = []
        if rdv.statut != ancien_statut:
            changements.append(
                f'{_libelle_statut_rdv(ancien_statut)} → '
                f'{_libelle_statut_rdv(rdv.statut)}')
        if rdv.scheduled_at != ancien_quand:
            changements.append(
                f'déplacé du {_quand_rdv(ancien_quand)} au '
                f'{_quand_rdv(rdv.scheduled_at)}')
            if rdv.reminder_sent:
                rdv.reminder_sent = False
                rdv.save(update_fields=['reminder_sent'])
        if changements and rdv.lead_id:
            _noter_rdv(rdv.lead, self.request.user,
                       f'RDV #{rdv.pk} : ' + ' ; '.join(changements))
        if rdv.lead_id and rdv.lead_id != ancien_lead_id and ancien_lead_id:
            _noter_rdv(Lead.objects.filter(pk=ancien_lead_id).first(),
                       self.request.user,
                       f'RDV #{rdv.pk} : rattaché à un autre lead')

    def perform_destroy(self, instance):
        """ACRM23 — la SUPPRESSION d'un rendez-vous est journalisée au
        chatter du lead (acteur, date du rendez-vous)."""
        lead = instance.lead
        pk, quand = instance.pk, instance.scheduled_at
        super().perform_destroy(instance)
        if lead is not None:
            _noter_rdv(lead, self.request.user,
                       f'RDV #{pk} du {_quand_rdv(quand)} : supprimé')

    @extend_schema(responses=sd.EXPORT_ICS)
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

    @extend_schema(request=None, responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='confirmer-whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer_whatsapp(self, request, pk=None):
        """VX245(b) — aperçu du message de CONFIRMATION WhatsApp post-RDV
        (date/heure + lien `.ics`). N'ENVOIE RIEN : le commercial ouvre
        WhatsApp lui-même après avoir vérifié l'aperçu (même convention que
        `LeadViewSet.whatsapp_devis`)."""
        appt = self.get_object()
        from .visites_rdv import build_appointment_confirmation_whatsapp

        message, wa_url, ics_url = build_appointment_confirmation_whatsapp(
            request, appt)
        if wa_url is None:
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'message': message, 'wa_url': wa_url, 'ics_url': ics_url,
        })


# ── FG39 — ObjectifCommercial / KPI Target ────────────────────────────────────

@extend_schema_view(list=extend_schema(parameters=[sd.param('metric'), sd.param('year', OpenApiTypes.INT), sd.param('period_type'), sd.param('owner', description='Identifiant ou « null ».')]))
class ObjectifCommercialViewSet(CompanyScopedModelViewSet):
    """CRUD objectifs commerciaux + endpoint d'atteinte (réalisé vs cible).

    Routes :
      GET/POST  /crm/objectifs/
      GET/PATCH /crm/objectifs/{id}/
      DELETE    /crm/objectifs/{id}/
      GET       /crm/objectifs/attainment/?year=&metric=&period_type=&owner=
      GET       /crm/objectifs/{id}/attainment/
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
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

    @extend_schema(responses=ObjectifAttainmentSerializer)
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

    # YAPIC6 — sans cette annotation le schéma documente un OBJET unique alors
    # que l'action renvoie une LISTE (drf-spectacular déduit le détail depuis
    # le serializer). Annotation de schéma uniquement : aucun effet runtime.
    @extend_schema(
        parameters=[
            sd.param('metric'), sd.param('year', OpenApiTypes.INT),
            sd.param('period_type'),
            sd.param('owner', description='Identifiant ou « null ».'),
        ],
        responses=ObjectifAttainmentSerializer(many=True),
    )
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

@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD]))
class ConcurrentPerteViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

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
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
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


# ── NTCRM4 — Catégories de forecast ──────────────────────────────────────────

@extend_schema_view(list=extend_schema(parameters=[sd.P_OWNER, sd.param('categorie'), sd.param('periode', description='AAAA-MM')]))
class ForecastEntryViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """CRUD des catégorisations forecast (commit/best-case/pipeline/omis).

    Routes :
      GET/POST  /crm/forecast-entries/?owner=&categorie=&periode=
      GET/PATCH /crm/forecast-entries/{id}/
    La réponse liste inclut ``totaux_par_categorie`` (somme des montants
    effectifs des lignes filtrées, par catégorie)."""
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
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


@extend_schema(parameters=[sd.param('periode', description='AAAA-MM'), sd.param('equipe', OpenApiTypes.INT)], responses=sd.OBJ)
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


@extend_schema(parameters=[sd.P_OWNER, sd.param('semaines', OpenApiTypes.INT)], responses=sd.OBJ)
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

@extend_schema_view(list=extend_schema(parameters=[sd.param('client', OpenApiTypes.INT)]))
class PlanCompteViewSet(_PorteeEnfantsMixin, ChatterViewSetMixin, CompanyScopedModelViewSet):

    """NTCRM10 — Plan de compte. ARC8 : l'historique (chatter) converge sur
    ``records.Activity`` — création + changements de champ suivis journalisés
    via ``records.services`` (le « mail.thread » maison), jamais un modèle
    ``*Activity`` local. Le mixin ``ChatterViewSetMixin`` ajoute en plus les
    actions génériques ``chatter/historique`` (GET) et ``chatter/noter`` (POST)."""
    # ACRM9 — lectures bornées à la portée (leads : — ;

    # clients : client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ()

    portee_clients = ('client',)
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
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = RevueCompte.objects.select_related('plan')
    serializer_class = RevueCompteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # RevueCompte n'a PAS de champ `company` propre (scopée via son plan
        # de compte parent) : `TenantMixin.get_queryset()` (appelé par
        # `super()`) filtre sur `company=user.company`, ce qui lève un
        # FieldError (500) sur ce modèle — on construit donc le queryset
        # directement, jamais via `super().get_queryset()`.
        qs = RevueCompte.objects.select_related('plan')
        user = self.request.user
        if user.company_id:
            return qs.filter(plan__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── NTCRM12 — Playbooks de vente par étape ───────────────────────────────────

class PlaybookViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = Playbook.objects.prefetch_related('etapes__taches')
    serializer_class = PlaybookSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class _PlaybookEnfantViewSetMixin:
    """CRX14 — socle des deux enfants de playbook (étapes, tâches).

    ``PlaybookEtape`` et ``PlaybookTache`` N'ONT PAS de champ ``company`` : la
    frontière société passe par le playbook parent. Le ``get_queryset`` de
    ``TenantMixin`` (``qs.filter(company=…)``) levait donc un ``FieldError``
    AVANT d'atteindre le re-scope ``playbook__company`` écrit juste après —
    autrement dit ce re-scope était MORT et toute lecture/écriture d'un objet
    existant (list, retrieve, update, destroy) répondait 500. On remplace
    entièrement le filtrage par le chemin parent, en gardant la sémantique de
    ``TenantMixin`` pour les trois acteurs : utilisateur d'une société →
    scopé ; superuser SANS société (acteur plateforme) → tout ; ni l'un ni
    l'autre → rien.

    ``perform_create``/``perform_update`` valident en plus le PARENT désigné
    par le corps : sans cela, un id de playbook (ou d'étape) d'une autre
    société suffisait à y greffer — ou à y déplacer — une étape.
    """

    #: Chemin ORM du parent portant la société (ex. ``playbook__company_id``).
    company_path = ''
    #: Nom du champ de relation parent dans le corps de la requête.
    parent_field = ''

    def base_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        qs = self.base_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(**{self.company_path: user.company_id})
        if user.is_superuser:
            return qs
        return qs.none()

    def parent_company_id(self, parent):
        raise NotImplementedError

    def _valider_parent(self, serializer):
        company_id = getattr(self.request.user, 'company_id', None)
        if not company_id:
            return
        parent = serializer.validated_data.get(self.parent_field)
        if parent is None:
            # Absent d'un PATCH partiel : le parent existant a déjà été scopé
            # par ``get_queryset``, rien à revalider.
            if serializer.partial:
                return
            raise DRFValidationError(
                {self.parent_field: 'Ce champ est obligatoire.'})
        if self.parent_company_id(parent) != company_id:
            raise DRFValidationError(
                {self.parent_field: 'Élément hors de votre société.'})

    def perform_create(self, serializer):
        self._valider_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._valider_parent(serializer)
        serializer.save()


class PlaybookEtapeViewSet(_PlaybookEnfantViewSetMixin,
                           CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = PlaybookEtape.objects.select_related('playbook').prefetch_related('taches')
    serializer_class = PlaybookEtapeSerializer
    company_path = 'playbook__company_id'
    parent_field = 'playbook'

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def base_queryset(self):
        return PlaybookEtape.objects.select_related(
            'playbook').prefetch_related('taches')

    def parent_company_id(self, parent):
        return parent.company_id


class PlaybookTacheViewSet(_PlaybookEnfantViewSetMixin,
                           CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = PlaybookTache.objects.select_related('etape__playbook')
    serializer_class = PlaybookTacheSerializer
    company_path = 'etape__playbook__company_id'
    parent_field = 'etape'

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def base_queryset(self):
        return PlaybookTache.objects.select_related('etape__playbook')

    def parent_company_id(self, parent):
        return parent.playbook.company_id


class _LeadPlaybookPermission(IsAnyRole):
    """ACRM8 — lire la progression : tout rôle interne ; cocher une tâche
    (POST) est une écriture commerciale : ``crm_modifier``."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return HasPermissionOrLegacy('crm_modifier')().has_permission(
            request, view)


@api_view(['GET', 'POST'])
@permission_classes([_LeadPlaybookPermission])
def lead_playbook_view(request, lead_id):
    """NTCRM12 — ``GET`` : progression playbook du lead (toutes les tâches
    générées pour son étape courante ou une étape antérieure). ``POST``
    ``{'tache': <id>, 'fait': true}`` : coche/décoche UNE tâche, pose
    l'acteur+la date côté serveur (jamais silencieux).

    ACRM8/ACRM9 — le lead est résolu dans la PORTÉE de l'appelant : hors
    portée = absent (404)."""
    from .selectors import leads_en_portee
    lead = leads_en_portee(request.user).filter(pk=lead_id).first()
    if lead is None:
        return Response({'detail': 'Lead introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        # AGR526 — `tache__etape__playbook` : la clé de texte (`cle_message`)
        # se lit sur le NOM du playbook, sans requête par ligne.
        progress = lead.playbook_progress.select_related(
            'tache', 'tache__etape', 'tache__etape__playbook', 'lead',
            'fait_par').all()
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


# ── LB48 — Vues enregistrées par compte ────────────────────────────────────

@extend_schema_view(list=extend_schema(parameters=[sd.param('page')]))
class SavedViewViewSet(CompanyScopedModelViewSet):
    """LB48 — vues enregistrées PERSONNELLES (filtres + disposition) pour une
    page donnée (ex. ``crm.leads``).

    Double scoping systématique : société (``TenantMixin``, hérité de
    ``CompanyScopedModelViewSet``) ET utilisateur — chaque utilisateur ne
    voit/modifie QUE ses propres vues, jamais celles d'un collègue même dans
    la même société (``get_queryset`` filtre en plus sur
    ``request.user``, donc un id d'une autre personne rend 404, pas 403).
    ``company``/``user`` sont toujours posés côté serveur dans
    ``perform_create`` — jamais lus du corps de requête.

    Routes :
      GET/POST         /crm/vues-enregistrees/?page=crm.leads
      GET/PATCH/DELETE  /crm/vues-enregistrees/{id}/
      POST              /crm/vues-enregistrees/reorder/
                         {"page": "crm.leads", "ids": [3, 1, 2]}
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = SavedView.objects.all()
    serializer_class = SavedViewSerializer
    # Pagination COUPÉE : listes personnelles minuscules, et surtout le
    # paramètre de filtre `?page=crm.leads` entrerait en collision avec le
    # `?page=<n>` du paginateur DRF (→ 404 « Page non valide », attrapé au
    # rig). Sans paginateur, `page` redevient un filtre libre.
    pagination_class = None

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)
        page = self.request.query_params.get('page')
        if page:
            qs = qs.filter(page=page)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            user=self.request.user,
        )

    @extend_schema(request=sd.corps('CrmSavedViewReorderRequest', page=serializers.CharField(), ids=serializers.ListField(child=serializers.IntegerField())), responses=SavedViewSerializer(many=True))
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Réordonne en bloc les vues de l'utilisateur pour une page :
        ``{"page": "crm.leads", "ids": [3, 1, 2]}`` → ``rank`` = index dans la
        liste fournie. Les ids qui n'appartiennent pas à l'utilisateur actif
        pour cette page (autre page, autre utilisateur, id inconnu) sont
        silencieusement ignorés — jamais d'erreur pour un id étranger."""
        from django.db import transaction
        page = request.data.get('page')
        ids = request.data.get('ids') or []
        if not page or not isinstance(ids, list):
            return Response(
                {'detail': "Paramètres 'page' et 'ids' (liste) requis."},
                status=status.HTTP_400_BAD_REQUEST)
        owned_by_id = {
            v.id: v for v in SavedView.objects.filter(
                company=request.user.company, user=request.user,
                page=page, id__in=ids)
        }
        with transaction.atomic():
            for index, view_id in enumerate(ids):
                view = owned_by_id.get(view_id)
                if view is None:
                    continue
                if view.rank != index:
                    view.rank = index
                    view.save(update_fields=['rank'])
        result = SavedView.objects.filter(
            company=request.user.company, user=request.user, page=page,
        ).order_by('rank', 'id')
        return Response(SavedViewSerializer(result, many=True).data)


# ── QJ-EQUIPE-2 (14/09/2026) — écran de revue T-TRACE + registre équipe ──────


# ── CAD-D ── CAD45 — une touche « appel » traitée PAR ÉCRIT ──────────────────
