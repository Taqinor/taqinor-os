"""Viewsets DRF du module ``apps.education``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête).
"""
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import AnneeScolaire, Classe, Eleve, Famille, Inscription, Niveau
from .serializers import (
    AnneeScolaireSerializer, ClasseSerializer, EleveSerializer,
    FamilleSerializer, InscriptionSerializer, NiveauSerializer)


class AnneeScolaireViewSet(CompanyScopedModelViewSet):
    queryset = AnneeScolaire.objects.all()
    serializer_class = AnneeScolaireSerializer


class NiveauViewSet(CompanyScopedModelViewSet):
    queryset = Niveau.objects.all()
    serializer_class = NiveauSerializer


class ClasseViewSet(CompanyScopedModelViewSet):
    """NTEDU1 — une classe affiche son effectif courant vs ``capacite_max``
    (propriété calculée ``Classe.effectif``, jamais un champ dénormalisé)."""

    queryset = Classe.objects.select_related('annee_scolaire', 'niveau').all()
    serializer_class = ClasseSerializer


class FamilleViewSet(CompanyScopedModelViewSet):
    queryset = Famille.objects.all()
    serializer_class = FamilleSerializer


class EleveViewSet(CompanyScopedModelViewSet):
    """NTEDU2 — ``numero_dossier`` attribué côté serveur à la création
    (anti-collision, jamais un ``count()+1``). Les élèves radiés sont exclus
    des listes actives par défaut (``?actifs=1``) mais restent consultables
    en historique (aucune exclusion par défaut du queryset de base)."""

    queryset = Eleve.objects.select_related('famille', 'classe').all()
    serializer_class = EleveSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('actifs') == '1':
            qs = qs.exclude(
                statut__in=[Eleve.Statut.RADIE, Eleve.Statut.DIPLOME])
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        from .services import attribuer_numero_dossier
        attribuer_numero_dossier(serializer.instance)


class InscriptionViewSet(CompanyScopedModelViewSet):
    """NTEDU3 — workflow d'inscription (validation/affectation/liste
    d'attente). Les actions ``valider``/``refuser``/``affecter_classe``
    passent TOUJOURS par ``services.py`` (jamais une mutation directe de
    statut dans le viewset)."""

    queryset = Inscription.objects.select_related(
        'eleve', 'annee_scolaire', 'classe_demandee', 'classe_affectee').all()
    serializer_class = InscriptionSerializer

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        from .services import valider_inscription
        inscription = valider_inscription(self.get_object(), user=request.user)
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        from .services import refuser_inscription
        inscription = refuser_inscription(self.get_object(), user=request.user)
        return Response(InscriptionSerializer(inscription).data)

    @action(detail=True, methods=['post'], url_path='affecter-classe')
    def affecter_classe_action(self, request, pk=None):
        from .services import affecter_classe

        classe_id = request.data.get('classe')
        classe = Classe.objects.filter(
            company=request.user.company, pk=classe_id).first()
        if classe is None:
            raise ValidationError({'classe': 'Classe introuvable.'})
        inscription = affecter_classe(
            self.get_object(), classe, user=request.user)
        return Response(InscriptionSerializer(inscription).data)
