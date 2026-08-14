from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
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

        # NTRET1 — mode offline : un rejeu (même uuid_client, ex. queue
        # rejouée deux fois, ou réponse réseau perdue puis retentée) ne crée
        # jamais une 2e vente — on renvoie l'existante telle quelle.
        uuid_client = serializer.validated_data.get('uuid_client')
        if uuid_client:
            existante = selectors.vente_par_uuid_client(company, uuid_client)
            if existante is not None:
                serializer.instance = existante
                return

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

    # ── NTRET12/13 — Promotions panier + coupon à code unique ───────────────

    @action(detail=True, methods=['get'], url_path='promotions')
    def promotions(self, request, pk=None):
        """NTRET12 — aperçu des promotions actives applicables au panier
        (lecture seule, aucun effet de bord)."""
        vente = self.get_object()
        remises = services.promotions_applicables(vente)
        return Response({
            'remises': [
                {'regle_id': r.regle_id, 'libelle': r.libelle, 'montant': str(r.montant)}
                for r in remises
            ],
            'total_remise': str(services.total_remises_promotions(vente)),
        })

    @action(detail=True, methods=['post'], url_path='coupon')
    def coupon(self, request, pk=None):
        """NTRET13 — Applique (consomme) un coupon à code unique saisi à
        l'écran caisse."""
        vente = self.get_object()
        code = request.data.get('code')
        try:
            coupon, montant = services.appliquer_coupon(
                vente=vente, code=code, user=request.user)
        except services.CouponPosError as exc:
            raise ValidationError(str(exc))
        return Response({'code': coupon.code, 'montant_remise': str(montant)})

    # ── NTRET5 — Arrhes / acompte sur commande comptoir ─────────────────────

    @action(detail=True, methods=['post'], url_path='arrhes')
    def arrhes(self, request, pk=None):
        vente = self.get_object()
        try:
            montant_arrhes = Decimal(str(request.data.get('montant_arrhes')))
        except (InvalidOperation, TypeError):
            raise ValidationError({'montant_arrhes': 'Montant invalide.'})
        try:
            services.encaisser_arrhes(
                vente=vente, montant_arrhes=montant_arrhes,
                paiement=request.data.get('paiement') or {}, user=request.user)
        except services.ArrhesError as exc:
            raise ValidationError(str(exc))
        return Response(VenteComptoirSerializer(vente).data)

    @action(detail=True, methods=['post'], url_path='solde-arrhes')
    def solde_arrhes(self, request, pk=None):
        vente = self.get_object()
        try:
            services.encaisser_solde_arrhes(
                vente=vente, paiement=request.data.get('paiement') or {},
                user=request.user)
        except services.ArrhesError as exc:
            raise ValidationError(str(exc))
        return Response(VenteComptoirSerializer(vente).data)

    @action(detail=True, methods=['post'], url_path='remettre-marchandise')
    def remettre_marchandise(self, request, pk=None):
        vente = self.get_object()
        try:
            services.remettre_marchandise_override(
                vente=vente, user=request.user,
                motif=request.data.get('motif', ''))
        except services.ArrhesError as exc:
            raise ValidationError(str(exc))
        return Response(VenteComptoirSerializer(vente).data)

    @action(detail=True, methods=['get'], url_path='ticket-arrhes-pdf')
    def ticket_arrhes_pdf(self, request, pk=None):
        vente = self.get_object()
        if vente.montant_arrhes is None:
            raise ValidationError("Cette vente n'a pas d'arrhes encaissées.")
        pdf_bytes = receipt.receipt_arrhes_pdf(
            vente, solde_restant=services.solde_restant_arrhes(vente))
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="arrhes-{vente.reference}.pdf"')
        return response

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

    @action(detail=False, methods=['post'], url_path='emettre-carte-cadeau',
            permission_classes=[IsResponsableOrAdmin])
    def emettre_carte_cadeau(self, request):
        """NTRET15 — Émet une carte cadeau au comptoir (encaissée comme une
        vente normale, sans ligne de stock)."""
        company = request.user.company
        client = None
        client_id = request.data.get('client')
        if client_id:
            from apps.crm.selectors import get_company_client
            client = get_company_client(company, client_id)
            if client is None:
                raise ValidationError({'client': 'Client inconnu.'})
        try:
            montant = Decimal(str(request.data.get('montant')))
        except (InvalidOperation, TypeError):
            raise ValidationError({'montant': 'Montant invalide.'})

        session_caisse = None
        session_id = request.data.get('session_caisse')
        if session_id:
            session_caisse = SessionCaisse.objects.filter(
                id=session_id, company=company).first()

        try:
            carte, facture = services.emettre_carte_cadeau_comptoir(
                company=company, montant=montant,
                paiement=request.data.get('paiement') or {}, user=request.user,
                client=client, session_caisse=session_caisse,
                code=request.data.get('code'),
                date_expiration=request.data.get('date_expiration'),
            )
        except services.CarteCadeauPosError as exc:
            raise ValidationError(str(exc))
        return Response({
            'code': carte.code,
            'solde': str(carte.solde),
            'facture': facture.reference,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='payer-carte-cadeau')
    def payer_carte_cadeau(self, request, pk=None):
        """NTRET15 — Vérifie (sans consommer) une carte cadeau comme mode de
        paiement candidat pour cette vente — aperçu du solde disponible
        avant de l'inclure dans les ``paiements`` de ``valider/``."""
        vente = self.get_object()
        from apps.promotions.services import CarteCadeauError, verifier_carte_cadeau
        try:
            carte = verifier_carte_cadeau(
                vente.company, request.data.get('code'))
        except CarteCadeauError as exc:
            raise ValidationError(str(exc))
        return Response({'code': carte.code, 'solde': str(carte.solde)})

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

    # PACT7 — sans cette déclaration, le schéma OpenAPI publiait cet agrégat
    # soit VIDE, soit avec le ``VenteComptoirSerializer`` du ViewSet — un
    # MENSONGE (la vue renvoie {nb_ventes, total_ttc, ..., top_produits,
    # top_categories, top_vendeurs, comparatif_boutiques}, jamais un objet
    # ``VenteComptoir``). Cf. apps/flotte/views.py::VehiculeViewSet.tableau_bord.
    # NOTE : ``include_marge`` peut ajouter une clé ``marge`` par ligne de
    # ``top_produits`` (jamais exposée hors permission) — non déclarée ici
    # (dette assumée, comme pour tout champ conditionnel du dépôt).
    @extend_schema(responses=inline_serializer('PosDashboardRetail', {
        'nb_ventes': serializers.IntegerField(),
        'total_ttc': serializers.CharField(),
        'panier_moyen': serializers.CharField(),
        'taux_transformation_pct': serializers.CharField(),
        'ventes_par_m2': serializers.CharField(allow_null=True),
        'top_produits': inline_serializer('PosDashboardRetailTopProduit', {
            'nom': serializers.CharField(),
            'total': serializers.CharField(),
        }, many=True),
        'top_categories': inline_serializer('PosDashboardRetailTopCategorie', {
            'nom': serializers.CharField(),
            'total': serializers.CharField(),
        }, many=True),
        'top_vendeurs': inline_serializer('PosDashboardRetailTopVendeur', {
            'nom': serializers.CharField(),
            'total': serializers.CharField(),
        }, many=True),
        'comparatif_boutiques': serializers.DictField(child=serializers.CharField()),
    }))
    @action(detail=False, methods=['get'], url_path='dashboard-retail',
            permission_classes=[IsResponsableOrAdmin])
    def dashboard_retail(self, request):
        """NTRET16 — Tableau de bord retail (panier moyen, transformation,
        ventes/m², top produits/catégories/vendeurs, comparatif boutiques)."""
        data = selectors.dashboard_retail(
            company=request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
            boutique=request.query_params.get('boutique'),
            include_marge=_peut_voir_marge(request.user),
        )
        return Response(data)

    # PACT7 — export xlsx (fichier binaire, pas du JSON) : forme déclarée
    # comme les autres exports du dépôt, ex.
    # apps/adminops/views_licences.py::licence_pdf_view.
    @extend_schema(responses={200: OpenApiTypes.BINARY})
    @action(detail=False, methods=['get'], url_path='dashboard-retail-export',
            permission_classes=[IsResponsableOrAdmin])
    def dashboard_retail_export(self, request):
        """NTRET16 — export xlsx du tableau de bord retail (jamais de marge)."""
        return selectors.export_dashboard_retail_xlsx(
            company=request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'),
        )


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

    @staticmethod
    def _serialize_rapport(data):
        return {
            'nb_ventes': data['nb_ventes'],
            'total': str(data['total']),
            'par_mode': {
                mode: {'total': str(v['total']), 'nb': v['nb']}
                for mode, v in data['par_mode'].items()
            },
        }

    # YRBAC4 — garde DÉCLARÉE sur les deux NOUVELLES actions rapport (X et
    # PDF du Z). Elle reprend à l'identique le ``permission_classes`` de
    # CLASSE de ce viewset (``IsResponsableOrAdmin``, ligne ~441) : un état de
    # caisse et un document fiscal ne se lisent pas sans rôle. Aucun
    # ``get_permissions`` sur ``SessionCaisseViewSet`` → la déclaration est
    # bien celle que DRF applique (même motif que ``CommandeViewSet.
    # encaisser_facture``/``dashboard`` plus haut dans ce fichier).
    @action(detail=True, methods=['get'], url_path='rapport-x',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_x_view(self, request, pk=None):
        """NTRET2 — Rapport X : lecture à tout moment, aucun effet de bord,
        relisible N fois (session ouverte ou déjà clôturée)."""
        session = self.get_object()
        x = services.rapport_x(session)
        return Response(self._serialize_rapport(x))

    @action(detail=True, methods=['get'], url_path='rapport-z')
    def rapport_z_view(self, request, pk=None):
        """NTRET2 — Rapport Z OFFICIEL : exige la clôture, numéroté
        séquentiellement, une seule fois par session (2e appel → 409)."""
        session = self.get_object()
        try:
            data = services.generer_rapport_z(session, user=request.user)
        except services.RapportZDejaGenereError as exc:
            return Response(
                {'detail': str(exc), 'numero_rapport_z': session.numero_rapport_z},
                status=status.HTTP_409_CONFLICT)
        except services.RapportZError as exc:
            raise ValidationError(str(exc))
        payload = self._serialize_rapport(data)
        payload['numero_rapport_z'] = data['numero_rapport_z']
        return Response(payload)

    @action(detail=True, methods=['get'], url_path='rapport-z-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_z_pdf_view(self, request, pk=None):
        """NTRET2 — PDF du rapport Z, numéroté séquentiellement. Le rapport
        DOIT déjà avoir été généré (``rapport-z/``) — ce point ne génère
        jamais un nouveau numéro, il ne fait que rendre le PDF."""
        session = self.get_object()
        if not session.numero_rapport_z:
            raise ValidationError(
                'Le rapport Z doit être généré (GET rapport-z/) avant le PDF.')
        data = services.rapport_x(session)
        pdf_bytes = receipt.rapport_z_pdf(session, data)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="rapport-z-{session.numero_rapport_z}.pdf"')
        return response


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


# ── NTRET3 — Multi-caissiers avec PIN de session ────────────────────────────

class PinCaissierThrottle(SimpleRateThrottle):
    """5 tentatives / 5 minutes, par (société, utilisateur CIBLÉ) — jamais par
    IP seule : plusieurs caissiers partagent le même poste physique, throttler
    par IP bloquerait tout le monde ensemble sur une erreur d'un seul."""
    scope = 'pos_pin_caissier'

    def get_cache_key(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return None
        target = request.data.get('user_id') or request.user.id
        ident = f'{getattr(request.user, "company_id", "")}:{target}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def parse_rate(self, rate):
        # DRF n'exprime nativement que minute/heure/jour (settings.py garde
        # une entrée DEFAULT_THROTTLE_RATES['pos_pin_caissier'] pour que
        # get_rate() ne lève pas — sa valeur est ignorée, le couple
        # (nombre, durée) réel est câblé ici : 5 tentatives / 5 min = 300 s).
        return (5, 300)


class VerifierPinView(APIView):
    """NTRET3 — Vérifie le PIN d'un caissier : déverrouille l'écran caisse
    sans re-login JWT complet et sans perdre le panier en cours. Journalise un
    changement de caissier (apps.audit) quand l'utilisateur déverrouillé
    diffère du caissier précédemment actif sur ce poste."""
    permission_classes = [IsAnyRole]
    throttle_classes = [PinCaissierThrottle]

    @extend_schema(request=None, responses=inline_serializer('PosVerifierPinResultat', {
        'id': serializers.IntegerField(),
        'username': serializers.CharField(),
    }))
    def post(self, request):
        company = request.user.company
        user_id = request.data.get('user_id')
        pin = request.data.get('pin')
        if not user_id or not pin:
            raise ValidationError({'detail': 'user_id et pin requis.'})
        try:
            user = services.verifier_pin(
                company=company, user_id=user_id, raw_pin=pin,
                caissier_precedent=request.data.get('caissier_precedent'),
                acting_user=request.user,
            )
        except services.PinCaissierError as exc:
            raise ValidationError(str(exc))
        return Response({'id': user.id, 'username': user.username})


class DefinirPinView(APIView):
    """NTRET3 — Définit (ou change) SON PROPRE PIN de verrouillage rapide."""
    permission_classes = [IsAnyRole]

    @extend_schema(request=None, responses=inline_serializer('PosDefinirPinResultat', {
        'ok': serializers.BooleanField(),
    }))
    def post(self, request):
        try:
            services.definir_pin(
                company=request.user.company, user=request.user,
                raw_pin=request.data.get('pin'))
        except services.PinCaissierError as exc:
            raise ValidationError(str(exc))
        return Response({'ok': True})
