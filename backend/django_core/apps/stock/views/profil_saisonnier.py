"""XSTK17 (AUDV04/DRAFT165-114) — CRUD des profils saisonniers de seuils.

``creer_profil_saisonnier``/``profil_saisonnier_actif``/``seuil_effectif_
produit`` existaient déjà côté ``services.py`` (consommés par les sélecteurs
de réappro FG54/FG65/FG326) mais aucun ViewSet/serializer/URL n'exposait la
CRÉATION/lecture d'un profil à un Acheteur — capacité inaccessible hors
tests. Ce module ferme ce trou, sans dupliquer la validation de chevauchement
calendaire (déjà posée par ``services.creer_profil_saisonnier``)."""
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import ProfilSaisonnier


class ProfilSaisonnierSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)

    class Meta:
        model = ProfilSaisonnier
        fields = [
            'id', 'produit', 'produit_nom', 'categorie', 'categorie_nom',
            'nom', 'mois_debut', 'mois_fin', 'seuil_min', 'seuil_max',
            'quantite_cible', 'actif', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class ProfilSaisonnierViewSet(CompanyScopedModelViewSet):
    """XSTK17 — profils saisonniers de seuils min/max/cible (produit XOR
    catégorie). Lecture tout rôle (un Acheteur doit voir la saison en
    vigueur), écriture responsable/admin. La création passe PAR
    ``services.creer_profil_saisonnier`` pour hériter du garde anti-
    chevauchement calendaire (jamais dupliqué ici)."""
    queryset = ProfilSaisonnier.objects.select_related(
        'produit', 'categorie', 'created_by').all()
    serializer_class = ProfilSaisonnierSerializer
    ordering = ['mois_debut']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        produit_id = params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        categorie_id = params.get('categorie')
        if categorie_id:
            qs = qs.filter(categorie_id=categorie_id)
        actif = params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from ..services import creer_profil_saisonnier
        data = serializer.validated_data
        try:
            profil = creer_profil_saisonnier(
                request.user.company,
                produit=data.get('produit'), categorie=data.get('categorie'),
                mois_debut=data['mois_debut'], mois_fin=data['mois_fin'],
                seuil_min=data.get('seuil_min'),
                seuil_max=data.get('seuil_max'),
                quantite_cible=data.get('quantite_cible'),
                nom=data.get('nom'), user=request.user,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(
            self.get_serializer(profil).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)
