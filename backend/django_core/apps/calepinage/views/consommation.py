"""CAL149 — la porte des PROFILS TYPES de consommation de la société.

FORME D'URL (CAL233) : ``/api/django/calepinage/parametres/profils-types/``.
Ce n'est pas une seconde famille d'URL pour l'objet métier — aucun
identifiant de calepinage n'y entre : c'est un RÉGLAGE société, servi sous le
préfixe ``parametres`` comme la suggestion de pente (CAL237).

* ``GET`` — les profils SAISIS par la société, puis les profils de repli
  ÉTIQUETÉS « hypothèse interne » (jamais présentés comme des mesures).
* ``PUT`` — remplace les profils saisis. La société vient TOUJOURS de
  ``request.user``, jamais d'un corps de requête ; un refus est rendu 400 en
  NOMMANT le champ fautif (règle fondateur du 08/09/2026).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR, PeutGererCalepinage
from ..serializers_conso import (
    ProfilsTypesEcritureSerializer, ProfilsTypesSerializer,
)
from ..services.profils_types import (
    ProfilInvalide, enregistrer_profils, profil_depuis_import,
    profils_de_societe,
)
from .calepinages import CalepinageViewSet

__all__ = ['ProfilsTypesView', 'proposer_consommation']


class ProfilsTypesView(APIView):
    """Les profils types de consommation de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(responses={200: ProfilsTypesSerializer})
    def get(self, request, *args, **kwargs):
        profils = profils_de_societe(getattr(request.user, 'company', None))
        return Response({'profils': profils})

    @extend_schema(request=ProfilsTypesEcritureSerializer,
                   responses={200: ProfilsTypesSerializer})
    def put(self, request, *args, **kwargs):
        corps = request.data if isinstance(request.data, dict) else {}
        company = getattr(request.user, 'company', None)
        import_ = corps.get('depuis_import')
        if isinstance(import_, dict):
            # ACAL310 — un aperçu CSV CONFIRMÉ devient un profil SOCIÉTÉ
            # (``profils_types.profil_depuis_import``), avec sa provenance.
            try:
                profil_depuis_import(
                    company, import_.get('apercu') or {},
                    cle=import_.get('cle'), libelle=import_.get('libelle'),
                    famille=import_.get('famille'),
                    origine=import_.get('origine'))
            except ProfilInvalide as refus:
                return Response(
                    {'depuis_import.' + (refus.champ or 'apercu'):
                     [str(refus)]}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'profils': profils_de_societe(company)})
        try:
            profils = enregistrer_profils(
                company, corps.get('profils'), utilisateur=request.user)
        except ProfilInvalide as refus:
            return Response({refus.champ or 'profils': [str(refus)]},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'profils': profils})


#: ACAL310 — la forme DÉCLARÉE de la consommation proposée (contrat
#: ``calepinage_consommation_proposee.json``).
FORME_PROPOSITION = inline_serializer('CalepinageConsommationProposee', {
    'consumption': serializers.DictField(allow_null=True),
    'kwh_annuel': serializers.FloatField(allow_null=True),
    'courbe24': serializers.ListField(child=serializers.FloatField(),
                                      allow_null=True),
    'saisons': serializers.DictField(),
    'avertissements': serializers.ListField(child=serializers.CharField()),
})


@extend_schema(request=None, responses={200: FORME_PROPOSITION})
@action(detail=True, methods=['post'], url_path='consommation/proposer',
        url_name='consommation-proposer',
        permission_classes=[PeutGererCalepinage])
def proposer_consommation(self, request, pk=None):
    """ACAL310 — ``POST /calepinages/<pk>/consommation/proposer/``.

    La consommation PROPOSÉE par le serveur (D-ACAL-20) depuis le lead
    (factures + barème de la SOCIÉTÉ), des factures saisies, des appareils
    (et charges : climatisation, PAC, véhicule) ou un relevé CSV ; option
    Ramadan. LECTURE PURE : rien n'est écrit (la persistance passe par le
    document). 400 NOMMANT le champ ; 404 pour un lead absent.
    """
    from ..services.charges import ChargeInvalide
    from ..services.consommation import (
        ImportCourbeInvalide, LeadIntrouvable,
        ProfilInvalide as ConsommationInvalide, proposer_consommation as
        proposer,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    corps = request.data if isinstance(request.data, dict) else {}
    try:
        rendu = proposer(calepinage, corps,
                         company=getattr(request.user, 'company', None))
    except LeadIntrouvable:
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    except (ConsommationInvalide, ImportCourbeInvalide,
            ChargeInvalide) as refus:
        champ = getattr(refus, 'champ', '') or 'consommation'
        return Response({champ: str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(rendu)


# Rattachement au viewset PIVOT (patron CALX2, ``views/rattachements.py``).
CalepinageViewSet.proposer_consommation = proposer_consommation
