from datetime import date as _date

from drf_spectacular.utils import extend_schema_view
from ..openapi_params import entier_requete, qstr
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from . import openapi_docs as D
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from core.mixins import company_qs
from core.conflit_etat import ConflitEtat
from core.parseurs import corps_valide
from ..models import Facture, Paiement, RetenueSubie
from ..serializers_facturation import (
    FactureSerializer, PaiementSerializer, AffectationPaiementSerializer,
    PaiementEnvoyerRecuRequestSerializer, PaiementVentilerRequestSerializer,
    RetenueSubieSerializer,
)
from ..serializers_facturation import PaiementAvecRetenueEntreeSerializer  # ENF11 : utilisé par @extend_schema
from authentication.permissions import (
    IsAnyRole, IsResponsableOrAdmin, HasPermissionOrLegacy,
)
from core.permissions import declared_action_permissions
import logging

logger = logging.getLogger(__name__)
READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _refus_etat(exc):
    """CI #1001 — refus d'un service qui dépend de l'ÉTAT stocké (corps déjà
    validé par le sérialiseur publié) : 409 ``ConflitEtat`` portant ``detail``
    (forme publiée ``ErreurDetail``) et les clés de champ d'origine."""
    corps = dict(exc.detail)
    corps.setdefault('detail', next(iter(corps.values())))
    return ConflitEtat(corps)


def _refus_si_rejete(paiement):
    """AUD132 (PAY-12) — 409 si ``paiement`` est REJETÉ, sinon ``None``.

    Un règlement rejeté (chèque impayé, virement retourné) n'a plus d'existence
    monétaire : aucune quittance ne doit l'attester, ni en PDF ni par email.
    """
    if paiement.statut == Paiement.Statut.ANNULE_SAISIE:
        # AFAC17 — une saisie annulée n'atteste plus aucun règlement.
        return Response(
            {'detail': ('Saisie annulée : aucune quittance ne peut être '
                        'émise.')},
            status=status.HTTP_409_CONFLICT)
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


@extend_schema_view(list=extend_schema(
    parameters=[qstr('remisable', desc='1/true : seulement les paiements remisables en banque.')]))
class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule des paiements (l'enregistrement passe par la facture) —
    XFAC1 ajoute deux actions d'écriture pour les AVANCES non affectées
    (règlement reçu sans facture) : enregistrement + ventilation sur des
    factures ouvertes du même client.

    Visible par tout rôle authentifié ; tenant-scopé par société.
    """
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
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
        # ENF11 — un id non entier (« abc » dans l'URL ou le corps) = facture
        # introuvable, jamais ValueError → 500.
        try:
            facture_id = int(facture_id)
        except (TypeError, ValueError):
            return None
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
        if self.action in ('rejeter', 'annuler_saisie', 'reaffecter'):
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    @extend_schema(request=D.RejeterPaiementRequest,
                   responses=PaiementSerializer)
    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """YLEDG5 — marque ce paiement REJETÉ (chèque impayé / virement
        rejeté). Motif obligatoire ; frais optionnels. Rouvre la facture
        (montant_du remonte, statut recalculé) et ré-arme les relances. Le
        paiement n'est jamais supprimé (piste d'audit) ; un double rejet est
        refusé (409)."""
        from ..services import rejeter_paiement, PaiementRejectError
        paiement = self.get_object()
        # CI #997 (2) — corps validé par sa forme publiée (texte, décimal,
        # date stricts) : ``date_rejet: ""`` valait « aujourd'hui » en silence.
        corps = corps_valide(request, D.RejeterPaiementRequest)
        try:
            rejeter_paiement(
                paiement=paiement, motif=corps['motif'],
                frais=corps.get('frais'), date_rejet=corps.get('date_rejet'),
                user=request.user,
            )
        except PaiementRejectError as exc:
            code = (status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)
            return Response({'detail': exc.message}, status=code)
        return Response(PaiementSerializer(paiement).data)

    @extend_schema(request=D.AnnulerSaisieRequest,
                   responses={200: PaiementSerializer, 409: D.ErreurCode})
    @action(detail=True, methods=['post'], url_path='annuler-saisie')
    def annuler_saisie(self, request, pk=None):
        """AFAC17 — annule une saisie de paiement ERRONÉE (motif obligatoire,
        datée, signée) ; contrat ``paiement_annuler_saisie.json``."""
        from ..domain.encaissements import (
            CorrectionPaiementRefusee, annuler_saisie_paiement,
        )
        paiement = self.get_object()
        # CI #997 (2) — ``motif: [null, null]`` levait AttributeError (500) :
        # présent, il est validé (texte strict) ; absent → ``motif_requis``.
        motif = None
        if not isinstance(request.data, dict) or 'motif' in request.data:
            motif = corps_valide(request, D.AnnulerSaisieRequest)['motif']
        try:
            annuler_saisie_paiement(
                paiement=paiement, motif=motif, user=request.user)
        except CorrectionPaiementRefusee as exc:
            return Response(
                {'code': exc.code, 'detail': exc.detail},
                status=(status.HTTP_409_CONFLICT if exc.conflit
                        else status.HTTP_400_BAD_REQUEST))
        paiement.refresh_from_db()
        return Response(PaiementSerializer(paiement).data)

    @extend_schema(request=D.ReaffecterRequest,
                   responses={200: D.ReaffecterResponse, 409: D.ErreurCode})
    @action(detail=True, methods=['post'], url_path='reaffecter')
    def reaffecter(self, request, pk=None):
        """AFAC17 — réaffecte le paiement à une autre facture du MÊME client
        (encaissable) ; contrat ``paiement_reaffecter.json``."""
        from ..domain.encaissements import (
            CorrectionPaiementRefusee, reaffecter_paiement,
        )
        paiement = self.get_object()
        # CI #997 (2) — corps tableau → 500, ``"5"``/``5.5`` lus en entier :
        # entier JSON strict ; un id bien formé inconnu → 404 (ressource).
        cible_id = corps_valide(request, D.ReaffecterRequest)['facture_cible']
        cible = self._facture_visible(cible_id)
        if cible is None:
            return Response(
                {'code': 'cible_invalide', 'detail': 'Facture cible inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            paiement, source, cible = reaffecter_paiement(
                paiement=paiement, facture_cible=cible, user=request.user)
        except CorrectionPaiementRefusee as exc:
            return Response(
                {'code': exc.code, 'detail': exc.detail},
                status=(status.HTTP_409_CONFLICT if exc.conflit
                        else status.HTTP_400_BAD_REQUEST))

        def _facture(f):
            return {'id': f.id, 'reference': f.reference,
                    'montant_du': f'{f.montant_du:.2f}', 'statut': f.statut}
        return Response({
            'paiement': PaiementSerializer(paiement).data,
            'facture_source': _facture(source),
            'facture_cible': _facture(cible),
        })

    @extend_schema(parameters=[OpenApiParameter('client', OpenApiTypes.INT, required=False)],
                   responses=PaiementSerializer(many=True))
    @action(pagination_class=None, detail=False, methods=['get'], url_path='avances-non-affectees')
    def avances_non_affectees(self, request):
        """XFAC1 — avances (paiements sans facture) encore disponibles,
        optionnellement filtrées par client (``?client=<id>``)."""
        qs = self.get_queryset().filter(
            facture__isnull=True,
        ).exclude(
            statut_affectation=Paiement.StatutAffectation.AFFECTE)
        # CI #997 fuzz (24/10) : ``?client=`` publié entier — vide, répété ou
        # illisible = 400 (le vide était lu « pas de filtre »).
        client_id = entier_requete(request, 'client')
        if client_id is not None:
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
        # CI #997 — corps non objet (``[null, null]``) : 400, plus 500.
        if not isinstance(request.data, dict):
            return Response({'detail': 'Corps JSON objet attendu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        client_id = request.data.get('client')
        # ENF11 — un ``client`` non entier (« None », texte…) répond 400 comme
        # un id inconnu : ``filter(pk='None')`` levait ValueError (500).
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            client_id = None
        # Scoping EXPLICITE par la société (superuser sans société : `company_qs`
        # garde son comportement historique de portée globale).
        client = (company_qs(
            client_base_qs(company), request.user).filter(pk=client_id).first()
            if client_id is not None else None)
        if client is None:
            return Response({'detail': 'Client introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ENF11 — entrées validées AVANT l'écriture : date, mode, montant
        # fini et borné, référence ≤ 120 (une date/un mode/un montant
        # démesuré/une référence trop longue finissaient en 500 à l'INSERT).
        from datetime import date as _date
        from decimal import Decimal, InvalidOperation
        brut_date = request.data.get('date_paiement')
        try:
            date_paiement = (
                timezone.localdate() if brut_date in (None, '')
                else _date.fromisoformat(str(brut_date)))
        except ValueError:
            return Response(
                {'date_paiement': 'Date invalide (attendu AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        mode = request.data.get('mode') or Paiement.Mode.VIREMENT
        if mode not in Paiement.Mode.values:
            return Response(
                {'mode': 'Mode de paiement inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        brut_montant = request.data.get('montant')
        if brut_montant not in (None, ''):
            try:
                nombre = Decimal(str(brut_montant))
            except (InvalidOperation, ValueError):
                nombre = None
            if (nombre is None or not nombre.is_finite()
                    or abs(nombre) >= Decimal('1e10')):
                return Response(
                    {'montant': 'Montant invalide.'},
                    status=status.HTTP_400_BAD_REQUEST)
        reference = request.data.get('reference', '')
        if reference is not None and len(str(reference)) > 120:
            return Response(
                {'reference': 'Au plus 120 caractères.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            paiement = _enregistrer_avance(
                company=company, client=client,
                montant=request.data.get('montant'),
                date_paiement=date_paiement,
                mode=mode,
                reference=reference,
                note=request.data.get('note', ''),
                created_by=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PaiementSerializer(paiement).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=PaiementVentilerRequestSerializer,
                   responses={201: AffectationPaiementSerializer,
                              404: D.ErreurDetail, 409: D.ErreurDetail})
    @action(detail=True, methods=['post'], url_path='ventiler')
    def ventiler(self, request, pk=None):
        """XFAC1 — ventile une avance non affectée sur UNE facture ouverte du
        même client. Corps : ``{facture, montant}``. Peut être appelée
        plusieurs fois pour répartir la même avance sur plusieurs factures."""
        from ..services import ventiler_avance as _ventiler_avance

        paiement = self.get_object()
        entree = PaiementVentilerRequestSerializer(data=request.data)
        if not entree.is_valid():
            return Response(entree.errors, status=status.HTTP_400_BAD_REQUEST)
        facture = self._facture_visible(entree.validated_data['facture'])
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            affectation = _ventiler_avance(
                paiement=paiement, facture=facture,
                montant=entree.validated_data['montant'], user=request.user,
            )
        except ValidationError as exc:
            raise _refus_etat(exc)
        return Response(
            AffectationPaiementSerializer(affectation).data,
            status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter('facture_id', OpenApiTypes.INT,
                                     OpenApiParameter.PATH)],
        request=PaiementAvecRetenueEntreeSerializer,
        responses={201: D.PaiementAvecRetenueResponse,
                   409: D.ErreurDetail},
        # ENF11 — montant publié strictement positif (« Le montant doit être
        # positif. »), comme le sérialiseur d'entrée le valide (min 0.01).
        extensions=D.CORPS_MONTANT_POSITIF)
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
            raise _refus_etat(exc)
        return Response({
            'paiement': PaiementSerializer(paiement).data,
            'retenue': RetenueSubieSerializer(retenue).data,
            'facture': FactureSerializer(facture.__class__.objects.get(
                pk=facture.pk)).data,
        }, status=status.HTTP_201_CREATED)

    @extend_schema(responses=RetenueSubieSerializer(many=True))
    @action(pagination_class=None, detail=False, methods=['get'], url_path='attestations-ras-en-attente')
    def attestations_ras_en_attente(self, request):
        """XFAC4 — état des attestations RAS à recevoir (non reçues)."""
        qs = RetenueSubie.objects.select_related('facture').filter(
            attestation_recue=False)
        qs = company_qs(qs, request.user)
        return Response(RetenueSubieSerializer(qs, many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter('retenue_id', OpenApiTypes.INT,
                                     OpenApiParameter.PATH)],
        request=D.AttestationRecueRequest, responses=RetenueSubieSerializer)
    @action(detail=False, methods=['post'],
            url_path=r'retenues/(?P<retenue_id>[^/.]+)/attestation-recue',
            permission_classes=[IsResponsableOrAdmin])
    def attestation_recue(self, request, retenue_id=None):
        """XFAC4 — coche la réception de l'attestation RAS (+ justificatif)."""
        try:
            retenue_id = int(retenue_id)
        except (TypeError, ValueError):
            retenue_id = None
        retenue = company_qs(
            RetenueSubie.objects.all(), request.user).filter(
            pk=retenue_id).first() if retenue_id is not None else None
        if retenue is None:
            return Response({'detail': 'Retenue introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        # ENF11 — date lue AVANT toute écriture (une chaîne illisible
        # finissait en ValidationError Django → 500).
        brute = request.data.get('attestation_date')
        try:
            date_attestation = (
                _date.fromisoformat(str(brute)) if brute
                else timezone.now().date())
        except ValueError:
            return Response(
                {'attestation_date': 'Date invalide (attendu AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        fichier = request.data.get('attestation_fichier')
        if fichier and len(str(fichier)) > 500:
            return Response(
                {'attestation_fichier': 'Au plus 500 caractères.'},
                status=status.HTTP_400_BAD_REQUEST)
        retenue.attestation_recue = True
        retenue.attestation_date = date_attestation
        if fichier:
            retenue.attestation_fichier = str(fichier)
        retenue.save(update_fields=[
            'attestation_recue', 'attestation_date', 'attestation_fichier'])
        return Response(RetenueSubieSerializer(retenue).data)

    @extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY,
                              409: D.ErreurDetail})
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
        from ..utils.pdf import assurer_numero_recu, generate_recu_pdf
        try:
            pdf_bytes = generate_recu_pdf(paiement)
        except Exception:
            # VNT43 — message générique : l'exception brute reste au journal.
            logger.warning("paiement.PaiementViewSet.recu_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            return Response({'detail': 'PDF du reçu indisponible.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # VNT43 — fichier nommé par le numéro de reçu de la société (posé au
        # rendu, stable), comme l'e-mail — jamais par l'id technique.
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="Quittance_{assurer_numero_recu(paiement)}.pdf"')
        return resp

    @extend_schema(request=PaiementEnvoyerRecuRequestSerializer,
                   responses={201: D.EnvoyerRecuResponse,
                              409: D.ErreurDetail})
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
        entree = PaiementEnvoyerRecuRequestSerializer(data=request.data)
        if not entree.is_valid():
            return Response(entree.errors, status=status.HTTP_400_BAD_REQUEST)
        log = send_recu_email(
            paiement, user=request.user,
            to_email=entree.validated_data.get('to_email'))
        return Response({
            'statut': log.statut, 'to_email': log.to_email,
            'erreur': log.erreur,
        }, status=status.HTTP_201_CREATED)
