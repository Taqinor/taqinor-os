from django.db import transaction
from django.http import HttpResponse
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.stock.models import MouvementStock
from .models import (
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
)
from .serializers import (
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from .utils.references import create_with_reference

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
            'generer_pdf', 'telecharger_pdf', 'convertir_en_bc', 'proposal',
            'generer_facture',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from apps.crm.services import resolve_client_for_lead

        company = self.request.user.company
        lead = serializer.validated_data.get('lead')
        client = serializer.validated_data.get('client')

        # Tenant safety: lead and client must belong to the user's company.
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})

        # Lead-primary: when no client is given, resolve it from the lead
        # (reuses the linked/matching client, else creates one — no duplicates).
        if client is None:
            if lead is None:
                raise ValidationError(
                    {'client': 'Un client ou un lead est requis.'})
            client = resolve_client_for_lead(lead)

        create_with_reference(
            Devis, 'DEV', company,
            lambda ref: serializer.save(
                reference=ref,
                client=client,
                created_by=self.request.user,
                company=company,
            ),
        )

        # Mouvement automatique du funnel CRM : un devis créé directement en
        # « envoyé »/« accepté » avance le lead (ancien statut ≡ brouillon).
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, Devis.Statut.BROUILLON,
            serializer.instance.statut, self.request.user,
        )

    def perform_update(self, serializer):
        # Snapshot du statut AVANT écriture, puis mouvement automatique du
        # funnel CRM (envoye → QUOTE_SENT, accepte → SIGNED). Import local
        # pour éviter les cycles, comme dans perform_create.
        ancien_statut = serializer.instance.statut
        super().perform_update(serializer)
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, ancien_statut,
            serializer.instance.statut, self.request.user,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
        from .quote_engine import clean_pdf_options
        from .tasks import task_generate_devis_pdf
        # Format options (simulator parity) — whitelisted server-side.
        pdf_options = clean_pdf_options(request.data)
        task = task_generate_devis_pdf.delay(devis.id, pdf_options)
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='proposal',
        permission_classes=[IsResponsableOrAdmin],
    )
    def proposal(self, request, pk=None):
        """Canonical client-facing quote PDF path (CLAUDE.md rule #4).

        Renders the premium quote PDF for this devis (synchronously, via the
        vendored quote engine), stores it in MinIO and streams it inline.
        """
        devis = self.get_object()
        try:
            from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
            from .utils.pdf import download_pdf
            # Format via query params, e.g. ?pdf_mode=onepage&devis_final=1
            raw = {
                'pdf_mode': request.query_params.get('pdf_mode'),
                'payment_mode': request.query_params.get('payment_mode'),
                'custom_acompte': request.query_params.get('custom_acompte'),
            }
            if 'show_monthly' in request.query_params:
                raw['show_monthly'] = request.query_params['show_monthly'] not in ('0', 'false')
            if 'devis_final' in request.query_params:
                raw['devis_final'] = request.query_params['devis_final'] in ('1', 'true')
            # Page « Étude » (4e page premium) — dégrade proprement à 3 pages
            # si le devis n'a pas de données d'étude (géré par le moteur).
            if 'include_etude' in request.query_params:
                raw['include_etude'] = request.query_params['include_etude'] in ('1', 'true')
            key = generate_premium_devis_pdf(devis.id, clean_pdf_options(raw))
            pdf_bytes = download_pdf(key)
        except Exception as exc:
            return Response(
                {'detail': f'Génération de la proposition échouée : {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="Proposition_{devis.reference}.pdf"'
        )
        return response

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
        company = request.user.company
        bc = create_with_reference(
            BonCommande, 'BC', company,
            lambda ref: BonCommande.objects.create(
                reference=ref,
                devis=devis,
                client=devis.client,
                statut=BonCommande.Statut.EN_ATTENTE,
                company=company,
            ),
        )
        serializer = BonCommandeSerializer(bc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-facture',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_facture(self, request, pk=None):
        """Génère la PROCHAINE facture de tranche de l'échéancier du devis.

        1er appel → facture d'acompte (30 % ou 50 % selon le mode) ; appels
        suivants → tranche matériel puis solde. Chaque facture est numérotée
        sans collision et créée « Émise » (postée). L'échéancier vient de
        l'unique mapping PAYMENT_TERMS_BY_MODE.
        """
        devis = self.get_object()
        from .utils.echeancier import creer_facture_tranche
        try:
            facture = creer_facture_tranche(
                devis, request.user, request.user.company,
                create_with_reference,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )


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
        elif self.action in WRITE_ACTIONS + ['destroy']:
            # Retirer une LIGNE fait partie de l'édition normale d'un
            # brouillon (le générateur remplace les lignes) — même niveau
            # que les autres écritures. Supprimer le DEVIS entier reste admin.
            return [IsResponsableOrAdmin()]
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
        company = self.request.user.company
        create_with_reference(
            BonCommande, 'BC', company,
            lambda ref: serializer.save(reference=ref, company=company),
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
        company = request.user.company

        def _create_facture(ref):
            facture = Facture.objects.create(
                reference=ref,
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
                        # Reporte le taux TVA de la ligne de devis (10/20),
                        # pour que la facture reproduise fidèlement la TVA.
                        taux_tva=ligne.taux_tva,
                    )
            return facture

        # create_with_reference runs _create_facture inside a transaction, so
        # the facture and its copied lines stay atomic like before.
        facture = create_with_reference(Facture, 'FAC', company, _create_facture)
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
        if self.action in READ_ACTIONS + ['paiements']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'emettre', 'marquer_payee', 'enregistrer_paiement',
            'generer_pdf', 'telecharger_pdf', 'envoyer_email',
        ]:
            return [IsResponsableOrAdmin()]
        # Annuler une facture = réservé à l'admin/propriétaire (geste comptable).
        elif self.action in ['destroy', 'annuler']:
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company
        create_with_reference(
            Facture, 'FAC', company,
            lambda ref: serializer.save(
                created_by=self.request.user,
                reference=ref,
                company=company,
            ),
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
            permission_classes=[IsAdminRole])
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

    @action(detail=True, methods=['get'], url_path='paiements',
            permission_classes=[IsAnyRole])
    def paiements(self, request, pk=None):
        """Liste les paiements enregistrés sur cette facture."""
        facture = self.get_object()
        return Response(
            PaiementSerializer(
                facture.paiements.all(), many=True
            ).data
        )

    @action(detail=True, methods=['post'], url_path='enregistrer-paiement',
            permission_classes=[IsResponsableOrAdmin])
    def enregistrer_paiement(self, request, pk=None):
        """Enregistre MANUELLEMENT un paiement (montant + date + mode).

        Réduit le reste à payer de la facture et le solde du devis. Quand la
        facture est intégralement réglée, elle passe automatiquement « Payée ».
        Disponible à la Commerciale (création) ; l'annulation reste admin.
        """
        from decimal import Decimal
        facture = self.get_object()
        if facture.statut == Facture.Statut.ANNULEE:
            return Response(
                {'detail': 'Impossible d\'encaisser sur une facture annulée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PaiementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        montant = serializer.validated_data.get('montant')
        if montant is None or montant <= 0:
            return Response(
                {'detail': 'Le montant du paiement doit être positif.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            serializer.save(
                facture=facture,
                company=facture.company,
                created_by=request.user,
            )
            # Statut auto : intégralement réglée → « Payée ».
            facture.refresh_from_db()
            if facture.montant_du <= Decimal('0') and \
                    facture.statut != Facture.Statut.ANNULEE:
                facture.statut = Facture.Statut.PAYEE
                facture.save(update_fields=['statut'])
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

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


class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule des paiements (l'enregistrement passe par la facture).

    Visible par tout rôle authentifié ; tenant-scopé par société.
    """
    queryset = Paiement.objects.select_related(
        'facture', 'created_by'
    ).all()
    serializer_class = PaiementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'montant', 'date_creation']
    ordering = ['-date_paiement']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        return [IsAnyRole()]


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
