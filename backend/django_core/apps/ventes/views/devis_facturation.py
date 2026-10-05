"""SPL141 — ``convertir-bc``, ``generer-facture`` et ``proforma-pdf`` du
devis (flux devis → BC → facture, propriétaire facturation), déplacement
pur depuis ``views/devis.py`` : corps octet-identiques, routes inchangées.

Les imports function-locaux des corps (``from ..services import
reserver_stock_devis_facture…``, ``from ..utils.echeancier import
creer_facture_tranche``, ``from ..utils.pdf import generate_proforma_pdf``,
``from .. import activity``) restent dans les corps.
"""
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis, BonCommande
from ..serializers_facturation import BonCommandeSerializer, FactureSerializer
from authentication.permissions import IsResponsableOrAdmin
from ..utils.references import create_with_reference
from ..utils.company_settings import create_numbered


class DevisFacturationActionsMixin:
    """SPL141 — actions de facturation de ``DevisViewSet`` (mixin, aucune base)."""

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
        bc = create_numbered(
            BonCommande, company, 'bon_commande',
            lambda ref: BonCommande.objects.create(
                reference=ref,
                devis=devis,
                client=devis.client,
                statut=BonCommande.Statut.EN_ATTENTE,
                company=company,
            ),
        )
        # YEVNT6 — événement documentaire (best-effort).
        from core.events import bon_commande_cree
        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=company)
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
        from ..utils.echeancier import creer_facture_tranche
        from ..services import (
            reserver_stock_devis_facture, StockInsuffisantError,
            verifier_credit_hold, CreditHoldError,
            verifier_sale_warnings, SaleWarningError,
        )
        company = request.user.company
        # XFAC28 — blocage crédit dur (étend FG41). Flag OFF (défaut) → no-op.
        if devis.client_id is not None:
            override = bool(request.data.get('override_credit'))
            try:
                verifier_credit_hold(
                    devis.client, override=override, user=request.user,
                    chatter_target=devis, contexte='génération facture')
            except CreditHoldError as exc:
                return Response(
                    {'detail': (
                        'Client en blocage crédit : '
                        f'{exc.motif}. Un responsable/admin peut passer '
                        'outre avec `override_credit: true`.'),
                     'credit_hold': True},
                    status=status.HTTP_403_FORBIDDEN)
        # ZSAL9 — avertissement de vente BLOQUANT (produit/client). Vide → no-op.
        try:
            verifier_sale_warnings(
                devis, override=bool(request.data.get('override_avertissement')),
                user=request.user, chatter_target=devis)
        except SaleWarningError as exc:
            return Response(
                {'detail': (
                    f'Avertissement de vente bloquant : {exc.motif}. '
                    'Un responsable/admin peut passer outre avec '
                    '`override_avertissement: true`.'),
                 'sale_warning': True},
                status=status.HTTP_403_FORBIDDEN)
        try:
            # U9 — la facturation directe par échéancier court-circuite le bon
            # de commande : on réserve/consomme ici le stock matériel du devis,
            # comme le ferait la livraison d'un BC, dans la MÊME transaction que
            # la facture (rollback atomique si la réservation échoue). La garde
            # anti-double-comptage du service évite de re-décompter quand un BC
            # livré existe déjà ou qu'une tranche antérieure a déjà réservé.
            with transaction.atomic():
                reserver_stock_devis_facture(
                    devis=devis, user=request.user, company=company)
                facture = creer_facture_tranche(
                    devis, request.user, company,
                    create_with_reference,
                )
        except StockInsuffisantError as exc:
            return Response(
                {'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='proforma-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def proforma_pdf(self, request, pk=None):
        """XFAC10 — facture PRO-FORMA NON comptabilisée : layout facture
        legacy filigrané « PRO-FORMA — ne constitue pas une facture »,
        numérotation propre PF- (utils/references.py), AUCUN impact sur les
        statuts/GL/numérotation des vraies factures. Trace au chatter.

        QJR19 (décision fondateur D1 du 29/08/2026 — l'endpoint est CONSERVÉ) :
        LE RENDU D'ABORD, LE DOCUMENT ENSUITE. Le ``ProformaDocument`` et sa
        référence ``PF-`` étaient créés AVANT le rendu : un gabarit qui plantait
        (ligne de section/note, XSAL14) consommait quand même le numéro, et la
        séquence de la société avançait pour un document qui n'a jamais existé.
        Le rendu se fait donc À L'INTÉRIEUR de la fabrique passée à
        ``create_with_reference`` — ce qui garantit AUSSI que le numéro IMPRIMÉ
        sur le PDF est exactement celui qui est enregistré, même en cas de
        course sur la référence.
        """
        from ..models import ProformaDocument
        from ..utils.pdf import generate_proforma_pdf

        devis = self.get_object()
        company = request.user.company
        rendu = {}

        def _rendre_puis_creer(ref):
            rendu['pdf'] = generate_proforma_pdf(devis, ref)
            return ProformaDocument.objects.create(
                company=company, devis=devis, reference=ref,
                created_by=request.user,
            )

        try:
            proforma = create_with_reference(
                ProformaDocument, 'PF', company, _rendre_puis_creer,
                period='monthly')
        except Exception as exc:
            return Response({'detail': f'PDF indisponible : {exc}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        pdf_bytes = rendu['pdf']

        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            f'Facture pro-forma {proforma.reference} générée par '
            f'{getattr(request.user, "username", "?")}.')

        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="{proforma.reference}.pdf"')
        return resp
