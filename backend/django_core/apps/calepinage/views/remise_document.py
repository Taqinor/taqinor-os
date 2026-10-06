"""ACAL222 — la REMISE EXPLICITE d'un document du calepinage.

LE CONSTAT (C-ACAL-121)
-----------------------
``GET rapport-etude.pdf`` écrivait une version (et un objet MinIO) à CHAQUE
lecture : trois clics, trois versions ; les douze autres pièces n'étaient
jamais versionnées. Un téléchargement n'est pas une remise.

LA RÈGLE
--------
``POST calepinages/<pk>/remettre-document/`` ``{code, langue}`` :

* rend la pièce par le MÊME handler que son ``GET`` (mêmes gardes « aucun
  montant », mêmes refus 400 nommés, relayés tels quels) — jamais une
  seconde fabrique ;
* l'enregistre comme version (``services/documents/versions_document.py``)
  sous verrou de ligne, nommée par l'EMPREINTE DES ENTRÉES (ACAL221) ;
* **201** nouvelle version ; **200** ``deja_remise: true`` quand la même
  empreinte a déjà été remise (même numéro, aucune copie) ; **400** sous le
  champ nommé (code inconnu, pièce refusée).

Le REGISTRE ci-dessous est l'UNIQUE liste ``code -> (rendu, extension,
mime)`` ; ``dossier_fin_chantier`` et ``pack_technique`` n'y sont pas (ils se
déposent déjà en GED). Ni ``/proposal`` ni aucun statut de devis (règle #4).

Rattachée au ``CalepinageViewSet`` par AFFECTATION D'ATTRIBUT (patron
``views/export_csv.py``) ; le module est importé en fin de
``views/documents.py``, donc avant ``router.register``.
"""
from __future__ import annotations

from django.http import QueryDict
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from .calepinages import CalepinageViewSet

MIME_PDF = 'application/pdf'
MIME_SVG = 'image/svg+xml'
MIME_JSON = 'application/json'

#: ``code -> (action GET qui rend la pièce, extension, mime)`` — LE registre.
REGISTRE_REMISE = {
    'rapport_etude': ('rapport_etude_pdf', 'pdf', MIME_PDF),
    'rapport_ombrage': ('rapport_ombrage_pdf', 'pdf', MIME_PDF),
    'export_projet_json': ('export_projet_json', 'json', MIME_JSON),
    'plan_cablage': ('plan_cablage_pdf', 'pdf', MIME_PDF),
    'manuel_proprietaire': ('manuel_proprietaire_pdf', 'pdf', MIME_PDF),
    'document_asbuilt': ('document_asbuilt_pdf', 'pdf', MIME_PDF),
    'presentation_compacte': ('presentation_compacte_pdf', 'pdf', MIME_PDF),
    'diagramme_pertes': ('diagramme_pertes_svg', 'svg', MIME_SVG),
    'planche_pdf': ('planche_pdf', 'pdf', MIME_PDF),
    'plan_pose_pdf': ('plan_pose_pdf', 'pdf', MIME_PDF),
    'plan_toiture_pdf': ('plan_toiture_pdf', 'pdf', MIME_PDF),
    'plan_masse_pdf': ('plan_masse_pdf', 'pdf', MIME_PDF),
    'note_calcul_pdf': ('note_calcul_pdf', 'pdf', MIME_PDF),
}


class _RequeteDeRendu:
    """La requête vue par le handler GET : MÊME utilisateur, MÊME requête,
    seuls les paramètres de lecture (``langue``) viennent du corps."""

    def __init__(self, requete, parametres):
        self._requete = requete
        self.query_params = parametres
        self.GET = parametres

    def __getattr__(self, nom):
        return getattr(self._requete, nom)


def _octets(reponse):
    """Les octets EXACTS que le GET aurait servis."""
    if isinstance(reponse, Response):
        from rest_framework.renderers import JSONRenderer

        return JSONRenderer().render(reponse.data)
    return bytes(reponse.content)


def rendre_document(viewset, requete, code, langue):
    """``(octets, None)`` — ou ``(None, reponse_de_refus)`` relayée du GET."""
    nom_action, _extension, _mime = REGISTRE_REMISE[code]
    parametres = QueryDict(mutable=True)
    if langue:
        parametres['langue'] = langue
    handler = getattr(viewset, nom_action)
    reponse = handler(_RequeteDeRendu(requete, parametres),
                      pk=viewset.kwargs.get('pk'))
    if getattr(reponse, 'status_code', 500) != status.HTTP_200_OK:
        return None, reponse
    return _octets(reponse), None


REMISE_SCHEMA = inline_serializer('CalepinageRemiseDocument', {
    'numero': drf_serializers.IntegerField(),
    'code': drf_serializers.CharField(),
    'langue': drf_serializers.CharField(),
    'empreinte': drf_serializers.CharField(allow_null=True),
    'deja_remise': drf_serializers.BooleanField(),
    'produit_le': drf_serializers.DateTimeField(),
    'attachment': drf_serializers.IntegerField(),
})


@extend_schema(request=OpenApiTypes.OBJECT,
               responses={201: REMISE_SCHEMA, 200: REMISE_SCHEMA})
@action(detail=True, methods=['post'], url_path='remettre-document',
        url_name='remettre-document', permission_classes=[PeutGererCalepinage])
def remettre_document(self, request, pk=None):
    """ACAL222 — remet UNE pièce : rendue par son GET, versionnée, dédoublonnée.

    * **201** — nouvelle version ``{numero, code, langue, empreinte,
      deja_remise: false, produit_le, attachment}`` ;
    * **200** — ``deja_remise: true`` : la même empreinte des entrées a déjà
      été remise, même numéro, aucune copie ;
    * **400** — code inconnu (sous ``code``), ou le refus du GET relayé tel
      quel (champ nommé).
    """
    from ..services.documents.versions_document import (
        VersionDocumentRefuse, empreinte_courante,
        enregistrer_version_document,
    )

    # L'OBJET D'ABORD (borné société par get_queryset) : le calepinage d'une
    # autre société est INTROUVABLE (404) avant toute lecture du corps —
    # jamais un 400 sur le code qui confirmerait qu'il existe.
    calepinage = self.get_object()
    code = str(request.data.get('code') or '').strip()
    if code not in REGISTRE_REMISE:
        return Response(
            {'code': 'Document inconnu : « %s ». Codes admis : %s.'
             % (code, ', '.join(REGISTRE_REMISE))},
            status=status.HTTP_400_BAD_REQUEST)
    langue = request.data.get('langue') or None
    # Le RENDU d'abord : une pièce refusée par son GET l'est ici à
    # l'identique (même statut, même corps), avant toute lecture d'empreinte.
    octets, refus = rendre_document(self, request, code, langue)
    if refus is not None:
        return refus
    empreinte = empreinte_courante(calepinage, code, langue)
    _action, extension, mime = REGISTRE_REMISE[code]
    try:
        version = enregistrer_version_document(
            calepinage, code=code, octets=octets, langue=langue,
            user=getattr(request, 'user', None), empreinte=empreinte,
            extension=extension, mime=mime)
    except VersionDocumentRefuse as erreur:
        return Response({erreur.champ or 'octets': str(erreur)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(_corps(code, version),
                    status=(status.HTTP_200_OK if version['deja_remise']
                            else status.HTTP_201_CREATED))


def _corps(code, version):
    """La réponse du contrat ``calepinage_documents.json::remise``."""
    return {
        'numero': version['numero'],
        'code': code,
        'langue': version['langue'],
        'empreinte': version['empreinte'],
        'deja_remise': version['deja_remise'],
        'produit_le': version['produit_le'],
        'attachment': version['attachment'].pk,
    }


CalepinageViewSet.remettre_document = remettre_document
