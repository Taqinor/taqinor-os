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
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import (
    CAL_GERER, CAL_VOIR, PeutGererCalepinage, PeutLireOuEcrireCalepinage,
    exiger_droit_reglages_societe,
)
from ..serializers import corps_obligatoire
from ..serializers_conso import (
    ConsommationProposerCorpsSerializer, ProfilsTypesEcritureSerializer,
    ProfilsTypesSerializer,
)
from ..services.profils_types import (
    ProfilEnConflit, ProfilInvalide, enregistrer_profils, profil_depuis_import,
    profils_de_societe, valider_forme_profils,
)
from .calepinages import CalepinageViewSet

__all__ = ['ProfilsTypesView', 'lire_facture_consommation', 'proposer_consommation']


class ProfilsTypesView(APIView):
    """Les profils types de consommation de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    # Corps JSON SEUL : ``profils`` est une liste d'objets imbriqués, que ni un
    # formulaire multipart (parts texte) ni urlencoded ne portent.
    parser_classes = [JSONParser]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(responses={200: ProfilsTypesSerializer})
    def get(self, request, *args, **kwargs):
        profils = profils_de_societe(getattr(request.user, 'company', None))
        return Response({'profils': profils})

    @extend_schema(request=ProfilsTypesEcritureSerializer,
                   responses={200: ProfilsTypesSerializer})
    def put(self, request, *args, **kwargs):
        exiger_droit_reglages_societe(request.user)  # D-ACAL-104
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
            # La FORME d'abord, toute seule (400 nommant ``profils[<rang>].<champ>``) :
            # le prédicat que le schéma du ``PUT`` publie.
            valider_forme_profils(corps.get('profils'))
            profils = enregistrer_profils(
                company, corps.get('profils'), utilisateur=request.user)
        except ProfilInvalide as refus:
            # La FORME fautive (schéma publié) reste un 400 ; une clé en double
            # ou une journée entièrement nulle sont des faits que ce schéma ne
            # peut pas dire : 409.
            return Response({refus.champ or 'profils': [str(refus)]},
                            status=(status.HTTP_409_CONFLICT
                                    if isinstance(refus, ProfilEnConflit)
                                    else status.HTTP_400_BAD_REQUEST))
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
    # ACAL836 — servi seulement pour la saisie « factures.mois » : douze
    # lignes ``{mois, facture_mad, kwh, source}`` (``facture`` | ``estime``).
    'mois': serializers.ListField(child=serializers.DictField(),
                                  required=False),
})


@extend_schema(request=ConsommationProposerCorpsSerializer,
               responses={200: FORME_PROPOSITION})
@corps_obligatoire
@action(detail=True, methods=['post'], url_path='consommation/proposer',
        url_name='consommation-proposer',
        permission_classes=[PeutGererCalepinage],
        parser_classes=[JSONParser])  # sous-documents imbriqués : JSON seul
def proposer_consommation(self, request, pk=None):
    """ACAL310 — ``POST /calepinages/<pk>/consommation/proposer/``.

    La consommation PROPOSÉE par le serveur (D-ACAL-20) depuis le lead
    (factures + barème de la SOCIÉTÉ), des factures saisies, des appareils
    (et charges : climatisation, PAC, véhicule) ou un relevé CSV ; option
    Ramadan. LECTURE PURE : rien n'est écrit (la persistance passe par le
    document). 400 NOMMANT le champ pour la FORME du corps (source inconnue,
    sous-document du mauvais type ou absent) ; 409 pour le CONTENU que le
    service refuse (facture non finie, appareil hors contrat, CSV illisible,
    classe tarifaire non résolue) ; 409 pour un lead absent (le calepinage existe).
    """
    from ..services.charges import ChargeInvalide
    from ..services.consommation import (
        ImportCourbeInvalide, LeadIntrouvable,
        ProfilInvalide as ConsommationInvalide, proposer_consommation as
        proposer,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    champs = ConsommationProposerCorpsSerializer(data=request.data)
    champs.is_valid(raise_exception=True)
    corps = dict(champs.validated_data)
    try:
        rendu = proposer(calepinage, corps,
                         company=getattr(request.user, 'company', None))
    except LeadIntrouvable:
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_409_CONFLICT)
    except (ConsommationInvalide, ImportCourbeInvalide,
            ChargeInvalide) as refus:
        champ = getattr(refus, 'champ', '') or 'consommation'
        return Response({champ: str(refus)},
                        status=status.HTTP_409_CONFLICT)
    return Response(rendu)


#: ACAL839 — au plus 10 Mo par photo (la borne du dépôt de photos du module).
MAX_OCTETS_PHOTO_FACTURE = 10 * 1024 * 1024
REFUS_FICHIER = 'Déposez la photo de la facture dans le champ « fichier » (10 Mo au maximum).'


@extend_schema(methods=['GET'], responses={200: inline_serializer('CalepinageLireFactureDispo', {
    'disponible': serializers.BooleanField(), 'motif': serializers.CharField(allow_null=True),
    'lignes': serializers.ListField(child=serializers.DictField())})})
@extend_schema(methods=['POST'], request=inline_serializer('CalepinageLireFactureCorps', {
    'fichier': serializers.FileField()}), responses={200: inline_serializer('CalepinageLireFacture', {
        'disponible': serializers.BooleanField(), 'motif': serializers.CharField(allow_null=True),
        'lignes': serializers.ListField(child=serializers.DictField())})})
@action(detail=True, methods=['get', 'post'], url_path='consommation/lire-facture',
        url_name='consommation-lire-facture',
        permission_classes=[PeutLireOuEcrireCalepinage], parser_classes=[MultiPartParser])
def lire_facture_consommation(self, request, pk=None):
    """ACAL839 — ``GET``/``POST /calepinages/<pk>/consommation/lire-facture/``.

    ``GET`` dit si la lecture d'une photo de facture est disponible ; ``POST``
    (multipart ``fichier``) rend la PROPOSITION ``{disponible, motif, lignes:
    [{mois, kwh}]}`` — ``mois`` toujours ``null`` (la lecture ne rend jamais de
    mois : l'écran le fait choisir). LECTURE PURE : rien n'est écrit, la photo
    n'est pas stockée. OCR coupé : 200 et ``lignes`` vides, aucun appel réseau.
    Fichier absent ou trop gros : 400 ``{fichier}``.
    """
    from apps.crm import services as crm_services

    from .import_plan import _refus

    self.get_object()  # L'OBJET D'ABORD : borné société (autre société ⇒ 404)
    utilisateur = request.user
    if request.method == 'GET':
        return Response(crm_services.lire_photo_facture(utilisateur, None))
    fichier = request.FILES.get('fichier')
    if fichier is None or not fichier.size:
        return _refus('fichier', REFUS_FICHIER)
    if fichier.size > MAX_OCTETS_PHOTO_FACTURE:
        return _refus('fichier', REFUS_FICHIER)
    return Response(crm_services.lire_photo_facture(
        utilisateur, fichier.read(), nom=fichier.name or '',
        mime=getattr(fichier, 'content_type', '') or ''))


# Rattachement au viewset PIVOT (patron CALX2, ``views/rattachements.py``).
CalepinageViewSet.proposer_consommation = proposer_consommation
CalepinageViewSet.lire_facture_consommation = lire_facture_consommation
