"""CAL195 — le SCHÉMA UNIFILAIRE du calepinage, servi en HTTP.

LE CONSTAT
----------
Le schéma unifilaire existe depuis PV46, mais il était ENFERMÉ : il part d'un
DEVIS, et le seul chemin vers lui traverse le moteur de devis vendorisé
(``apps.ventes.quote_engine.builder._sld_svg``). Or ce moteur REND — il ne
s'importe pas (règle #4, CLAUDE.md), et aucune autre app n'a le droit
d'atteindre un de ses modules internes. Un calepinage sans devis n'avait donc
AUCUN schéma, alors que le dessin est produit par un module PUR
(``core.electrique.schema``) qui ne connaît ni devis, ni prix, ni statut.

CE MODULE NE DESSINE RIEN
--------------------------
Il ne connaît ni traits, ni blocs, ni repères. Il fait deux choses : il
demande au module électrique du calepinage sa ``Conception`` (CAL124 —
chaînes par MPPT CAL125, câbles dimensionnés CAL131, check-list d'organes
CAL132 : les objets sont ceux de ``core.electrique.types``, pas une copie),
puis il la donne à la porte cross-app ``apps.ventes.selectors.
schema_unifilaire_svg``. Le dessin est donc celui du MÊME moteur que le
devis — jamais une seconde planche qui pourrait le contredire.

FICHE INCOMPLÈTE ⇒ PAS DE SCHÉMA
---------------------------------
Même discipline que PVFCH-ANNEXE : une conception dont une fiche est muette
(``Conception.fiche_incomplete``) ou qui porte des bloquants n'obtient pas un
schéma approximatif — elle n'en obtient aucun, et la réponse DIT pourquoi
(``bloquants``, libellés français du service). Un schéma d'aspect officiel
bâti sur des caractéristiques devinées est un défaut invisible.

LA FORME D'URL RESTE UNIQUE (CAL233) — ``@action`` du viewset pivot, servie
sous ``/api/django/calepinage/calepinages/<pk>/…``, jamais un second viewset.

AUCUN MONTANT. Le moteur électrique ne manipule que des grandeurs publiques
et des quantités ; ``Produit.prix_achat`` n'entre ici par aucun chemin.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['SchemaUnifilaireMixin']

#: Les clés de la réponse. TOUJOURS toutes présentes : l'écran n'a jamais à
#: deviner si une clé existe (leçon PACT10 du 03/08/2026).
CLES_SCHEMA = ('calepinage', 'svg', 'bloquants', 'manquantes')


class SchemaUnifilaireMixin:
    """L'``@action`` « schéma unifilaire » du viewset pivot."""

    @action(detail=True, methods=['get'], url_path='schema-unifilaire',
            permission_classes=[PeutVoirCalepinage])
    def schema_unifilaire(self, request, pk=None):
        """CAL195 — le schéma unifilaire de CE calepinage, en SVG inline.

        Lecture PURE : rien n'est écrit, aucun statut n'est touché.
        ``svg`` vaut ``null`` quand la conception ne permet pas de dessiner ;
        ``bloquants``/``manquantes`` portent alors les libellés français du
        service électrique, tels quels — jamais un message reformulé ici.
        """
        from apps.ventes.selectors import schema_unifilaire_svg

        from ..services.electrique import (
            TemperaturesInvalides, bloquants_nommes,
            conception_du_calepinage,
        )

        calepinage = self.get_object()
        try:
            conception, _materiel, _donnees, _document = (
                conception_du_calepinage(calepinage))
        except TemperaturesInvalides as refus:
            return Response({refus.champ or 'temperatures': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

        manquantes = list(getattr(conception, 'manquantes', ()) or ())
        bloquants = list(bloquants_nommes(conception) or ())
        svg = None
        # Le dessin ne sort que si la conception est COMPLÈTE et sans
        # bloquant : mêmes portails que l'annexe technique du devis.
        if not manquantes and not bloquants:
            svg = schema_unifilaire_svg(
                entree=getattr(conception, 'entree', None),
                resultat=getattr(conception, 'resultat', None),
                cartouche={
                    'client': getattr(
                        getattr(calepinage, 'client', None), 'nom', '') or '',
                    'reference': calepinage.titre or '',
                    'date': (calepinage.created_at.strftime('%d/%m/%Y')
                             if getattr(calepinage, 'created_at', None)
                             else ''),
                })
        return Response({
            'calepinage': calepinage.pk,
            'svg': svg,
            'bloquants': bloquants,
            'manquantes': manquantes,
        })
