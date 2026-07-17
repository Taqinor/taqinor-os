"""Vues du module Innovation (boîte à idées interne).

Palier d'accès :
  * lecture/proposition/vote — tout utilisateur connecté de la société
    (``IsAnyRole``) — « logged-in users only » (NTIDE4/NTIDE8) ;
  * transitions de statut (examiner/retenir/réaliser/fermer) — palier
    Directeur/Responsable (``IsResponsableOrAdmin``, NTIDE5) ;
  * tableau de bord, paramètres de campagne, export, actions en masse —
    palier administration (``IsAdminOrResponsableTier``, NTIDE6/7/12/13).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import Idee, InnovationSettings, VoteIdee
from .serializers import (
    IdeeDetailSerializer, IdeeSerializer, InnovationSettingsSerializer,
    VoteIdeeSerializer,
)


class IdeeViewSet(CompanyScopedModelViewSet):
    """Boîte à idées interne : liste/détail/proposition + actions (NTIDE4/5).

    Aucun ``destroy`` : une idée se ferme (action ``fermer``), elle ne se
    supprime jamais (dossier de décision produit, comme les litiges/dossiers
    légaux ailleurs dans le dépôt)."""

    queryset = Idee.objects.select_related('auteur').all()
    serializer_class = IdeeSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    permission_classes = [IsAnyRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['votes_count', 'created_at', 'id']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return IdeeDetailSerializer
        return IdeeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # NTIDE18 — une idée en brouillon (draft=True) reste interne à son
        # auteur : invisible de tout le monde d'autre, y compris dans les
        # exports/actions en masse admin (qui réutilisent get_queryset()).
        from django.db.models import Q
        qs = qs.filter(Q(draft=False) | Q(auteur=self.request.user))
        params = self.request.query_params
        # NTIDE19 — une idée masquée (modération) disparaît des listes
        # normales ; le palier Directeur/Responsable peut la retrouver avec
        # ``?include_archived=1`` (« reste accessible en admin »), jamais un
        # autre palier.
        include_archived = (
            params.get('include_archived') == '1'
            and getattr(self.request.user, 'is_responsable', False))
        if not include_archived:
            qs = qs.exclude(archived=True)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        contexte = params.get('contexte')
        if contexte:
            qs = qs.filter(contexte__iexact=contexte)
        created_since = params.get('created_since')
        if created_since:
            qs = qs.filter(created_at__gte=created_since)
        owner = params.get('owner') or params.get('auteur')
        if owner:
            qs = qs.filter(auteur_id=owner)
        return qs

    def perform_create(self, serializer):
        # NTIDE18 — « Enregistrer en brouillon » : lu directement du corps
        # (c'est l'intention même de la case à cocher), jamais depuis un
        # champ PATCH-able ensuite (``draft`` est read-only, cf. serializer).
        draft = bool(self.request.data.get('draft'))
        idee = serializer.save(
            company=self.request.user.company, auteur=self.request.user,
            draft=draft)
        from apps.records.models import Activity
        from apps.records.services import log_activity
        log_activity(
            idee, Activity.Kind.CREATION, user=self.request.user,
            company=idee.company)

    # ── NTIDE10 — autocomplétion du contexte ────────────────────────────────
    @action(detail=False, methods=['get'], url_path='contextes',
            permission_classes=[IsAnyRole])
    def contextes(self, request):
        """Les 5 contextes existants les plus fréquents (autocomplétion)."""
        data = selectors.contextes_frequents(request.user.company)
        return Response({'results': data})

    # ── NTIDE20 — dédup : idées similaires (avant de proposer un doublon) ────
    @action(detail=False, methods=['get'], url_path='similaires',
            permission_classes=[IsAnyRole])
    def similaires(self, request):
        """« Existe-t-il une idée similaire ? » — top 3, recherche
        titre+description (``?q=texte``)."""
        texte = request.query_params.get('q', '')
        data = selectors.idees_similaires(request.user.company, texte)
        return Response({'results': data})

    # ── NTIDE6 — tableau de bord admin ──────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='tableau-bord',
            permission_classes=[IsAdminOrResponsableTier])
    def tableau_bord(self, request):
        """KPI par statut, top votes, plus récentes, heat-chart contexte."""
        return Response(selectors.tableau_bord_idees(request.user.company))

    # ── NTIDE5 — machine à états + chatter ──────────────────────────────────
    def _transition(self, request, target):
        idee = self.get_object()
        note = (request.data.get('note') or '').strip()
        try:
            services.transitionner(
                idee, target=target, user=request.user, note=note)
        except services.TransitionInvalide as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(IdeeSerializer(idee).data)

    @action(detail=True, methods=['post'], url_path='examiner',
            permission_classes=[IsResponsableOrAdmin])
    def examiner(self, request, pk=None):
        """ouvert → examinée."""
        return self._transition(request, Idee.Statut.EXAMINEE)

    @action(detail=True, methods=['post'], url_path='retenir',
            permission_classes=[IsResponsableOrAdmin])
    def retenir(self, request, pk=None):
        """examinée → retenue."""
        return self._transition(request, Idee.Statut.RETENUE)

    @action(detail=True, methods=['post'], url_path='realiser',
            permission_classes=[IsResponsableOrAdmin])
    def realiser(self, request, pk=None):
        """retenue → réalisée."""
        return self._transition(request, Idee.Statut.REALISEE)

    @action(detail=True, methods=['post'], url_path='fermer',
            permission_classes=[IsResponsableOrAdmin])
    def fermer(self, request, pk=None):
        """ouvert|examinée|retenue → fermée. Note de fermeture optionnelle
        (``{"note": "..."}``), journalisée dans le chatter."""
        return self._transition(request, Idee.Statut.FERMEE)

    # ── NTIDE18 — publier une idée brouillon (draft → False) ─────────────────
    @action(detail=True, methods=['post'], url_path='publier',
            permission_classes=[IsAnyRole])
    def publier(self, request, pk=None):
        """Réservé à l'auteur du brouillon (403 sinon). Une fois publiée,
        l'idée redevient visible de toute la société (``get_queryset``)."""
        idee = self.get_object()
        if idee.auteur_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "Seul l'auteur peut publier son brouillon.")
        if idee.draft:
            idee.draft = False
            idee.save(update_fields=['draft', 'updated_at'])
        return Response(IdeeSerializer(idee).data)

    # ── NTIDE19 — modération : masquer une idée sans la supprimer ────────────
    @action(detail=True, methods=['post'], url_path='masquer',
            permission_classes=[IsResponsableOrAdmin])
    def masquer(self, request, pk=None):
        """Palier Directeur/Responsable uniquement. Ne supprime jamais
        l'idée : elle disparaît des listes normales (``get_queryset``) mais
        reste consultable via ``?include_archived=1`` (même palier).
        Journalise dans le chatter générique (ARC8)."""
        idee = self.get_object()
        if not idee.archived:
            idee.archived = True
            idee.save(update_fields=['archived', 'updated_at'])
            from apps.records.models import Activity
            from apps.records.services import log_activity
            log_activity(
                idee, Activity.Kind.MODIFICATION, user=request.user,
                field='archived', field_label='Masquée', old_value='False',
                new_value='True', company=idee.company)
        return Response(IdeeSerializer(idee).data)

    # ── NTIDE17 — l'auteur ré-ouvre sa propre idée fermée/examinée ───────────
    @action(detail=True, methods=['post'], url_path='reouvrir',
            permission_classes=[IsAnyRole])
    def reouvrir(self, request, pk=None):
        """« Notion de "auteur peut modifier" » : réservé à l'auteur (403
        sinon), depuis FERMÉE/EXAMINÉE uniquement (verrouillé après
        RETENUE/RÉALISÉE — géré côté serveur, 400 sinon)."""
        idee = self.get_object()
        try:
            services.reouvrir(idee, request.user)
        except services.ReouvertureInterdite as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(IdeeSerializer(idee).data)

    # ── NTIDE14 — lier une idée à un devis/ticket/chantier (opaque string-FK) ─
    @action(detail=True, methods=['post'], url_path='lier',
            permission_classes=[IsAnyRole])
    def lier(self, request, pk=None):
        """Corps : ``{linked_type: 'devis'|'ticket'|'chantier', linked_id:
        N}``. Saisie MANUELLE (type + identifiant) — jamais une recherche
        live dans les modèles ``ventes``/``sav``/``installations`` (cross-app
        interdit, cf. règle de frontière) : ``linked_id`` reste une référence
        OPAQUE, exactement comme la pré-détection de création (NTIDE11).
        Journalise le lien dans le chatter générique (ARC8)."""
        idee = self.get_object()
        linked_type = (request.data.get('linked_type') or '').strip()
        linked_id_raw = request.data.get('linked_id')
        if linked_type not in Idee.LinkedType.values:
            return Response({'linked_type': 'Type invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            linked_id = int(linked_id_raw)
            if linked_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'linked_id': 'Identifiant invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)

        old_type, old_id = idee.linked_type, idee.linked_id
        idee.linked_type = linked_type
        idee.linked_id = linked_id
        idee.save(update_fields=['linked_type', 'linked_id', 'updated_at'])

        from apps.records.models import Activity
        from apps.records.services import log_activity
        old_label = f'{old_type} #{old_id}' if old_type else ''
        new_label = f'{linked_type} #{linked_id}'
        log_activity(
            idee, Activity.Kind.MODIFICATION, user=request.user,
            field='linked_type', field_label='Lié à',
            old_value=old_label, new_value=new_label, company=idee.company)
        return Response(IdeeSerializer(idee).data)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Timeline chatter (générique ``records.Activity``, ARC8)."""
        idee = self.get_object()
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs
        qs = chatter_qs(idee, company=idee.company)
        return Response(ChatterActivitySerializer(qs, many=True).data)

    # ── NTIDE12 — export .xlsx (paramètres → campagnes innovation) ──────────
    @action(detail=False, methods=['get'], url_path='export-xlsx',
            permission_classes=[IsAdminOrResponsableTier])
    def export_xlsx(self, request):
        """Exporte les idées (filtres statut/contexte/date déjà appliqués par
        ``get_queryset``) en .xlsx."""
        from .exports import export_idees_xlsx
        qs = self.filter_queryset(self.get_queryset()).select_related('auteur')
        return export_idees_xlsx(qs)

    # ── NTIDE13 — actions en masse (admin) ───────────────────────────────────
    @action(detail=False, methods=['post'], url_path='bulk',
            permission_classes=[IsAdminOrResponsableTier])
    def bulk(self, request):
        """Corps : {ids: [...], action: 'set_statut'|'add_tag'|'remove_tag'
        |'export', + paramètres}. ``export`` court-circuite vers le .xlsx de
        la sélection (NTIDE12 sur la sélection) ; les autres délèguent à
        ``services.apply_bulk_action``."""
        ids = request.data.get('ids') or []
        op = request.data.get('action')
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Sélectionnez au moins une idée.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if op == 'export':
            from .exports import export_idees_xlsx
            qs = (Idee.objects.filter(
                company=request.user.company, id__in=ids)
                .select_related('auteur'))
            return export_idees_xlsx(qs)
        if op not in services.BULK_ACTIONS:
            return Response({'detail': 'Action en masse inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = services.apply_bulk_action(
                company=request.user.company, user=request.user,
                ids=ids, op=op, params=request.data)
        except (DjangoValidationError, ValueError) as exc:
            detail = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
            return Response({'detail': detail},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class VoteIdeeViewSet(CompanyScopedModelViewSet):
    """Votes sur idées (NTIDE2). Lecture : tout utilisateur connecté.
    Création : tout utilisateur connecté (sauf l'auteur de l'idée, cf.
    ``services.voter``). Suppression : le votant lui-même ou l'admin
    (« créateur/admin », NTIDE2)."""

    queryset = VoteIdee.objects.select_related('votant', 'idee').all()
    serializer_class = VoteIdeeSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    permission_classes = [IsAnyRole]

    def perform_create(self, serializer):
        idee = serializer.validated_data['idee']
        if idee.company_id != self.request.user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Idée hors de votre société.')
        try:
            vote = services.voter(idee, self.request.user)
        except services.VoteInterdit as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'idee': str(exc)}) from exc
        serializer.instance = vote

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.votant_id != user.id and not (
                user.is_superuser or user.is_admin_role):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Seul l\'auteur du vote ou un administrateur peut le retirer.')
        services.retirer_vote(instance)

    # ── Sélecteurs exposés (NTIDE2) ──────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='recents',
            permission_classes=[IsAnyRole])
    def recents(self, request):
        """Votes récents de la société (``votes_recents``)."""
        qs = self.get_queryset().order_by('-created_at')[:20]
        return Response(VoteIdeeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-idees',
            permission_classes=[IsAnyRole])
    def mes_idees(self, request):
        """Votes reçus sur les idées PROPOSÉES par l'appelant
        (``votes_my_ideas``)."""
        qs = self.get_queryset().filter(idee__auteur=request.user)
        return Response(VoteIdeeSerializer(qs, many=True).data)


class InnovationSettingsView(APIView):
    """Paramètres → Avancé « Campagnes innovation » (NTIDE7).

    Singleton par société (``get_or_create``). Chaque changement journalise
    une ligne ``SettingsAuditLog`` (section ``innovation``)."""

    permission_classes = [IsAdminOrResponsableTier]

    def _instance(self, request):
        obj, _ = InnovationSettings.objects.get_or_create(
            company=request.user.company)
        return obj

    def get(self, request):
        return Response(
            InnovationSettingsSerializer(self._instance(request)).data)

    def patch(self, request):
        instance = self._instance(request)
        serializer = InnovationSettingsSerializer(
            instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        from apps.parametres.models_audit import SettingsAuditLog
        champs_label = {
            'campagnes_activees': 'Campagnes activées',
            'segment_defaut': 'Segment par défaut',
            'theme_couleur_cta': 'Thème couleur du CTA',
            'message_relance': 'Message de relance',
            'seuil_votes_notification': 'Seuil de votes pour notifier l\'auteur',
        }
        anciennes = {f: getattr(instance, f) for f in champs_label}
        serializer.save()
        for champ, label in champs_label.items():
            nouvelle = getattr(instance, champ)
            if nouvelle != anciennes[champ]:
                SettingsAuditLog.log_change(
                    company=request.user.company, user=request.user,
                    section='innovation', field=champ, field_label=label,
                    old=anciennes[champ], new=nouvelle)
        return Response(serializer.data)

    put = patch
