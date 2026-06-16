from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import HasPermissionOrLegacy, IsAdminRole
from apps.ventes.utils.references import create_with_reference
from apps.imports.exports import XlsxExportMixin

from . import activity
from .models import (
    ContratMaintenance, Equipement, ReclamationGarantie, Ticket, TicketPiece,
)
from .serializers import (
    ContratMaintenanceSerializer,
    EquipementSerializer, ReclamationGarantieSerializer,
    TicketSerializer, TicketActivitySerializer, TicketPieceSerializer,
    EXPIRING_SOON_DAYS,
)
from .services import decrementer_stock_piece, generer_ticket_du
from .pdf import rapport_intervention_pdf, rapport_maintenance_pdf

# Statuts d'un ticket considérés « résolu / clôturé » — autorisent le rapport.
CLOSED_STATUTS = [Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE]

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class EquipementViewSet(XlsxExportMixin, TenantMixin, viewsets.ModelViewSet):
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

    # Export .xlsx (respecte tous les filtres produit/marque/garantie/etc.).
    export_filename = 'equipements.xlsx'
    export_sheet_title = 'Équipements'
    export_columns = [
        ('numero_serie', 'N° série'), ('produit', 'Produit'),
        ('marque', 'Marque'), ('installation', 'Chantier'),
        ('client', 'Client'), ('statut', 'Statut'),
        ('date_pose', 'Date pose'),
        ('date_fin_garantie', 'Fin garantie'),
        ('date_fin_garantie_production', 'Fin garantie production'),
    ]

    def get_export_row(self, obj):
        inst = obj.installation
        return {
            'numero_serie': obj.numero_serie or '',
            'produit': obj.produit.nom if obj.produit else '',
            'marque': (obj.produit.marque or '') if obj.produit else '',
            'installation': inst.reference if inst else '',
            'client': (str(inst.client) if inst and inst.client else ''),
            'statut': obj.get_statut_display(),
            'date_pose': str(obj.date_pose) if obj.date_pose else '',
            'date_fin_garantie': (str(obj.date_fin_garantie)
                                  if obj.date_fin_garantie else ''),
            'date_fin_garantie_production': (
                str(obj.date_fin_garantie_production)
                if obj.date_fin_garantie_production else ''),
        }

    def get_queryset(self):
        qs = super().get_queryset()
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
        if self.action in READ_ACTIONS + ['export', 'garanties_expirent']:
            return [HasPermissionOrLegacy('equipement_voir')()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('equipement_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    @action(detail=False, methods=['get'], url_path='garanties-expirent',
            permission_classes=[HasPermissionOrLegacy('equipement_voir')])
    def garanties_expirent(self, request):
        """Garanties qui expirent (N48) — équipements dont la fin de garantie
        tombe dans l'horizon ?jours (défaut 90). Calculé à la volée, scopé à la
        société. Inclut les garanties déjà dépassées (jours négatifs)."""
        try:
            jours = int(request.query_params.get('jours', 90))
        except (ValueError, TypeError):
            jours = 90
        today = timezone.localdate()
        horizon = today + timedelta(days=jours)
        qs = (self.get_queryset()
              .filter(date_fin_garantie__isnull=False,
                      date_fin_garantie__lte=horizon)
              .order_by('date_fin_garantie'))
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        return Response(self.get_serializer(qs, many=True).data)

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
        serializer.save(company=company, created_by=self.request.user)
        # Calcul des horloges de garantie après la pose des FK.
        inst = serializer.instance
        inst.recompute_garanties()
        inst.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production'])

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)
        inst = serializer.instance
        inst.recompute_garanties()
        inst.save(update_fields=[
            'date_fin_garantie', 'date_fin_garantie_production'])


class TicketViewSet(XlsxExportMixin, TenantMixin, viewsets.ModelViewSet):
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

    # Export .xlsx (respecte statut/type/priorité/technicien/ouvert/annule…).
    export_filename = 'tickets-sav.xlsx'
    export_sheet_title = 'Tickets SAV'
    export_columns = [
        ('reference', 'Référence'), ('client', 'Client'),
        ('installation', 'Chantier'), ('type', 'Type'),
        ('statut', 'Statut'), ('priorite', 'Priorité'),
        ('sous_garantie', 'Sous garantie'),
        ('date_ouverture', 'Ouvert le'),
        ('date_resolution', 'Résolu le'),
    ]

    def get_export_row(self, obj):
        return {
            'reference': obj.reference,
            'client': str(obj.client) if obj.client else '',
            'installation': (obj.installation.reference
                             if obj.installation else ''),
            'type': obj.get_type_display(),
            'statut': obj.get_statut_display(),
            'priorite': obj.get_priorite_display(),
            'sous_garantie': obj.get_sous_garantie_display(),
            'date_ouverture': (str(obj.date_ouverture)
                               if obj.date_ouverture else ''),
            'date_resolution': (str(obj.date_resolution)
                                if obj.date_resolution else ''),
        }

    def get_queryset(self):
        qs = super().get_queryset()
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
        # 'pieces' (GET+POST) et 'rapport_pdf' : lecture autorisée par sav_voir ;
        # l'écriture des pièces revérifie sav_gerer dans l'action elle-même.
        if self.action in READ_ACTIONS + [
                'historique', 'export', 'rapport_pdf', 'pieces']:
            return [HasPermissionOrLegacy('sav_voir')()]
        elif self.action in WRITE_ACTIONS + [
                'noter', 'annuler', 'reactiver', 'supprimer_piece']:
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

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        date_ouverture = (
            serializer.validated_data.get('date_ouverture')
            or timezone.localdate())
        create_with_reference(
            Ticket, 'SAV', company,
            lambda ref: serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
                date_ouverture=date_ouverture),
        )
        activity.log_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        old = Ticket.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        activity.log_changes(old, serializer.instance, self.request.user)

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

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def rapport_pdf(self, request, pk=None):
        """Rapport d'intervention FR (N45) — disponible uniquement pour un
        ticket résolu/clôturé. Rendu à la volée, streamé en PDF, jamais stocké.
        Côté client : aucun prix d'achat."""
        ticket = self.get_object()
        if ticket.statut not in CLOSED_STATUTS:
            return Response(
                {'detail': 'Le rapport est disponible une fois le ticket '
                           'résolu ou clôturé.'},
                status=status.HTTP_400_BAD_REQUEST)
        pdf_bytes = rapport_intervention_pdf(ticket)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="rapport-{ticket.reference}.pdf"')
        return response

    @action(detail=True, methods=['get', 'post'], url_path='pieces',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def pieces(self, request, pk=None):
        """Pièces consommées sur le ticket (N46).

        GET : liste. POST (sav_gerer) : enregistre une pièce et décrémente
        OPTIONNELLEMENT le stock (?decrement=1 / body decrementer_stock=true),
        en réutilisant le patron MouvementStock SORTIE de l'OS."""
        ticket = self.get_object()
        if request.method == 'GET':
            qs = ticket.pieces.select_related('produit').all()
            return Response(TicketPieceSerializer(qs, many=True).data)

        # Écriture → exige sav_gerer.
        if not HasPermissionOrLegacy('sav_gerer')().has_permission(
                request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        company = request.user.company
        produit_id = request.data.get('produit')
        quantite = request.data.get('quantite', 1)
        from apps.stock.models import Produit
        try:
            produit = Produit.objects.get(pk=produit_id)
        except (Produit.DoesNotExist, ValueError, TypeError):
            return Response({'produit': 'Produit inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if produit.company_id not in (company.id, None):
            return Response({'produit': 'Produit inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            quantite = int(quantite)
        except (ValueError, TypeError):
            quantite = 1
        if quantite < 1:
            return Response({'quantite': 'Quantité invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)

        piece = TicketPiece.objects.create(
            company=company, ticket=ticket, produit=produit,
            quantite=quantite, note=(request.data.get('note') or None),
            created_by=request.user)

        decrement = (request.query_params.get('decrement') == '1'
                     or request.data.get('decrementer_stock') in
                     (True, 'true', '1', 1))
        if decrement:
            decrementer_stock_piece(piece, user=request.user)
            piece.refresh_from_db()
        activity.log_note(
            ticket, request.user,
            f"Pièce ajoutée : {quantite} × {produit.nom}"
            + (' (stock décrémenté)' if piece.stock_decremente else ''))
        return Response(TicketPieceSerializer(piece).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'],
            url_path=r'pieces/(?P<piece_id>[^/.]+)',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def supprimer_piece(self, request, pk=None, piece_id=None):
        """Retire une pièce du ticket (ne ré-incrémente PAS le stock — le
        mouvement reste tracé ; un ajustement manuel s'en charge si besoin)."""
        ticket = self.get_object()
        try:
            piece = ticket.pieces.get(pk=piece_id)
        except TicketPiece.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        piece.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContratMaintenanceViewSet(TenantMixin, viewsets.ModelViewSet):
    """Contrats de maintenance préventive (visites récurrentes). Tout est scopé
    à la société ; le client est résolu côté serveur depuis le chantier. La
    détection d'échéance et la génération de tickets sont calculées À LA LECTURE
    / à la demande — aucun planificateur, comme partout dans l'OS."""
    queryset = ContratMaintenance.objects.select_related(
        'client', 'installation',
    ).all()
    serializer_class = ContratMaintenanceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'libelle', 'client__nom', 'client__prenom', 'installation__reference',
    ]
    ordering_fields = ['date_debut', 'derniere_visite', 'date_creation']
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        client = params.get('client')
        actif = params.get('actif')
        if installation:
            qs = qs.filter(installation_id=installation)
        if client:
            qs = qs.filter(client_id=client)
        if actif == 'true':
            qs = qs.filter(actif=True)
        elif actif == 'false':
            qs = qs.filter(actif=False)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
                'a_venir', 'a_renouveler', 'rapport_pdf']:
            return [HasPermissionOrLegacy('sav_voir')()]
        elif self.action in WRITE_ACTIONS + ['generer_dus', 'visite_effectuee']:
            return [HasPermissionOrLegacy('sav_gerer')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def _check_tenant(self, serializer):
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        if installation is not None and installation.company_id != company.id:
            raise ValidationError({'installation': 'Chantier inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        # Client résolu côté serveur depuis le chantier — jamais lu du corps.
        installation = serializer.validated_data.get('installation')
        serializer.save(
            company=company, client=installation.client,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        installation = serializer.validated_data.get('installation')
        client = installation.client if installation is not None else None
        if client is not None:
            serializer.save(company=company, client=client)
        else:
            serializer.save(company=company)

    @action(detail=True, methods=['post'], url_path='generer-dus',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def generer_dus(self, request, pk=None):
        """Génère le ticket dû d'UN contrat (idempotent). Renvoie le contrat à
        jour + le ticket créé le cas échéant."""
        contrat = self.get_object()
        ticket = generer_ticket_du(contrat, user=request.user)
        contrat.refresh_from_db()
        data = self.get_serializer(contrat).data
        data['ticket_genere'] = (
            TicketSerializer(ticket, context={'request': request}).data
            if ticket else None)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='a-venir',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def a_venir(self, request):
        """Liste les contrats actifs dont une visite est due / due bientôt —
        échéances CALCULÉES à la lecture. On NE génère rien ici par défaut :
        ?generer=1 déclenche en plus la création des tickets dus (idempotente)."""
        generate = request.query_params.get('generer') == '1'
        rows = []
        for contrat in self.get_queryset().filter(actif=True):
            if not contrat.est_a_venir():
                continue
            if generate:
                generer_ticket_du(contrat, user=request.user)
                contrat.refresh_from_db()
            rows.append(self.get_serializer(contrat).data)
        # Tri par échéance la plus proche d'abord (les plus en retard en tête).
        rows.sort(key=lambda r: r.get('prochaine_visite') or '')
        return Response(rows)

    @action(detail=False, methods=['get'], url_path='a-renouveler',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def a_renouveler(self, request):
        """Contrats actifs approchant leur renouvellement (N47) — date de fin
        dans l'horizon RENEWAL_SOON_DAYS, calculée à la lecture. Triés par
        date de fin la plus proche d'abord."""
        rows = []
        for contrat in self.get_queryset().filter(actif=True):
            if not contrat.a_renouveler():
                continue
            rows.append(self.get_serializer(contrat).data)
        rows.sort(key=lambda r: r.get('date_fin_effective') or '')
        return Response(rows)

    @action(detail=True, methods=['post'], url_path='visite-effectuee',
            permission_classes=[HasPermissionOrLegacy('sav_gerer')])
    def visite_effectuee(self, request, pk=None):
        """Marque une visite préventive comme effectuée (N47) : avance la
        dernière visite à aujourd'hui (ou ?date). Renvoie le contrat à jour ;
        le rapport PDF se récupère via l'action `rapport-pdf`."""
        contrat = self.get_object()
        date_str = request.data.get('date')
        if date_str:
            from django.utils.dateparse import parse_date
            d = parse_date(date_str)
            if d is None:
                return Response({'date': 'Date invalide.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            d = timezone.localdate()
        contrat.derniere_visite = d
        contrat.derniere_echeance_traitee = d
        contrat.save(update_fields=[
            'derniere_visite', 'derniere_echeance_traitee',
            'date_modification'])
        return Response(self.get_serializer(contrat).data)

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[HasPermissionOrLegacy('sav_voir')])
    def rapport_pdf(self, request, pk=None):
        """Rapport de maintenance préventive FR (N47). Rendu à la volée, streamé
        en PDF, jamais stocké. Côté client : aucun prix d'achat. ?ticket=<id>
        attache le compte rendu d'un ticket préventif clôturé du même contrat."""
        contrat = self.get_object()
        ticket = None
        ticket_id = request.query_params.get('ticket')
        if ticket_id:
            ticket = (Ticket.objects
                      .filter(pk=ticket_id, company=request.user.company,
                              installation=contrat.installation)
                      .prefetch_related('interventions', 'pieces__produit')
                      .first())
        pdf_bytes = rapport_maintenance_pdf(contrat, ticket=ticket)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="maintenance-contrat-{contrat.pk}.pdf"')
        return response


class ReclamationGarantieViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réclamations de garantie (N48) — trace auditable d'une demande de prise
    en charge sous garantie d'un équipement, avec son résultat. CRUD scopé à la
    société ; acteur posé côté serveur, équipement vérifié côté serveur."""
    queryset = ReclamationGarantie.objects.select_related(
        'equipement', 'equipement__produit',
    ).all()
    serializer_class = ReclamationGarantieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'description', 'equipement__numero_serie', 'equipement__produit__nom',
    ]
    ordering_fields = ['date', 'date_creation', 'resultat']
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        equipement = params.get('equipement')
        resultat = params.get('resultat')
        if equipement:
            qs = qs.filter(equipement_id=equipement)
        if resultat:
            qs = qs.filter(resultat=resultat)
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
        equipement = serializer.validated_data.get('equipement')
        if equipement is not None and equipement.company_id != company.id:
            raise ValidationError({'equipement': 'Équipement inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
