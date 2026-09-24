"""CALX370 — ``POST /calepinages/import-projet/`` : réimporter un projet.

L'EXPORT N'EST PAS REDOUBLÉ. Le fichier réimporté est celui que sert
``GET /calepinages/<pk>/export-projet.json/`` (CALX312, ``views/documents.py``,
service ``services/export_projet.document_de_projet``) ; cette porte en est
l'inverse et vit dans le MÊME module de service
(``services/export_projet.importer_projet``) — aucun second module d'export.

CE QUE LA PORTE FAIT
--------------------
* corps : ``{projet: <le fichier>, lead: <id> | client: <id>, titre?,
  apercu?}`` — le rattachement désigne un lead OU un client de la société de
  l'APPELANT ; ceux du fichier appartiennent à la société de départ et ne
  sont jamais repris ;
* ``apercu: true`` valide TOUT le fichier et rend ce qui SERAIT écrit, sans
  rien écrire (l'écran le montre avant la confirmation explicite) ;
* sinon, un NOUVEAU calepinage est créé (201) par ``services/creation.py``,
  sa conception enregistrée par ``services/layout.py::enregistrer_layout``,
  ses postes de pertes et ses variantes par leurs services — jamais par un
  second chemin ;
* un refus est rendu 400 en NOMMANT le chemin du champ fautif
  (``format_version``, ``roof_layout.zones.0.vertices``,
  ``variantes[1].nom``…) — règle fondateur du 08/09/2026.

La société et l'auteur viennent TOUJOURS du serveur (``request.user``) :
aucun identifiant de société ni d'utilisateur n'est lu du fichier ni du corps.
Forme : ``contract_samples/calepinage_projet_json.json``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.export_projet import ImportProjetRefuse, importer_projet

__all__ = ['import_projet']


def _identifiant(brut):
    """Un identifiant entier, ou ``None`` — jamais une valeur devinée."""
    if brut in (None, '') or isinstance(brut, bool):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


#: La forme DÉCLARÉE de la réponse (jamais un « type: object » vide —
#: check_openapi_shapes, R1). Contrat : ``calepinage_projet_json.json``.
IMPORT_PROJET_SCHEMA = inline_serializer('CalepinageImportProjet', {
    'calepinage': serializers.IntegerField(allow_null=True),
    'titre': serializers.CharField(allow_blank=True),
    'format_version': serializers.IntegerField(),
    'ecrit': serializers.BooleanField(),
    'modules': serializers.IntegerField(allow_null=True),
    'postes_pertes': serializers.IntegerField(),
    'variantes': serializers.IntegerField(),
    'variante_retenue': serializers.CharField(allow_null=True),
    'repris': serializers.ListField(child=serializers.CharField()),
    'ignores': serializers.ListField(child=serializers.DictField()),
    'avertissements': serializers.ListField(child=serializers.CharField()),
})


@extend_schema(responses={200: IMPORT_PROJET_SCHEMA,
                          201: IMPORT_PROJET_SCHEMA})
@action(detail=False, methods=['post'], url_path='import-projet',
        permission_classes=[PeutGererCalepinage])
def import_projet(self, request):
    """CALX370 — réimporte le fichier de projet (nouveau calepinage)."""
    corps = request.data if isinstance(request.data, dict) else {}
    apercu = corps.get('apercu') is True or str(
        corps.get('apercu') or '').lower() in ('1', 'true', 'oui')
    try:
        resume = importer_projet(
            corps.get('projet'), getattr(request.user, 'company', None),
            user=request.user,
            lead_id=_identifiant(corps.get('lead')),
            client_id=_identifiant(corps.get('client')),
            titre=str(corps.get('titre') or ''),
            apercu=apercu)
    except ImportProjetRefuse as refus:
        return Response({refus.champ or 'projet': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(resume, status=(status.HTTP_200_OK if apercu
                                    else status.HTTP_201_CREATED))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.import_projet = import_projet
