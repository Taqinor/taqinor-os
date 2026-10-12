"""SPL141 — ``convertir-bc``, ``generer-facture`` et ``proforma-pdf`` du
devis (flux devis → BC → facture, propriétaire facturation) ; routes
inchangées. VNT65 — ``generer-facture`` / ``facturer-complet`` = ENVELOPPES
de ``facturer_vente(emettre=True)`` : 409 rendu en 400 (contrat « Refus
400 »), version remplacée comprise ; stock U9 sorti à l'émission (VNT21).
Retrait des deux portes dès que le panneau (VNT75/VNT79) les remplace.
"""
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from . import openapi_docs as D
from ..models import Devis
from ..serializers_facturation import BonCommandeSerializer, FactureSerializer
from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminOrResponsableTier, IsResponsableOrAdmin,
)
from ..utils.references import create_with_reference
from ..utils.corps import valider_corps
import logging

logger = logging.getLogger(__name__)

#: VNT31 — clés ``vente`` du contrat ``devis_facturer.json`` (sous-ensemble
#: de ``etat_vente``, contrat ``vente_etat.json``).
CLES_VENTE_FACTURER = ('prix_convenu_ttc', 'emis_ttc', 'brouillons_ttc',
                       'paye_ttc', 'reste_a_facturer_ttc',
                       'reste_a_payer_ttc')
#: Les champs du corps transmis tels quels à ``facturer_vente``.
CHAMPS_FACTURER_VENTE = ('nature', 'montant_ttc', 'pourcentage',
                         'cle_attendue', 'libelle', 'emettre', 'paiements',
                         'remplacer_brouillons', 'utiliser_avances',
                         'override_credit')


def refus_porte_historique(exc):
    """VNT65 — refus de ``facturer_vente`` par une porte d'hier : 409 → 400
    (``detail`` + ``code``) ; 403 inchangé, ``credit_hold`` comme hier."""
    corps = dict(exc.corps)
    if exc.status == 403:
        corps['credit_hold'] = corps.get('code') == 'credit_hold'
        return Response(corps, status=status.HTTP_403_FORBIDDEN)
    return Response(corps, status=status.HTTP_400_BAD_REQUEST)


def _texte(valeur):
    from decimal import Decimal
    return f'{Decimal(str(valeur)):.2f}'


def apercu_facturer(devis, user):
    """GET ``devis/<id>/facturer/`` : le plan (tranches émise / brouillon /
    à faire), la prochaine tranche, l'acompte proposé et la vente — lus
    sur ``plan_facturation`` / ``etat_vente`` (aucun calcul ici)."""
    from ..vente_facturation import etat_vente, plan_facturation
    plan = plan_facturation(devis)
    etat = etat_vente(devis, user)
    p = plan['prochaine']
    return {
        'plan': [{'cle': t['cle'], 'libelle': t['libelle'],
                  'unite': t['unite'], 'valeur': _texte(t['valeur']),
                  'montant_ttc': _texte(t['montant_ttc']),
                  'statut': t['statut']} for t in plan['tranches']],
        'prochaine': ({'cle': p['cle'], 'libelle': p['libelle'],
                       'montant_ttc': _texte(p['montant_ttc'])}
                      if p else None),
        'acompte_propose': etat['acompte_propose'],
        'vente': {cle: etat[cle] for cle in CLES_VENTE_FACTURER},
    }


def refus_avant_facturer(vue, request, devis, corps):
    """403 avant toute écriture : émettre / encaisser / utiliser les avances
    exigent le code d'encaissement (même garde que
    ``factures/<id>/enregistrer-paiement/``) ; avertissement de vente
    bloquant (ZSAL9, ``override_avertissement``)."""
    if corps.get('emettre') or corps.get('paiements') \
            or corps.get('utiliser_avances'):
        if not HasPermissionOrLegacy('encaisser')().has_permission(
                request, vue):
            return Response(
                {'detail': ("Émettre ou encaisser une facture exige le "
                            "droit d'encaissement.")},
                status=status.HTTP_403_FORBIDDEN)
    from ..services import SaleWarningError, verifier_sale_warnings
    try:
        verifier_sale_warnings(
            devis, override=bool(corps.get('override_avertissement')),
            user=request.user, chatter_target=devis)
    except SaleWarningError as exc:
        return Response(
            {'detail': f'Avertissement de vente bloquant : {exc.motif}.',
             'code': 'sale_warning'}, status=status.HTTP_403_FORBIDDEN)
    return None


class DevisFacturationActionsMixin:
    """SPL141 — actions de facturation de ``DevisViewSet`` (mixin, aucune base)."""

    @extend_schema(request=None, responses={201: BonCommandeSerializer})
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
        # AMET6 (C-AMET-008) — LA porte unique `creer_bon_commande` (AMET5) :
        # contrôle « BC existant », numérotation et `bon_commande_cree`
        # (YEVNT6) partagés avec la création manuelle.
        from ..domain.facturation_ops import (
            BonCommandeExistant, creer_bon_commande)
        try:
            bc = creer_bon_commande(devis, request.user.company, request.user)
        except BonCommandeExistant as exc:
            return Response({'detail': exc.message},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer = BonCommandeSerializer(bc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=D.GenererFactureRequest,
                   responses={201: FactureSerializer, 403: D.ErreurGarde})
    @action(
        detail=True,
        methods=['post'],
        url_path='generer-facture',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_facture(self, request, pk=None):
        """Génère et ÉMET la PROCHAINE tranche de la vente — VNT65 :
        ``utils.echeancier.facturer_tranche_suivante`` (acompte, le brouillon
        automatique repris, puis matériel et solde)."""
        devis = self.get_object()
        # ENF11 — corps validé par son sérialiseur déclaré : un corps non
        # objet (liste, scalaire) ou un drapeau mal typé → 400, jamais 500.
        corps = valider_corps(request, D.GenererFactureRequest)
        from ..domain.facturation_vente import FacturationVenteRefusee
        from ..utils.echeancier import facturer_tranche_suivante
        from ..services import (
            verifier_credit_hold, CreditHoldError,
            verifier_sale_warnings, SaleWarningError,
        )
        # XFAC28 — blocage crédit dur (étend FG41). Flag OFF (défaut) → no-op.
        if devis.client_id is not None:
            override = bool(corps.get('override_credit'))
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
                devis, override=bool(corps.get('override_avertissement')),
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
            facture = facturer_tranche_suivante(devis, request.user)
        except FacturationVenteRefusee as exc:
            return refus_porte_historique(exc)
        except ValueError as exc:  # DevisDejaFacture (ATOT2)
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=D.FacturerCompletRequest,
                   responses={201: D.FacturerCompletResponse,
                              403: D.ErreurGarde})
    @action(
        detail=True,
        methods=['post'],
        url_path='facturer-complet',
        # ASEC29 / D-ASEC-1 — geste d'argent : code ``encaisser``.
        permission_classes=[HasPermissionOrLegacy('encaisser')],
    )
    def facturer_complet(self, request, pk=None):
        """« Facturer » un devis ACCEPTÉ en un geste (fondateur, 05/10/2026).

        Crée la facture COMPLÈTE (100 %, lignes du devis recopiées), l'émet
        (numéro définitif) puis consigne les paiements DÉJÀ reçus (0 à 5 :
        montant, date passée possible, mode, référence) — le tout atomique.
        Contrat : ``contract_samples/devis_facturer_complet.json``. Mêmes
        gardes que ``generer-facture`` (XFAC28, ZSAL9). VNT65 — enveloppe de
        ``facturer_vente(nature='complete', emettre=True)``. Jamais de prix
        d'achat ni de marge dans la réponse.
        """
        devis = self.get_object()
        valider_corps(request, D.FacturerCompletRequest)
        from ..models import Facture
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, facturer_vente)
        from ..selectors_facturation import (
            DevisDejaFacture, exiger_devis_facturable)
        from ..services import (
            verifier_credit_hold, CreditHoldError,
            verifier_sale_warnings, SaleWarningError,
        )
        if devis.client_id is not None:
            try:
                verifier_credit_hold(
                    devis.client,
                    override=bool(request.data.get('override_credit')),
                    user=request.user, chatter_target=devis,
                    contexte='facturation complète')
            except CreditHoldError as exc:
                return Response(
                    {'detail': (
                        'Client en blocage crédit : '
                        f'{exc.motif}. Un responsable/admin peut passer '
                        'outre avec `override_credit: true`.'),
                     'credit_hold': True},
                    status=status.HTTP_403_FORBIDDEN)
        try:
            verifier_sale_warnings(
                devis,
                override=bool(request.data.get('override_avertissement')),
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
            exiger_devis_facturable(devis, 'complete')  # ATOT2 nomme la facture
            facture, paiements = facturer_vente(
                devis, nature='complete', user=request.user, emettre=True,
                paiements=request.data.get('paiements') or [])
        except DevisDejaFacture as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_400_BAD_REQUEST)
        except FacturationVenteRefusee as exc:
            return refus_porte_historique(exc)
        from decimal import Decimal
        cent = Decimal('0.01')
        montant_paye = Decimal(str(facture.montant_paye))
        if facture.statut == Facture.Statut.PAYEE:
            statut = 'payee'
        elif montant_paye > 0 and facture.statut in (
                Facture.Statut.EMISE, Facture.Statut.EN_RETARD):
            # Statut de PAIEMENT servi à l'écran : la facture reste « Émise »
            # en base (aucun statut « partiellement payée » côté modèle).
            statut = 'partiellement_payee'
        else:
            statut = facture.statut
        return Response({
            'facture_id': facture.id,
            'facture_reference': facture.reference,
            'statut': statut,
            'total_ttc': str(Decimal(str(facture.total_ttc)).quantize(cent)),
            'montant_paye': str(montant_paye.quantize(cent)),
            'montant_du': str(Decimal(str(facture.montant_du)).quantize(cent)),
            'paiements': [{
                'id': p.id,
                'montant': str(Decimal(str(p.montant)).quantize(cent)),
                'date_paiement': p.date_paiement.isoformat(),
                'mode_paiement': p.mode,
                'reference': p.reference or '',
            } for p in paiements],
        }, status=status.HTTP_201_CREATED)

    @extend_schema(methods=['GET'], request=None,
                   responses={200: D.FacturerVenteApercu})
    @extend_schema(methods=['POST'], request=D.FacturerVenteRequest,
                   responses={201: D.FacturerVenteResponse,
                              400: D.ErreurFacturerVente,
                              403: D.ErreurFacturerVente,
                              409: D.ErreurFacturerVente})
    # api-only: l'écran FacturerVenteDialog arrive avec VNT45 (lot M1).
    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='facturer',
        permission_classes=[IsResponsableOrAdmin],
    )
    def facturer(self, request, pk=None):
        """VNT31 — « Facturer la vente » (contrat ``devis_facturer.json``).

        GET : l'aperçu (plan, prochaine tranche, acompte proposé, vente).
        POST : ``domain/facturation_vente.facturer_vente`` — la facture naît
        brouillon (``emettre`` / ``paiements`` / ``utiliser_avances`` exigent
        le code d'encaissement) ; les refus du service sont rendus tels quels
        (``code`` + clé fautive). Jamais de prix d'achat ni de marge."""
        devis = self.get_object()
        if request.method == 'GET':
            return Response(apercu_facturer(devis, request.user))
        corps = valider_corps(request, D.FacturerVenteRequest)
        refus = refus_avant_facturer(self, request, devis, corps)
        if refus is not None:
            return refus
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, facturer_vente)
        try:
            facture, _paiements = facturer_vente(
                devis, user=request.user,
                **{c: corps[c] for c in CHAMPS_FACTURER_VENTE if c in corps})
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        from ..vente_facturation import etat_vente
        etat = etat_vente(Devis.objects.get(
            pk=devis.pk, company_id=devis.company_id), request.user)
        return Response({
            'facture': {'id': facture.pk, 'reference': facture.reference,
                        'statut': facture.statut,
                        'total_ttc': _texte(facture.total_ttc),
                        'nature': facture.type_facture},
            'vente': {cle: etat[cle] for cle in CLES_VENTE_FACTURER},
        }, status=status.HTTP_201_CREATED)

    @extend_schema(request=OpenApiTypes.OBJECT,
                   responses={200: OpenApiTypes.OBJECT, 400: D.ErreurDetail,
                              409: D.ErreurDetail})
    # api-only: l'écran (panneau de vente, échéancier d'un accepté) arrive
    # avec les lanes frontend du lot M2 (contrat devis_echeancier.json).
    @action(detail=True, methods=['put'], url_path='echeancier',
            permission_classes=[IsAdminOrResponsableTier,
                                IsResponsableOrAdmin])
    def echeancier_vente(self, request, pk=None):
        """VNT66 — ``PUT devis/<id>/echeancier/`` (contrat
        ``devis_echeancier.json``, arbitrage 5 : palier responsable/admin ET
        code d'écriture ventes) : ``facturation_vente.
        modifier_echeancier_vente`` ; 200 = ``{id, reference, statut,
        echeancier}`` ; refus rendus tels quels (400 / 409)."""
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, echeancier_du_contrat,
            modifier_echeancier_vente)
        devis = self.get_object()
        try:
            devis = modifier_echeancier_vente(
                devis, request.data.get('tranches'), user=request.user)
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        return Response({'id': devis.pk, 'reference': devis.reference,
                         'statut': devis.statut,
                         'echeancier': echeancier_du_contrat(devis)})

    @extend_schema(request=None, responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
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
            logger.warning(
                "devis_facturation.DevisFacturationActionsMixin.proforma_pdf "
                ": erreur ignorée (mode dégradé)", exc_info=True)
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
