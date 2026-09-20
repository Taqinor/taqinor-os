"""Le viewset PIVOT du module Calepinage — CAL16.

UNE SEULE FORME D'URL (CAL233) : tout l'objet métier est servi sous
``/api/django/calepinage/calepinages/<pk>/…``, les sous-ressources en
``@action`` du routeur DRF. Aucune seconde famille d'URL n'est ouverte ici.

CE QUI EST GARANTI PAR LE SOCLE, ET PAS RECODÉ
-----------------------------------------------
* ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) : le queryset est filtré
  sur ``request.user.company`` et la société est POSÉE côté serveur — un
  ``company`` envoyé dans le corps n'existe pas pour le sérialiseur, donc il
  est ignoré, et un calepinage d'une autre société est INTROUVABLE (404),
  jamais « interdit » (un 403 confirmerait son existence) ;
* ``core.permissions.ScopedPermission`` + ``read_permission``/
  ``write_permission`` : lecture gardée par ``calepinage_voir``, écriture par
  ``calepinage_gerer`` (codes lus de ``apps/calepinage/permissions.py``, jamais
  écrits en littéral ici) ;
* chaque ``@action`` déclare EN PLUS sa propre garde (``PeutVoirCalepinage`` /
  ``PeutGererCalepinage``). ``get_permissions`` CUMULE les deux (patron
  ``apps/ao/viewsets.py``) : la garde déclarée par l'action est un plafond
  supplémentaire, jamais une substitution qui jetterait la garde du domaine.

LES FILTRES SONT RÉELLEMENT SERVIS (leçon PV22)
------------------------------------------------
``?lead=`` ``?client=`` ``?statut=`` ``?depuis=`` ``?q=`` passent par
``selectors.appliquer_filtres_liste`` — la MÊME fonction que le sélecteur
public. Un filtre ILLISIBLE (statut inconnu, date invalide) est REFUSÉ 400 en
nommant le champ, jamais avalé en silence : un filtre ignoré fait ouvrir le
mauvais objet (``LeadWorkspace.jsx`` l'a montré).
"""
from __future__ import annotations

import json
from datetime import timedelta

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.records.views import ChatterViewSetMixin
from core.idempotency import (
    IDEMPOTENCY_KEY_HEADER, IdempotencyConflict, IdempotencyRecord,
    _fingerprint,
)
from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import Calepinage
from ..permissions import (
    CAL_GERER, CAL_VOIR, PeutGererCalepinage, PeutLireOuEcrireCalepinage,
    PeutVoirCalepinage,
)
from ..serializers import CalepinageSerializer, CalepinageVarianteSerializer
# CAL52 — la sous-ressource « photos de site » vit dans SON fichier
# (``views/photos.py``) : une base de plus, zéro logique ajoutée ici.
from .photos import PhotosSiteMixin
# CAL64 — idem pour le relevé terrain mobile (``views/releve.py``).
from .releve import ReleveTerrainMixin
# CAL174 — les SOUS-RESSOURCES de sortie (planche PDF/SVG) vivent dans leur
# propre module de vues ; elles sont greffées ICI, sur le viewset pivot, pour
# rester des ``@action`` de la SEULE forme d'URL du module (CAL233).
from .sorties import SortiesMixin
from ..services.devis import (
    DevisRefuse, generer_devis, resynchroniser_devis,
)
from ..services.layout import LayoutRefuse, enregistrer_layout
from ..services.variantes import (
    VarianteRefusee, creer_variante, modifier_variante, retenir_variante,
    supprimer_variante,
)
from ..services.versions import VersionInvalide, restaurer_version
from .electrique import ElectriqueActionsMixin

__all__ = ['CalepinageViewSet', 'contexte_conception', 'detail_calepinage']

#: Durée de validité de l'URL présignée du rendu (celle du stockage ventes).
DUREE_URL_IMAGE = timedelta(hours=1)


class ActionIdempotenteMixin:
    """CAL21 — le contrat ``Idempotency-Key`` de ``core.idempotency``, pour une
    ``@action``.

    ``IdempotentCreateMixin`` ne couvre que ``create`` ; une action métier en a
    autant besoin — un double-clic ou un rejeu réseau ne doit pas basculer deux
    fois la variante retenue d'un dossier.

    L'EMPREINTE inclut la CIBLE et le nom de l'action, pas seulement le corps :
    sans cela, deux ``retenir`` sur DEUX variantes, envoyés avec la même clé et
    un corps vide, auraient la même empreinte et le second rejouerait la
    réponse du premier — il aurait retenu la mauvaise variante EN SILENCE.
    (Le module ``apps.ao`` porte le même mixin ; on ne l'importe pas — une app
    n'importe jamais les vues d'une autre.)
    """

    def _cle_idempotence(self, request):
        brut = (request.META.get(IDEMPOTENCY_KEY_HEADER)
                or request.headers.get('Idempotency-Key'))
        return brut.strip()[:255] if brut else None

    def _empreinte_idempotence(self, request):
        return _fingerprint({
            'action': getattr(self, 'action', ''),
            'cible': str(self.kwargs.get('pk', '')),
            'sous_cible': str(self.kwargs.get('variante_id', '')),
            'corps': json.loads(json.dumps(request.data, default=str)),
        })

    def executer_idempotent(self, request, calcul):
        cle = self._cle_idempotence(request)
        if not cle:
            return calcul()
        company = getattr(request.user, 'company', None)
        endpoint = '%s.%s' % (type(self).__qualname__,
                              getattr(self, 'action', ''))
        empreinte = self._empreinte_idempotence(request)
        memorise = IdempotencyRecord.objects.filter(
            company=company, endpoint=endpoint, key=cle).first()
        if memorise is not None:
            if memorise.request_fingerprint != empreinte:
                raise IdempotencyConflict()
            return Response(memorise.response_body,
                            status=memorise.response_status)
        reponse = calcul()
        try:
            IdempotencyRecord.objects.get_or_create(
                company=company, endpoint=endpoint, key=cle,
                defaults={'request_fingerprint': empreinte,
                          'response_status': reponse.status_code,
                          # NORMALISÉ avant écriture : un `Decimal` ou un
                          # `datetime` resté dans le corps ferait échouer le
                          # `json.dumps` du JSONField, et l'idempotence
                          # deviendrait un no-op SILENCIEUX.
                          'response_body': json.loads(
                              json.dumps(reponse.data, default=str))})
        except Exception:  # noqa: BLE001 — l'idempotence est un CONFORT : elle
            # ne fait jamais échouer une action qui a déjà réussi.
            pass
        return reponse


class CalepinageViewSet(PhotosSiteMixin, ReleveTerrainMixin,
                        ChatterViewSetMixin, ActionIdempotenteMixin,
                        ElectriqueActionsMixin, SortiesMixin,
                        CompanyScopedModelViewSet):
    """CRUD du pivot ``Calepinage`` + ses sous-ressources en ``@action``.

    CAL26 — le chatter est celui de la PLATEFORME (``records``) :
    ``chatter/historique`` (GET) et ``chatter/noter`` (POST) sont hérités de
    ``apps.records.views.ChatterViewSetMixin``. Aucune classe ``…Activity``
    maison n'existe dans ce module, et aucune seconde API de chatter n'est
    ouverte.
    """

    queryset = Calepinage.objects.select_related('client', 'devis').all()
    serializer_class = CalepinageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at', 'statut', 'titre']

    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    def get_permissions(self):
        """``ScopedPermission`` TOUJOURS, + la garde déclarée par l'action.

        Cumul et jamais substitution : sans ``declared_action_permissions``,
        le ``permission_classes=`` d'une ``@action`` serait complètement
        inopérant (cf. ``core.permissions``).
        """
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            permissions.extend(declared)
        return permissions

    # ── Liste : des filtres qui filtrent VRAIMENT ──────────────────────────
    def get_queryset(self):
        params = getattr(self.request, 'query_params', {}) or {}
        return selectors.appliquer_filtres_liste(
            super().get_queryset(),
            lead_id=_entier(params.get('lead'), 'lead'),
            client_id=_entier(params.get('client'), 'client'),
            statut=_statut(params.get('statut')),
            depuis=_moment(params.get('depuis')),
            q=params.get('q'))

    def perform_create(self, serializer):
        """Société ET auteur posés côté serveur — jamais lus du corps."""
        serializer.save(company=self.request.user.company,
                        cree_par=self.request.user)

    # ── Détail : l'agrégat du contrat CAL1 ─────────────────────────────────
    def retrieve(self, request, *args, **kwargs):
        """CAL17 — TOUT ce que la fiche calepinage affiche, en UN appel.

        Sans agrégat, l'écran ouvrirait quatre requêtes et chaque lane
        inventerait sa forme (incident PACT10 du 03/08/2026). La forme est
        celle de ``contract_samples/calepinage_detail.json`` : toutes les clés
        TOUJOURS présentes, une grandeur non mesurée à ``null`` et jamais à
        ``0``. Lecture PURE (aucun statut, aucun layout n'est écrit) ; un
        calepinage d'une autre société est introuvable (404, get_queryset).
        """
        return Response(detail_calepinage(self.get_object(), request))

    # ── La conception elle-même ────────────────────────────────────────────
    @action(detail=True, methods=['get', 'post'], url_path='layout',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def layout(self, request, pk=None):
        """CAL18 — lit (GET) ou enregistre (POST) la conception du calepinage.

        Patron exact de ``apps/ao/views.py::AppelOffreViewSet.layout`` : le
        corps POST EST le layout sérialisé, et les enveloppes
        ``{"layout": …}`` / ``{"roof_layout": …}`` sont acceptées telles
        quelles. SEULS ``roof_layout`` / ``layout_hash`` sont touchés — aucun
        statut n'est écrit (règle #4).

        L'écriture passe par ``services.enregistrer_layout`` (CAL13), jamais
        par une écriture directe de vue : c'est lui qui calcule l'empreinte
        (``apps.ventes.services.layout_hash``, jamais recodée) et qui dépose
        une VERSION quand — et seulement quand — la conception a changé. Un
        renvoi à l'identique répond donc ``{"inchange": true}`` sans créer de
        version. Un corps vide est refusé en français ; un calepinage d'une
        autre société est introuvable (404, ``get_queryset``).
        """
        calepinage = self.get_object()  # borné société par get_queryset
        if request.method.lower() == 'get':
            return Response({'roof_layout': calepinage.roof_layout,
                             'layout_hash': calepinage.layout_hash or None})

        payload = _corps_de_layout(request.data)
        if payload is None:
            return Response(
                {'roof_layout': "Conception manquante ou invalide : le corps "
                                "attendu est le document de conception."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = enregistrer_layout(calepinage, payload,
                                          user=request.user)
        except LayoutRefuse as refus:
            return Response({refus.champ or 'roof_layout': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        version = resultat['version']
        return Response({
            'roof_layout': calepinage.roof_layout,
            'layout_hash': resultat['layout_hash'] or None,
            'inchange': resultat['inchange'],
            'version': version.pk if version is not None else None,
        })

    # ── Le pont vers le devis : appeler, jamais refaire ────────────────────
    @action(detail=True, methods=['post'], url_path='generer-devis',
            permission_classes=[PeutGererCalepinage])
    def generer_devis(self, request, pk=None):
        """CAL24 — crée (ou RETROUVE) le devis de ce calepinage.

        Le chemin canonique existe déjà et n'est pas doublé :
        ``apps.ventes.services.build_devis_from_layout``, appelé par
        ``services.devis.generer_devis`` avec le lead/client DU CALEPINAGE et
        l'auteur côté serveur. Aucune ligne de devis n'est fabriquée ici,
        aucun PDF n'est produit (règle #4).

        Un second appel rend le MÊME devis (dédup ``lead`` + ``layout_hash``)
        et un catalogue invalide remonte le 422 du serveur ventes, mot pour
        mot.
        """
        calepinage = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            devis, cree = generer_devis(
                calepinage, user=request.user,
                taux_tva=corps.get('taux_tva'),
                remise_globale=corps.get('remise_globale'))
        except DevisRefuse as refus:
            return Response(_refus_devis(refus), status=refus.statut)
        return Response(
            {'devis': devis.pk, 'reference': devis.reference,
             'statut': devis.statut, 'layout_hash': devis.layout_hash or None,
             'deduplique': not cree},
            status=(status.HTTP_201_CREATED if cree else status.HTTP_200_OK))

    @action(detail=True, methods=['post'], url_path='sync-devis',
            permission_classes=[PeutGererCalepinage])
    def sync_devis(self, request, pk=None):
        """CAL25 — resynchronise le devis lié sur la conception COURANTE.

        ``apps.ventes.services.sync_devis_from_layout`` fait le travail
        CHIRURGICAL (quantités, batterie, onduleur accordé au scénario) et
        préserve prix négociés, remises, sections et notes. Son 409 sur un
        devis émis — avec ``revision_possible`` — se propage TEL QUEL : ni
        traduit, ni adouci. Sans devis lié, le refus NOMME le geste à faire
        (« Générer le devis »).
        """
        calepinage = self.get_object()
        try:
            resultat = resynchroniser_devis(calepinage, user=request.user)
        except DevisRefuse as refus:
            return Response(_refus_devis(refus), status=refus.statut)
        return Response(resultat)

    # ── Les variantes : CRUD, bascule idempotente, comparatif ──────────────
    @action(detail=True, methods=['get', 'post'], url_path='variantes',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def variantes(self, request, pk=None):
        """CAL21 — liste (GET) ou crée (POST) une variante, la RETENUE en tête.

        La création passe par ``services.creer_variante`` : ``retenue`` n'a
        qu'un seul chemin d'écriture, et ``?retenir=1`` dans le corps emprunte
        la bascule ATOMIQUE (jamais deux retenues, jamais zéro).
        """
        calepinage = self.get_object()
        if request.method.lower() == 'get':
            return Response(CalepinageVarianteSerializer(
                selectors.variantes(calepinage), many=True).data)
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            variante = creer_variante(
                calepinage, nom=corps.get('nom'),
                roof_layout=corps.get('roof_layout'),
                resultat=corps.get('resultat'), user=request.user,
                retenir=_booleen(corps.get('retenir')))
        except VarianteRefusee as refus:
            return Response({refus.champ or 'variante': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(CalepinageVarianteSerializer(variante).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'patch', 'delete'],
            url_path=r'variantes/(?P<variante_id>[^/.]+)',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def variante(self, request, pk=None, variante_id=None):
        """CAL21 — lit, édite ou retire UNE variante (jamais ``retenue``).

        La variante RETENUE ne se supprime pas : la retirer laisserait le
        calepinage sans option choisie (le refus le dit et nomme le geste).
        """
        calepinage = self.get_object()
        variante = selectors.variantes(calepinage).filter(
            pk=variante_id).first()
        if variante is None:
            return Response({'detail': 'Variante introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        methode = request.method.lower()
        if methode == 'get':
            return Response(CalepinageVarianteSerializer(variante).data)
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            if methode == 'delete':
                supprimer_variante(variante)
                return Response(status=status.HTTP_204_NO_CONTENT)
            variante = modifier_variante(
                variante, nom=corps.get('nom'),
                roof_layout=corps.get('roof_layout', ...),
                resultat=corps.get('resultat', ...))
        except VarianteRefusee as refus:
            return Response({refus.champ or 'variante': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(CalepinageVarianteSerializer(variante).data)

    @action(detail=True, methods=['post'],
            url_path=r'variantes/(?P<variante_id>[^/.]+)/retenir',
            permission_classes=[PeutGererCalepinage])
    def retenir(self, request, pk=None, variante_id=None):
        """CAL21 — bascule la variante retenue, IDEMPOTEMMENT.

        Deux appels portant la MÊME ``Idempotency-Key`` ne basculent qu'une
        fois : un double-clic ou un rejeu réseau ne doit pas faire valser
        l'option retenue d'un dossier.
        """
        calepinage = self.get_object()
        variante = selectors.variantes(calepinage).filter(
            pk=variante_id).first()
        if variante is None:
            return Response({'detail': 'Variante introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        def basculer():
            retenir_variante(variante)
            return Response(CalepinageVarianteSerializer(variante).data)

        return self.executer_idempotent(request, basculer)

    @action(detail=True, methods=['get'], url_path='comparer',
            permission_classes=[PeutVoirCalepinage])
    def comparer(self, request, pk=None):
        """CAL21 — le comparatif des variantes (contrat CAL3).

        Le calcul est celui du sélecteur : une variante non simulée le DIT et
        ses grandeurs valent ``null`` ; les écarts sont relatifs à la retenue.
        """
        return Response(selectors.comparer_variantes(self.get_object()))

    # ── L'historique : visible, et REJOUABLE sans être réécrit ─────────────
    @action(detail=True, methods=['get'], url_path='versions',
            permission_classes=[PeutVoirCalepinage])
    def versions(self, request, pk=None):
        """CAL20 — l'historique, du plus récent au plus ancien.

        CAL8 fait vivre l'historique ; sans cette route il reste invisible.
        Borné société par ``get_queryset`` (le calepinage), donc une version
        d'une autre société n'apparaît jamais.
        """
        calepinage = self.get_object()
        return Response([
            _version_en_ligne(version)
            for version in selectors.versions(calepinage)
        ])

    @action(detail=True, methods=['post'],
            url_path=r'versions/(?P<version_id>[^/.]+)/restaurer',
            permission_classes=[PeutGererCalepinage])
    def restaurer(self, request, pk=None, version_id=None):
        """CAL20 — REJOUE une version : une version de PLUS, jamais une de moins.

        Aucun instantané n'est réécrit et aucun n'est supprimé : l'état
        restauré redevient courant ET s'ajoute en tête de l'historique
        (``services.versions.restaurer_version``, qui passe par le chemin
        d'écriture commun). Une version d'une AUTRE société — ou d'un autre
        calepinage — est introuvable (404).
        """
        calepinage = self.get_object()  # borné société par get_queryset
        version = selectors.versions(calepinage).filter(pk=version_id).first()
        if version is None:
            return Response({'detail': 'Version introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            resultat = restaurer_version(version, user=request.user)
        except VersionInvalide as refus:
            return Response({refus.champ or 'version': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        neuve = resultat['version']
        return Response({
            'restauree': version.pk,
            'version': neuve.pk if neuve is not None else None,
            'layout_hash': resultat['layout_hash'] or None,
            'inchange': resultat['inchange'],
        })

    @action(detail=True, methods=['get'], url_path='design-context',
            permission_classes=[PeutVoirCalepinage])
    def design_context(self, request, pk=None):
        """CAL231 — TOUT ce que l'atelier doit savoir d'un calepinage.

        Jumeau NEUTRE de ``ventes``/``devis/<id>/design-context/`` (PV17) et de
        ``ao``/``appels-offres/<id>/design-context/`` : mêmes sept clés,
        TOUJOURS présentes (contrat
        ``contract_samples/calepinage_design_context.json``). LECTURE PURE,
        bornée société par ``get_queryset`` (404 pour une autre société).
        """
        return Response(contexte_conception(self.get_object(), request))

    @action(detail=True, methods=['post'], url_path='roof-image',
            permission_classes=[PeutGererCalepinage],
            parser_classes=[MultiPartParser, FormParser])
    def roof_image(self, request, pk=None):
        """CAL19 — réceptionne le rendu (PNG/JPEG) et le range dans MinIO.

        AUCUN second chemin de stockage : la validation magic-bytes, le bucket
        et l'URL présignée 1 h sont ceux du chemin ventes, exposés par les
        fonctions minces ``apps.ventes.services.type_image_toiture`` /
        ``stocker_image_toiture`` / ``url_image_toiture`` (CAL19). Ce module
        n'importe ni une vue ni un modèle ventes.

        La clé est DÉRIVÉE côté serveur et porte la société
        (``roofs/<company_id>/calepinage-<pk>.<ext>``) : rien n'est lu du corps
        hors le fichier lui-même. Un fichier qui n'est pas une image est refusé
        avec le motif du SERVEUR. Aucun statut ne bouge (règle #4).
        """
        from apps.ventes import services as ventes_services

        # L'OBJET D'ABORD (CAL29) : un calepinage d'une autre société doit
        # rendre 404 quel que soit le corps envoyé. Valider le fichier avant
        # aurait répondu « fichier manquant » sur un objet qui, pour cet
        # appelant, n'existe pas — un oracle d'existence par la bande.
        calepinage = self.get_object()  # borné société par get_queryset
        fichier = request.FILES.get('image') or request.FILES.get('file')
        if fichier is None:
            return Response(
                {'image': "Fichier image manquant (champ « image »)."},
                status=status.HTTP_400_BAD_REQUEST)
        donnees = fichier.read()
        extension, mime = ventes_services.type_image_toiture(donnees)
        if extension is None:
            return Response({'image': 'Image invalide (PNG ou JPEG attendu).'},
                            status=status.HTTP_400_BAD_REQUEST)

        cle = (f'roofs/{calepinage.company_id or 0}/'
               f'calepinage-{calepinage.pk}.{extension}')
        ventes_services.stocker_image_toiture(donnees, cle,
                                              content_type=mime)
        calepinage.roof_image = cle
        calepinage.save(update_fields=['roof_image', 'updated_at'])
        return Response(
            {'roof_image': cle,
             'url': ventes_services.url_image_toiture(cle)},
            status=status.HTTP_201_CREATED)


def _corps_de_layout(donnees):
    """Le document de conception d'un corps de requête, ou ``None``.

    Accepte le layout NU et les deux enveloppes historiques (``layout`` /
    ``roof_layout``) — les mêmes que côté ventes et côté AO, pour qu'un même
    client puisse parler aux trois portes sans se reformater.
    """
    if isinstance(donnees, dict):
        for enveloppe in ('layout', 'roof_layout'):
            if set(donnees.keys()) == {enveloppe}:
                donnees = donnees[enveloppe]
                break
    if not isinstance(donnees, dict) or not donnees:
        return None
    return donnees


def _refus_devis(refus):
    """Le corps d'un refus du pont devis — la charge VENTES telle quelle.

    Quand le serveur ventes a parlé (pré-vol 422, conflit 409), on rend SON
    dictionnaire : ni traduit, ni adouci, ni renuméroté. Sinon on nomme le
    champ fautif, en français.
    """
    return refus.donnees or {refus.champ or 'detail': str(refus)}


def _version_en_ligne(version):
    """Une version d'historique, telle que la liste l'affiche."""
    return {
        'id': version.pk,
        'libelle': version.libelle or '',
        'layout_hash': _texte(version.layout_hash),
        'cree_le': _horodatage(version.created_at),
        'cree_par': _personne(getattr(version, 'cree_par', None)),
        'a_un_resultat': bool(version.resultat),
    }


# ── CAL231 — LE CONTEXTE DE CONCEPTION (jumeau neutre de PV17) ────────────

def contexte_conception(calepinage, request=None):
    """Les SEPT clés du contexte d'atelier — toutes toujours présentes.

    Dictionnaire LITTÉRAL (comme ``detail_calepinage``) pour que la garde de
    contrat lise la forme réellement renvoyée.
    """
    company = getattr(calepinage, 'company', None)
    contexte_devis = _contexte_devis_lie(calepinage, company)
    geometrie = _geometrie(calepinage, contexte_devis)
    cible = _cible(calepinage, contexte_devis)
    return {
        'calepinage': {
            'id': calepinage.pk,
            'titre': _texte(getattr(calepinage, 'titre', '')) or '',
            'statut': calepinage.statut,
            'lead': getattr(calepinage, 'lead_id', None),
            'client': getattr(calepinage, 'client_id', None),
            'devis': getattr(calepinage, 'devis_id', None),
        },
        'geometrie': geometrie,
        'cible': cible,
        'carte': _config_carte(),
        'modifiable': not _raison_lecture_seule(contexte_devis),
        'raison_lecture_seule': _raison_lecture_seule(contexte_devis),
        'avertissements': _avertissements(geometrie, cible, contexte_devis),
    }


def _contexte_devis_lie(calepinage, company):
    """Le contexte d'atelier du DEVIS lié, ou ``None``.

    Lecture cross-app par ``apps.ventes.selectors`` — la MÊME fonction que
    l'atelier devis, jamais un second calcul de cible ni une seconde façon de
    dire « lecture seule ».
    """
    from apps.ventes.selectors import (
        contexte_conception_devis, get_devis_by_pk,
    )

    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id or company is None:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        return None
    return contexte_conception_devis(devis, company)


def _geometrie(calepinage, contexte_devis):
    """``{source, roof_layout, pin, outline, contour_client}``.

    Le layout du CALEPINAGE prime ; à défaut, l'épingle et le contour posés
    au diagnostic (CAL15). Sans aucune source, ``source`` vaut ``'none'`` et
    rien n'est deviné — pas de centre du Maroc inventé.
    """
    from .. import selectors as cal_selectors

    geo = cal_selectors.contexte_geographique(calepinage)
    contour_client = geo['outline'] or []
    if contexte_devis is not None:
        contour_client = (contexte_devis.get('geometrie', {})
                          .get('contour_client') or contour_client)
    layout = getattr(calepinage, 'roof_layout', None)
    if isinstance(layout, dict) and layout:
        pin = layout.get('pin')
        outline = layout.get('outline')
        return {
            'source': 'calepinage',
            'roof_layout': layout,
            'pin': pin if isinstance(pin, dict) else geo['pin'],
            'outline': outline if isinstance(outline, list) else (
                geo['outline'] or []),
            'contour_client': contour_client,
        }
    if geo['pin'] is not None or geo['outline']:
        return {
            'source': 'lead',
            'roof_layout': None,
            'pin': geo['pin'],
            'outline': geo['outline'] or [],
            'contour_client': contour_client,
        }
    return {'source': 'none', 'roof_layout': None, 'pin': None,
            'outline': [], 'contour_client': contour_client}


def _cible(calepinage, contexte_devis):
    """La cible de puissance, ou ``None`` — JAMAIS une puissance inventée.

    Ordre : la cible du DEVIS lié (celle que l'atelier devis emploie), sinon
    celle déduite des factures du lead (CAL147, quand elle existera), sinon
    ``None`` — et l'écran affiche « non renseignée ». Un toit dessiné sur une
    cible devinée ne correspond à aucun devis.
    """
    if contexte_devis is not None and contexte_devis.get('cible'):
        return dict(contexte_devis['cible'], source='devis')
    return _cible_des_factures(calepinage)


def _cible_des_factures(calepinage):
    """CAL147 — la cible déduite des factures du lead, ou ``None``.

    Le déducteur de CAL147 n'est pas encore posé : tant qu'il manque, cette
    fonction rend ``None``. C'est le refus explicite d'inventer une puissance
    (un ``0`` ici se lirait « zéro kWc voulu »).
    """
    return None


def _raison_lecture_seule(contexte_devis):
    """La phrase FRANÇAISE du serveur ventes, reprise MOT POUR MOT.

    Ni traduite, ni adoucie : si l'écran disait autre chose que la porte
    d'écriture, l'utilisateur apprendrait le refus deux fois, et différemment.
    """
    if contexte_devis is None:
        return ''
    return contexte_devis.get('raison_lecture_seule') or ''


def _avertissements(geometrie, cible, contexte_devis):
    """Ce qui manque, DIT en français — jamais tu."""
    messages = list((contexte_devis or {}).get('avertissements') or [])
    if geometrie['source'] == 'none':
        messages.append(
            'Aucune géométrie de toiture connue pour ce calepinage : '
            'commencez par situer le bâtiment sur la carte.')
    if cible is None:
        messages.append('Aucune cible de puissance connue : renseignez-la, '
                        'ou rattachez un devis.')
    return messages


def _config_carte():
    """Clés carte du builder 3D — MIROIR de ``ventes/views/roof_config.py``.

    Mêmes variables d'environnement, même forme que les contextes devis et AO
    (``apps/ao/selectors.py::_config_carte_builder`` fait exactement pareil) :
    c'est de la CONFIGURATION, pas une donnée société — la lire ici évite de
    faire dépendre ce module de ventes pour une clé d'API.
    """
    import os

    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return {'available': bool(maptiler), 'maptilerKey': maptiler,
            'mapboxToken': mapbox or None}


# ── CAL17 — L'AGRÉGAT DE DÉTAIL (la forme est le contrat) ──────────────────

def detail_calepinage(calepinage, request=None):
    """Le dictionnaire servi par ``GET /calepinages/<pk>/``.

    Écrit en DICTIONNAIRE LITTÉRAL, et pas monté clé par clé : c'est ce qui
    permet à ``scripts/check_api_shapes.py`` de lire la forme réellement
    renvoyée et de la confronter à l'échantillon committé. Une clé en trop ou
    en moins d'un côté rougit — l'écran ne peut plus diverger en silence.

    Les lectures cross-app passent par ``apps.crm.selectors`` /
    ``apps.ventes.selectors`` (jamais leurs modèles).
    """
    from .. import selectors as cal_selectors

    company = getattr(calepinage, 'company', None)
    layout = getattr(calepinage, 'roof_layout', None)
    return {
        'id': calepinage.pk,
        'reference': _reference(calepinage),
        'nom': _texte(getattr(calepinage, 'titre', '')) or str(calepinage),
        'statut': calepinage.statut,
        'statut_libelle': calepinage.get_statut_display(),
        'cree_le': _horodatage(getattr(calepinage, 'created_at', None)),
        'modifie_le': _horodatage(getattr(calepinage, 'updated_at', None)),
        'cree_par': _personne(getattr(calepinage, 'cree_par', None)),
        'responsable': _responsable(calepinage, company),
        'lead': _lead(calepinage, company),
        'client': _client(calepinage),
        'devis': _devis(calepinage, company),
        'layout_present': bool(layout),
        'layout_hash': _texte(getattr(calepinage, 'layout_hash', '')),
        'layout_schema_version': _schema_version(layout),
        'version_moteur': _texte(getattr(calepinage, 'version_moteur', '')),
        'versions': _compteur_versions(calepinage),
        'variantes': _compteur_variantes(calepinage),
        'image': _image(calepinage),
        'contexte_geographique': cal_selectors.contexte_geographique(
            calepinage),
        'permissions': _permissions(calepinage, request),
    }


def _reference(calepinage):
    """« CAL-AAMM-0001 » — DÉRIVÉE, jamais un numéro stocké.

    Le modèle ne porte pas de référence (aucune migration n'est ajoutée par
    cette lane) : l'étiquette est déduite de la date de création et de
    l'identifiant, donc elle est stable dans le temps et ne peut pas
    « rétrécir » comme un ``count()+1``. Le jour où une vraie numérotation
    arrivera, elle passera par ``apps/ventes/utils/references.py``.
    """
    cree = getattr(calepinage, 'created_at', None)
    if cree is None:
        return f'CAL-{calepinage.pk:04d}'
    return f'CAL-{cree.strftime("%y%m")}-{calepinage.pk:04d}'


def _texte(valeur):
    """Une chaîne non vide, ou ``None`` — jamais une chaîne vide trompeuse."""
    texte = (valeur or '').strip() if isinstance(valeur, str) else ''
    return texte or None


def _horodatage(moment):
    return moment.isoformat() if moment is not None else None


def _personne(user):
    """``{id, nom_complet}`` d'un compte, ou ``None``."""
    if user is None:
        return None
    nom = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return {'id': user.pk,
            'nom_complet': nom or getattr(user, 'username', '')}


def _responsable(calepinage, company):
    """Le responsable du LEAD rattaché, ou ``None``.

    Le calepinage ne porte pas de responsable propre : plutôt que d'en
    inventer un (ou de coder en dur un prénom, ce que la règle fondateur
    interdit), on rend celui du lead — la personne qui répond réellement du
    dossier — et ``None`` quand il n'y en a pas.
    """
    lead = _lead_objet(calepinage, company)
    return _personne(getattr(lead, 'owner', None)) if lead is not None \
        else None


def _lead_objet(calepinage, company):
    from apps.crm.selectors import get_company_lead

    return get_company_lead(company, getattr(calepinage, 'lead_id', None))


def _lead(calepinage, company):
    """``{id, nom, ville}`` du lead rattaché, ou ``None``."""
    lead = _lead_objet(calepinage, company)
    if lead is None:
        return None
    nom = ' '.join(p for p in [getattr(lead, 'nom', ''),
                               getattr(lead, 'prenom', '') or ''] if p).strip()
    return {'id': lead.pk, 'nom': nom or f'Lead #{lead.pk}',
            'ville': _texte(getattr(lead, 'ville', ''))}


def _client(calepinage):
    """``{id, nom, ville}`` du client rattaché, ou ``None``."""
    client = getattr(calepinage, 'client', None)
    if client is None:
        return None
    return {'id': client.pk, 'nom': str(client),
            'ville': _texte(getattr(client, 'ville', ''))}


def _devis(calepinage, company):
    """``{id, reference, statut}`` du devis lié, ou ``None``.

    Lu par ``apps.ventes.selectors`` et RE-BORNÉ à la société : un calepinage
    ne peut pas servir de passerelle vers le devis d'une autre société.
    """
    from apps.ventes.selectors import get_devis_by_pk

    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id or company is None:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        return None
    return {'id': devis.pk, 'reference': devis.reference,
            'statut': devis.statut}


def _schema_version(layout):
    """La version de schéma DÉCLARÉE par le document, ou ``None``.

    Jamais une version supposée : un layout qui ne dit pas sa version n'en a
    pas, et l'écran doit pouvoir le lire tel quel.
    """
    if not isinstance(layout, dict):
        return None
    for cle in ('schema_version', 'schemaVersion', 'version'):
        valeur = layout.get(cle)
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            return valeur
    return None


def _compteur_versions(calepinage):
    """``{total, courante_id, derniere_le}`` — ``null`` quand il n'y a rien.

    Discipline du contrat : un calepinage SANS historique rend ``null``, pas
    ``0``. Publier un zéro ferait lire « aucune version enregistrée » là où
    rien n'a encore été mesuré.
    """
    from .. import selectors as cal_selectors

    derniere = cal_selectors.versions(calepinage).first()
    if derniere is None:
        return {'total': None, 'courante_id': None, 'derniere_le': None}
    return {
        'total': cal_selectors.versions(calepinage).count(),
        'courante_id': derniere.pk,
        'derniere_le': _horodatage(derniere.created_at),
    }


def _compteur_variantes(calepinage):
    """``{total, retenue_id, non_simulees}`` — ``null`` quand il n'y en a pas.

    ``non_simulees`` compte les variantes sans résultat de moteur : ce sont
    celles dont aucune grandeur de production n'est connue (elles ne valent
    pas « zéro kWh »).
    """
    from .. import selectors as cal_selectors

    lignes = list(cal_selectors.variantes(calepinage))
    if not lignes:
        return {'total': None, 'retenue_id': None, 'non_simulees': None}
    retenue = next((v for v in lignes if v.retenue), None)
    return {
        'total': len(lignes),
        'retenue_id': retenue.pk if retenue is not None else None,
        'non_simulees': len([v for v in lignes if not v.resultat]),
    }


def _image(calepinage):
    """``{url, genere_le, expire_le}`` du rendu stocké, ou trois ``null``.

    L'URL est PRÉSIGNÉE (lecture seule, 1 h) et fabriquée par le stockage
    ventes — jamais un second chemin de stockage (CAL19). Tant que la
    fonction mince de ``apps.ventes.services`` n'est pas là, l'URL vaut
    ``None`` : on ne fabrique jamais une URL qui ne mène nulle part.
    """
    from django.utils import timezone

    cle = _texte(getattr(calepinage, 'roof_image', ''))
    url = url_image_toiture(cle) if cle else None
    if url is None:
        return {'url': None, 'genere_le': None, 'expire_le': None}
    maintenant = timezone.now()
    return {
        'url': url,
        'genere_le': _horodatage(maintenant),
        'expire_le': _horodatage(maintenant + DUREE_URL_IMAGE),
    }


def url_image_toiture(cle):
    """L'URL présignée d'un rendu, par le stockage VENTES (jamais un second).

    Import FONCTION-LOCAL et résolution par ``getattr`` : la fonction mince
    côté ventes est posée par CAL19 ; avant elle, on rend ``None`` plutôt
    qu'une URL inventée. ``apps.calepinage`` n'importe ni une vue ni un modèle
    ventes (contrat import-linter).
    """
    if not cle:
        return None
    from apps.ventes import services as ventes_services

    fabrique = getattr(ventes_services, 'url_image_toiture', None)
    if fabrique is None:
        return None
    try:
        return fabrique(cle)
    except Exception:  # noqa: BLE001 — un stockage muet n'efface pas la fiche
        return None


def _permissions(calepinage, request):
    """Ce que L'APPELANT a le droit de faire — jamais un drapeau décoratif."""
    user = getattr(request, 'user', None) if request is not None else None
    peut_gerer = bool(user) and PeutGererCalepinage().has_permission(
        request, None)
    return {
        'peut_modifier': peut_gerer,
        'peut_supprimer': peut_gerer and not getattr(calepinage, 'devis_id',
                                                     None),
        'peut_retenir_variante': peut_gerer and bool(
            getattr(calepinage, 'variantes', None)
            and calepinage.variantes.exists()),
    }


# ── Lecture des paramètres de requête : refusée en NOMMANT le champ ────────

def _entier(valeur, champ):
    """Un identifiant entier, ou ``None`` quand le filtre est absent."""
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise DrfValidationError({
            champ: (f"Le filtre « {champ} » attend un identifiant "
                    f"(reçu : {valeur!r})."),
        })


def _statut(valeur):
    """Un statut du vocabulaire du serveur, ou ``None``.

    Un statut INCONNU est refusé : l'avaler rendrait la liste ENTIÈRE là où
    l'écran croit lire un sous-ensemble — exactement le mode de panne PV22.
    """
    if valeur in (None, ''):
        return None
    admis = [choix for choix, _ in Calepinage.Statut.choices]
    if valeur not in admis:
        raise DrfValidationError({
            'statut': (f"Statut inconnu : « {valeur} ». Statuts admis : "
                       f"{', '.join(admis)}."),
        })
    return valeur


def _booleen(valeur):
    """Un drapeau de corps de requête lu SANS deviner (défaut : faux)."""
    if isinstance(valeur, bool):
        return valeur
    return str(valeur or '').strip().lower() in ('1', 'true', 'vrai', 'oui')


def _moment(valeur):
    """Une date (ou un horodatage ISO), ou ``None`` — jamais une date devinée."""
    if valeur in (None, ''):
        return None
    moment = parse_datetime(valeur) or parse_date(valeur)
    if moment is None:
        raise DrfValidationError({
            'depuis': (f"Date illisible : « {valeur} ». Format attendu : "
                       "AAAA-MM-JJ (ou un horodatage ISO 8601)."),
        })
    return moment
