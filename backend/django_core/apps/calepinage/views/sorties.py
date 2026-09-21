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

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage

__all__ = ['SortiesMixin', 'reponse_de_fichier', 'inventaire_des_sorties']

#: Types MIME des sorties servies ici.
MIME_PDF = 'application/pdf'
MIME_SVG = 'image/svg+xml'
MIME_DXF = 'image/vnd.dxf'
MIME_XLSX = ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet')
MIME_CSV = 'text/csv; charset=utf-8'

#: Motifs d'indisponibilité — écrits UNE fois, servis à l'identique par
#: l'inventaire (CAL175) et par le refus de l'endpoint correspondant. Deux
#: formulations pour la même cause, c'est un écran qui n'explique pas la même
#: chose que le serveur.
SANS_CONCEPTION = ("Aucune conception enregistrée : la planche se compose de "
                   "la géométrie stockée, jamais d'un tracé reconstitué.")
SANS_RESULTAT = ("Aucune conception enregistrée : la note de calcul ne se rend "
                 "pas à partir de grandeurs absentes.")
SANS_GEOMETRIE = ("Aucune conception enregistrée : la géométrie exportée "
                  "serait vide.")
SANS_PARCELLE = ("Aucune parcelle saisie : le plan de masse ne dessine jamais "
                 "une limite de parcelle qui n'a pas été fournie.")
SANS_IMAGE = "Aucun rendu 3D enregistré pour ce calepinage."
SANS_PIECE = ("Aucune pièce disponible : un dossier technique ne se remet pas "
              "amputé en silence.")


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


def _base(calepinage):
    return '/api/django/calepinage/calepinages/%s/' % calepinage.pk


def inventaire_des_sorties(calepinage):
    """CAL175 — l'inventaire des sorties d'un calepinage, telles qu'elles sont.

    Un INVENTAIRE, pas une fabrique : cette fonction ne produit aucun document.
    Elle dit ce qui existe, où le télécharger, et — quand une sortie n'est pas
    prête — POURQUOI, en français. Une sortie indisponible reste LISTÉE : la
    masquer laisserait l'écran muet sur une absence qui a une cause.

    La forme est celle de ``contract_samples/calepinage_sorties.json`` (PACT10).
    """
    from ..services.planche import geometrie_de_planche, PlancheRefusee

    base = _base(calepinage)
    try:
        geometrie = geometrie_de_planche(calepinage.roof_layout)
    except PlancheRefusee:
        geometrie = None
    a_parcelle = bool((geometrie or {}).get('parcelle'))
    a_resultat = isinstance(calepinage.resultat, dict) \
        and bool(calepinage.resultat)

    def entree(code, libelle, extension, chemin, disponible, motif,
               produit_par='serveur'):
        return {
            'code': code,
            'libelle': libelle,
            'format': extension,
            'endpoint': base + chemin,
            'produit_par': produit_par,
            'disponible': bool(disponible),
            'motif_indisponible': None if disponible else motif,
        }

    dessinable = geometrie is not None
    sorties = [
        entree('planche_pdf', 'Planche de calepinage cotée (A3)', 'pdf',
               'planche.pdf/', dessinable, SANS_CONCEPTION),
        entree('planche_svg',
               'Planche de calepinage cotée (source vectorielle)', 'svg',
               'planche.svg/', dessinable, SANS_CONCEPTION),
        # Le PNG est la conversion NAVIGATEUR du SVG frère : son endpoint est
        # donc CELUI DU SVG, et `produit_par` le dit.
        entree('planche_png', 'Planche de calepinage cotée (image)', 'png',
               'planche.svg/', dessinable, SANS_CONCEPTION,
               produit_par='navigateur'),
        entree('plan_pose_pdf', 'Plan de pose (équipe terrain)', 'pdf',
               'plan-pose.pdf/', dessinable, SANS_CONCEPTION),
        entree('plan_toiture_pdf', 'Plan de toiture', 'pdf',
               'plan-toiture.pdf/', dessinable, SANS_CONCEPTION),
        entree('plan_masse_pdf', 'Plan de masse (bâtiment dans sa parcelle)',
               'pdf', 'plan-masse.pdf/', a_parcelle, SANS_PARCELLE),
        entree('note_calcul_pdf', 'Note de calcul', 'pdf',
               'note-calcul.pdf/', a_resultat, SANS_RESULTAT),
        entree('dxf',
               'Export DXF (calques TOITURE / OBSTACLES / MODULES / COTES)',
               'dxf', 'export.dxf/', dessinable, SANS_GEOMETRIE),
        entree('tableur_xlsx',
               'Modules, chaînes et nomenclature (classeur)', 'xlsx',
               'export.xlsx/', dessinable, SANS_GEOMETRIE),
        entree('tableur_csv', 'Modules, chaînes et nomenclature (CSV)', 'csv',
               'export.csv/', dessinable, SANS_GEOMETRIE),
        # Le rendu 3D n'a pas d'endpoint propre : son URL PRÉSIGNÉE voyage
        # dans l'agrégat de détail (clé ``image``). Annoncer ici une route
        # ``image/`` qui n'existe pas serait l'incident PACT10 reproduit.
        entree('image_3d', 'Rendu 3D de la toiture', 'png', '',
               bool(calepinage.roof_image), SANS_IMAGE),
        entree('pack_technique', 'Dossier technique (pièces fusionnées)',
               'pdf', 'pack-technique/', dessinable and a_resultat,
               SANS_PIECE),
    ]
    return {
        'calepinage': calepinage.pk,
        'titre': calepinage.titre or '',
        # Discipline du null : une empreinte non calculée n'est pas vide, elle
        # n'existe pas.
        'layout_hash': calepinage.layout_hash or None,
        'version_moteur': calepinage.version_moteur or None,
        'sorties': sorties,
    }


class SortiesMixin:
    """Les ``@action`` de sortie, greffées sur le viewset pivot du module."""

    @action(detail=True, methods=['get'], url_path='sorties',
            permission_classes=[PeutVoirCalepinage])
    def sorties(self, request, pk=None):
        """CAL175 — l'INVENTAIRE des sorties disponibles de ce calepinage."""
        return Response(inventaire_des_sorties(self.get_object()))

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

    # ── CAL194 / CAL211 — les trois plans dérivés ──────────────────────────
    def _plan(self, contenu):
        """Sert un plan PDF, ou reporte le REFUS du service mot pour mot."""
        from ..services.planche import (
            CONTENU_POSE, PlancheRefusee, nom_de_fichier, rendre_plan_pdf,
            rendre_plan_pose_pdf,
        )

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            if contenu == CONTENU_POSE:
                octets = rendre_plan_pose_pdf(calepinage,
                                              company=calepinage.company)
            else:
                octets = rendre_plan_pdf(calepinage, contenu=contenu,
                                         company=calepinage.company)
        except PlancheRefusee as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_PDF,
            nom_fichier=nom_de_fichier(calepinage, '%s.pdf' % contenu))

    @action(detail=True, methods=['get'], url_path='plan-pose.pdf',
            url_name='plan-pose-pdf', permission_classes=[PeutVoirCalepinage])
    def plan_pose_pdf(self, request, pk=None):
        """CAL211 — le plan de pose de l'équipe terrain (aucun montant)."""
        from ..services.planche import CONTENU_POSE

        return self._plan(CONTENU_POSE)

    @action(detail=True, methods=['get'], url_path='plan-toiture.pdf',
            url_name='plan-toiture-pdf',
            permission_classes=[PeutVoirCalepinage])
    def plan_toiture_pdf(self, request, pk=None):
        """CAL194 — la toiture seule, sans modules."""
        from ..services.planche import CONTENU_TOITURE

        return self._plan(CONTENU_TOITURE)

    @action(detail=True, methods=['get'], url_path='plan-masse.pdf',
            url_name='plan-masse-pdf',
            permission_classes=[PeutVoirCalepinage])
    def plan_masse_pdf(self, request, pk=None):
        """CAL194 — le bâtiment dans sa parcelle. REFUSÉ sans parcelle saisie."""
        from ..services.planche import CONTENU_MASSE

        return self._plan(CONTENU_MASSE)

    # ── CAL176/CAL177 — la note de calcul ──────────────────────────────────
    @action(detail=True, methods=['get'], url_path='note-calcul.pdf',
            url_name='note-calcul-pdf',
            permission_classes=[PeutVoirCalepinage])
    def note_calcul_pdf(self, request, pk=None):
        """La note de calcul — hypothèses sourcées, verdict de preuve."""
        from ..services.note_calcul import NoteRefusee, rendre_note_calcul
        from ..services.planche import nom_de_fichier

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            octets = rendre_note_calcul(calepinage,
                                        company=calepinage.company)
        except NoteRefusee as refus:
            return Response({refus.champ or 'resultat': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_PDF,
            nom_fichier=nom_de_fichier(calepinage, 'note.pdf'))

    # ── CAL178/CAL179 — les exports réutilisables ──────────────────────────
    @action(detail=True, methods=['get'], url_path='export.dxf',
            url_name='export-dxf', permission_classes=[PeutVoirCalepinage])
    def export_dxf(self, request, pk=None):
        """CAL178 — le DXF, pour le bureau d'études."""
        from ..services.export_dxf import exporter_dxf
        from ..services.planche import PlancheRefusee, nom_de_fichier

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            octets = exporter_dxf(calepinage)
        except PlancheRefusee as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_DXF,
            nom_fichier=nom_de_fichier(calepinage, 'dxf'))

    @action(detail=True, methods=['get'], url_path='export.xlsx',
            url_name='export-xlsx', permission_classes=[PeutVoirCalepinage])
    def export_xlsx(self, request, pk=None):
        """CAL179 — modules, chaînes et nomenclature. AUCUN prix."""
        return self._tableur('xlsx')

    @action(detail=True, methods=['get'], url_path='export.csv',
            url_name='export-csv', permission_classes=[PeutVoirCalepinage])
    def export_csv(self, request, pk=None):
        """CAL179 — la même chose en CSV (``?feuille=`` pour en choisir une)."""
        return self._tableur('csv')

    def _tableur(self, extension):
        from ..services.export_tableur import (
            ExportRefuse, exporter_csv, exporter_xlsx,
        )
        from ..services.planche import PlancheRefusee, nom_de_fichier

        calepinage = self.get_object()  # borné société par get_queryset
        params = getattr(self.request, 'query_params', {}) or {}
        try:
            if extension == 'csv':
                octets = exporter_csv(calepinage,
                                      feuille=params.get('feuille'))
            else:
                octets = exporter_xlsx(calepinage)
        except (ExportRefuse, PlancheRefusee) as refus:
            return Response({getattr(refus, 'champ', '') or 'roof_layout':
                             str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return reponse_de_fichier(
            octets, mime=MIME_CSV if extension == 'csv' else MIME_XLSX,
            nom_fichier=nom_de_fichier(calepinage, extension))

    # ── CAL181 — le dossier technique ──────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='pack-technique',
            url_name='pack-technique',
            permission_classes=[PeutGererCalepinage])
    def pack_technique(self, request, pk=None):
        """CAL181 — produit le dossier technique et le RANGE dans la GED.

        En ÉCRITURE (POST) et gardée par ``calepinage_gerer`` : l'appel CRÉE
        des documents GED. Une lecture n'a pas à écrire dans le référentiel.
        """
        from ..services.pack_technique import PackRefuse, construire_pack

        calepinage = self.get_object()  # borné société par get_queryset
        try:
            resultat = construire_pack(calepinage,
                                       company=calepinage.company,
                                       created_by=request.user)
        except PackRefuse as refus:
            return Response({refus.piece or 'pieces': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        document = resultat['document']
        return Response({
            'document': getattr(document, 'pk', None),
            'nom': getattr(document, 'nom', ''),
            'pieces': [{'code': code, 'libelle': libelle, 'pages': pages}
                       for code, libelle, pages in resultat['pieces']],
            'pages_attendues': resultat['pages_attendues'],
            # Les pièces ABSENTES sont dites, jamais tues.
            'signalements': resultat['signalements'],
        }, status=status.HTTP_201_CREATED)

    # ── CALX17 — la masse posée et la feuille de lestage ───────────────────
    @action(detail=True, methods=['get'], url_path='masse-lestage',
            url_name='masse-lestage',
            permission_classes=[PeutVoirCalepinage])
    def masse_lestage(self, request, pk=None):
        """CALX17 — la masse installée et le lest requis, TELS QUE CALCULÉS.

        ``services/lestage.masse_et_lestage`` (CAL163/CAL164) composait la
        masse posée et la feuille de lestage depuis le poids de FICHE et les
        saisies de la société — sans aucun appelant hors de ses tests, donc
        sans aucun consommateur. Cette porte est ce consommateur, et elle ne
        met RIEN de son cru : la réponse est la sortie du service mot pour
        mot (contrat ``contract_samples/calepinage_masse_lestage.json``).

        Le MODULE dont le poids est lu est celui que l'appelant DÉSIGNE
        (``?module=<id du produit>``), borné à la société par le sélecteur du
        stock ; à défaut, c'est le panneau du devis lié (CAL243). Aucun poids
        « moyen de catalogue » n'existe : sans fiche, la masse n'est pas
        publiée et le champ fautif est nommé par le service.

        Lecture PURE : aucun statut ne bouge, aucun document n'est écrit, et
        aucune somme d'argent n'apparaît ici.
        """
        from ..services.lestage import masse_et_lestage

        calepinage = self.get_object()  # borné société par get_queryset
        demande = str(request.query_params.get('module') or '').strip()
        if demande:
            try:
                produit_module_id = int(demande)
            except (TypeError, ValueError):
                # L'erreur NOMME le champ fautif — jamais un refus générique.
                return Response(
                    {'module': "« module » attend l'identifiant numérique "
                               f"d'un produit (reçu : « {demande} »)."},
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            produit_module_id = self._module_pose(calepinage)
        return Response(masse_et_lestage(
            calepinage, produit_module_id=produit_module_id))

    @staticmethod
    def _module_pose(calepinage):
        """L'identifiant du produit MODULE posé, d'après le devis lié.

        ``equipements_du_calepinage`` (CAL243) rend déjà la famille
        ``panneau`` du devis : la relire ici évite une deuxième règle de
        choix du module, qui finirait par diverger de la première. Aucun
        devis lié, ou aucun panneau sur ses lignes ⇒ ``None`` : le service
        liste alors le poids comme manquant, il n'en suppose pas un.
        """
        if not getattr(calepinage, 'devis_id', None):
            return None
        from ..services.equipements import equipements_du_calepinage

        panneau = (equipements_du_calepinage(calepinage) or {}).get('panneau')
        return (panneau or {}).get('produit')
