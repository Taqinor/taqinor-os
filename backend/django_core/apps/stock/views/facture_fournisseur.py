import logging

from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework.parsers import MultiPartParser, JSONParser  # noqa: F401
from rest_framework import serializers
from ..openapi_helpers import BINARY, DATE, INT, LISTE, NUM, P, PDF, STR, corps
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

logger = logging.getLogger(__name__)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


@extend_schema_view(list=extend_schema(parameters=[P('fournisseur', INT, False, 'Fournisseur (id)'), P('statut', STR, False, 'Statut')]))
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

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in ('comptes_a_payer', 'en_exception'):
            # ASTK11 (D-ASTK-2) — files dont l'objet est un montant d'achat :
            # `prix_achat_voir` requis (repli légacy can_view_buy_prices).
            from ..permissions import PeutVoirPrixAchat
            return [IsAnyRole(), PeutVoirPrixAchat()]
        if self.action in READ_ACTIONS + ['suggestions_bcf']:
            return [IsAnyRole()]
        if self.action == 'paiements' and self.request.method == 'GET':
            # ASTK241 — lire les règlements = règle UNIQUE de /paiements-fournisseur/.
            from .paiement_fournisseur import PeutLirePaiementsFournisseur
            return [PeutLirePaiementsFournisseur()]
        elif self.action in WRITE_ACTIONS + [
            'paiements', 'echeancier', 'resoudre_exception',
            'depuis_ocr', 'depuis_ubl',
        ]:
            # ASTK19 (D-ASTK-3) — saisir/modifier une facture fournisseur, la
            # régler, son échéancier, résoudre une exception, l'importer
            # (OCR/UBL) = « payer » : ``achats_payer`` (repli légacy).
            return [HasPermissionOrLegacy('achats_payer')()]
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
        # AUD232 — création + événement dans UNE transaction : un abonné qui
        # échoue ne peut plus laisser la facture committée toute seule
        # (`ATOMIC_REQUESTS` est absent des settings).
        with transaction.atomic():
            facture = create_with_reference(
                FactureFournisseur, 'FF', company, _save)
            # YLEDG2/YPROC3 — événement documentaire à la création d'une
            # facture fournisseur. Contrat UNIFIÉ (core/events.py) :
            # instance, company, user — compta pose l'écriture,
            # installations lettre les GR/IR.
            from core.events import facture_fournisseur_creee
            facture_fournisseur_creee.send(
                sender=FactureFournisseur, instance=facture,
                company=company, user=self.request.user)

    def perform_update(self, serializer):
        """NTP2P10 — confirmation du lien `bon_commande` (jamais posé
        silencieusement, l'utilisateur choisit).

        SOLMVP12 (20/09/2026) avait retiré l'évaluation immédiate du
        rapprochement 3 voies (lecture du module compta). ASTK107 la
        rebranche côté stock : au lien BCF, ``evaluer_rapprochement_3_voies``
        compare le HT facturé au reçu × PU du BCF et pose l'exception hors
        tolérance (paiement alors bloqué par ``check_facture_exception_gate``).

        ASTK99 — quand le PATCH fait ACQUÉRIR (ou changer) un BCF à la
        facture, `facture_fournisseur_creee` est émis UNE fois dans la même
        transaction (lettrage GR/IR des provisions du BCF) ; un PATCH qui ne
        change pas `bon_commande` n'émet rien."""
        from ..services import (
            _emettre_facture_creee, evaluer_rapprochement_3_voies,
        )
        ancien_bcf_id = serializer.instance.bon_commande_id
        with transaction.atomic():
            facture = serializer.save()
            if (facture.bon_commande_id is not None
                    and facture.bon_commande_id != ancien_bcf_id):
                evaluer_rapprochement_3_voies(facture)
                _emettre_facture_creee(facture, self.request.user)

    def perform_destroy(self, instance):
        """AUD207 — `PaiementFournisseur.facture` est désormais PROTECT (une
        migration additive a converti le CASCADE hérité) : sans ce garde-fou
        EN AMONT, Django lèverait une brute `ProtectedError` (500) au lieu
        d'un refus métier explicite. Même patron que l'action `annuler` de
        `installations/views/facture_soustraitant.py` (vérifie
        `facture.total_paye > 0` avant de permettre la suppression)."""
        from rest_framework.exceptions import ValidationError
        if instance.total_paye > 0:
            raise ValidationError({
                'detail': (
                    'Cette facture fournisseur porte des paiements réels '
                    '(total payé : ' + str(instance.total_paye) + ' MAD) : '
                    'suppression refusée.'
                ),
            })
        # ASTK85 — même garde pour un acompte ou un avoir IMPUTÉ : sans
        # elle, la suppression effaçait l'imputation (CASCADE / SET_NULL) et
        # le crédit fournisseur disparaissait (avoir « consommé » à vide,
        # acompte détaché mais compté consommé).
        nb_acomptes = (instance.imputations_acompte.order_by()
                       .values('acompte').distinct().count())
        if nb_acomptes:
            raise ValidationError({
                'detail': (
                    'Cette facture fournisseur porte '
                    f'{nb_acomptes} acompte(s) imputé(s) (total : '
                    f'{instance.total_acomptes_imputes} MAD) : '
                    'suppression refusée.'
                ),
            })
        imputations_avoir = list(
            instance.avoirs_imputes.select_related('avoir'))
        if imputations_avoir:
            refs = ', '.join(sorted({
                i.avoir.reference for i in imputations_avoir}))
            raise ValidationError({
                'detail': (
                    'Cette facture fournisseur porte un avoir imputé '
                    f'({refs} — total : {instance.total_avoirs_imputes} '
                    'MAD) : suppression refusée.'
                ),
            })
        # ASTK86 — dé-lettrer AVANT delete() les provisions GR/IR que cette
        # facture avait lettrées (le FK SET_NULL laissait lettre=True,
        # facture=None : dette latente fermée à tort). Service UNIQUE du
        # propriétaire chantiers (ASTK126), dans la même transaction.
        from apps.installations.services import delettrer_gr_ir_facture
        with transaction.atomic():
            delettrer_gr_ir_facture(instance)
            instance.delete()

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

    @extend_schema(
        request={'multipart/form-data': corps('FactureDepuisOcrMultipart', fields=serializers.CharField(help_text='JSON'), file=serializers.FileField(required=False), confirmer_malgre_doublon=serializers.BooleanField(required=False)),
                 'application/json': corps('FactureDepuisOcrJson', fields=serializers.DictField(), confirmer_malgre_doublon=serializers.BooleanField(required=False))},
        responses={201: FactureFournisseurSerializer})
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

    @extend_schema(parameters=[P('fournisseur', INT, True, 'Fournisseur (id)'), P('montant', NUM, False, 'Montant TTC')], responses=LISTE)
    @action(detail=False, methods=['get'], url_path='suggestions-bcf')
    def suggestions_bcf(self, request):
        """NTP2P10 — propose le(s) ``BonCommandeFournisseur`` correspondant
        à une facture OCR (matching fournisseur + montant approximatif +
        fenêtre de dates), le meilleur candidat en premier. LECTURE SEULE :
        ne lie JAMAIS rien — l'utilisateur confirme via un PATCH classique
        (``factures-fournisseur/{id}/`` avec ``bon_commande``), qui déclenche
        alors l'évaluation 3 voies (``perform_update``)."""
        from ..permissions import PeutVoirPrixAchat
        from ..selectors import suggerer_bcf_pour_facture

        fournisseur_id = request.query_params.get('fournisseur')
        if not fournisseur_id:
            return Response(
                {'detail': 'Le paramètre fournisseur est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        montant = request.query_params.get('montant')
        suggestions = suggerer_bcf_pour_facture(
            request.user.company, fournisseur_id=fournisseur_id,
            montant=montant)
        # ASTK240 (D-ASTK-2) — sans `prix_achat_voir`, aucun montant d'achat :
        # ni `montant_*` ni l'écart (montant saisi ± écart = total du BCF).
        if not PeutVoirPrixAchat().has_permission(request, self):
            suggestions = [{k: v for k, v in s.items() if not k.startswith(
                'montant') and k != 'ecart'} for s in suggestions]
        return Response(suggestions)

    @extend_schema(
        request={'multipart/form-data': corps('FactureDepuisUblMultipart', file=serializers.FileField())},
        responses={201: FactureFournisseurSerializer})
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

    @extend_schema(parameters=[P('date_debut', DATE), P('date_fin', DATE)], responses=LISTE)
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

    @extend_schema(responses=corps('FactureComptesAPayer', results=FactureFournisseurSerializer(many=True), total_du=serializers.CharField()))
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

    @extend_schema(responses={PDF: BINARY})
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

    @extend_schema(methods=['GET'], responses=PaiementFournisseurSerializer(many=True))
    @extend_schema(methods=['POST'], request=PaiementFournisseurSerializer, responses={201: FactureFournisseurSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='paiements')
    def paiements(self, request, pk=None):
        """GET : liste des paiements de la facture. POST : enregistre un
        paiement (montant/date/mode), recalcule le statut + le solde dû."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            # ASTK241 — gardé par get_permissions (PeutLirePaiementsFournisseur).
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
                verrouiller_facture_fournisseur_et_verifier_solde,
            )
            montant = serializer.validated_data['montant']
            # AUD208 (ZACC9) — verrouille la facture ET re-vérifie le solde
            # dû SOUS verrou : la garde de `validate()` (côté serializer,
            # `serializer.is_valid()` plus haut) tourne HORS transaction/
            # verrou — elle ne protège pas contre deux paiements concurrents
            # dont la SOMME dépasse le solde dû (chacun la passe isolément).
            try:
                facture = verrouiller_facture_fournisseur_et_verifier_solde(
                    facture, montant)
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            taux, montant_ras = compute_ras_tva(
                request.user.company, facture, montant)
            paiement = serializer.save(
                company=request.user.company, facture=facture,
                created_by=request.user,
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

    @extend_schema(request=corps('FactureResoudreExceptionCorps', commentaire=serializers.CharField(required=False, allow_blank=True)), responses=FactureFournisseurSerializer)
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

    @extend_schema(responses=FactureFournisseurSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='en-exception')
    def en_exception(self, request):
        """XPUR10 — file « Factures en exception » (rapprochement 3 voies
        hors tolérance, non résolu). LECTURE SEULE."""
        from ..services import factures_en_exception
        qs = factures_en_exception(request.user.company)
        return Response(self.get_serializer(qs, many=True).data)

    @extend_schema(methods=['GET'], responses=LISTE)
    @extend_schema(methods=['POST'], request=corps('FactureEcheancierCorps', tranches=serializers.ListField(child=serializers.DictField())), responses={201: EcheanceFactureFournisseurSerializer(many=True)})
    @action(detail=True, methods=['get', 'post'], url_path='echeancier')
    def echeancier(self, request, pk=None):
        """XPUR6 — GET : liste les tranches d'échéancier de la facture.
        POST : crée l'échéancier multi-tranches (corps : ``{"tranches": [
        {"pourcentage": 30, "date_echeance": "2026-08-01"}, ...]}``). Chaque
        tranche sans ``montant`` explicite est dérivée du TTC × pourcentage."""
        facture = self.get_object()
        if request.method.lower() == 'get':
            # AUDV04 (DRAFT165-112) — route par le sélecteur dédié plutôt que
            # par une lecture manuelle de `facture.echeances.all()` : c'était
            # la SEULE forme lisible côté écran Achats (payment run FG132/
            # FG133), le sélecteur restait mort (jamais appelé hors tests).
            from ..selectors import echeances_facture_fournisseur
            rows = echeances_facture_fournisseur(
                request.user.company, facture.pk)
            return Response(rows)
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
