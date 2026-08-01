"""AOF157 — endpoints de l'ÉCONOMIE d'un appel d'offres (DIRECTEUR SEUL).

Module SÉPARÉ des vues AO générales, et gardé par ``CanViewAoRentabilite``
(permission ``ao_rentabilite_voir``, ÉLEVÉE : non octroyable par un
non-administrateur, mappée sur AUCUN rôle Responsable/Commercial/Technicien/
Utilisateur — seuls Directeur et Administrateur la portent par héritage
d'``ALL_PERMISSIONS``).

Le socle reste ``CompanyScopedModelViewSet`` (scoping société + ``company``
posée côté serveur) : la garde de rentabilité s'AJOUTE, elle ne remplace pas
l'isolation multi-tenant.

Le VERROU de l'économie est respecté ici : une économie verrouillée n'accepte
plus d'écriture — une cascade de prix déjà propagée ne se laisse pas modifier
sous les pièces qui la citent.
"""
from __future__ import annotations

from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import CibleFinanciere, EconomieAO, LigneCoutRevient
from .permissions import CanViewAoRentabilite
from .serializers_directeur import (
    CibleFinanciereSerializer, EconomieAOSerializer,
    LigneCoutRevientSerializer,
)

__all__ = [
    'CibleFinanciereViewSet',
    'EconomieAOViewSet',
    'LigneCoutRevientViewSet',
]


class _BaseDirecteurViewSet(CompanyScopedModelViewSet):
    """Base des vues d'économie : société scopée + ``ao_rentabilite_voir``."""

    permission_classes = [CanViewAoRentabilite]

    def get_permissions(self):
        return [CanViewAoRentabilite()]

    @staticmethod
    def _refuser_si_verrouillee(economie):
        if economie is not None and economie.verrouillee:
            raise PermissionDenied(
                "L'économie de cet appel d'offres est VERROUILLÉE : une "
                'cascade de prix déjà propagée ne se modifie pas sous les '
                'pièces qui la citent.')


class EconomieAOViewSet(_BaseDirecteurViewSet):
    """Économie d'un AO — coût de revient, TVA, marge (directeur seul)."""

    queryset = EconomieAO.objects.prefetch_related('lignes', 'cibles').all()
    serializer_class = EconomieAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['appel_offre']

    def get_queryset(self):
        qs = super().get_queryset()
        appel_offre = self.request.query_params.get('appel_offre')
        if appel_offre not in (None, ''):
            qs = qs.filter(appel_offre=appel_offre)
        return qs

    def perform_update(self, serializer):
        self._refuser_si_verrouillee(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._refuser_si_verrouillee(instance)
        super().perform_destroy(instance)

    @action(detail=True, methods=['get'])
    def synthese(self, request, pk=None):
        """La chaîne complète, en une lecture — tout est DÉRIVÉ."""
        economie = self.get_object()
        return Response({
            'cout_revient_ht': str(economie.cout_revient_ht),
            'cout_regime_reduit_ht': str(economie.cout_regime_reduit_ht),
            'cout_regime_standard_ht': str(economie.cout_regime_standard_ht),
            'tva_deductible': str(economie.tva_deductible),
            'benefice_net_cible_ht': str(economie.benefice_net_cible_ht),
            'total_ht': str(economie.total_ht),
            'tva_collectee': str(economie.tva_collectee),
            'total_ttc': str(economie.total_ttc),
            'tva_nette_a_reverser': str(economie.tva_nette_a_reverser),
            'marge_pct': str(economie.marge_pct),
            'controle_tresorerie': str(economie.controle_tresorerie),
            'ecart_tresorerie': str(economie.ecart_tresorerie),
            'sous_seuil_psychologique': economie.sous_seuil_psychologique,
        })

    @action(detail=True, methods=['post'])
    def verrouiller(self, request, pk=None):
        economie = self.get_object()
        economie.verrouillee = True
        economie.save(update_fields=['verrouillee', 'updated_at'])
        return Response({'verrouillee': True})

    @action(detail=True, methods=['post'])
    def deverrouiller(self, request, pk=None):
        economie = self.get_object()
        economie.verrouillee = False
        economie.save(update_fields=['verrouillee', 'updated_at'])
        return Response({'verrouillee': False})


class LigneCoutRevientViewSet(_BaseDirecteurViewSet):
    """Postes du coût de revient (directeur seul)."""

    queryset = LigneCoutRevient.objects.all()
    serializer_class = LigneCoutRevientSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'poste']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('economie', 'poste', 'regime_tva'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        self._refuser_si_verrouillee(
            serializer.validated_data.get('economie'))
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._refuser_si_verrouillee(serializer.instance.economie)
        super().perform_update(serializer)


class CibleFinanciereViewSet(_BaseDirecteurViewSet):
    """Cibles de bénéfice VERSIONNÉES (directeur seul).

    Une nouvelle cible incrémente la version, désactive la précédente et
    TRACE son auteur côté serveur : un mouvement de prix se justifie.
    """

    queryset = CibleFinanciere.objects.all()
    serializer_class = CibleFinanciereSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version']

    def get_queryset(self):
        qs = super().get_queryset()
        economie = self.request.query_params.get('economie')
        if economie not in (None, ''):
            qs = qs.filter(economie=economie)
        return qs

    def create(self, request, *args, **kwargs):
        from . import services_directeur

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        economie = serializer.validated_data['economie']
        if economie.company_id != request.user.company_id:
            raise PermissionDenied("Économie hors de votre société.")
        self._refuser_si_verrouillee(economie)
        cible = services_directeur.nouvelle_cible(
            economie,
            benefice_net_cible_ht=serializer.validated_data[
                'benefice_net_cible_ht'],
            motif=serializer.validated_data.get('motif', ''),
            arrondi_psychologique=serializer.validated_data.get(
                'arrondi_psychologique'),
            seuil_psychologique=serializer.validated_data.get(
                'seuil_psychologique'),
            ligne_ajustement=serializer.validated_data.get(
                'ligne_ajustement'),
            user=request.user)
        return Response(self.get_serializer(cible).data,
                        status=status.HTTP_201_CREATED)
