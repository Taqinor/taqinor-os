from drf_spectacular.utils import extend_schema_view, extend_schema
from apps.ventes.views import openapi_docs as D
from apps.ventes.openapi_params import qint
from django.db import transaction
from django.http import HttpResponse
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.stock.services import (
    mouvement_type_sortie, record_stock_movement,
)
from apps.ventes.models import Facture, Avoir, NoteDebit
from apps.facturation.serializers import AvoirSerializer, NoteDebitSerializer
from apps.roles.permissions import DroitDeLaGrille  # AARG41
from authentication.permissions import (
    IsResponsableOrAdmin,
    IsAdminRole,
)
from apps.ventes.gardes_lecture import LectureFactures  # AARG12
from authentication.scoping import scope_queryset
from core.mixins import company_qs
from core.pagination import OrdreTotalMixin  # ERR-FACTURES-LISTE-ORDRE-INSTABLE
import logging

logger = logging.getLogger('apps.ventes.views.avoir')

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def _dgi_export_rectificatif(document, type_code):
    """AARG41 — export DGI local d'un avoir (381) / d'une note de débit (383),
    à la demande : même interrupteur et même réponse que la facture."""
    from apps.ventes.dgi import build_ubl_xml, is_dgi_enabled
    from core.conflit_etat import ConflitEtat
    if not is_dgi_enabled(document.company):
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    if document.statut == 'annulee':
        raise ConflitEtat("Un document annulé ne s'exporte pas à la DGI.")
    xml_str = build_ubl_xml(document, type_code=type_code,
                            origine=document.facture)
    response = HttpResponse(xml_str, content_type='application/xml')
    response['Content-Disposition'] = (
        f'attachment; filename="{document.reference}-dgi.xml"')
    return response


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


@extend_schema_view(list=extend_schema(
    parameters=[qint('facture')]))
class AvoirViewSet(OrdreTotalMixin, viewsets.ReadOnlyModelViewSet):
    """Avoirs (notes de crédit) : lecture pour tout rôle ; PDF pour
    Responsable/Admin ; annulation Admin. Création via la facture
    (creer-avoir), jamais directement."""
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
    queryset = Avoir.objects.select_related(
        'client', 'facture', 'created_by').prefetch_related('lignes').all()
    serializer_class = AvoirSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'facture__reference', 'client__nom']
    ordering_fields = ['date_emission', 'reference']
    ordering = ['-date_emission', '-id']  # ERR-FACTURES-LISTE-ORDRE-INSTABLE

    def get_queryset(self):
        qs = company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) — avoirs créés par soi / l'équipe.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [LectureFactures()]
        if self.action == 'annuler':
            return [IsAdminRole()]
        if self.action == 'dgi_export':  # AARG41 — comme la facture (ASEC50)
            return [IsResponsableOrAdmin(), DroitDeLaGrille('ventes_export')()]
        if self.action == 'telecharger_pdf':  # ADRG10 — « Générer PDF »
            return [IsResponsableOrAdmin(), DroitDeLaGrille('ventes_pdf')()]
        return [IsResponsableOrAdmin()]

    @staticmethod
    def _trace_contre_passation(avoir):
        """AUD127 — retrouve la trace ZFAC5 qui a annulé la facture d'origine
        POUR CET AVOIR.

        Un avoir de contre-passation ne porte pas son mode : la seule preuve
        du lien est le ``FactureActivity`` posé par ``creer_avoir``, dont le
        corps nomme l'avoir miroir et dont ``old_value`` porte le statut que
        la facture avait AVANT d'être annulée. C'est exactement ce qu'il faut
        pour la restaurer.
        """
        from apps.ventes.models import FactureActivity
        if avoir.facture_id is None:
            return None
        return (FactureActivity.objects
                .filter(facture_id=avoir.facture_id, field='statut',
                        new_value=Facture.Statut.ANNULEE,
                        body__contains=f'avoir miroir {avoir.reference}')
                .order_by('-id')
                .first())

    @staticmethod
    def _contre_passer_restockage(avoir, user):
        """AFAC28 — SORTIE miroir de chaque ENTRÉE de stock posée par le
        retour (lue par ``stock.selectors``, écrite par ``stock.services`` —
        jamais ses modèles). Idempotente : une sortie déjà posée sous la
        référence de l'avoir ⇒ rien à refaire. Renvoie un motif de refus
        (unités déjà ressorties : le stock retomberait sous son niveau
        d'avant le retour) ou ``None``. À appeler dans la transaction."""
        from apps.stock.selectors import mouvements_par_reference
        from apps.stock.services import (
            mouvement_type_entree, verrouiller_produit,
        )
        entree, sortie = mouvement_type_entree(), mouvement_type_sortie()
        mouvements = list(mouvements_par_reference(
            avoir.company, avoir.reference))
        if any(m.type_mouvement == sortie for m in mouvements):
            return None
        par_produit = {}
        for m in mouvements:
            if m.type_mouvement != entree or not m.produit_id:
                continue
            qte, avant = par_produit.get(m.produit_id, (0, None))
            par_produit[m.produit_id] = (
                qte + m.quantite,
                m.quantite_avant if avant is None
                else min(avant, m.quantite_avant))
        plan = []
        for produit_id, (qte, avant) in par_produit.items():
            produit = verrouiller_produit(produit_id)
            if avant is not None and produit.quantite_stock - qte < avant:
                return ('Les unités retournées sont déjà ressorties du stock '
                        f'(« {produit.nom} ») : annulation de l\'avoir '
                        'refusée.')
            plan.append((produit, qte))
        for produit, qte in plan:
            record_stock_movement(
                company=avoir.company, produit=produit,
                type_mouvement=sortie, quantite=qte,
                quantite_avant=produit.quantite_stock,
                quantite_apres=produit.quantite_stock - qte,
                reference=avoir.reference,
                note=f"Annulation de l'avoir de retour {avoir.reference}",
                created_by=user)
        return None

    @extend_schema(responses=D.DgiExportXml)
    @action(detail=True, methods=['get'], url_path='dgi-export')
    def dgi_export(self, request, pk=None):
        return _dgi_export_rectificatif(self.get_object(), '381')

    @extend_schema(request=None, responses=AvoirSerializer)
    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """AUD127 — annule un avoir ET contre-passe son effet.

        L'action posait ``statut='annulee'`` et rendait la réponse : AUCUN
        événement, alors que la CRÉATION émet ``avoir_cree`` auquel compta
        abonne l'écriture d'avoir. L'effet ERP était immédiat —
        ``Facture.avoirs_total`` exclut les avoirs annulés, donc
        ``montant_du`` remonte — pendant que le grand livre gardait l'avoir :
        une créance de 20 000 réapparaissait côté ERP alors que la
        comptabilité la considérait toujours comme créditée. Et si l'avoir
        était une CONTRE-PASSATION, la facture d'origine avait été forcée à
        ANNULEE et rien ne la restaurait.

        Désormais : idempotente (double annulation = no-op), elle restaure la
        facture d'origine d'une contre-passation à son statut antérieur (ou
        refuse en 400 si ce statut est introuvable), et émet ``avoir_annule``
        exactement une fois — d'où l'extourne côté compta.
        """
        avoir = self.get_object()
        if avoir.statut == Avoir.Statut.ANNULEE:
            # Idempotence : rien à annuler, aucun événement ré-émis (une
            # seconde extourne doublerait le grand livre).
            return Response(AvoirSerializer(avoir).data)

        from core.events import avoir_annule

        with transaction.atomic():
            # AARG74 — relu SOUS VERROU : une annulation concurrente déjà
            # commitée ⇒ la même réponse idempotente, sans second événement.
            avoir = Avoir.objects.select_for_update().get(pk=avoir.pk)
            if avoir.statut == Avoir.Statut.ANNULEE:
                return Response(AvoirSerializer(avoir).data)
            # AFAC28 (C-AFAC-025) — un avoir de RETOUR re-stocké a posé une
            # ENTRÉE de stock : l'annuler la contre-passe (SORTIE miroir,
            # référence = l'avoir), en premier et avant toute autre écriture ;
            # refus 400 si les unités sont déjà ressorties.
            if avoir.restocke:
                refus = self._contre_passer_restockage(avoir, request.user)
                if refus:
                    return Response({'detail': refus},
                                    status=status.HTTP_400_BAD_REQUEST)
            trace = self._trace_contre_passation(avoir)
            if trace is not None:
                facture = Facture.objects.get(pk=avoir.facture_id, company_id=avoir.company_id)
                ancien = (trace.old_value or '').strip()
                if not ancien or ancien == Facture.Statut.ANNULEE:
                    return Response(
                        {'detail': (
                            "Annulation refusée : cet avoir a contre-passé la "
                            f"facture {facture.reference}, et son statut "
                            "antérieur est introuvable — la facture ne peut "
                            "pas être restaurée."
                        )},
                        status=status.HTTP_400_BAD_REQUEST)
                if facture.statut == Facture.Statut.ANNULEE:
                    # AARG63 — LA porte : vente verrouillée, refacturée ou
                    # devis non accepté ⇒ 409 ; AARG2 : l'avance revient.
                    from apps.ventes.domain.annulation_facture import restaurer_facture
                    restaurer_facture(facture, avoir=avoir, trace=trace,
                                      user=request.user)
            # AARG59 — le trop-perçu parti en avance revient à la facture (409
            # si l'avance a servi), avant tout événement.
            from apps.ventes.domain.encaissements import (
                recalculer_statut_paiement, rendre_trop_percu_de_avoir,
            )
            rendre_trop_percu_de_avoir(
                Facture.objects.select_for_update().get(pk=avoir.facture_id),
                avoir, user=request.user)
            avoir.statut = Avoir.Statut.ANNULEE
            avoir.save(update_fields=['statut'])
            # YLEDG4 — symétrique d'``avoir_cree`` : compta extourne
            # l'écriture d'avoir (jamais de suppression, COMPTA11).
            avoir_annule.send(
                sender=Avoir, instance=avoir, company=avoir.company)
            # ATOT8 — le reste dû remonte : une facture PAYÉE grâce à cet
            # avoir revient au recouvrement (statut dérivé du reste dû).
            recalculer_statut_paiement(
                Facture.objects.get(
                    pk=avoir.facture_id, company=avoir.company),
                user=request.user, source='annulation_avoir')
        # AARG37 — le PDF servi ne doit plus montrer un avoir actif (rendu hors
        # transaction, best-effort comme NoteDebitViewSet.annuler).
        try:
            from apps.ventes.utils.pdf import generate_avoir_pdf
            generate_avoir_pdf(avoir.id)
            avoir.refresh_from_db()
        except Exception:  # noqa: BLE001 — PDF best-effort (D-ENF22-BLE001)
            logger.warning("avoir.AvoirViewSet.annuler : erreur ignorée (mode dégradé)", exc_info=True)
        return Response(AvoirSerializer(avoir).data)

    @extend_schema(responses=D.PdfBinaire)
    @action(detail=True, methods=['get'], url_path='telecharger-pdf')
    def telecharger_pdf(self, request, pk=None):
        avoir = self.get_object()
        from apps.ventes.utils.pdf import download_pdf, generate_avoir_pdf
        try:
            if not avoir.fichier_pdf:
                generate_avoir_pdf(avoir.id)
                avoir.refresh_from_db()
            pdf_bytes = download_pdf(avoir.fichier_pdf)
        except Exception:
            logger.warning("avoir.AvoirViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            return Response({'detail': 'PDF indisponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from apps.ventes.utils.filenames import document_filename
        filename = document_filename(
            'Avoir', avoir.reference,
            client=avoir.client if avoir.client_id else None,
            company=avoir.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"')
        return response


@extend_schema_view(list=extend_schema(
    parameters=[qint('facture')]))
class NoteDebitViewSet(OrdreTotalMixin, viewsets.ReadOnlyModelViewSet):
    """ZFAC4 — notes de débit : lecture pour tout rôle ; PDF pour
    Responsable/Admin. Création via la facture (creer-note-debit), jamais
    directement — même patron qu'``AvoirViewSet``."""
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
    queryset = NoteDebit.objects.select_related(
        'client', 'facture', 'created_by').prefetch_related('lignes').all()
    serializer_class = NoteDebitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'facture__reference', 'client__nom']
    ordering_fields = ['date_emission', 'reference']
    ordering = ['-date_emission', '-id']  # ERR-FACTURES-LISTE-ORDRE-INSTABLE

    def get_queryset(self):
        qs = company_qs(super().get_queryset(), self.request.user)
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [LectureFactures()]
        if self.action == 'annuler':
            return [IsAdminRole()]
        if self.action == 'dgi_export':  # AARG41 — comme la facture (ASEC50)
            return [IsResponsableOrAdmin(), DroitDeLaGrille('ventes_export')()]
        return [IsResponsableOrAdmin()]

    @extend_schema(responses=D.DgiExportXml)
    @action(detail=True, methods=['get'], url_path='dgi-export')
    def dgi_export(self, request, pk=None):
        return _dgi_export_rectificatif(self.get_object(), '383')

    @extend_schema(request=None,
                   responses={200: D.NoteDebitAnnuleeResponse,
                              201: D.NoteDebitAnnuleeResponse})
    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """AFAC32 (D-AFAC-C4) — annule une note de débit ÉMISE par un AVOIR de
        note de débit (jamais en place) : le reste dû revient, chatter tracé.
        Idempotente : rejouée, elle renvoie le même avoir (200, rien créé)."""
        note_debit = self.get_object()
        from apps.ventes.domain.facturation_ops import (
            AvoirRefuse, annuler_note_debit_par_avoir,
        )
        try:
            avoir, cree = annuler_note_debit_par_avoir(
                note_debit=note_debit, user=request.user)
        except AvoirRefuse as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_400_BAD_REQUEST)
        if cree:
            try:
                from apps.ventes.utils.pdf import generate_avoir_pdf
                generate_avoir_pdf(avoir.id)
                avoir.refresh_from_db()
            except Exception:  # noqa: BLE001 — PDF best-effort (D-ENF22-BLE001)
                logger.warning("avoir.NoteDebitViewSet.annuler : erreur ignorée (mode dégradé)", exc_info=True)
        return Response(
            {'note_debit': NoteDebitSerializer(note_debit).data,
             'avoir': AvoirSerializer(avoir).data, 'cree': cree},
            status=status.HTTP_201_CREATED if cree else status.HTTP_200_OK)

    @extend_schema(responses=D.PdfBinaire)
    @action(detail=True, methods=['get'], url_path='telecharger-pdf')
    def telecharger_pdf(self, request, pk=None):
        note_debit = self.get_object()
        from apps.ventes.utils.pdf import download_pdf, generate_note_debit_pdf
        try:
            if not note_debit.fichier_pdf:
                generate_note_debit_pdf(note_debit.id)
                note_debit.refresh_from_db()
            pdf_bytes = download_pdf(note_debit.fichier_pdf)
        except Exception:
            logger.warning("avoir.NoteDebitViewSet.telecharger_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            return Response({'detail': 'PDF indisponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        from apps.ventes.utils.filenames import document_filename
        filename = document_filename(
            'NoteDebit', note_debit.reference,
            client=note_debit.client if note_debit.client_id else None,
            company=note_debit.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"')
        return response
