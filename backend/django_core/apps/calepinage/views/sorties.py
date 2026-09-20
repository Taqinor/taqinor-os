"""CAL174 — les SORTIES d'un calepinage, servies en HTTP.

Le studio AO sait convertir un SVG en PNG côté navigateur
(``frontend/src/features/ao/studio/svgToPng.js``), mais RIEN n'était
téléchargeable côté calepinage ventes : la planche existait dans le code et
nulle part sur l'écran.

LA FORME D'URL RESTE UNIQUE (CAL233)
-------------------------------------
Ces sorties sont des SOUS-RESSOURCES du calepinage : elles sont servies en
``@action`` du routeur sous ``/api/django/calepinage/calepinages/<pk>/…``, et
c'est pourquoi ce module expose un MIXIN plutôt qu'un second viewset. Un
deuxième viewset aurait ouvert une seconde famille d'URL pour le même objet —
l'incident PACT10 par construction, et ``tests/test_structure_urls.py`` le
refuse.

CE QUI EST GARANTI, ET PAR QUI
-------------------------------
* **Société** — ``self.get_object()`` passe par le ``get_queryset`` du viewset
  pivot (``CompanyScopedModelViewSet``, ARC2) : un calepinage d'une autre
  société est INTROUVABLE (404), jamais « interdit » (un 403 confirmerait son
  existence). La société n'est jamais lue d'un paramètre.
* **Permission** — chaque action déclare ``PeutVoirCalepinage`` ; la garde de
  classe (``ScopedPermission``) s'y AJOUTE (``get_permissions`` du pivot),
  elle n'est pas remplacée.
* **Le PNG n'est pas servi par le serveur.** Aucun rasteriseur SVG n'est
  installé ; le navigateur convertit le SVG frère (``svgToPng.js``). Ouvrir
  ici un ``planche.png`` obligerait à ajouter une dépendance de rastérisation
  pour un besoin déjà couvert côté client.
* **Aucun statut ne bouge** (règle #4) : ces vues LISENT et rendent un
  document. Elles ne sont pas un chemin de devis client — ce sont des pièces
  techniques internes.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['SortiesMixin', 'reponse_de_fichier']

#: Types MIME des sorties servies ici.
MIME_PDF = 'application/pdf'
MIME_SVG = 'image/svg+xml'


def reponse_de_fichier(contenu, *, mime, nom_fichier):
    """Réponse de TÉLÉCHARGEMENT nommée d'après le calepinage.

    ``Content-Disposition: attachment`` avec un nom ASSAINI (``nom_de_fichier``
    ne laisse passer ni espace, ni guillemet, ni séparateur de chemin) : un nom
    reconstruit d'une saisie brute est une injection d'en-tête.
    """
    from django.http import HttpResponse

    reponse = HttpResponse(contenu, content_type=mime)
    reponse['Content-Disposition'] = 'attachment; filename="%s"' % nom_fichier
    return reponse


class SortiesMixin:
    """Les ``@action`` de sortie, greffées sur le viewset pivot du module."""

    @action(detail=True, methods=['get'], url_path='planche.pdf',
            url_name='planche-pdf', permission_classes=[PeutVoirCalepinage])
    def planche_pdf(self, request, pk=None):
        """CAL171/CAL174 — la planche de calepinage cotée, en PDF A3."""
        from ..services.planche import (
            PlancheRefusee, nom_de_fichier, rendre_planche_pdf,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            octets = rendre_planche_pdf(calepinage,
                                        company=calepinage.company)
        except PlancheRefusee as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_PDF,
            nom_fichier=nom_de_fichier(calepinage, 'pdf'))

    @action(detail=True, methods=['get'], url_path='planche.svg',
            url_name='planche-svg', permission_classes=[PeutVoirCalepinage])
    def planche_svg(self, request, pk=None):
        """CAL174 — le SVG SOURCE de la même planche.

        C'est LUI que le navigateur convertit en PNG (``svgToPng.js``) : le
        serveur n'a donc aucune sortie PNG à ouvrir, et aucune dépendance de
        rastérisation à ajouter.
        """
        from ..services.planche import (
            PlancheRefusee, nom_de_fichier, rendre_planche_svg,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            svg = rendre_planche_svg(calepinage)
        except PlancheRefusee as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            svg.encode('utf-8'), mime=MIME_SVG,
            nom_fichier=nom_de_fichier(calepinage, 'svg'))
