from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.stock.models import MouvementStock
from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture
from .serializers import (
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


class DevisViewSet(viewsets.ModelViewSet):
    queryset = Devis.objects.select_related(
        'client', 'created_by'
    ).prefetch_related('lignes').all()

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DevisWriteSerializer
        return DevisSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'generer_pdf', 'telecharger_pdf', 'convertir_en_bc'
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            company=self.request.user.company,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
        from .tasks import task_generate_devis_pdf
        task = task_generate_devis_pdf.delay(devis.id)
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='telecharger-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def telecharger_pdf(self, request, pk=None):
        devis = self.get_object()
        if not devis.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from .utils.pdf import download_pdf
            pdf_bytes = download_pdf(devis.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f'{devis.reference}.pdf'
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(
        detail=True,
        methods=['post'],
        url_path='convertir-bc',
        permission_classes=[IsResponsableOrAdmin],
    )
    def convertir_en_bc(self, request, pk=None):
        devis = self.get_object()
        if devis.statut != Devis.Statut.ACCEPTE:
            return Response(
                {'detail': (
                    'Le devis doit être au statut '
                    '« Accepté » pour être converti.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if BonCommande.objects.filter(devis=devis).exists():
            return Response(
                {'detail': 'Un bon de commande existe déjà pour ce devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        prefix = f"BC-{now.strftime('%Y%m')}"
        company = request.user.company
        count = BonCommande.objects.filter(
            reference__startswith=prefix, company=company
        ).count() + 1
        bc = BonCommande.objects.create(
            reference=f"{prefix}-{count:04d}",
            devis=devis,
            client=devis.client,
            statut=BonCommande.Statut.EN_ATTENTE,
            company=company,
        )
        serializer = BonCommandeSerializer(bc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LigneDevisViewSet(viewsets.ModelViewSet):
    queryset = LigneDevis.objects.select_related('devis', 'produit').all()
    serializer_class = LigneDevisSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(devis__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class BonCommandeViewSet(viewsets.ModelViewSet):
    queryset = BonCommande.objects.select_related('client', 'devis').all()
    serializer_class = BonCommandeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'client__nom', 'client__email']
    ordering_fields = [
        'date_creation', 'date_livraison_prevue', 'statut'
    ]
    ordering = ['-date_creation']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'confirmer', 'marquer_livre', 'annuler', 'creer_facture'
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        now = timezone.now()
        prefix = f"BC-{now.strftime('%Y%m')}"
        company = self.request.user.company
        count = BonCommande.objects.filter(
            reference__startswith=prefix, company=company
        ).count() + 1
        serializer.save(
            reference=f"{prefix}-{count:04d}",
            company=company,
        )

    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.EN_ATTENTE:
            return Response(
                {'detail': 'Seul un BC en attente peut être confirmé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.CONFIRME
        bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='marquer-livre',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_livre(self, request, pk=None):
        bc = self.get_object()
        if bc.statut != BonCommande.Statut.CONFIRME:
            return Response(
                {'detail': (
                    'Le BC doit être confirmé avant d\'être livré.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            if bc.devis:
                for ligne in bc.devis.lignes.select_related('produit'):
                    produit = ligne.produit
                    produit.refresh_from_db()
                    qte = int(ligne.quantite)
                    qte_avant = produit.quantite_stock
                    qte_apres = qte_avant - qte
                    if qte_apres < 0:
                        return Response(
                            {'detail': (
                                f'Stock insuffisant pour '
                                f'« {produit.nom} » '
                                f'(disponible : {qte_avant}, '
                                f'requis : {qte}).'
                            )},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    MouvementStock.objects.create(
                        company=bc.company,
                        produit=produit,
                        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                        quantite=qte,
                        quantite_avant=qte_avant,
                        quantite_apres=qte_apres,
                        reference=bc.reference,
                        note=f'Livraison BC {bc.reference}',
                        created_by=request.user,
                    )
                    produit.quantite_stock = qte_apres
                    produit.save(update_fields=['quantite_stock'])
            bc.statut = BonCommande.Statut.LIVRE
            bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        bc = self.get_object()
        if bc.statut == BonCommande.Statut.LIVRE:
            return Response(
                {'detail': 'Un BC livré ne peut pas être annulé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bc.statut = BonCommande.Statut.ANNULE
        bc.save()
        return Response(BonCommandeSerializer(bc).data)

    @action(detail=True, methods=['post'], url_path='creer-facture',
            permission_classes=[IsResponsableOrAdmin])
    def creer_facture(self, request, pk=None):
        bc = self.get_object()
        if bc.statut not in [
            BonCommande.Statut.CONFIRME, BonCommande.Statut.LIVRE
        ]:
            return Response(
                {'detail': 'Le BC doit être confirmé ou livré.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Facture.objects.filter(bon_commande=bc).exists():
            return Response(
                {'detail': 'Une facture existe déjà pour ce BC.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        prefix = f"FAC-{now.strftime('%Y%m')}"
        company = request.user.company
        count = Facture.objects.filter(
            reference__startswith=prefix, company=company
        ).count() + 1
        with transaction.atomic():
            facture = Facture.objects.create(
                reference=f"{prefix}-{count:04d}",
                bon_commande=bc,
                client=bc.client,
                statut=Facture.Statut.BROUILLON,
                created_by=request.user,
                company=company,
            )
            if bc.devis:
                for ligne in bc.devis.lignes.all():
                    LigneFacture.objects.create(
                        facture=facture,
                        produit=ligne.produit,
                        designation=ligne.designation,
                        quantite=ligne.quantite,
                        prix_unitaire=ligne.prix_unitaire,
                        remise=ligne.remise,
                    )
        return Response(
            FactureSerializer(facture).data,
            status=status.HTTP_201_CREATED,
        )


class FactureViewSet(viewsets.ModelViewSet):
    queryset = Facture.objects.select_related(
        'client', 'created_by', 'bon_commande'
    ).prefetch_related('lignes').all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'client__nom', 'client__prenom', 'client__email'
    ]
    ordering_fields = [
        'date_emission', 'date_echeance', 'statut', 'reference'
    ]
    ordering = ['-date_emission']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return FactureWriteSerializer
        return FactureSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'emettre', 'marquer_payee', 'annuler',
            'generer_pdf', 'telecharger_pdf', 'envoyer_email',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        now = timezone.now()
        prefix = f"FAC-{now.strftime('%Y%m')}"
        company = self.request.user.company
        count = Facture.objects.filter(
            reference__startswith=prefix, company=company
        ).count() + 1
        serializer.save(
            created_by=self.request.user,
            reference=f"{prefix}-{count:04d}",
            company=company,
        )

    @action(detail=True, methods=['post'], url_path='emettre',
            permission_classes=[IsResponsableOrAdmin])
    def emettre(self, request, pk=None):
        facture = self.get_object()
        if facture.statut != Facture.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une facture brouillon peut être émise.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not facture.lignes.exists():
            return Response(
                {'detail': (
                    'La facture doit contenir au moins une ligne.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.EMISE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='marquer-payee',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_payee(self, request, pk=None):
        facture = self.get_object()
        if facture.statut not in [
            Facture.Statut.EMISE, Facture.Statut.EN_RETARD
        ]:
            return Response(
                {'detail': (
                    'Seule une facture émise ou en retard '
                    'peut être marquée payée.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.PAYEE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        facture = self.get_object()
        if facture.statut == Facture.Statut.PAYEE:
            return Response(
                {'detail': 'Une facture payée ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facture.statut = Facture.Statut.ANNULEE
        facture.save()
        return Response(FactureSerializer(facture).data)

    @action(detail=True, methods=['post'], url_path='generer-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def generer_pdf(self, request, pk=None):
        facture = self.get_object()
        from .tasks import task_generate_facture_pdf
        task = task_generate_facture_pdf.delay(facture.id)
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='telecharger-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def telecharger_pdf(self, request, pk=None):
        facture = self.get_object()
        if not facture.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from .utils.pdf import download_pdf
            pdf_bytes = download_pdf(facture.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f'{facture.reference}.pdf'
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        return Response(
            {'detail': 'Envoi email (TODO Sem. 4)'},
            status=status.HTTP_202_ACCEPTED,
        )


class LigneFactureViewSet(viewsets.ModelViewSet):
    queryset = LigneFacture.objects.select_related(
        'facture', 'produit'
    ).all()
    serializer_class = LigneFactureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(facture__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]
