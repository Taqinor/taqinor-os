from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction, IntegrityError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from apps.ventes.utils.references import create_with_reference

from . import activity
from .models import (
    Equipement, Ticket, PieceConsommee,
    SavSlaSettings, MaintenanceChecklistTemplate, MaintenanceChecklistItem,
    TicketChecklistItem, WarrantyClaim, KbArticle,
)
from .pdf import rapport_intervention_pdf
from .serializers import (
    EquipementSerializer, TicketSerializer, TicketActivitySerializer,
    PieceConsommeeSerializer, EXPIRING_SOON_DAYS,
    SavSlaSettingsSerializer,
    MaintenanceChecklistTemplateSerializer, MaintenanceChecklistItemSerializer,
    TicketChecklistItemSerializer,
    WarrantyClaimSerializer,
    KbArticleSerializer,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class EquipementViewSet(TenantMixin, viewsets.ModelViewSet):
    """Parc d'équipements (n° de série + horloges de garantie). Tout est scopé
    à la société ; les dates de fin de garantie sont CALCULÉES côté serveur."""
    queryset = Equipement.objects.select_related(
        'produit', 'installation', 'installation__client',
    ).all()
    serializer_class = EquipementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_serie', 'produit__nom', 'produit__marque']
    ordering_fields = [
        'date_fin_garantie', 'date_pose', 'date_creation', 'numero_serie',
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # Portée de visibilité (Feature F) — équipements créés par soi / l'équipe.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        params = self.request.query_params
        produit = params.get('produit')
        marque = params.get('marque')
        installation = params.get('installation')
        client = params.get('client')
        statut = params.get('statut')
        garantie = params.get('garantie')
        if produit:
            qs = qs.filter(produit_id=produit)
        if marque:
            qs = qs.filter(produit__marque__icontains=marque)
        if installation:
            qs = qs.filter(installation_id=installation)
        if client:
            qs = qs.filter(installation__client_id=client)
        if statut:
            qs = qs.filter(statut=statut)
        if garantie:
            today = timezone.localdate()
            soon = today + timedelta(days=EXPIRING_SOON_DAYS)
            if garantie == 'non_renseignee':
                qs = qs.filter(date_fin_garantie__isnull=True)
            elif garantie == 'hors_garantie':
                qs = qs.filter(date_fin_garantie__lt=today)
            elif garantie == 'expire_bientot':
                qs = qs.filter(
                    date_fin_garantie__gte=today, date_fin_garantie__lte=soon)
            elif garantie == 'sous_garantie':
                qs = qs.filter(date_fin_garantie__gt=soon)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [HasPermissionOrLegacy('equipement_voir')()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('equipement_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        produit = serializer.validated_data.get('produit')
        ticket = serializer.validated_data.get('remplace_par_ticket')
        if installation is not None and installation.company_id != company.id:
            raise ValidationError({'installation': 'Chantier inconnu.'})
        if produit is not None and produit.company_id not in (company.id, None):
            raise ValidationError({'produit': 'Produit inconnu.'})
        if ticket is not None and ticket.company_id != company.id:
            raise ValidationError({'remplace_par_ticket': 'Ticket inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        try:
            serializer.save(company=company, created_by=self.request.user)
        except IntegrityError:
            # L636 — filet de course si la contrainte d'unicité DB se déclenche
            # entre la validation serializer et l'écriture.
            raise ValidationError(
                {'numero_serie':
                 'Ce numéro de série existe déjà dans votre société.'})
        # Calcul des horloges de garantie après la pose des FK.
        inst = serializer.instance
        inst.recompute_garanties()
        # FG85 — jeton QR EQUIP:<id> posé à la création.
        inst.equipement_token = f'EQUIP:{inst.pk}'
        inst.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production',
            'equipement_token'])

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'numero_serie':
                 'Ce numéro de série existe déjà dans votre société.'})
        inst = serializer.instance
        inst.recompute_garanties()
        # FG85 — assure que le jeton est toujours présent (migration d'équipements existants).
        token = f'EQUIP:{inst.pk}'
        update_fields = ['date_fin_garantie', 'date_fin_garantie_production']
        if inst.equipement_token != token:
            inst.equipement_token = token
            update_fields.append('equipement_token')
        inst.save(update_fields=update_fields)

    @action(detail=False, methods=['get'], url_path='etiquettes',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def etiquettes(self, request):
        """FG85 — Étiquettes QR pour les équipements du parc.

        ?ids=1,2,3 pour un sous-ensemble ; sans filtre = tous les équipements
        de la société (limité à 200 pour WeasyPrint). Symbologie : qr (défaut)
        ou code128. Renvoie HTML prêt pour impression / conversion PDF."""
        from apps.stock.labels import render_labels_html
        from django.http import HttpResponse as HR

        qs = self.get_queryset()
        ids_param = request.query_params.get('ids', '')
        if ids_param:
            try:
                ids = [int(i) for i in ids_param.split(',') if i.strip()]
            except ValueError:
                return Response({'detail': 'ids invalides.'}, status=400)
            qs = qs.filter(pk__in=ids)
        qs = qs[:200]

        items = []
        for eq in qs:
            # Assure le jeton présent (rétro-compat équipements sans token).
            token = eq.equipement_token or f'EQUIP:{eq.pk}'
            titre = eq.produit.nom if eq.produit_id else '—'
            sous_titre = eq.numero_serie or '(sans série)'
            items.append({'token': token, 'titre': titre, 'sous_titre': sous_titre})

        if not items:
            return Response({'detail': 'Aucun équipement.'}, status=404)

        symbology = request.query_params.get('symbology', 'qr')
        html = render_labels_html(items, symbology=symbology)
        return HR(html, content_type='text/html; charset=utf-8')


class TicketViewSet(TenantMixin, viewsets.ModelViewSet):
    """Tickets SAV + historique « chatter ». Cycle de vie propre (liste fermée
    en ordre d'entonnoir), indépendant des étapes lead / statuts de document.
    Tout est scopé à la société ; acteur et société posés côté serveur."""
    queryset = Ticket.objects.select_related(
        'client', 'installation', 'equipement', 'equipement__produit',
        'technicien_responsable',
    ).prefetch_related('interventions').all()
    serializer_class = TicketSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'description', 'client__nom', 'client__prenom',
        'installation__reference',
    ]
    ordering_fields = [
        'reference', 'date_creation', 'date_ouverture', 'priorite', 'statut',
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # Portée de visibilité (Feature F) — tickets créés par soi / dont on est
        # le technicien responsable / ceux de l'équipe. 'all' → inchangé.
        from authentication.scoping import scope_queryset
        qs = scope_queryset(
            qs, self.request.user, ['technicien_responsable', 'created_by'])
        params = self.request.query_params
        statut = params.get('statut')
        type_ = params.get('type')
        priorite = params.get('priorite')
        technicien = params.get('technicien')
        client = params.get('client')
        installation = params.get('installation')
        equipement = params.get('equipement')
        if statut:
            qs = qs.filter(statut=statut)
        if type_:
            qs = qs.filter(type=type_)
        if priorite:
            qs = qs.filter(priorite=priorite)
        if technicien:
            qs = qs.filter(technicien_responsable_id=technicien)
        if client:
            qs = qs.filter(client_id=client)
        if installation:
            qs = qs.filter(installation_id=installation)
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        # File de service par défaut = tickets OUVERTS non annulés. ?ouvert=tous
        # pour tout voir ; un filtre ?statut explicite l'emporte.
        if self.action == 'list' and not statut:
            ouvert = params.get('ouvert')
            if ouvert != 'tous':
                qs = qs.filter(statut__in=Ticket.OPEN_STATUTS, annule=False)
        # Drapeau d'annulation (comme « Perdu »).
        annule = params.get('annule')
        if self.action == 'list':
            if annule == 'only':
                qs = qs.filter(annule=True)
            elif annule == 'sans':
                qs = qs.filter(annule=False)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique', 'rapport_pdf']:
            return [HasPermissionOrLegacy('sav_voir')()]
        elif self.action in WRITE_ACTIONS + ['noter', 'annuler', 'reactiver']:
            return [HasPermissionOrLegacy('sav_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        company = self.request.user.company
        for field in ('client', 'installation', 'equipement'):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.company_id != company.id:
                raise ValidationError({field: 'Référence inconnue.'})

    def _resolve_from_equipement(self, serializer):
        """Quand un ticket est ouvert depuis le parc (un équipement lié) sans
        client ni chantier explicite, déduire l'installation et le client de
        l'équipement — ainsi un ticket créé depuis un équipement porte
        client + installation + equipement sans sélection manuelle."""
        equipement = serializer.validated_data.get('equipement')
        if equipement is None:
            return
        installation = getattr(equipement, 'installation', None)
        if installation is None:
            return
        if serializer.validated_data.get('installation') is None:
            serializer.validated_data['installation'] = installation
        if serializer.validated_data.get('client') is None:
            client = getattr(installation, 'client', None)
            if client is not None:
                serializer.validated_data['client'] = client

    def _compute_sla_due_at(self, company, priorite, date_ouverture):
        """FG81 — Calcule sla_due_at depuis les réglages société (ou None)."""
        sla = SavSlaSettings.get(company)
        if not sla.sla_breach_enabled:
            return None
        _, resolution_days = sla.days_for(priorite)
        return date_ouverture + timedelta(days=resolution_days)

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        self._resolve_from_equipement(serializer)
        # client est optionnel au niveau sérialiseur (peut venir de l'équipement) ;
        # s'il n'a pas pu être résolu, on rétablit l'exigence ici.
        if not serializer.validated_data.get('client'):
            raise ValidationError({'client': 'Ce champ est obligatoire.'})
        date_ouverture = (
            serializer.validated_data.get('date_ouverture')
            or timezone.localdate())
        # FG81 — SLA : calcul de l'échéance cible à la création.
        priorite = serializer.validated_data.get('priorite', 'normale')
        sla_due_at = self._compute_sla_due_at(company, priorite, date_ouverture)
        create_with_reference(
            Ticket, 'SAV', company,
            lambda ref: serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
                date_ouverture=date_ouverture,
                sla_due_at=sla_due_at),
        )
        activity.log_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        old = Ticket.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        # FG81 — recalcule sla_breach après toute mise à jour de statut.
        inst = serializer.instance
        inst.recompute_sla_breach()
        inst.save(update_fields=['sla_breach'])
        activity.log_changes(old, inst, self.request.user)

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def historique(self, request, pk=None):
        ticket = self.get_object()
        return Response(
            TicketActivitySerializer(ticket.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def noter(self, request, pk=None):
        ticket = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(ticket, request.user, body)
        return Response(TicketActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def annuler(self, request, pk=None):
        """Annule le ticket (DRAPEAU avec motif — pas une étape)."""
        ticket = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not ticket.annule:
            ticket.annule = True
            ticket.motif_annulation = motif or None
            ticket.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(
                ticket, request.user,
                f"Ticket annulé{(' : ' + motif) if motif else ''}")
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reactiver',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def reactiver(self, request, pk=None):
        ticket = self.get_object()
        if ticket.annule:
            ticket.annule = False
            ticket.motif_annulation = None
            ticket.save(update_fields=['annule', 'motif_annulation'])
            activity.log_note(ticket, request.user, "Ticket réactivé")
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='premier-reponse',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def premier_reponse(self, request, pk=None):
        """FG81 — Enregistre la date de première réponse (horloge de réponse SLA).

        Idempotent : si déjà posée, renvoie la valeur existante. La date peut
        être fournie en body (`at` ISO8601) sinon utilise now()."""
        ticket = self.get_object()
        if ticket.date_premiere_reponse is None:
            at_raw = request.data.get('at')
            if at_raw:
                from django.utils.dateparse import parse_datetime
                at = parse_datetime(at_raw)
                if at is None:
                    return Response({'detail': 'Date invalide.'}, status=400)
            else:
                at = timezone.now()
            ticket.date_premiere_reponse = at
            ticket.save(update_fields=['date_premiere_reponse'])
            activity.log_note(
                ticket, request.user,
                f'Première réponse enregistrée le {at.strftime("%d/%m/%Y %H:%M")}')
        return Response(
            TicketSerializer(ticket, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def rapport_pdf(self, request, pk=None):
        """Rapport d'intervention SAV (N45) — PDF régénéré à la demande.

        Aucun prix d'achat / marge n'y figure. Disponible sur tout ticket."""
        ticket = self.get_object()
        pdf_bytes = rapport_intervention_pdf(ticket)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="rapport-intervention-{ticket.reference}.pdf"')
        return resp

    @action(detail=True, methods=['get', 'post'], url_path='pieces',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def pieces(self, request, pk=None):
        """N46 — pièces consommées sur le ticket. GET liste, POST ajoute.

        Sur ajout, `decrement` (vrai) décrémente le stock (MouvementStock
        SORTIE, jamais en double). Les prix d'achat restent internes : ils
        n'apparaissent jamais ici ni sur le rapport d'intervention."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.pieces.select_related('produit')
            return Response(PieceConsommeeSerializer(qs, many=True).data)
        from apps.stock.selectors import (
            get_produit_or_raise, produit_does_not_exist,
        )
        from apps.stock.services import (
            mouvement_type_sortie, record_stock_movement,
        )
        try:
            quantite = Decimal(str(request.data.get('quantite') or '1'))
        except (InvalidOperation, TypeError):
            return Response({'detail': 'Quantité invalide.'}, status=400)
        if quantite <= 0:
            return Response({'detail': 'Quantité invalide.'}, status=400)
        try:
            produit = get_produit_or_raise(
                ticket.company, request.data.get('produit'))
        except (produit_does_not_exist(), ValueError, TypeError):
            return Response({'detail': 'Produit inconnu.'}, status=404)
        decrement = str(request.data.get('decrement') or '') in (
            '1', 'true', 'True', 'on')
        if decrement:
            # ERR80 — garde plancher : ne jamais piloter le stock en négatif.
            # On bloque le décrément qui dépasserait le stock en main.
            produit.refresh_from_db()
            if quantite > produit.quantite_stock:
                return Response(
                    {'detail': 'Stock insuffisant : '
                     f'{produit.quantite_stock} en main, {quantite} demandé(s).'},
                    status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            piece = PieceConsommee.objects.create(
                company=ticket.company, ticket=ticket, produit=produit,
                quantite=quantite, created_by=request.user)
            if decrement:
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant - quantite
                record_stock_movement(
                    company=ticket.company, produit=produit,
                    type_mouvement=mouvement_type_sortie(),
                    quantite=quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Consommation SAV {ticket.reference}',
                    created_by=request.user)
                piece.stock_decremente = True
                piece.save(update_fields=['stock_decremente'])
            # L310 — journaliser l'ajout (et le décrément éventuel) à l'Historique.
            suffixe = ' (stock −)' if decrement else ''
            activity.log_note(
                ticket, request.user,
                f'Pièce {produit.nom} ×{quantite} consommée{suffixe}')
        return Response(
            PieceConsommeeSerializer(piece).data, status=201)

    @action(detail=True, methods=['delete'],
            url_path=r'pieces/(?P<piece_id>[^/.]+)',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def supprimer_piece(self, request, pk=None, piece_id=None):
        """Retire une pièce du ticket ; si le stock avait été décrémenté, le
        ré-incrémente (MouvementStock ENTRÉE) pour rester cohérent."""
        ticket = self.get_object()
        from apps.stock.services import (
            mouvement_type_entree, record_stock_movement,
        )
        try:
            piece = ticket.pieces.select_related('produit').get(pk=piece_id)
        except (PieceConsommee.DoesNotExist, ValueError):
            return Response({'detail': 'Introuvable.'}, status=404)
        with transaction.atomic():
            if piece.stock_decremente:
                produit = piece.produit
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant + piece.quantite
                record_stock_movement(
                    company=ticket.company, produit=produit,
                    type_mouvement=mouvement_type_entree(),
                    quantite=piece.quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Annulation pièce SAV {ticket.reference}',
                    created_by=request.user)
            # L310 — journaliser le retrait (et la ré-incrémentation éventuelle).
            suffixe = ' (stock +)' if piece.stock_decremente else ''
            nom = getattr(piece.produit, 'nom', '?')
            qte = piece.quantite
            activity.log_note(
                ticket, request.user,
                f'Pièce {nom} ×{qte} retirée{suffixe}')
            piece.delete()
        return Response(status=204)

    @action(detail=True, methods=['get', 'post', 'patch'],
            url_path='checklist',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def checklist(self, request, pk=None):
        """FG82 — Checklist de visite de maintenance sur le ticket.

        GET : liste les items cochés/non cochés.
        POST : initialise depuis un template (body: {template_id: N}) ;
               idempotent (ne duplique pas si déjà initialisée).
        PATCH : met à jour un item (body: {cle: 'X', coche: true, note: '…'}).
        """
        ticket = self.get_object()
        if request.method == 'GET':
            items = ticket.checklist_items.order_by('ordre', 'cle')
            return Response(TicketChecklistItemSerializer(items, many=True).data)

        if request.method == 'POST':
            template_id = request.data.get('template_id')
            if not template_id:
                return Response({'detail': 'template_id requis.'}, status=400)
            try:
                tmpl = MaintenanceChecklistTemplate.objects.get(
                    pk=template_id, company=ticket.company)
            except MaintenanceChecklistTemplate.DoesNotExist:
                return Response({'detail': 'Template introuvable.'}, status=404)
            created = 0
            for item in tmpl.items.filter(actif=True):
                _, is_new = TicketChecklistItem.objects.get_or_create(
                    ticket=ticket, cle=item.cle,
                    defaults={
                        'company': ticket.company,
                        'libelle': item.libelle,
                        'ordre': item.ordre,
                    })
                if is_new:
                    created += 1
            items = ticket.checklist_items.order_by('ordre', 'cle')
            return Response(TicketChecklistItemSerializer(items, many=True).data,
                            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        # PATCH — mise à jour d'un item
        cle = request.data.get('cle')
        if not cle:
            return Response({'detail': 'cle requis.'}, status=400)
        try:
            item = ticket.checklist_items.get(cle=cle)
        except TicketChecklistItem.DoesNotExist:
            return Response({'detail': 'Item introuvable.'}, status=404)
        if 'coche' in request.data:
            item.coche = bool(request.data['coche'])
            if item.coche:
                item.coche_par = request.user
                item.date_coche = timezone.now()
            else:
                item.coche_par = None
                item.date_coche = None
        if 'note' in request.data:
            item.note = request.data['note'] or ''
        item.save()
        return Response(TicketChecklistItemSerializer(item).data)


# ── FG81 — Réglages SLA ────────────────────────────────────────────────────────

class SavSlaSettingsViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réglages SLA SAV par société (FG81). Singleton : list renvoie l'unique
    enregistrement ; écriture responsable/admin."""
    queryset = SavSlaSettings.objects.all()
    serializer_class = SavSlaSettingsSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def list(self, request, *args, **kwargs):
        company = request.user.company
        if company is None:
            return Response({})
        obj = SavSlaSettings.get(company)
        return Response(self.get_serializer(obj).data)

    def create(self, request, *args, **kwargs):
        """Upsert du singleton (PATCH-like via POST)."""
        company = request.user.company
        obj = SavSlaSettings.get(company)
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── FG82 — Checklist templates ────────────────────────────────────────────────

class MaintenanceChecklistTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """Templates de checklist de maintenance (FG82). Lecture tout rôle."""
    queryset = MaintenanceChecklistTemplate.objects.prefetch_related('items').all()
    serializer_class = MaintenanceChecklistTemplateSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(actif=True)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        if instance.protege:
            raise ValidationError('Ce template est protégé et ne peut être supprimé.')
        instance.delete()


# ── FG83 — Réclamation garantie fournisseur ───────────────────────────────────

class WarrantyClaimViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réclamations garantie fournisseur / flux RMA (FG83).
    Lecture tout rôle ; écriture responsable/admin."""
    queryset = WarrantyClaim.objects.select_related(
        'equipement', 'equipement__produit', 'ticket',
    ).all()
    serializer_class = WarrantyClaimSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['rma_ref', 'description', 'fournisseur_nom_cache']
    ordering_fields = ['date_creation', 'date_signalement', 'statut']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        equipement = self.request.query_params.get('equipement')
        ticket = self.request.query_params.get('ticket')
        statut = self.request.query_params.get('statut')
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        equipement = serializer.validated_data.get('equipement')
        ticket = serializer.validated_data.get('ticket')
        if equipement and equipement.company_id != company.id:
            raise ValidationError({'equipement': 'Équipement inconnu.'})
        if ticket and ticket.company_id != company.id:
            raise ValidationError({'ticket': 'Ticket inconnu.'})

    def _resolve_fournisseur(self, serializer):
        """Résout le nom du fournisseur via stock.selectors (cross-app)."""
        fid = serializer.validated_data.get('fournisseur_id_ext')
        if fid:
            try:
                from apps.stock.selectors import get_fournisseur_by_id
                f = get_fournisseur_by_id(self.request.user.company, fid)
                if f:
                    serializer.validated_data['fournisseur_nom_cache'] = f.nom
            except Exception:
                pass

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        self._resolve_fournisseur(serializer)
        super().perform_update(serializer)


# ── FG87 — Base de connaissances SAV ─────────────────────────────────────────

class KbArticleViewSet(TenantMixin, viewsets.ModelViewSet):
    """Articles de la base de connaissances SAV (FG87).
    Cherchables par texte libre + filtrables par produit/catégorie."""
    queryset = KbArticle.objects.select_related('produit').all()
    serializer_class = KbArticleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'corps', 'categorie', 'tags']
    ordering_fields = ['date_modification', 'date_creation', 'titre']
    ordering = ['-date_modification']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(actif=True)
        produit = self.request.query_params.get('produit')
        categorie = self.request.query_params.get('categorie')
        if produit:
            qs = qs.filter(produit_id=produit)
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)


# ── FG89 — Prévision pièces SAV ───────────────────────────────────────────────

def sav_parts_forecast(request):
    """FG89 — Aperçu consommation de pièces SAV sur une fenêtre glissante.

    Agrège PieceConsommee par produit sur les N derniers mois, calcule la
    consommation mensuelle moyenne et suggère une quantité de réapprovisionnement.
    Interne uniquement — aucun prix d'achat n'est exposé.
    """
    from rest_framework.request import Request as DRFRequest
    from apps.sav.models import PieceConsommee
    from django.db.models import Sum

    company = request.user.company
    months = int(request.query_params.get('months', 12))
    since = timezone.localdate() - timedelta(days=months * 30)

    qs = (PieceConsommee.objects
          .filter(company=company, date_creation__date__gte=since)
          .values('produit', 'produit__nom', 'produit__marque', 'produit__sku')
          .annotate(total_consomme=Sum('quantite'))
          .order_by('-total_consomme'))

    results = []
    for row in qs:
        mensuel_moyen = float(row['total_consomme']) / max(months, 1)
        results.append({
            'produit': row['produit'],
            'nom': row['produit__nom'],
            'marque': row['produit__marque'] or '',
            'sku': row['produit__sku'] or '',
            'total_consomme': float(row['total_consomme']),
            'mois_fenetre': months,
            'consommation_mensuelle_moy': round(mensuel_moyen, 2),
            # Suggestion : 2 mois de stock de sécurité.
            'qte_suggere_reappro': round(mensuel_moyen * 2, 1),
        })

    return Response(results)


# ── FG81 — Scan journalier de breach (appelé par Celery-beat ou management cmd) ──

def scan_sla_breaches():
    """FG81 — Parcourt tous les tickets ouverts avec sla_due_at dépassé, met à
    jour sla_breach et notifie le technicien responsable. Idempotent.

    Appelé par le scan journalier (management command ou Celery-beat).
    Aucune modification si sla_breach_enabled est False pour la société."""
    from apps.notifications.services import notify
    from apps.notifications.models import EventType

    today = timezone.localdate()
    breached = Ticket.objects.filter(
        statut__in=Ticket.OPEN_STATUTS,
        annule=False,
        sla_due_at__lt=today,
        sla_breach=False,
    ).select_related('company', 'technicien_responsable')

    updated = 0
    for ticket in breached:
        # Vérifie que la société a activé les notifications SLA.
        sla = SavSlaSettings.get(ticket.company)
        if not sla.sla_breach_enabled:
            continue
        ticket.sla_breach = True
        ticket.save(update_fields=['sla_breach'])
        updated += 1
        if ticket.technicien_responsable_id:
            notify(
                user=ticket.technicien_responsable,
                event_type=EventType.SAV_TICKET_BREACHING,
                title=f'SLA dépassé — {ticket.reference}',
                body=(f'Le ticket {ticket.reference} a dépassé son délai SLA '
                      f'({ticket.sla_due_at.strftime("%d/%m/%Y")}).'),
                link=f'/sav/tickets/{ticket.pk}',
                company=ticket.company,
            )
    return updated
