from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework.parsers import MultiPartParser, JSONParser  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
    EcheanceFactureFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class FactureFournisseurViewSet(CompanyScopedModelViewSet):
    """G5 — Factures fournisseur / comptes à payer (AP).

    Numérotation sans trou (préfixe FF). Le solde dû = TTC − Σ paiements ; le
    statut de règlement est recalculé à chaque paiement. L'action `paiements`
    liste/ajoute les règlements ; `comptes-a-payer` liste les factures non
    soldées. Usage INTERNE (montants d'achat jamais client-facing)."""
    queryset = FactureFournisseur.objects.select_related(
        'fournisseur', 'bon_commande', 'created_by',
    ).prefetch_related('lignes__produit', 'paiements').all()
    serializer_class = FactureFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'ref_fournisseur', 'fournisseur__nom', 'note',
    ]
    ordering_fields = [
        'date_creation', 'date_facture', 'date_echeance', 'statut',
        'reference', 'montant_ttc',
    ]
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['comptes_a_payer', 'en_exception']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'paiements', 'echeancier', 'resoudre_exception',
            'depuis_ocr', 'depuis_ubl',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'releve_deductions_tva':
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur_id = self.request.query_params.get('fournisseur')
        if fournisseur_id:
            qs = qs.filter(fournisseur_id=fournisseur_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        facture = create_with_reference(
            FactureFournisseur, 'FF', company, _save)
        # YLEDG2/YPROC3 — événement documentaire à la création d'une facture
        # fournisseur. Contrat UNIFIÉ (core/events.py) : instance, company,
        # user — compta pose l'écriture, installations lettre les GR/IR.
        from core.events import facture_fournisseur_creee
        facture_fournisseur_creee.send(
            sender=FactureFournisseur, instance=facture,
            company=company, user=self.request.user)

    def create(self, request, *args, **kwargs):
        # XPUR11 — WARNING (non bloquant) de doublon : même fournisseur +
        # même ref_fournisseur, ou même montant TTC ± 7 jours. La création
        # n'est jamais empêchée ; un override est journalisé (best-effort)
        # quand le corps porte `confirmer_malgre_doublon`.
        from ..services import (
            detect_facture_fournisseur_doublon, log_doublon_override,
        )
        doublons = []
        fournisseur_id = request.data.get('fournisseur')
        if fournisseur_id:
            from datetime import date as _date
            date_facture = request.data.get('date_facture')
            if isinstance(date_facture, str):
                try:
                    date_facture = _date.fromisoformat(date_facture)
                except ValueError:
                    date_facture = None
            doublons = detect_facture_fournisseur_doublon(
                request.user.company,
                fournisseur_id=fournisseur_id,
                ref_fournisseur=request.data.get('ref_fournisseur'),
                montant_ttc=request.data.get('montant_ttc'),
                date_facture=date_facture,
            )
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED and doublons:
            response.data['doublon_warning'] = doublons
            if request.data.get('confirmer_malgre_doublon'):
                try:
                    facture = FactureFournisseur.objects.get(
                        pk=response.data['id'])
                    log_doublon_override(
                        user=request.user, instance=facture,
                        detail=(
                            f'Facture fournisseur {facture.reference} créée '
                            f'malgré {len(doublons)} doublon(s) potentiel(s) '
                            '(override confirmé).'))
                except Exception:  # noqa: BLE001 — best-effort
                    pass
        return response

    @action(detail=False, methods=['post'], url_path='depuis-ocr',
            parser_classes=[MultiPartParser, JSONParser])
    def depuis_ocr(self, request):
        """XACC36 — SINK : convertit les champs extraits par l'OCR (prompt
        stock de ``ocr_service.py``) en brouillon `FactureFournisseur`.

        Corps (JSON ou multipart) : ``fields`` (JSON string ou objet —
        ``donnees_structurees`` de l'OCR), ``file`` (le scan, optionnel —
        rattaché en pièce jointe via records/MinIO), ``confirmer_malgre_
        doublon`` (bool). Jamais de montant inventé : un champ manquant reste
        vide. Sans fournisseur matché (ICE puis nom), refuse explicitement —
        la saisie manuelle reste intacte (dégradation propre)."""
        import json
        from ..services import creer_facture_fournisseur_depuis_ocr

        fields = request.data.get('fields') or {}
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except (TypeError, ValueError):
                fields = {}
        if not isinstance(fields, dict):
            return Response(
                {'detail': 'Le champ « fields » doit être un objet.'},
                status=status.HTTP_400_BAD_REQUEST)

        attachment = None
        upload = request.FILES.get('file')
        if upload is not None:
            from apps.records.storage import store_attachment
            meta, err = store_attachment(upload)
            if meta:
                attachment = meta

        try:
            facture, doublons = creer_facture_fournisseur_depuis_ocr(
                company=request.user.company, user=request.user,
                fields=fields, attachment=attachment,
                confirmer_malgre_doublon=bool(
                    request.data.get('confirmer_malgre_doublon')),
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = self.get_serializer(facture).data
        if doublons:
            data['doublon_warning'] = doublons
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='depuis-ubl',
            parser_classes=[MultiPartParser, JSONParser])
    def depuis_ubl(self, request):
        """XPUR26 — préparation mandat DGI 2026 (e-facturation ENTRANTE) :
        parse un fichier UBL 2.1 (corps multipart, clé ``file``) et crée une
        `FactureFournisseur` BROUILLON pré-remplie (fournisseur matché par
        ICE, lignes, TVA, numéro de clearance DGI). Total no-op (400) tant
        que ``AchatsParametres.einvoicing_entrant_actif`` est OFF (défaut) —
        aucune régression pour les sociétés qui n'ont pas activé le flag."""
        from ..models import AchatsParametres
        from ..services import creer_facture_fournisseur_depuis_ubl

        parametres = AchatsParametres.for_company(request.user.company)
        if not parametres.einvoicing_entrant_actif:
            return Response(
                {'detail': "L'e-facturation entrante (UBL) n'est pas "
                           'activée pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)

        upload = request.FILES.get('file')
        if upload is None:
            return Response(
                {'detail': 'Fichier UBL manquant (champ « file »).'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            facture = creer_facture_fournisseur_depuis_ubl(
                company=request.user.company, user=request.user,
                xml_bytes=upload.read())
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            self.get_serializer(facture).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='releve-deductions-tva')
    def releve_deductions_tva(self, request):
        """XPUR17 — relevé de déductions TVA (achats) groupé PAR TAUX sur la
        période (query params ``date_debut``/``date_fin`` optionnels).
        Réservé Responsable/Admin (donnée comptable). LECTURE SEULE."""
        from ..selectors import releve_deductions_tva_par_taux
        releve = releve_deductions_tva_par_taux(
            request.user.company,
            date_debut=request.query_params.get('date_debut'),
            date_fin=request.query_params.get('date_fin'))
        return Response(releve)

    @action(detail=False, methods=['get'], url_path='comptes-a-payer')
    def comptes_a_payer(self, request):
        """Liste des factures fournisseur NON soldées (à payer ou
        partiellement payées), triées par échéance puis date. INTERNE."""
        from decimal import Decimal
        qs = self.filter_queryset(self.get_queryset()).exclude(
            statut=FactureFournisseur.Statut.PAYEE).order_by(
            'date_echeance', '-date_creation')
        data = self.get_serializer(qs, many=True).data
        total_du = sum((Decimal(f['solde_du']) for f in data), Decimal('0'))
        return Response({'results': data, 'total_du': str(total_du)})

    @action(detail=True, methods=['get'], url_path='pdf',
            permission_classes=[IsResponsableOrAdmin])
    def pdf(self, request, pk=None):
        """FG55 — PDF facture fournisseur (INTERNE — montre les prix d'achat).
        Jamais un document client."""
        from ..services import generate_facture_fournisseur_pdf
        facture = self.get_object()
        pdf_bytes = generate_facture_fournisseur_pdf(facture)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{facture.reference}.pdf"')
        return response

    @action(detail=True, methods=['get', 'post'], url_path='paiements')
    def paiements(self, request, pk=None):
        """GET : liste des paiements de la facture. POST : enregistre un
        paiement (montant/date/mode), recalcule le statut + le solde dû."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            qs = facture.paiements.select_related('created_by').all()
            return Response(
                PaiementFournisseurSerializer(qs, many=True).data)
        # XPUR1/XPUR4/XPUR10 — mêmes gates que PaiementFournisseurViewSet.
        # create (fournisseur bloqué, conformité expirée, exception 3 voies).
        from ..services import (
            check_paiement_conformite_gate, check_fournisseur_statut_paiement,
            check_facture_exception_gate,
        )
        try:
            check_fournisseur_statut_paiement(facture.fournisseur)
            check_paiement_conformite_gate(
                request.user.company, facture.fournisseur)
            check_facture_exception_gate(request.user.company, facture)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # POST — enregistre un paiement, company posée serveur.
        serializer = PaiementFournisseurSerializer(
            data={**request.data, 'facture': facture.id},
            context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            from ..services import (
                recompute_facture_fournisseur_statut, compute_ras_tva,
            )
            montant = serializer.validated_data['montant']
            taux, montant_ras = compute_ras_tva(
                request.user.company, facture, montant)
            paiement = serializer.save(
                company=request.user.company, created_by=request.user,
                taux_ras=taux, montant_ras_tva=montant_ras)
            facture.refresh_from_db()
            recompute_facture_fournisseur_statut(facture)
            # ZACC9 — ce POST enregistrait déjà le paiement mais ne postait
            # AUCUNE écriture comptable (contrairement au chemin
            # PaiementFournisseurViewSet.create qui émet déjà cet événement,
            # YLEDG2). Même seam générique, jamais d'import direct du
            # service compta : idempotent côté récepteur
            # (`ecriture_pour_paiement_fournisseur` vérifie l'existence
            # avant de poster).
            from core.events import paiement_fournisseur_enregistre
            paiement_fournisseur_enregistre.send(
                sender=paiement.__class__, instance=paiement,
                company=request.user.company)
        return Response(self.get_serializer(facture).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='resoudre-exception')
    def resoudre_exception(self, request, pk=None):
        """XPUR10 — résout (Responsable/Admin) une facture en exception de
        rapprochement 3 voies, débloquant le paiement. Corps optionnel :
        ``{"commentaire": "..."}``."""
        from ..services import resoudre_exception_facture
        facture = self.get_object()
        try:
            resoudre_exception_facture(
                facture, user=request.user,
                commentaire=request.data.get('commentaire', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(facture).data)

    @action(detail=False, methods=['get'], url_path='en-exception')
    def en_exception(self, request):
        """XPUR10 — file « Factures en exception » (rapprochement 3 voies
        hors tolérance, non résolu). LECTURE SEULE."""
        from ..services import factures_en_exception
        qs = factures_en_exception(request.user.company)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='echeancier')
    def echeancier(self, request, pk=None):
        """XPUR6 — GET : liste les tranches d'échéancier de la facture.
        POST : crée l'échéancier multi-tranches (corps : ``{"tranches": [
        {"pourcentage": 30, "date_echeance": "2026-08-01"}, ...]}``). Chaque
        tranche sans ``montant`` explicite est dérivée du TTC × pourcentage."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            qs = facture.echeances.all()
            return Response(
                EcheanceFactureFournisseurSerializer(qs, many=True).data)
        tranches = request.data.get('tranches') or []
        if not isinstance(tranches, list) or not tranches:
            return Response(
                {'detail': 'Au moins une tranche est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        for t in tranches:
            if not t.get('date_echeance'):
                return Response(
                    {'detail': 'Chaque tranche doit porter une date '
                               "d'échéance."},
                    status=status.HTTP_400_BAD_REQUEST)
        from ..services import creer_echeancier_facture_fournisseur
        created = creer_echeancier_facture_fournisseur(
            request.user.company, facture, tranches)
        return Response(
            EcheanceFactureFournisseurSerializer(created, many=True).data,
            status=status.HTTP_201_CREATED)
