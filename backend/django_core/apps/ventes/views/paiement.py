from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.exceptions import ValidationError  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    AffectationPaiement, RetenueSubie, Avoir, LigneAvoir, FollowupLevel,
    RelanceLog, EmailLog,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AffectationPaiementSerializer,
    RetenueSubieSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule des paiements (l'enregistrement passe par la facture) —
    XFAC1 ajoute deux actions d'écriture pour les AVANCES non affectées
    (règlement reçu sans facture) : enregistrement + ventilation sur des
    factures ouvertes du même client.

    Visible par tout rôle authentifié ; tenant-scopé par société.
    """
    queryset = Paiement.objects.select_related(
        'facture', 'facture__client', 'client', 'created_by'
    ).all()
    serializer_class = PaiementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'montant', 'date_creation']
    ordering = ['-date_paiement']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in ('enregistrer_avance', 'ventiler', 'rejeter'):
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """YLEDG5 — marque ce paiement REJETÉ (chèque impayé / virement
        rejeté). Motif obligatoire ; frais optionnels. Rouvre la facture
        (montant_du remonte, statut recalculé) et ré-arme les relances. Le
        paiement n'est jamais supprimé (piste d'audit) ; un double rejet est
        refusé (409)."""
        from ..services import rejeter_paiement, PaiementRejectError
        paiement = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'Le motif du rejet est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            rejeter_paiement(
                paiement=paiement, motif=motif,
                frais=request.data.get('frais'),
                date_rejet=request.data.get('date_rejet'),
                user=request.user,
            )
        except PaiementRejectError as exc:
            code = (status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)
            return Response({'detail': exc.message}, status=code)
        return Response(PaiementSerializer(paiement).data)

    @action(detail=False, methods=['get'], url_path='avances-non-affectees')
    def avances_non_affectees(self, request):
        """XFAC1 — avances (paiements sans facture) encore disponibles,
        optionnellement filtrées par client (``?client=<id>``)."""
        qs = self.get_queryset().filter(
            facture__isnull=True,
        ).exclude(
            statut_affectation=Paiement.StatutAffectation.AFFECTE)
        client_id = request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        rows = [p for p in qs if p.montant_disponible > 0]
        return Response(PaiementSerializer(rows, many=True).data)

    @action(detail=False, methods=['post'], url_path='enregistrer-avance')
    def enregistrer_avance(self, request):
        """XFAC1 — enregistre un règlement reçu SANS facture (avance/acompte à
        la commande/trop-perçu), rattaché directement au client."""
        from apps.crm.selectors import client_base_qs
        from ..services import enregistrer_avance as _enregistrer_avance

        company = request.user.company
        client_id = request.data.get('client')
        client = _company_qs(client_base_qs(), request.user).filter(
            pk=client_id).first()
        if client is None:
            return Response({'detail': 'Client introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            paiement = _enregistrer_avance(
                company=company, client=client,
                montant=request.data.get('montant'),
                date_paiement=request.data.get('date_paiement'),
                mode=request.data.get('mode', Paiement.Mode.VIREMENT),
                reference=request.data.get('reference', ''),
                note=request.data.get('note', ''),
                created_by=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PaiementSerializer(paiement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='ventiler')
    def ventiler(self, request, pk=None):
        """XFAC1 — ventile une avance non affectée sur UNE facture ouverte du
        même client. Corps : ``{facture, montant}``. Peut être appelée
        plusieurs fois pour répartir la même avance sur plusieurs factures."""
        from ..services import ventiler_avance as _ventiler_avance

        paiement = self.get_object()
        facture = _company_qs(Facture.objects.all(), request.user).filter(
            pk=request.data.get('facture')).first()
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            affectation = _ventiler_avance(
                paiement=paiement, facture=facture,
                montant=request.data.get('montant'), user=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            AffectationPaiementSerializer(affectation).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'],
            url_path=r'factures/(?P<facture_id>[^/.]+)/paiement-avec-retenue',
            permission_classes=[IsResponsableOrAdmin])
    def paiement_avec_retenue(self, request, facture_id=None):
        """XFAC4 — enregistre un paiement PARTIEL + une retenue à la source
        (RAS TVA/RAS IS) qui, ENSEMBLE, soldent la facture. Corps :
        ``{montant, date_paiement, mode, type_retenue, taux, reference?,
        note?}``."""
        from ..services import (
            enregistrer_paiement_avec_retenue as _enregistrer_avec_retenue,
        )
        facture = _company_qs(Facture.objects.all(), request.user).filter(
            pk=facture_id).first()
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            paiement, retenue = _enregistrer_avec_retenue(
                facture=facture, montant=request.data.get('montant'),
                date_paiement=request.data.get('date_paiement'),
                mode=request.data.get('mode', Paiement.Mode.VIREMENT),
                type_retenue=request.data.get(
                    'type_retenue', RetenueSubie.TypeRetenue.RAS_TVA),
                taux=request.data.get('taux'),
                reference=request.data.get('reference', ''),
                note=request.data.get('note', ''),
                created_by=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'paiement': PaiementSerializer(paiement).data,
            'retenue': RetenueSubieSerializer(retenue).data,
            'facture': FactureSerializer(facture.__class__.objects.get(
                pk=facture.pk)).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='attestations-ras-en-attente')
    def attestations_ras_en_attente(self, request):
        """XFAC4 — état des attestations RAS à recevoir (non reçues)."""
        qs = RetenueSubie.objects.select_related('facture').filter(
            attestation_recue=False)
        qs = _company_qs(qs, request.user)
        return Response(RetenueSubieSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'],
            url_path=r'retenues/(?P<retenue_id>[^/.]+)/attestation-recue',
            permission_classes=[IsResponsableOrAdmin])
    def attestation_recue(self, request, retenue_id=None):
        """XFAC4 — coche la réception de l'attestation RAS (+ justificatif)."""
        retenue = _company_qs(
            RetenueSubie.objects.all(), request.user).filter(
            pk=retenue_id).first()
        if retenue is None:
            return Response({'detail': 'Retenue introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        retenue.attestation_recue = True
        retenue.attestation_date = (
            request.data.get('attestation_date') or timezone.now().date())
        if request.data.get('attestation_fichier'):
            retenue.attestation_fichier = request.data.get(
                'attestation_fichier')
        retenue.save(update_fields=[
            'attestation_recue', 'attestation_date', 'attestation_fichier'])
        return Response(RetenueSubieSerializer(retenue).data)

    @action(detail=True, methods=['get'], url_path='recu-pdf',
            permission_classes=[IsAnyRole])
    def recu_pdf(self, request, pk=None):
        """XFAC9 — quittance (reçu de paiement) PDF pour CE paiement."""
        paiement = self.get_object()
        from ..utils.pdf import generate_recu_pdf
        try:
            pdf_bytes = generate_recu_pdf(paiement)
        except Exception as exc:
            return Response({'detail': f'PDF indisponible : {exc}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="Quittance_{paiement.id}.pdf"')
        return resp

    @action(detail=True, methods=['post'], url_path='envoyer-recu',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_recu(self, request, pk=None):
        """XFAC9 — envoi optionnel de la quittance au client par email."""
        from ..email_service import send_recu_email
        paiement = self.get_object()
        log = send_recu_email(
            paiement, user=request.user,
            to_email=request.data.get('to_email'))
        return Response({
            'statut': log.statut, 'to_email': log.to_email,
            'erreur': log.erreur,
        }, status=status.HTTP_201_CREATED)
