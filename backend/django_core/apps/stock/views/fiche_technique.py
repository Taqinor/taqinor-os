from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from ..importers.fiche_pan_ond import FichierIllisible, champs_a_ecrire, parse_pan_ond_bytes
from ..models import FicheTechnique, Produit
from ..serializers import FicheTechniqueSerializer
from authentication.permissions import (
    IsAnyRole,
    IsAdminRole,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class FicheTechniqueViewSet(CompanyScopedModelViewSet):
    """DC35 / FG254 — fiches techniques (datasheets) rattachées aux produits.

    Multi-tenant : le queryset est filtré sur la société du demandeur
    (``TenantMixin``) et ``company`` est forcé serveur dans ``perform_create``
    — jamais accepté depuis le corps de la requête. Lecture tout rôle, écriture
    selon la permission stock, suppression admin."""
    queryset = FicheTechnique.objects.select_related('produit').all()
    serializer_class = FicheTechniqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-date_mise_a_jour']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['date_creation', 'date_mise_a_jour', 'pmax_wc']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    @action(detail=False, methods=['post'], url_path='importer-datasheet')
    def importer_datasheet(self, request):
        """CAL117 — import OPTIONNEL d'une fiche constructeur .PAN/.OND.

        Sans ``confirmer=true`` (ou par défaut) : APERÇU seul, aucune
        écriture — rend le mapping proposé, les clés reconnues/non reconnues
        et celles déjà saisies (donc qui seraient IGNORÉES à la
        confirmation). Avec ``confirmer=true`` : écrit UNIQUEMENT les champs
        encore vides de la fiche (crée la fiche si le produit n'en a pas
        encore) — un champ déjà saisi n'est JAMAIS écrasé."""
        upload = request.FILES.get('file')
        produit_id = request.data.get('produit')
        if upload is None or not produit_id:
            return Response(
                {'detail': 'produit et file sont requis.',
                 'champ': 'file' if upload is None else 'produit'},
                status=status.HTTP_400_BAD_REQUEST)
        produit = Produit.objects.filter(
            pk=produit_id, company=request.user.company).first()
        if produit is None:
            return Response(
                {'detail': 'Produit introuvable.', 'champ': 'produit'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            proposition = parse_pan_ond_bytes(
                upload.read(), filename=getattr(upload, 'name', '') or '')
        except FichierIllisible as exc:
            return Response(
                {'detail': str(exc), 'champ': exc.champ},
                status=status.HTTP_400_BAD_REQUEST)

        fiche = getattr(produit, 'fiche_technique', None)
        if fiche is not None:
            a_ecrire, deja_saisis = champs_a_ecrire(fiche, proposition.mapping)
        else:
            a_ecrire, deja_saisis = dict(proposition.mapping), []

        confirmer = str(request.data.get('confirmer', '')).lower() in (
            '1', 'true', 'on', 'oui')
        if not confirmer:
            return Response({
                'type_fiche': proposition.type_fiche,
                'mapping': {k: str(v) for k, v in a_ecrire.items()},
                'reconnus': proposition.reconnus,
                'non_reconnus': proposition.non_reconnus,
                'deja_saisis': deja_saisis,
                'confirme': False,
            })

        if fiche is None:
            fiche = FicheTechnique(
                company=request.user.company, produit=produit,
                type_fiche=proposition.type_fiche)
        for champ_nom, valeur in a_ecrire.items():
            setattr(fiche, champ_nom, valeur)
        fiche.save()
        return Response({
            'type_fiche': proposition.type_fiche,
            'ecrits': sorted(a_ecrire.keys()),
            'deja_saisis': deja_saisis,
            'non_reconnus': proposition.non_reconnus,
            'confirme': True,
            'fiche': FicheTechniqueSerializer(fiche).data,
        })
