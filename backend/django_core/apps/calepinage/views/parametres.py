"""Les réglages société du module — CAL45 (endpoint posé par CAL16).

``GET /api/django/calepinage/parametres/`` rend les SEPT sections, toujours
toutes présentes (contrat ``contract_samples/parametres_calepinage.json``) :
une société qui n'a jamais rien réglé reçoit sept objets vides, ce qui veut
dire « comportement d'aujourd'hui, strictement inchangé » — jamais une clé
absente que l'écran devrait deviner.

CAL246 — la même réponse porte AUSSI ``kits`` : le catalogue de kits de pose
(``selectors.kits_de_pose_disponibles``, CAL198), RÉSOLU à la lecture — ce
n'est donc pas une section de plus de ``ParametresCalepinage`` (aucune
migration), et ``PUT`` le refuse à cette place comme toute clé inconnue. Le
catalogue lui-même se règle DANS la section ``presets`` (clé ``kits``,
SOLMVP15) : un seul chemin d'écriture, celui du domaine.

``PUT`` pose les sections fournies (mise à jour PARTIELLE) par le SEUL chemin
d'écriture du domaine, ``services.parametres.enregistrer_parametres`` : une
section inconnue est refusée en la NOMMANT, en français. La société vient
TOUJOURS de ``request.user`` — jamais d'un corps de requête.

Un GET n'écrit rien : le sélecteur est en lecture pure (un GET qui crée une
ligne en base est un GET qui ment).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from ..permissions import CAL_GERER, CAL_VOIR
from ..selectors import (
    kits_de_pose_disponibles, parametres_de_societe, registre_des_reglages,
)
from ..services.parametres import (
    ReglageInterdit, ReglageInvalide, enregistrer_parametres,
)

__all__ = ['ParametresCalepinageView', 'SuggestionPenteIGNView']

#: ACAL288 — la clé DÉRIVÉE de la section ``documents`` (contrat
#: ``parametres_calepinage.json``) et son refus en écriture
#: (``exemple_refus_catalogue_rapport``).
CLE_CATALOGUE = 'catalogue_rapport'
MESSAGE_CATALOGUE = ("Clé dérivée en lecture seule : elle ne s'enregistre "
                     "pas.")


def _catalogue_rapport():
    """``[{code, titre, obligatoire}]`` dans l'ordre du contrat
    ``rapport_etude.json`` (``sections_declarees``) — aucun second
    catalogue."""
    from ..services.rapport.contrat import sections_declarees

    return [{'code': section['code'], 'titre': section['titre'],
             'obligatoire': bool(section.get('obligatoire'))}
            for section in sections_declarees()]


def _refus_nomme(refus):
    """Le ``ValidationError`` de ``full_clean`` en corps 400 NOMMÉ : une
    section garde sa clé ; une clé qui n'est pas une section (le code de la
    section de rapport fautive) est rangée sous ``documents``."""
    from ..selectors import SECTIONS_PARAMETRES

    corps = {}
    for champ, messages in getattr(refus, 'message_dict', {}).items():
        texte = ' '.join(str(m) for m in messages)
        if champ in SECTIONS_PARAMETRES:
            corps[champ] = texte
        else:
            corps.setdefault('documents', {})[champ] = texte
    return corps or {'detail': ' '.join(str(m) for m in refus.messages)}


def _forme_registre():
    """CALX145/69 — la forme du ``registre`` publié : deux sections, chacune
    une LISTE de lignes ``{cle, libelle, unite, reference}`` (l'ordre du
    registre de ``services/parametres_cles.py``, jamais réordonné). Voir
    ``selectors.registre_des_reglages``."""
    return inline_serializer('CalepinageRegistreReponse', {
        'simulation': serializers.ListField(child=serializers.DictField()),
        'electrique_societe': serializers.ListField(
            child=serializers.DictField()),
    })


def _forme_reglages(nom, avec_registre=False):
    """YAPIC6/PACT7 — la forme DÉCLARÉE des réglages, tirée du contrat.

    Les sept sections sont celles de `contract_samples/
    parametres_calepinage.json` : ce sont des documents de réglage libres
    (chaque section a son propre vocabulaire, versionné dans le contrat),
    donc un `DictField` par section — pas un `dict` nu, que la garde
    `scripts/check_openapi_shapes.py` interdit à juste titre : une forme qui
    valide tout ne protège rien.

    ``avec_registre`` — CALX145/69 : ajoute la clé DÉRIVÉE ``registre``
    (labels/unités/références), publiée SEULEMENT sur les réponses (GET,
    PUT écrite) : comme ``kits`` (CAL246), ``PUT`` ne l'accepte jamais en
    entrée, donc absente de la forme de requête.
    """
    champs = {
        'imagerie': serializers.DictField(),
        'degagements': serializers.DictField(),
        'zones_types': serializers.DictField(),
        'gabarits_disposition': serializers.DictField(),
        'presets': serializers.DictField(),
        'favoris_materiel': serializers.DictField(),
        'gabarits_dossier': serializers.DictField(),
        'norme_electrique': serializers.DictField(),
        'lestage': serializers.DictField(),
        # CALX145 — deux sections à REGISTRE : leurs clés admises sont
        # déclarées une par une dans ``services/parametres_cles.py``, donc
        # leur vocabulaire vit là, pas dans la forme HTTP.
        'simulation': serializers.DictField(),
        'electrique_societe': serializers.DictField(),
        # CALX307 — configuration documentaire ; ACAL288 : porte en lecture
        # la clé DÉRIVÉE ``catalogue_rapport``.
        'documents': serializers.DictField(),
    }
    if avec_registre:
        champs['registre'] = _forme_registre()
    return inline_serializer(nom, champs)


class ParametresCalepinageView(APIView):
    """Les réglages calepinage de la société de l'appelant."""

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(responses={200: _forme_reglages(
        'CalepinageParametresReponse', avec_registre=True)})
    def get(self, request, *args, **kwargs):
        company = getattr(request.user, 'company', None)
        reponse = parametres_de_societe(company)
        # CAL246 — catalogue LU (AO), jamais stocké : ajouté à la réponse,
        # jamais accepté en écriture (PUT ne connaît que les 7 sections).
        reponse['kits'] = kits_de_pose_disponibles(company)
        # CALX145/69 — le registre des deux sections « simulation » et
        # « electrique_societe » (labels, unités, références doctrinales),
        # publié en LECTURE SEULE : l'écran n'a plus à le redéclarer,
        # ``services/parametres_cles.py`` reste la seule déclaration.
        reponse['registre'] = registre_des_reglages()
        # ACAL288 — le catalogue des sections du rapport d'étude, DÉRIVÉ du
        # contrat ``rapport_etude.json`` (jamais stocké, jamais accepté en
        # écriture) : l'écran coche parmi CES sections, dans CET ordre.
        reponse['documents'] = dict(reponse.get('documents') or {},
                                    catalogue_rapport=_catalogue_rapport())
        # ACAL129 — le fuseau EFFECTIF du site (imagerie, sinon profil
        # société) et sa provenance, en LECTURE SEULE : jamais accepté en
        # écriture.
        from ..services.site import fuseau_du_site

        effectif = fuseau_du_site(reponse.get('imagerie') or {},
                                  company=company)
        # Contrat ``site_imagerie.json`` : ``imagerie.site_effectif``, clé
        # DÉRIVÉE de la section (jamais stockée, retirée d'un PUT).
        reponse['imagerie'] = dict(reponse.get('imagerie') or {},
                                   site_effectif={
                                       'fuseau': effectif['fuseau'],
                                       'source': effectif['provenance'],
                                       'mention': effectif['mention']})
        return Response(reponse)

    @extend_schema(request=_forme_reglages('CalepinageParametresRequete'),
                   responses={200: _forme_reglages(
                       'CalepinageParametresEcrite')})
    def put(self, request, *args, **kwargs):
        donnees = request.data if isinstance(request.data, dict) else None
        if donnees is None:
            return Response(
                {'detail': "Le corps attendu est un objet « section : "
                           "réglages »."},
                status=status.HTTP_400_BAD_REQUEST)
        imagerie = donnees.get('imagerie')
        if isinstance(imagerie, dict) and 'site_effectif' in imagerie:
            # ACAL129 — clé DÉRIVÉE servie par GET : un aller-retour GET → PUT
            # la renvoie ; elle n'est jamais écrite.
            donnees = dict(donnees, imagerie={
                cle: valeur for cle, valeur in imagerie.items()
                if cle != 'site_effectif'})
        documents = donnees.get('documents')
        if isinstance(documents, dict) and CLE_CATALOGUE in documents:
            # ACAL288 — clé DÉRIVÉE : refusée en la nommant, rien d'écrit.
            return Response({'documents': {CLE_CATALOGUE: MESSAGE_CATALOGUE}},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            reglages = enregistrer_parametres(
                getattr(request.user, 'company', None), donnees,
                user=request.user)
        except ReglageInterdit as refus:
            # ACAL302 — clé de gouvernance changée sans
            # ``calepinage_approuver`` : 403 qui NOMME la clé, rien d'écrit.
            return Response({refus.champ: str(refus)},
                            status=status.HTTP_403_FORBIDDEN)
        except ReglageInvalide as refus:
            # ACAL132 — une clé d'une section À REGISTRE est nommée DANS sa
            # section (``{simulation: {sigma_modele_pct: motif}}``, contrat
            # ``parametres_calepinage.json::exemple_refus_type``).
            if getattr(refus, 'section', ''):
                return Response({refus.section: {refus.champ: str(refus)}},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as refus:
            # ACAL288 — ``full_clean`` refuse (ex. section obligatoire du
            # rapport décochée, code inconnu) : 400 qui NOMME le champ, jamais
            # un 500. Une clé hors sections vient de ``documents``.
            return Response(_refus_nomme(refus),
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(reglages)


#: ACAL134 — la forme DÉCLARÉE du geste « tout recalculer ».
FORME_RECALCUL = inline_serializer('CalepinageRecalculSimulations', dict(
    soumis=serializers.IntegerField(),
    jobs=serializers.ListField(child=serializers.DictField()),
    reste=serializers.IntegerField(),
))


class RecalculerSimulationsView(APIView):
    """ACAL134 — ``POST /calepinage/parametres/recalculer-simulations/``.

    Après un changement de réglage société, relance en tâche de fond chaque
    simulation PÉRIMÉE de la société de l'appelant (et d'elle seule), sans
    forcer : une simulation fraîche se court-circuite. Même droit que le PUT
    des réglages (``calepinage_gerer``).
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    @extend_schema(request=None, responses={202: FORME_RECALCUL})
    def post(self, request, *args, **kwargs):
        from ..services.simulation import recalculer_simulations_societe

        rendu = recalculer_simulations_societe(
            getattr(request.user, 'company', None), request.user)
        return Response(rendu, status=status.HTTP_202_ACCEPTED)


#: YAPIC6 — une APIView doit DÉCLARER sa forme (drf-spectacular ne la devine
#: pas) : c'est la réponse réelle de ``get``/``post`` ci-dessous, ni plus ni moins.
FORME_SUGGESTION_PENTE = inline_serializer('CalepinageSuggestionPenteReponse', dict(
    disponible=serializers.BooleanField(),
    pays_couvert=serializers.CharField(),
    source=serializers.CharField(),
    source_url=serializers.CharField(),
    suggestions=serializers.ListField(child=serializers.DictField()),
    detail=serializers.CharField(allow_blank=True),
))
FORME_SUGGESTION_PENTE_DEMANDE = inline_serializer('CalepinageSuggestionPenteDemande', dict(
    roof_layout=serializers.DictField(required=False),
))


class SuggestionPenteIGNView(APIView):
    """CAL237 — pente et azimut SUGGÉRÉS par pan, depuis l'IGN. France seule.

    La porte vit AVEC les réglages parce que c'est un RÉGLAGE qui la commande :
    le service n'existe que si la société a déclaré ``pays = 'fr'`` dans sa
    section « imagerie » (CAL47). Elle ne sert aucun objet métier — aucun
    identifiant de calepinage n'entre ici — et ne persiste RIEN : elle propose.

    * ``GET`` — le service est-il offert ici ? Réponse LOCALE : aucune requête
      sortante n'est émise, même quand il l'est.
    * ``POST`` — ``{"roof_layout": {…}}`` (ou le document nu) : une suggestion
      par pan exploitable, chacune portant sa SOURCE et son horodatage. Le
      document n'est pas modifié : c'est le dessinateur qui accepte ou jette,
      et une suggestion refusée laisse la pente saisie seule vérité.
    * ``403`` — société hors France : le motif FRANÇAIS nomme le champ
      (« pays »), et aucune requête sortante n'a été émise.
    """

    permission_classes = [ScopedPermission]
    read_permission = CAL_VOIR
    #: Proposer consomme du temps serveur et un quota externe : c'est une
    #: écriture au sens des permissions, comme le moteur (CAL22).
    write_permission = CAL_GERER

    @extend_schema(responses={200: FORME_SUGGESTION_PENTE})
    def get(self, request, *args, **kwargs):
        from ..services.lidar_ign import (
            PAYS_COUVERT, SOURCE, URL_SOURCE, service_disponible,
        )

        company = getattr(request.user, 'company', None)
        return Response({
            'disponible': service_disponible(company),
            'pays_couvert': PAYS_COUVERT,
            'source': SOURCE,
            'source_url': URL_SOURCE,
            'suggestions': [],
            'detail': '',
        })

    @extend_schema(request=FORME_SUGGESTION_PENTE_DEMANDE,
                   responses={200: FORME_SUGGESTION_PENTE})
    def post(self, request, *args, **kwargs):
        from ..services.lidar_ign import (
            PAYS_COUVERT, SOURCE, URL_SOURCE, ServiceIndisponible,
            suggerer_pentes,
        )

        donnees = request.data if isinstance(request.data, dict) else None
        document = None
        if isinstance(donnees, dict):
            document = donnees.get('roof_layout')
            if not isinstance(document, dict):
                document = donnees
        if not isinstance(document, dict) or not document.get('zones'):
            return Response(
                {'roof_layout': "Document de conception manquant : aucun pan "
                                "(« zones ») à analyser."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            suggestions = suggerer_pentes(
                getattr(request.user, 'company', None), document)
        except ServiceIndisponible as refus:
            return Response(
                {refus.champ or 'detail': str(refus),
                 'disponible': False,
                 'pays_couvert': PAYS_COUVERT,
                 'source': SOURCE,
                 'source_url': URL_SOURCE,
                 'suggestions': []},
                status=status.HTTP_403_FORBIDDEN)

        return Response({
            'disponible': True,
            'pays_couvert': PAYS_COUVERT,
            'source': SOURCE,
            'source_url': URL_SOURCE,
            'suggestions': suggestions,
            'detail': '' if suggestions else (
                "Aucun pan ne porte assez de points d'altitude exploitables : "
                "aucune pente n'est suggérée (rien n'est deviné)."),
        })
