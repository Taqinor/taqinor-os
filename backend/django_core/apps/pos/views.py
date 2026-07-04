from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from . import escpos, receipt, selectors, services
from .models import (
    CommandeRetrait,
    ConfigMaterielPOS,
    LigneCommandeRetrait,
    LigneVenteComptoir,
    SessionCaisse,
    ShareLinkTicket,
    VenteComptoir,
)
from .serializers import (
    CommandeRetraitSerializer,
    ConfigMaterielPOSSerializer,
    SessionCaisseSerializer,
    VenteComptoirSerializer,
)


def _company_qs(qs, user):
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _peut_voir_marge(user):
    """XPOS11 — la marge (via prix_achat) n'apparaît QUE derrière la
    permission ``prix_achat_voir`` existante, jamais dans un export client.
    Même garde que ``HasPermissionOrLegacy`` (rôle fin → permission ERP,
    compte hérité sans rôle → palier responsable/admin)."""
    if not (user and user.is_authenticated):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None):
        return user.has_erp_permission('prix_achat_voir')
    return bool(getattr(user, 'is_responsable', False))


class VenteComptoirViewSet(viewsets.ModelViewSet):
    """XPOS1 — Vente comptoir. Scoping multi-tenant + validation."""
    queryset = VenteComptoir.objects.select_related(
        'client', 'session_caisse', 'caissier', 'facture'
    ).prefetch_related('lignes').all()
    serializer_class = VenteComptoirSerializer

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        from apps.ventes.utils.references import create_with_reference
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})

        def _create(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        instance = create_with_reference(
            VenteComptoir, 'VC', company, _create)
        serializer.instance = instance

    @action(detail=True, methods=['post'], url_path='lignes')
    def ajouter_ligne(self, request, pk=None):
        vente = self.get_object()
        if vente.statut != VenteComptoir.Statut.BROUILLON:
            raise ValidationError('Vente déjà validée.')
        produit_id = request.data.get('produit')
        quantite = request.data.get('quantite', 1)
        prix = request.data.get('prix_unitaire_ttc')
        from apps.stock.selectors import get_produit_scoped
        produit = get_produit_scoped(vente.company, produit_id)
        if produit is None:
            raise ValidationError({'produit': 'Produit inconnu.'})
        ligne = LigneVenteComptoir.objects.create(
            vente=vente,
            produit=produit,
            designation=produit.nom,
            quantite=quantite,
            prix_unitaire_ttc=prix if prix is not None else produit.prix_vente,
            remise=request.data.get('remise', 0),
            taux_tva=request.data.get('taux_tva'),
            numeros_serie=request.data.get('numeros_serie') or [],
        )
        from .serializers import LigneVenteComptoirSerializer
        return Response(
            LigneVenteComptoirSerializer(ligne).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        vente = self.get_object()
        paiements = request.data.get('paiements') or []
        try:
            services.valider_vente(
                vente=vente, paiements=paiements, user=request.user)
        except services.VenteComptoirError as exc:
            raise ValidationError(str(exc))
        return Response(VenteComptoirSerializer(vente).data)

    @action(detail=True, methods=['get'], url_path='ticket-pdf')
    def ticket_pdf(self, request, pk=None):
        vente = self.get_object()
        if vente.statut != VenteComptoir.Statut.VALIDEE:
            raise ValidationError('Vente non validée.')
        paiements = vente.facture.paiements.all() if vente.facture_id else []
        pdf_bytes = receipt.receipt_pdf(vente, paiements=paiements)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="ticket-{vente.reference}.pdf"')
        return response

    @action(detail=True, methods=['post'], url_path='ticket-escpos')
    def ticket_escpos(self, request, pk=None):
        """XPOS18 — Génère le flux ESC/POS brut. Envoi réseau GATED : sans
        config imprimante active, no-op (le flux est simplement renvoyé)."""
        vente = self.get_object()
        if vente.statut != VenteComptoir.Statut.VALIDEE:
            raise ValidationError('Vente non validée.')
        identite = receipt._company_identity(vente.company)
        paiements = vente.facture.paiements.all() if vente.facture_id else []
        payload = escpos.build_ticket_escpos(
            vente, identite=identite, paiements=paiements)
        config = ConfigMaterielPOS.objects.filter(company=vente.company).first()
        sent = escpos.send_to_printer(payload, config=config)
        if request.query_params.get('download') == '1':
            response = HttpResponse(
                payload, content_type='application/octet-stream')
            response['Content-Disposition'] = (
                f'attachment; filename="ticket-{vente.reference}.bin"')
            return response
        return Response({'sent_to_printer': sent, 'bytes': len(payload)})

    @action(detail=True, methods=['post'], url_path='ticket-share-link')
    def ticket_share_link(self, request, pk=None):
        vente = self.get_object()
        if vente.statut != VenteComptoir.Statut.VALIDEE:
            raise ValidationError('Vente non validée.')
        link = ShareLinkTicket.for_vente(vente)
        return Response({'token': link.token, 'expires_at': link.expires_at})

    @action(detail=False, methods=['post'], url_path='encaisser-facture',
            permission_classes=[IsResponsableOrAdmin])
    def encaisser_facture(self, request):
        """XPOS6 — Encaisser un devis/une facture existants au comptoir."""
        from apps.ventes.services import get_facture_or_none
        company = request.user.company
        facture_id = request.data.get('facture')
        facture = get_facture_or_none(company=company, facture_id=facture_id)
        if facture is None:
            raise ValidationError({'facture': 'Facture inconnue.'})
        try:
            montant = Decimal(str(request.data.get('montant')))
        except (InvalidOperation, TypeError):
            raise ValidationError({'montant': 'Montant invalide.'})
        try:
            paiement = services.encaisser_facture_existante(
                facture=facture, montant=montant,
                mode=request.data.get('mode', 'especes'),
                company=company, user=request.user,
                reference=request.data.get('reference', ''),
                note=request.data.get('note', ''),
            )
        except services.EncaissementCompteError as exc:
            raise ValidationError(str(exc))
        return Response({
            'id': paiement.id,
            'montant': str(paiement.montant),
            'mode': paiement.mode,
            'facture': facture.reference,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='factures-recherche',
            permission_classes=[IsResponsableOrAdmin])
    def factures_recherche(self, request):
        """XPOS6 — recherche par référence/client des factures avec solde dû."""
        from apps.ventes.services import facturables_pour_devis
        query = request.query_params.get('q', '')
        rows = facturables_pour_devis(
            company=request.user.company, query=query)
        return Response([
            {
                'id': f.id,
                'reference': f.reference,
                'client': str(f.client) if f.client_id else '',
                'montant_du': str(f.montant_du),
                'total_ttc': str(f.total_ttc),
            }
            for f in rows
        ])

    @action(detail=False, methods=['get'], url_path='dashboard',
            permission_classes=[IsResponsableOrAdmin])
    def dashboard(self, request):
        """XPOS11 — Reporting ventes comptoir (6 axes + drill-down)."""
        data = selectors.dashboard_data(
            company=request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
            include_marge=_peut_voir_marge(request.user),
        )
        return Response(data)

    @action(detail=False, methods=['get'], url_path='dashboard-export',
            permission_classes=[IsResponsableOrAdmin])
    def dashboard_export(self, request):
        """XPOS11 — export xlsx du dashboard (jamais de marge dans un export
        client — la marge n'apparaît que dans l'agrégat JSON, jamais ici)."""
        return selectors.export_dashboard_xlsx(company=request.user.company)


class SessionCaisseViewSet(viewsets.ModelViewSet):
    """XPOS4 — Sessions de caisse comptoir."""
    queryset = SessionCaisse.objects.select_related(
        'caisse_comptable', 'caissier').all()
    serializer_class = SessionCaisseSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        company = self.request.user.company
        caisse_comptable = serializer.validated_data.get('caisse_comptable')
        try:
            session = services.ouvrir_session(
                company=company,
                caisse_comptable=caisse_comptable,
                caissier=serializer.validated_data.get(
                    'caissier') or self.request.user,
                fond_ouverture=serializer.validated_data.get(
                    'fond_ouverture', 0),
                user=self.request.user,
            )
        except services.SessionCaisseError as exc:
            raise ValidationError(str(exc))
        serializer.instance = session

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        session = self.get_object()
        try:
            montant_compte = Decimal(str(request.data.get('montant_compte')))
        except (InvalidOperation, TypeError):
            raise ValidationError({'montant_compte': 'Montant invalide.'})
        montant_tpe = request.data.get('montant_tpe_compte')
        if montant_tpe is not None:
            try:
                montant_tpe = Decimal(str(montant_tpe))
            except InvalidOperation:
                raise ValidationError({'montant_tpe_compte': 'Montant invalide.'})
        try:
            services.cloturer_session(
                session=session,
                montant_compte=montant_compte,
                montant_tpe_compte=montant_tpe,
                commentaire=request.data.get('commentaire', ''),
                user=request.user,
            )
        except services.SessionCaisseError as exc:
            raise ValidationError(str(exc))
        return Response(SessionCaisseSerializer(session).data)

    @action(detail=True, methods=['get'], url_path='rapport-z')
    def rapport_z_view(self, request, pk=None):
        session = self.get_object()
        z = services.rapport_z(session)
        return Response({
            'nb_ventes': z['nb_ventes'],
            'total': str(z['total']),
            'par_mode': {
                mode: {'total': str(v['total']), 'nb': v['nb']}
                for mode, v in z['par_mode'].items()
            },
        })


class CommandeRetraitViewSet(viewsets.ModelViewSet):
    """XPOS15 — Click-and-collect (retrait en magasin)."""
    queryset = CommandeRetrait.objects.select_related(
        'client', 'devis', 'vente_comptoir').prefetch_related('lignes').all()
    serializer_class = CommandeRetraitSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        from apps.ventes.utils.references import create_with_reference
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})

        def _create(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        instance = create_with_reference(
            CommandeRetrait, 'RET', company, _create)
        serializer.instance = instance

    @action(detail=True, methods=['post'], url_path='lignes')
    def ajouter_ligne(self, request, pk=None):
        commande = self.get_object()
        if commande.statut != CommandeRetrait.Statut.A_PREPARER:
            raise ValidationError('Commande déjà en préparation.')
        produit_id = request.data.get('produit')
        from apps.stock.selectors import get_produit_scoped
        produit = get_produit_scoped(commande.company, produit_id)
        if produit is None:
            raise ValidationError({'produit': 'Produit inconnu.'})
        ligne = LigneCommandeRetrait.objects.create(
            commande=commande, produit=produit,
            quantite=request.data.get('quantite', 1))
        from .serializers import LigneCommandeRetraitSerializer
        return Response(
            LigneCommandeRetraitSerializer(ligne).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='marquer-pret')
    def marquer_pret_view(self, request, pk=None):
        commande = self.get_object()
        try:
            services.marquer_pret(commande=commande, user=request.user)
        except services.CommandeRetraitError as exc:
            raise ValidationError(str(exc))
        return Response(CommandeRetraitSerializer(commande).data)

    @action(detail=True, methods=['post'], url_path='remettre')
    def remettre(self, request, pk=None):
        commande = self.get_object()
        try:
            services.remettre_commande(
                commande=commande,
                code_saisi=request.data.get('code', ''),
                user=request.user,
            )
        except services.CommandeRetraitError as exc:
            raise ValidationError(str(exc))
        return Response(CommandeRetraitSerializer(commande).data)


class ConfigMaterielPOSViewSet(viewsets.ModelViewSet):
    """XPOS18 — Configuration matériel comptoir (imprimante réseau)."""
    queryset = ConfigMaterielPOS.objects.all()
    serializer_class = ConfigMaterielPOSSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        company = self.request.user.company
        serializer.save(company=company)


class PublicTicketPDFView(APIView):
    """XPOS3 — Lien public tokenisé (sans login) vers le PDF du ticket."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        link = ShareLinkTicket.objects.filter(token=token).first()
        if link is None or not link.is_valid:
            return Response(
                {'detail': 'Lien invalide ou expiré.'},
                status=status.HTTP_404_NOT_FOUND)
        vente = link.vente
        paiements = vente.facture.paiements.all() if vente.facture_id else []
        pdf_bytes = receipt.receipt_pdf(vente, paiements=paiements)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="ticket-{vente.reference}.pdf"')
        return response
