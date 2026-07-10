"""Vues FG311 — RFQ multi-fournisseurs & comparatif d'offres.

``RFQViewSet`` : CRUD des demandes de prix + cycle de vie
(``envoyer`` / ``cloturer``) + action ``retenir`` qui sélectionne UNE offre
(les autres sont automatiquement dé-sélectionnées). ``RFQOffreViewSet`` : CRUD
des réponses fournisseur. Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` : référence/société/created_by posés côté
serveur ; les FK liées sont validées tenant. Cross-app : ``stock.Fournisseur``
en string-FK.
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import RFQ, RFQOffre, RFQConsultation
from ..serializers import (
    RFQSerializer, RFQOffreSerializer, RFQConsultationSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class RFQViewSet(CompanyScopedModelViewSet):
    """FG311 — RFQ. Lecture tout rôle, écriture responsable/admin. Référence
    anti-collision + société + `created_by` posés serveur ; `demande` validée
    tenant. Filtrable par `statut`, `demande`. Cycle de vie + `retenir`."""
    queryset = RFQ.objects.select_related(
        'demande', 'created_by').prefetch_related('offres').all()
    serializer_class = RFQSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        demande = params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        demande = serializer.validated_data.get('demande')
        if demande is not None and getattr(
                demande, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'demande': 'Demande inconnue pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(RFQ, 'RFQ', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def envoyer(self, request, pk=None):
        """FG311 — marque la RFQ comme envoyée (brouillon → envoyée)."""
        rfq = self.get_object()
        if rfq.statut not in (RFQ.Statut.BROUILLON, RFQ.Statut.ENVOYEE):
            return Response(
                {'detail': "Seule une RFQ brouillon peut être envoyée."},
                status=status.HTTP_400_BAD_REQUEST)
        rfq.statut = RFQ.Statut.ENVOYEE
        rfq.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(rfq).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """FG311 — clôt la RFQ (le choix est fait)."""
        rfq = self.get_object()
        rfq.statut = RFQ.Statut.CLOTUREE
        rfq.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(rfq).data)

    @action(detail=True, methods=['post'])
    def retenir(self, request, pk=None):
        """FG311/YPROC6 — retient UNE offre de la RFQ (les autres sont
        dé-sélectionnées). Quand l'offre porte un FOURNISSEUR CATALOGUE et
        qu'aucun BCF n'est encore lié à cette RFQ, adjuge aussi : crée le BCF
        brouillon chez le fournisseur gagnant, passe la DA liée `commandee`
        (si approuvée), mémorise le prix gagnant dans `PrixFournisseur`,
        clôture la RFQ. Une offre nom-libre (sans fournisseur catalogue) ne
        fait QUE basculer la sélection — comportement historique inchangé,
        aucune adjudication possible sans fournisseur catalogue. Corps :
        `offre` (id). L'offre doit appartenir à cette RFQ. Idempotent :
        ré-adjuger une RFQ déjà liée à un BCF → 400."""
        from apps.stock.services import (
            creer_bcf_depuis_lignes, record_purchase_price,
        )

        rfq = self.get_object()
        company = request.user.company
        offre_id = request.data.get('offre')
        if not offre_id:
            return Response(
                {'offre': 'Paramètre `offre` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        offre = rfq.offres.filter(id=offre_id).first()
        if offre is None:
            return Response(
                {'offre': "Cette offre n'appartient pas à la RFQ."},
                status=status.HTTP_400_BAD_REQUEST)

        rfq.offres.exclude(id=offre.id).update(retenue=False)
        offre.retenue = True
        offre.save(update_fields=['retenue', 'date_modification'])

        # Adjudication (YPROC6) : seulement pour une offre à fournisseur
        # catalogue, et seulement si cette RFQ n'a pas déjà un BCF lié
        # (idempotence — re-basculer la sélection reste possible sans jamais
        # recréer de second BCF).
        if offre.fournisseur_id is not None and not rfq.bon_commande_id:
            demande = rfq.demande
            if demande is not None:
                lignes = [
                    (ligne.produit_id,
                     ligne.designation or
                     (ligne.produit.nom if ligne.produit_id else ''),
                     ligne.quantite, ligne.prix_estime)
                    for ligne in demande.lignes.select_related(
                        'produit').all()
                ]
            else:
                lignes = []
            if not lignes:
                lignes = [(None, rfq.objet or f'RFQ {rfq.reference}', 1,
                          offre.montant_ht)]

            bon = creer_bcf_depuis_lignes(
                company=company, user=request.user,
                fournisseur=offre.fournisseur, lignes=lignes,
                note=f'Adjugé depuis {rfq.reference}')
            rfq.bon_commande = bon
            rfq.statut = RFQ.Statut.CLOTUREE
            rfq.save(update_fields=[
                'bon_commande', 'statut', 'date_modification'])

            if (demande is not None
                    and demande.statut == demande.Statut.APPROUVEE):
                demande.bon_commande = demande.bon_commande or bon
                demande.statut = demande.Statut.COMMANDEE
                demande.save(update_fields=[
                    'bon_commande', 'statut', 'date_modification'])

            # Mémorise le prix unitaire gagnant (INTERNE) pour les lignes à
            # produit catalogue — alimente le comparatif fournisseurs.
            from django.utils import timezone as _tz
            for produit_id, _designation, _qte, prix in lignes:
                if produit_id:
                    from apps.stock.models import Produit as _Produit
                    produit = _Produit.objects.filter(
                        id=produit_id, company=company).first()
                    if produit is not None:
                        record_purchase_price(
                            company=company, produit=produit,
                            fournisseur=offre.fournisseur, prix_achat=prix,
                            date=_tz.now().date())

        return Response(self.get_serializer(rfq).data)

    @action(detail=True, methods=['post'], url_path='consulter')
    def consulter(self, request, pk=None):
        """XPUR20 — ajoute un fournisseur consulté (crée sa consultation +
        jeton public, idempotent : ré-appeler pour un fournisseur déjà
        consulté renvoie sa consultation existante). Corps : `fournisseur`
        (id, doit appartenir à la société)."""
        rfq = self.get_object()
        company = request.user.company
        fournisseur_id = request.data.get('fournisseur')
        if not fournisseur_id:
            return Response(
                {'fournisseur': 'Paramètre `fournisseur` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from apps.stock.models import Fournisseur
        fournisseur = Fournisseur.objects.filter(
            id=fournisseur_id, company=company).first()
        if fournisseur is None:
            return Response(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        consultation, _ = RFQConsultation.objects.get_or_create(
            rfq=rfq, fournisseur=fournisseur, defaults={'company': company})
        return Response(
            RFQConsultationSerializer(consultation).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='envoyer-consultations')
    def envoyer_consultations(self, request, pk=None):
        """XPUR20 — envoie la RFQ (PDF, aucun prix interne) par email ET
        WhatsApp à chaque fournisseur consulté n'ayant pas de bouton grisé.
        Corps optionnel : `consultations` (liste d'ids) — sinon TOUTES les
        consultations non révoquées de la RFQ. WhatsApp reste manuel-first :
        on ouvre un brouillon wa.me (le commercial appuie lui-même sur
        Envoyer) — on trace seulement que le lien a été généré."""
        from .. import rfq_service
        rfq = self.get_object()
        ids = request.data.get('consultations')
        qs = rfq.consultations.filter(revoque=False).select_related(
            'fournisseur')
        if ids:
            qs = qs.filter(id__in=ids)
        results = []
        for consultation in qs:
            results.append(
                rfq_service.envoyer_consultation(consultation, request))
        return Response({'resultats': results})

    @action(detail=True, methods=['post'], url_path='relancer-non-repondants')
    def relancer_non_repondants(self, request, pk=None):
        """XPUR20 — relance UNIQUEMENT les fournisseurs consultés n'ayant pas
        encore répondu (aucune offre liée), avant `date_limite_reponse`."""
        from .. import rfq_service
        rfq = self.get_object()
        qs = rfq.consultations.filter(
            revoque=False, offre__isnull=True).select_related('fournisseur')
        results = []
        for consultation in qs:
            res = rfq_service.envoyer_consultation(consultation, request)
            consultation.nb_relances += 1
            consultation.derniere_relance_le = timezone.now()
            consultation.save(
                update_fields=['nb_relances', 'derniere_relance_le'])
            results.append(res)
        return Response({'resultats': results})


class RFQConsultationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XPUR20/21 — lecture des consultations (fournisseurs invités) d'une
    RFQ, avec statut d'envoi/réponse par destinataire. Écriture via les
    actions dédiées de `RFQViewSet` (`consulter`, `envoyer-consultations`,
    `relancer-non-repondants`)."""
    queryset = RFQConsultation.objects.select_related(
        'rfq', 'fournisseur', 'offre').all()
    serializer_class = RFQConsultationSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset()
        rfq = self.request.query_params.get('rfq')
        if rfq:
            qs = qs.filter(rfq_id=rfq)
        return qs


class RFQOffreViewSet(CompanyScopedModelViewSet):
    """FG311 — réponses fournisseur à une RFQ. La RFQ parente est validée tenant.
    Filtrable par `rfq`. Lecture tout rôle, écriture responsable/admin."""
    queryset = RFQOffre.objects.select_related('rfq', 'fournisseur').all()
    serializer_class = RFQOffreSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        rfq = self.request.query_params.get('rfq')
        if rfq:
            qs = qs.filter(rfq_id=rfq)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        rfq = serializer.validated_data.get('rfq')
        if rfq is not None and getattr(rfq, 'company_id', None) != cid:
            raise ValidationError({'rfq': 'RFQ inconnue pour cette société.'})
        fournisseur = serializer.validated_data.get('fournisseur')
        if fournisseur is not None and getattr(
                fournisseur, 'company_id', None) != cid:
            raise ValidationError(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)
