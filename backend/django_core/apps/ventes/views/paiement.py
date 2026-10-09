from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from drf_spectacular.utils import extend_schema
from . import openapi_docs as D
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.exceptions import ValidationError  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.mixins import company_qs
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
    LigneDevisSerializer,
    DevisActivitySerializer,
)
from ..serializers_facturation import (  # noqa: F401
    BonCommandeSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AffectationPaiementSerializer,
    RetenueSubieSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)
from core.permissions import declared_action_permissions
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401
READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _refus_si_rejete(paiement):
    """AUD132 (PAY-12) — 409 si ``paiement`` est REJETÉ, sinon ``None``.

    Un règlement rejeté (chèque impayé, virement retourné) n'a plus d'existence
    monétaire : aucune quittance ne doit l'attester, ni en PDF ni par email.
    """
    if paiement.statut == Paiement.Statut.REJETE:
        motif = (paiement.motif_rejet or '').strip()
        detail = 'Règlement rejeté : aucune quittance ne peut être émise.'
        if motif:
            detail = f'{detail[:-1]} ({motif}).'
        return Response({'detail': detail}, status=status.HTTP_409_CONFLICT)
    return None


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
        # AFAC55 (C-AFAC-048) — même portée que `FactureViewSet` : un rôle
        # restreint ne voit que les paiements qu'il a saisis ou ceux des
        # factures de sa portée (créées par soi / l'équipe).
        from authentication.scoping import scope_queryset
        qs = scope_queryset(
            company_qs(super().get_queryset(), self.request.user),
            self.request.user, ['created_by', 'facture__created_by'])
        # AFAC60 (C-AFAC-054) — `?remisable=1` : seuls les paiements qu'une
        # remise d'encaissement accepterait (MÊME prédicat que la déclaration).
        if str(self.request.query_params.get('remisable') or '').strip() in (
                '1', 'true', 'True'):
            from .remise_encaissement import paiements_remisables
            qs = paiements_remisables(qs)
        return qs

    def _facture_visible(self, facture_id):
        """AFAC55 — facture de la société ET de la portée du rôle, ou None."""
        from authentication.scoping import scope_queryset
        return scope_queryset(
            company_qs(Facture.objects.all(), self.request.user),
            self.request.user, ['created_by']).filter(pk=facture_id).first()

    def get_permissions(self):
        # La garde déclarée par l'@action elle-même PRIME sur le tiering
        # ci-dessous. Sans cette ligne, l'ancien `if/else` sur `self.action`
        # jetait EN SILENCE le `permission_classes=` du décorateur : les trois
        # @action d'écriture déclarées `IsResponsableOrAdmin`
        # (`paiement-avec-retenue`, `attestation-recue`, `envoyer-recu`)
        # retombaient sur le `return [IsAnyRole()]` final — n'importe quel rôle
        # authentifié pouvait solder une facture via une retenue à la source,
        # cocher la réception d'une attestation RAS ou envoyer une quittance au
        # client. Trou RBAC réel, refermé ici (durcissement).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        # ASEC29 / D-ASEC-1 — enregistrer et ventiler une avance sont des
        # gestes d'argent : code ``encaisser`` (seule source).
        if self.action in ('enregistrer_avance', 'ventiler'):
            return [HasPermissionOrLegacy('encaisser')()]
        if self.action == 'rejeter':
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

    @extend_schema(parameters=[OpenApiParameter('client', OpenApiTypes.INT, required=False)], responses=PaiementSerializer(many=True))
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

    @extend_schema(request=D.EnregistrerAvanceRequest, responses={201: PaiementSerializer})
    @action(detail=False, methods=['post'], url_path='enregistrer-avance')
    def enregistrer_avance(self, request):
        """XFAC1 — enregistre un règlement reçu SANS facture (avance/acompte à
        la commande/trop-perçu), rattaché directement au client.

        AUD134 — c'est le SEUL chemin où `client` reste choisi par l'appelant
        (`PaiementSerializer.client` est désormais en lecture seule). Il est
        résolu à travers `crm.selectors.client_base_qs(company)`, donc borné à
        la société de l'utilisateur : un id d'une autre société renvoie 400,
        jamais un paiement rattaché hors tenant."""
        from apps.crm.selectors import client_base_qs
        from ..services import enregistrer_avance as _enregistrer_avance

        company = request.user.company
        client_id = request.data.get('client')
        # Scoping EXPLICITE par la société (superuser sans société : `company_qs`
        # garde son comportement historique de portée globale).
        client = company_qs(
            client_base_qs(company), request.user).filter(pk=client_id).first()
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

    @extend_schema(request=D.VentilerRequest, responses={201: AffectationPaiementSerializer})
    @action(detail=True, methods=['post'], url_path='ventiler')
    def ventiler(self, request, pk=None):
        """XFAC1 — ventile une avance non affectée sur UNE facture ouverte du
        même client. Corps : ``{facture, montant}``. Peut être appelée
        plusieurs fois pour répartir la même avance sur plusieurs factures."""
        from ..services import ventiler_avance as _ventiler_avance

        paiement = self.get_object()
        facture = self._facture_visible(request.data.get('facture'))
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
        facture = self._facture_visible(facture_id)
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        # AFAC30 (C-AFAC-029) — l'ENTRÉE est validée par un sérialiseur :
        # 400 en français sous le champ fautif, plus jamais un 500 ni un
        # `mode`/`type_retenue` inconnu enregistré.
        from ..serializers_facturation import (
            PaiementAvecRetenueEntreeSerializer,
        )
        entree = PaiementAvecRetenueEntreeSerializer(data=request.data)
        if not entree.is_valid():
            return Response(entree.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        donnees = entree.validated_data
        try:
            paiement, retenue = _enregistrer_avec_retenue(
                facture=facture, montant=donnees['montant'],
                date_paiement=donnees['date_paiement'],
                mode=donnees['mode'],
                type_retenue=donnees['type_retenue'],
                taux=donnees['taux'],
                reference=donnees['reference'],
                note=donnees['note'],
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

    @extend_schema(responses=RetenueSubieSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='attestations-ras-en-attente')
    def attestations_ras_en_attente(self, request):
        """XFAC4 — état des attestations RAS à recevoir (non reçues)."""
        qs = RetenueSubie.objects.select_related('facture').filter(
            attestation_recue=False)
        qs = company_qs(qs, request.user)
        return Response(RetenueSubieSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'],
            url_path=r'retenues/(?P<retenue_id>[^/.]+)/attestation-recue',
            permission_classes=[IsResponsableOrAdmin])
    def attestation_recue(self, request, retenue_id=None):
        """XFAC4 — coche la réception de l'attestation RAS (+ justificatif)."""
        retenue = company_qs(
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
        """XFAC9 — quittance (reçu de paiement) PDF pour CE paiement.

        AUD132 (PAY-12) — la quittance ne contrôlait PAS ``paiement.statut`` :
        elle affirmait donc un règlement de 30 000 pour un chèque sans
        provision, tout en imprimant en bas de page un ``solde_restant``
        recalculé depuis ``facture.montant_du`` qui, lui, avait remonté après
        le rejet. Un paiement rejeté n'a plus de quittance (409)."""
        paiement = self.get_object()
        conflit = _refus_si_rejete(paiement)
        if conflit is not None:
            return conflit
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
        """XFAC9 — envoi optionnel de la quittance au client par email.

        AUD132 (PAY-12) — même garde que ``recu_pdf`` : envoyer la quittance
        d'un règlement rejeté enverrait au client la preuve écrite d'un
        paiement qu'il n'a pas fait. 409, et RIEN ne part."""
        from ..email_service import send_recu_email
        paiement = self.get_object()
        conflit = _refus_si_rejete(paiement)
        if conflit is not None:
            return conflit
        log = send_recu_email(
            paiement, user=request.user,
            to_email=request.data.get('to_email'))
        return Response({
            'statut': log.statut, 'to_email': log.to_email,
            'erreur': log.erreur,
        }, status=status.HTTP_201_CREATED)
