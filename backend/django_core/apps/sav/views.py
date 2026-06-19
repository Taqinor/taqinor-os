from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import HasPermissionOrLegacy, IsAdminRole
from apps.ventes.utils.references import create_with_reference

from . import activity
from .models import Equipement, Ticket, PieceConsommee
from .pdf import rapport_intervention_pdf
from .serializers import (
    EquipementSerializer, TicketSerializer, TicketActivitySerializer,
    PieceConsommeeSerializer, EXPIRING_SOON_DAYS,
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

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        company = self.request.user.company
        self._resolve_from_equipement(serializer)
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
        from apps.stock.models import Produit, MouvementStock
        try:
            quantite = Decimal(str(request.data.get('quantite') or '1'))
        except (InvalidOperation, TypeError):
            return Response({'detail': 'Quantité invalide.'}, status=400)
        if quantite <= 0:
            return Response({'detail': 'Quantité invalide.'}, status=400)
        try:
            produit = Produit.objects.get(
                pk=request.data.get('produit'), company=ticket.company)
        except (Produit.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Produit inconnu.'}, status=404)
        decrement = str(request.data.get('decrement') or '') in (
            '1', 'true', 'True', 'on')
        with transaction.atomic():
            piece = PieceConsommee.objects.create(
                company=ticket.company, ticket=ticket, produit=produit,
                quantite=quantite, created_by=request.user)
            if decrement:
                produit.refresh_from_db()
                qte_avant = produit.quantite_stock
                qte_apres = qte_avant - quantite
                MouvementStock.objects.create(
                    company=ticket.company, produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                    quantite=quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Consommation SAV {ticket.reference}',
                    created_by=request.user)
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
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
        from apps.stock.models import MouvementStock
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
                MouvementStock.objects.create(
                    company=ticket.company, produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                    quantite=piece.quantite, quantite_avant=qte_avant,
                    quantite_apres=qte_apres, reference=ticket.reference,
                    note=f'Annulation pièce SAV {ticket.reference}',
                    created_by=request.user)
                produit.quantite_stock = qte_apres
                produit.save(update_fields=['quantite_stock'])
            # L310 — journaliser le retrait (et la ré-incrémentation éventuelle).
            suffixe = ' (stock +)' if piece.stock_decremente else ''
            nom = getattr(piece.produit, 'nom', '?')
            qte = piece.quantite
            activity.log_note(
                ticket, request.user,
                f'Pièce {nom} ×{qte} retirée{suffixe}')
            piece.delete()
        return Response(status=204)
