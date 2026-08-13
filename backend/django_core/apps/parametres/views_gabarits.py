"""NTEXT19 — API des gabarits de document custom + rendu PDF.

``GET parametres/gabarits-document/`` liste les gabarits de la société et
``GET parametres/gabarits-document/<code>/rendre/?cible_id=<id>`` STREAME le
PDF d'un objet réel :

  1. l'objet cible est résolu par le ``selectors.py`` de l'app propriétaire
     (``gabarits_contexte``) — jamais un import de modèle cross-app ;
  2. le contexte est une LISTE BLANCHE de placeholders (jamais de prix d'achat
     ni de marge) ;
  3. le corps est substitué par ``core.templating`` (littéral, valeurs
     échappées) puis rendu par le moteur PDF mutualisé du noyau.

Un placeholder inconnu du contexte reste LITTÉRAL (``core.templating`` en mode
non strict) : un gabarit mal orthographié n'a jamais fait planter un rendu.

⚠ RÈGLE #4 — la cible « devis » est refusée par le modèle lui-même : aucun
devis client ne sort d'ici, il passe uniquement par ``/proposal``.
"""
from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from .gabarits import rendre_pdf, variables_du_gabarit
from .gabarits_contexte import construire_contexte
from .models import GabaritDocumentCustom


class GabaritDocumentCustomSerializer(serializers.ModelSerializer):
    cible_label = serializers.CharField(
        source='get_cible_display', read_only=True)
    variables = serializers.SerializerMethodField()

    class Meta:
        model = GabaritDocumentCustom
        fields = ['id', 'code', 'nom', 'cible', 'cible_label', 'corps',
                  'actif', 'variables']
        read_only_fields = ['id', 'cible_label', 'variables']

    def get_variables(self, obj):
        return variables_du_gabarit(obj)


class GabaritDocumentCustomViewSet(CompanyScopedModelViewSet):
    """Lecture des gabarits + action de rendu, bornées à la société.

    Volontairement LECTURE SEULE côté API (``http_method_names`` limité aux
    méthodes de lecture) : l'édition d'un gabarit reste un geste
    d'administration, le besoin livré ici est le RENDU. ``code`` sert de clé
    d'URL (identifiant stable par société).
    """

    http_method_names = ['get', 'head', 'options']
    serializer_class = GabaritDocumentCustomSerializer
    queryset = GabaritDocumentCustom.objects.all()
    lookup_field = 'code'
    lookup_value_regex = '[-a-zA-Z0-9_]+'
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            qs = qs.filter(actif=True)
        return qs

    @action(detail=True, methods=['get'], url_path='rendre')
    def rendre(self, request, code=None):
        """Rend le gabarit pour ``?cible_id=<id>`` et streame le PDF."""
        gabarit = self.get_object()
        cible_id = (request.query_params.get('cible_id') or '').strip()
        if not cible_id:
            return Response(
                {'detail': 'Le paramètre « cible_id » est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        contexte = construire_contexte(
            gabarit.cible, request.user.company, cible_id)
        if contexte is None:
            return Response(
                {'detail': f'Aucun {gabarit.get_cible_display().lower()} '
                           f'« {cible_id} » dans cette société.'},
                status=status.HTTP_404_NOT_FOUND)

        try:
            pdf = rendre_pdf(gabarit, contexte)
        except Exception:
            return Response(
                {'detail': 'Rendu PDF indisponible sur ce serveur.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)

        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = (
            f'inline; filename="{gabarit.code}-{cible_id}.pdf"')
        return reponse
