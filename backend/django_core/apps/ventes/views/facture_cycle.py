"""Gestes de CYCLE d'une facture, hors ``views/facture.py`` (C20 : le
fichier ne grossit pas). VNT67 y pose ``montant-tranche`` ; VNT97 y déplace
émettre, remettre en brouillon, marquer payée et annuler
(``FactureCycleActionsMixin``, en tête des bases de ``FactureViewSet``)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsResponsableOrAdmin,
)

from . import openapi_docs as D
from ..models import Avoir, Facture
from ..serializers_facturation import FactureSerializer
from ..utils.corps import valider_corps


def refuser_devis_du_corps(donnees, facture=None):
    """VNT89 — la porte MANUELLE (création / modification d'une facture) est
    fermée aux devis : 400 ``facture_de_devis`` (« passez par Facturer la
    vente ») ; règle : ``facturation_vente.devis_impose_au_corps``."""
    from ..domain.facturation_vente import (
        FACTURE_DE_DEVIS_REFUSE, devis_impose_au_corps)
    if devis_impose_au_corps(donnees, facture):
        raise ValidationError(FACTURE_DE_DEVIS_REFUSE)


#: VNT13 (D-VNT-1, arbitrage 5) — annuler une facture / supprimer un
#: brouillon : palier responsable/admin ET un code d'écriture ``ventes_*``.
#: Jamais un Commercial (codes sans palier), ni un Technicien responsable ou
#: un Admin RH (palier sans code ventes). Remplace IsSuperuserOnly (AUD103) :
#: la garde destructive est désormais ``perform_destroy`` (brouillon seul).
PEUT_ANNULER = [IsAdminOrResponsableTier, IsResponsableOrAdmin]


class FactureCycleActionsMixin:
    """Actions de cycle de ``FactureViewSet`` (mixin, aucune base)."""

    @extend_schema(request=OpenApiTypes.OBJECT,
                   responses={200: FactureSerializer, 400: D.ErreurDetail,
                              409: D.ErreurDetail})
    # api-only: le geste « Modifier le montant » du panneau de vente
    # (peut.modifier_montant, VNT23) arrive avec les lanes frontend M2.
    @action(detail=True, methods=['post'], url_path='montant-tranche',
            permission_classes=[IsAdminOrResponsableTier,
                                IsResponsableOrAdmin])
    def montant_tranche(self, request, pk=None):
        """VNT67 — le TTC d'un BROUILLON de tranche (arbitrage 5 : palier
        responsable/admin ET code d'écriture) : ``facturation_vente.
        modifier_montant_tranche`` ; refus rendus tels quels (400 / 409)."""
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, modifier_montant_tranche)
        facture = self.get_object()
        try:
            facture = modifier_montant_tranche(
                facture, request.data.get('montant_ttc'), user=request.user)
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        facture.refresh_from_db()
        return Response(FactureSerializer(facture).data)

    @extend_schema(request=None,
                   responses={200: D.FactureEmise, 403: D.ErreurDetail})
    @action(detail=True, methods=['post'], url_path='emettre')
    def emettre(self, request, pk=None):
        facture = self.get_object()
        if facture.statut != Facture.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une facture brouillon peut être émise.'},
                status=status.HTTP_409_CONFLICT,
            )
        # AUD101 — l'émission (workflow de revue XFAC18, verrou de période,
        # blocage crédit XFAC28, dérivation d'échéance XFAC23, pose du statut
        # et émission de `facture_emise`) vit DANS le service unique. L'écran
        # ne fait plus que traduire ses refus en 400/403 français.
        from ..domain.facturation_ops import EmissionRefusee, emettre_facture
        from ..domain.recouvrement import CreditHoldError
        try:
            anomalies = emettre_facture(  # VNT32 : lignes OU libellé
                facture, user=request.user, source='ecran_facture',
                exiger_lignes=True)
        except EmissionRefusee as exc:
            vide = not (facture.lignes.exists() or facture.libelle)
            return Response({'detail': exc.motif}, status=(
                status.HTTP_409_CONFLICT if vide
                else status.HTTP_400_BAD_REQUEST))
        except CreditHoldError as exc:
            return Response({'detail': exc.motif},
                            status=status.HTTP_403_FORBIDDEN)
        data = FactureSerializer(facture).data
        if anomalies:
            data['anomalies'] = anomalies
        return Response(data)

    @extend_schema(request=None, responses=FactureSerializer)
    @action(detail=True, methods=['post'], url_path='remettre-brouillon',
            permission_classes=[IsResponsableOrAdmin])
    def remettre_brouillon(self, request, pk=None):
        """ZFAC1 — Reset to Draft.

        Repasse une facture ÉMISE en brouillon UNIQUEMENT si elle ne porte
        AUCUN argent (AFAC11 : paiements, avances ventilées, notes de débit
        émises, retenues subies, avoirs actifs — prédicat unique
        ``argent_rattache``) et que XFAC24 (immutabilité) n'est pas activée
        pour la société. Contrôlé SOUS VERROU de la facture (un paiement
        concurrent ne peut pas passer entre la garde et la bascule). Le lien
        de paiement actif est RÉVOQUÉ : le client ne peut plus payer une
        facture en cours d'édition. Le numéro/référence est CONSERVÉ (pas de
        renumérotation) — seul le statut change. (Aucun contrôle de période
        comptable n'est fait ici — YLEDG3 hors périmètre.)"""
        from django.db import transaction

        from ..domain.encaissements import (
            argent_rattache, decrire_argent_rattache, revoquer_lien_paiement,
        )
        facture = self.get_object()
        with transaction.atomic():
            facture = Facture.objects.select_for_update().get(pk=facture.pk)
            if facture.statut != Facture.Statut.EMISE:
                return Response(
                    {'detail': (
                        'Seule une facture émise (sans paiement ni avoir) peut '
                        'être remise en brouillon.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            if facture.paiements.exists():
                return Response(
                    {'detail': (
                        'Impossible : cette facture a déjà au moins un '
                        'paiement enregistré.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            if facture.avoirs.exclude(statut=Avoir.Statut.ANNULEE).exists():
                return Response(
                    {'detail': (
                        'Impossible : cette facture a un avoir actif.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            argent = decrire_argent_rattache(argent_rattache(facture))
            if argent:
                return Response(
                    {'detail': (
                        'Impossible de remettre en brouillon : de l\'argent '
                        f'est rattaché à cette facture ({argent}). Corrigez '
                        'par un avoir ou une note de débit.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            from apps.parametres.models import CompanyProfile
            profile = CompanyProfile.get(company=facture.company)
            if getattr(profile, 'factures_immuables', False):
                return Response(
                    {'detail': (
                        "Facture immuable : l'immutabilité (XFAC24) est activée "
                        "pour cette société — corrigez par un avoir puis une "
                        "nouvelle facture."
                    )},
                    status=status.HTTP_409_CONFLICT,
                )
            ancien = facture.statut
            facture.statut = Facture.Statut.BROUILLON
            facture.save(update_fields=['statut'])
            revoquer_lien_paiement(facture=facture, user=request.user)
        from .. import activity
        activity.log_facture_remise_brouillon(facture, request.user, ancien)
        return Response(FactureSerializer(facture).data)

    @extend_schema(request=D.MarquerPayeeRequest, responses=FactureSerializer)
    @action(detail=True, methods=['post'], url_path='marquer-payee',
            permission_classes=[IsAdminRole])
    def marquer_payee(self, request, pk=None):
        """Bascule MANUELLE en « payée » — resserrée par AUD124.

        Le geste reste légitime (constater un règlement enregistré hors ERP,
        solder un résiduel sous la tolérance société), mais il faisait
        DISPARAÎTRE une créance sans aucune contrepartie : le recouvrement
        filtre sur le STATUT (`ventes/recouvrement.py`
        ``.exclude(statut__in=['payee', …])``) et ``jours_retard`` retombe à 0
        dès que le statut vaut ``payee``, pendant que ``montant_du`` — dérivé
        des paiements — continue d'afficher la totalité. Une créance de
        40 000 MAD sortait de la balance âgée d'un clic, sans qu'aucun écran
        ne dise qui, quand ni pourquoi.

        Trois resserrages (le dépôt possédait déjà le geste correct :
        ``abandonner-solde``, qui exige un motif, passe l'écriture d'abandon
        et journalise) :
          * MOTIF obligatoire ;
          * un résiduel au-dessus de la tolérance société est REFUSÉ et
            redirigé vers ``abandonner-solde`` — c'est lui qui sait passer
            l'écriture d'abandon de créance ;
          * trace ``FactureActivity`` systématique nommant l'auteur et le
            motif, et permission dédiée (admin) distincte de l'édition
            courante (responsable), comme ``annuler``.
        """
        facture = self.get_object()
        if facture.statut not in [
            Facture.Statut.EMISE, Facture.Statut.EN_RETARD
        ]:
            return Response(
                {'detail': (
                    'Seule une facture émise ou en retard '
                    'peut être marquée payée.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        # AFAC9 — LA porte unique (acompte CAD122 avant J+7).
        from ..domain.encaissements import motif_non_encaissable
        motif_refus = motif_non_encaissable(facture)
        if motif_refus:
            return Response({'detail': motif_refus},
                            status=status.HTTP_409_CONFLICT)
        motif = valider_corps(request, D.MarquerPayeeRequest)['motif'].strip()
        # Résiduel réel vs tolérance société (XFAC13, défaut 0 = aucun
        # résiduel toléré). Au-dessus, ce n'est pas un « marquer payée » :
        # c'est un abandon de créance, qui a son propre geste et son écriture.
        from decimal import Decimal
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=facture.company)
        tolerance = getattr(
            profile, 'tolerance_ecart_reglement', None) or Decimal('0')
        reste = facture.montant_du
        if reste > tolerance:
            return Response(
                {'detail': (
                    f'Cette facture a un reste dû de {reste:.2f} MAD, '
                    f'au-dessus de la tolérance société '
                    f'({tolerance:.2f} MAD). Utilisez « abandonner-solde » '
                    f'pour l\'abandonner avec son écriture, ou enregistrez '
                    f'l\'encaissement.'
                ),
                 'action_attendue': 'abandonner-solde'},
                status=status.HTTP_409_CONFLICT,
            )
        # AUD102 (P1) — la bascule passe par LE service unique. ``force`` : un
        # passage MANUEL « marquer payée » est un geste responsable/admin
        # délibéré qui solde sans encaissement — l'un des deux seuls cas
        # autorisés à sauter la garde centime-près. Le montant informatif
        # porté par l'événement reste le TTC du document, comme avant.
        from ..domain.encaissements import marquer_facture_soldee
        marquer_facture_soldee(
            facture, montant=facture.total_ttc, user=request.user,
            source='marquer_payee_manuel', force=True)
        facture.refresh_from_db()
        # AUD124 — trace systématique : qui, quand, pourquoi.
        from .. import activity
        activity.log_facture_marquee_payee(facture, request.user, motif)
        return Response(FactureSerializer(facture).data)

    @extend_schema(request=D.FactureAnnulerRequest, responses=D.FactureAnnulee)
    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=PEUT_ANNULER)
    def annuler(self, request, pk=None):
        """Annule une facture — délégué mince (VNT10) : le corps vit dans
        ``domain/annulation_facture.annuler_facture`` (FG50, AFAC12, AFAC23,
        YEVNT6) ; un refus y lève ``AnnulationRefusee`` → 400, corps inchangé.
        ENF11 : corps validé par son sérialiseur déclaré (400, jamais 500) ;
        réponse = facture + ``avoir`` (contrat ``facture_annulation.json``).
        """
        from ..domain.annulation_facture import (
            AnnulationRefusee, annuler_facture, avoir_annulation_corps,
        )
        facture = self.get_object()
        try:
            facture = annuler_facture(
                facture, user=request.user, directive=valider_corps(
                    request, D.FactureAnnulerRequest).get('acompte'))
        except AnnulationRefusee as refus:
            return Response(refus.corps, status=status.HTTP_400_BAD_REQUEST)
        return Response({**FactureSerializer(facture).data,
                         'avoir': avoir_annulation_corps(facture)})
