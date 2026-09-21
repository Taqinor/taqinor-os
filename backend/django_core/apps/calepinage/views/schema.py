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
Il ne connaît ni traits, ni blocs, ni repères. Il délègue tout à
``services/sld.py`` : ``schema_du_calepinage`` pour la lecture,
``enregistrer_edition_sld`` pour l'écriture. Le dessin reste celui du MÊME
moteur PUR que le devis (``core.electrique.schema``) — jamais une seconde
planche qui pourrait le contredire.

CALX234 — LE ``POST`` EST LA PORTE D'ÉCRITURE
----------------------------------------------
Le moteur acceptait déjà une surcharge de positions par organe ; personne ne
pouvait l'atteindre. Le chemin calepinage appelle désormais le moteur
DIRECTEMENT (``services/sld.py``) au lieu de traverser la porte cross-app
``apps.ventes.selectors.schema_unifilaire_svg`` : cette porte reste INTACTE,
octet pour octet, pour le chemin ``devis=``. Le ``POST`` porte
``{libelles, reperes, positions}`` et rend le MÊME document que le ``GET``,
édition appliquée ; un refus NOMME le champ fautif
(``edition.positions.<clef>``), jamais un « non enregistré » générique.

CALX237 — LE GABARIT DÉPEND DE LA NORME, JAMAIS DU PAYS SEUL
--------------------------------------------------------------
Sans norme choisie, la planche servie ici passe en mode TOPOLOGIE
(désignations, quantités, repères — aucun calibre, aucune section) et porte
un bandeau qui nomme le réglage manquant. Le gabarit est décidé par
``services/sld.py::gabarit_de_schema``, sur le verdict de
``services/norme.py`` : aucun gabarit marocain n'est supposé.

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

from ..permissions import PeutLireOuEcrireCalepinage, PeutVoirCalepinage

__all__ = ['SchemaUnifilaireMixin']

#: Les clés de la réponse. TOUJOURS toutes présentes : l'écran n'a jamais à
#: deviner si une clé existe (leçon PACT10 du 03/08/2026). CALX234 en ajoute
#: deux — ``blocs`` (les organes dessinés, un par bloc) et ``edition`` (ce que
#: l'utilisateur a changé) — et n'en retire aucune ; le contrat CALX204
#: (``contract_samples/calepinage_sld.json``) les fige toutes les six.
CLES_SCHEMA = ('calepinage', 'svg', 'blocs', 'edition', 'bloquants',
               'manquantes')


class SchemaUnifilaireMixin:
    """L'``@action`` « schéma unifilaire » du viewset pivot."""

    @action(detail=True, methods=['get', 'post'],
            url_path='schema-unifilaire',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def schema_unifilaire(self, request, pk=None):
        """CAL195/CALX234 — le schéma unifilaire de CE calepinage.

        ``GET`` : lecture PURE — rien n'est écrit, aucun statut n'est touché.
        ``POST`` : le corps est l'édition (``{libelles, reperes,
        positions}``), SEUL ``resultat['sld_edition']`` est écrit, et la
        réponse est le MÊME document, édition appliquée.

        ``svg`` vaut ``null`` quand la conception ne permet pas de dessiner ;
        ``bloquants``/``manquantes`` portent alors les libellés français du
        service électrique, tels quels — jamais un message reformulé ici.
        """
        from ..services.electrique import TemperaturesInvalides
        from ..services.sld import (
            SldRefuse, enregistrer_edition_sld, schema_du_calepinage,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            if request.method.lower() == 'post':
                enregistrer_edition_sld(calepinage, request.data)
            return Response(schema_du_calepinage(calepinage))
        except TemperaturesInvalides as refus:
            return Response({refus.champ or 'temperatures': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        except SldRefuse as refus:
            return Response({refus.champ or 'edition': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

    # ── CALX235 — le MÊME schéma, repris par un bureau d'études ───────────
    @action(detail=True, methods=['get'],
            url_path='schema-unifilaire.dxf',
            url_name='schema-unifilaire-dxf',
            permission_classes=[PeutVoirCalepinage])
    def schema_unifilaire_dxf(self, request, pk=None):
        """CALX235 — le schéma unifilaire en DXF, quatre calques nommés.

        Le fichier est transposé du MÊME dessin que le SVG (blocs, positions
        éditées, liaisons) : les deux ne peuvent pas diverger. Une
        conception incomplète ou bloquée ne produit AUCUN fichier — 400 qui
        NOMME le champ en cause.
        """
        from ..services.electrique import TemperaturesInvalides
        from ..services.planche import nom_de_fichier
        from ..services.sld import SldRefuse
        from ..services.sld_export import exporter_sld_dxf
        from .sorties import MIME_DXF, reponse_de_fichier

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            octets = exporter_sld_dxf(calepinage)
        except (SldRefuse, TemperaturesInvalides) as refus:
            return Response(
                {getattr(refus, 'champ', '') or 'schema': str(refus)},
                status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_DXF,
            nom_fichier=nom_de_fichier(calepinage, 'schema.dxf'))
