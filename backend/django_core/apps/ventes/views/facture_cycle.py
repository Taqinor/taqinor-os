"""VNT97 — cycle de la facture (émettre, remettre en brouillon, marquer
payée, annuler, montant de tranche) : actions de ``FactureViewSet`` portées par
``FactureCycleActionsMixin``, déplacées telles quelles depuis
``views/facture.py`` (et ``views/facture_montant_tranche.py``, VNT67). Aucune
route dans ``urls.py`` : le routeur les découvre sur le viewset.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsResponsableOrAdmin,
)
from . import openapi_docs as D
from ..models import Avoir, Facture
from ..serializers_facturation import FactureListeSerializer, FactureSerializer
from ..utils.corps import valider_corps

#: VNT13 (D-VNT-1, arbitrage 5) — annuler une facture / supprimer un
#: brouillon : palier responsable/admin ET un code d'écriture ``ventes_*``.
#: Jamais un Commercial (codes sans palier), ni un Technicien responsable ou
#: un Admin RH (palier sans code ventes). Remplace IsSuperuserOnly (AUD103) :
#: la garde destructive est désormais ``perform_destroy`` (brouillon seul).
PEUT_ANNULER = [IsAdminOrResponsableTier, IsResponsableOrAdmin]


class FactureCycleActionsMixin:
    """Le cycle de vie d'une facture : émission, retour en brouillon,
    solde manuel, annulation et TTC d'un brouillon de tranche."""

    @extend_schema(request=None,
                   responses={200: D.FactureEmise, 403: D.ErreurDetail})
    # Garde explicite = celle du tiering de ``FactureViewSet.get_permissions``
    # ('emettre' → IsResponsableOrAdmin), inchangée depuis le déplacement VNT97.
    @action(detail=True, methods=['post'], url_path='emettre',
            permission_classes=[IsResponsableOrAdmin])
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

    @extend_schema(request=None, responses=FactureListeSerializer)
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

    @extend_schema(request=D.MarquerPayeeRequest, responses=FactureListeSerializer)
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

    @extend_schema(request=D.FactureAnnulerRequest, responses=D.FactureAnnulee,
                   extensions=D.CORPS_ANNULER_CIBLE_SI_TRANSFERT)
    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=PEUT_ANNULER)
    def annuler(self, request, pk=None):
        """Annule une facture — délégué mince (VNT10) : le corps vit dans
        ``domain/annulation_facture.annuler_facture`` (FG50, AFAC12, AFAC23,
        YEVNT6) ; un refus y lève ``AnnulationRefusee`` → 409, corps inchangé.
        ENF11 : corps validé par son sérialiseur déclaré (400, jamais 500) ;
        réponse = facture + ``avoir`` (contrat ``facture_annulation.json``).
        """
        from ..domain.annulation_facture import (
            AnnulationRefusee, annuler_facture, avoir_annulation_corps,
        )
        facture = self.get_object()
        directive = valider_corps(request, D.FactureAnnulerRequest).get(
            'acompte')
        # ENF11 — la seule règle d'ENTRÉE d'une directive que le sérialiseur
        # ne porte pas (publiée en ``anyOf``) : « transferer » exige sa cible.
        if directive and directive.get('action') == 'transferer' and not (
                directive.get('facture_cible')):
            return Response({'detail': 'La facture cible est requise.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            facture = annuler_facture(
                facture, user=request.user, directive=directive)
        except AnnulationRefusee as refus:
            # ENF11 — le corps est valide : le refus vient de l'ÉTAT (payée,
            # déjà annulée, note de débit / avoir actif, argent rattaché sans
            # directive, cible d'un autre devis ou soldée, rien à rendre)
            # → 409, corps inchangé (``code`` lu par l'écran).
            return Response(refus.corps, status=status.HTTP_409_CONFLICT)
        return Response({**FactureSerializer(facture).data,
                         'avoir': avoir_annulation_corps(facture)})

    # api-only: l'écran arrive avec le panneau de vente (VNT75/VNT79).
    @extend_schema(
        request=inline_serializer('FactureMontantTranche', {
            'montant_ttc': serializers.CharField()}),
        responses={200: FactureListeSerializer, 400: D.ErreurDevisFige,
                   409: D.ErreurDevisFige})
    @action(detail=True, methods=['post'], url_path='montant-tranche',
            permission_classes=[IsAdminOrResponsableTier,
                                IsResponsableOrAdmin])
    def montant_tranche(self, request, pk=None):
        """VNT67 — le TTC d'un brouillon de tranche : HT / TVA / ventilation
        au prorata du plan, échéancier réécrit ; 409 sur une émise."""
        from ..domain.facturation_vente import (
            FacturationVenteRefusee, modifier_montant_tranche)
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            facture = modifier_montant_tranche(
                self.get_object(), corps.get('montant_ttc'),
                user=request.user)
        except FacturationVenteRefusee as exc:
            return Response(exc.corps, status=exc.status)
        return Response(FactureSerializer(facture).data)
