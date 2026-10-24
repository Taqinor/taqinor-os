"""Les réglages société du module — CAL45 (endpoint posé par CAL16).

``GET /api/django/calepinage/parametres/`` rend les ONZE sections de ``ParametresCalepinage.SECTIONS``, toujours
toutes présentes (contrat ``contract_samples/parametres_calepinage.json``) :
une société qui n'a jamais rien réglé reçoit onze objets vides, ce qui veut
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
from drf_spectacular.utils import (
    extend_schema, extend_schema_field, inline_serializer,
)
from drf_spectacular.drainage import set_override
from rest_framework import serializers, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.champs_stricts import MOTIF_SANS_NUL
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.parseurs import PARSEURS_JSON
from core.permissions import ScopedPermission

from ..models import ParametresCalepinage
from ..permissions import CAL_GERER, CAL_VOIR
from ..selectors import (
    kits_de_pose_disponibles, parametres_de_societe, registre_des_reglages,
)
from ..services.parametres import (
    CaractereInterditEnCle, ReglageInterdit, ReglageInvalide,
    enregistrer_parametres,
)

__all__ = ['ParametresCalepinageView', 'SuggestionPenteIGNView']

#: ACAL288 — la clé DÉRIVÉE de la section ``documents`` (contrat
#: ``parametres_calepinage.json``) et son refus en écriture
#: (``exemple_refus_catalogue_rapport``).
CLE_CATALOGUE = 'catalogue_rapport'
MESSAGE_CATALOGUE = ("Clé dérivée en lecture seule : elle ne s'enregistre "
                     "pas.")


def _schema_gabarit():
    """api-fuzz (24/10/2026) — la forme d'UN gabarit, dérivée des constantes de
    ``services.gabarits`` (jamais une liste recopiée) : exactement ce que
    ``_gabarit`` accepte — clés admises seules, choix fermés, nombres bornés,
    comptes entiers ≥ 1, rives à 4 clés numériques. Un corps conforme passe,
    un corps hors forme est refusé 400 nommé par le serveur."""
    from ..services import gabarits as g
    nombre = {'type': 'number', 'minimum': 0}
    angle = {'type': 'number', 'minimum': 0, 'exclusiveMaximum': 90}
    props = {}
    for cle, _libelle in g.REGLAGES:
        if cle == 'libelle':
            props[cle] = {}
        elif cle == 'orientation':
            props[cle] = {'type': 'string', 'enum': list(g.ORIENTATIONS)}
        elif cle == 'famille':
            props[cle] = {'type': 'string', 'enum': list(g.FAMILLES)}
        elif cle == 'roofType':
            props[cle] = {'type': 'string', 'enum': list(g.TYPES_TOITURE)}
        elif cle == 'rives':
            props[cle] = {'type': 'object', 'additionalProperties': False,
                          'properties': {r: dict(nombre) for r in g.RIVES}}
        elif cle in ('facingManual', 'neededAuto'):
            props[cle] = {'type': 'boolean'}
        elif cle == 'priorite':
            props[cle] = {'type': 'integer'}
        elif cle in g.COMPTES:
            props[cle] = {'type': 'integer', 'minimum': 1}
        elif cle == 'facingAzimuthDeg':
            props[cle] = {'type': 'number', 'minimum': 0, 'maximum': 360}
        elif cle == 'chassis_sous_pente_deg':
            props[cle] = {'type': 'number', 'exclusiveMinimum': 0,
                          'exclusiveMaximum': 90}
        elif cle in ('pitchDeg', 'chassis_inclinaison_deg'):
            props[cle] = dict(angle)
        else:
            props[cle] = dict(nombre)
    return {'type': 'object', 'additionalProperties': False,
            'properties': props}


class _GabaritsDispositionField(serializers.DictField):
    """``gabarits_disposition`` : ``{nom: gabarit}`` — chaque valeur est un
    objet de la forme ``_schema_gabarit`` (un flottant ou une clé inconnue
    sont HORS schéma, comme le serveur les refuse)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        set_override(self, 'field', {
            'type': 'object', 'additionalProperties': _schema_gabarit()})


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


#: Fenêtres d'années publiées pour ``simulation.fenetre_annees`` : le serveur
#: lit « AAAA-AAAA » (début ≤ fin), ce qu'un schéma ne sait pas exprimer — le
#: contrat en publie des représentants (la saisie « [2015, 2024] » reste lue).
_FENETRES_ANNEES = ('2005-2020', '2010-2023', '2015-2024')

#: Valeurs que ``_booleen`` lit comme oui / non (``services/parametres.py``).
_MOTS_BOOLEENS = ('oui', 'vrai', 'true', '1', 'active', 'activee', 'activée',
                  'non', 'faux', 'false', '0', 'aucune', 'sans',
                  'desactivee', 'désactivée', 'inactive')


def _forme_publiee(forme):
    """La forme d'une ``table`` (``parametres_cles.FORMES_TABLES``) telle que
    le contrat la publie : la MÊME déclaration que le validateur d'écriture,
    copiée, dont chaque texte porte en plus le motif « sans NUL »."""
    if isinstance(forme, dict):
        publiee = {cle: _forme_publiee(sous) for cle, sous in forme.items()}
        if forme.get('type') == 'string':
            publiee['pattern'] = MOTIF_SANS_NUL
        return publiee
    if isinstance(forme, (list, tuple)):
        return [_forme_publiee(sous) for sous in forme]
    return forme


def _schema_valeur_de_cle(declaration, forme=None):
    """Le schéma de la ``valeur`` d'une clé à registre, tiré de son type
    déclaré (``parametres_cles.TYPES_CLES``) — jamais une seconde table.
    ``forme`` : celle d'une clé ``table`` (``FORMES_TABLES``)."""
    genre = declaration.get('type')
    bornes = {cle: declaration[cle] for cle in ('minimum', 'maximum')
              if cle in declaration}
    if genre in ('nombre', 'pourcentage', 'table_mensuelle'):
        return {'type': 'number', **bornes}
    if genre == 'entier':
        return {'type': 'integer', **bornes}
    if genre == 'enum':
        return {'type': 'string', 'enum': list(declaration['valeurs'])}
    if genre == 'booleen':
        return {'anyOf': [{'type': 'boolean'},
                          {'type': 'integer', 'enum': [0, 1]},
                          {'type': 'string', 'enum': list(_MOTS_BOOLEENS)}]}
    if genre == 'intervalle_annees':
        return {'type': 'string', 'enum': list(_FENETRES_ANNEES)}
    # ``table`` : la forme DÉCLARÉE de la clé, la même que le PUT applique.
    return _forme_publiee(forme)


def _schema_section_a_registre(section):
    """Une section À REGISTRE : AUCUNE clé hors registre, chaque clé
    ``{valeur, source, reference}`` (ou ``null`` pour la retirer)."""
    from ..services.parametres_cles import (
        SOURCES_ADMISES, forme_de_table, registre, type_de_cle,
    )

    entree = {'type': 'object', 'nullable': True,
              'additionalProperties': False,
              'required': ['valeur', 'source'], 'properties': {}}
    proprietes = {}
    for cle in registre(section):
        proprietes[cle] = dict(entree, properties={
            'valeur': _schema_valeur_de_cle(type_de_cle(section, cle),
                                            forme_de_table(section, cle)),
            'source': {'type': 'string', 'enum': list(SOURCES_ADMISES)},
            'reference': {'type': 'string', 'nullable': True,
                          'pattern': MOTIF_SANS_NUL}})
    return {'type': 'object', 'additionalProperties': False,
            'properties': proprietes}


#: Sections dont le vocabulaire est validé clé par clé côté serveur (chacune
#: a son normaliseur : ``services/site.py``, ``zones_reglementaires.py``,
#: ``degagements.py``, ``lestage.py``) et qui REFUSENT toute clé inconnue. Le
#: schéma de REQUÊTE n'en publie que l'objet vide — le vocabulaire détaillé
#: est celui de ``contract_samples/parametres_calepinage.json`` ; rien n'est
#: annoncé qui serait refusé.
_SECTIONS_A_VOCABULAIRE_FERME = ('imagerie', 'degagements', 'zones_types',
                                 'lestage')


def _champ_section(schema):
    @extend_schema_field(schema)
    class ChampSection(serializers.JSONField):
        pass

    return ChampSection(required=False)


def _sections_requete_resserrees():
    """CI #997 fuzz (2) — ``PUT parametres/`` : un objet « conforme » portant
    une clé de plus (``x-schemathesis-additional``) était refusé 400 « Réglage
    inconnu ». Le schéma de REQUÊTE dit désormais la vérité des six sections
    à vocabulaire fermé : les deux à registre clé par clé, les quatre autres
    en objet vide."""
    from ..services.parametres_cles import (
        SECTION_ELECTRIQUE_SOCIETE, SECTION_SIMULATION,
    )

    champs = {section: _champ_section({
        'type': 'object', 'additionalProperties': False})
        for section in _SECTIONS_A_VOCABULAIRE_FERME}
    for section in (SECTION_SIMULATION, SECTION_ELECTRIQUE_SOCIETE):
        champs[section] = _champ_section(_schema_section_a_registre(section))
    return champs


def _forme_reglages(nom, avec_registre=False, partielle=False):
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
    # CI #997 fuzz — le PUT est PARTIEL (sections absentes laissées telles
    # quelles, les écrans n'envoient qu'une section) : `partielle` les rend
    # facultatives dans le schéma de requête.
    requis = not partielle
    champs = {
        'imagerie': serializers.DictField(required=requis),
        'degagements': serializers.DictField(required=requis),
        'zones_types': serializers.DictField(required=requis),
        'gabarits_disposition': _GabaritsDispositionField(required=requis),
        'presets': serializers.DictField(required=requis),
        'favoris_materiel': serializers.DictField(required=requis),
        'norme_electrique': serializers.DictField(required=requis),
        'lestage': serializers.DictField(required=requis),
        # CALX145 — deux sections à REGISTRE : leurs clés admises sont
        # déclarées une par une dans ``services/parametres_cles.py``, donc
        # leur vocabulaire vit là, pas dans la forme HTTP.
        'simulation': serializers.DictField(required=requis),
        'electrique_societe': serializers.DictField(required=requis),
        # CALX307 — configuration documentaire ; ACAL288 : porte en lecture
        # la clé DÉRIVÉE ``catalogue_rapport``.
        'documents': serializers.DictField(required=requis),
    }
    if partielle:
        champs.update(_sections_requete_resserrees())
    if avec_registre:
        champs['registre'] = _forme_registre()
    return inline_serializer(nom, champs)


class ParametresCalepinageView(APIView):
    """Les réglages calepinage de la société de l'appelant."""

    # Fuzz CI #997 : sections = objets JSON ; un multipart n'en porte que des
    # chaînes (« doit être un objet (reçu : str) ») → corps JSON seul publié.
    parser_classes = PARSEURS_JSON
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

    # ENF11 (nocturne 15/10) — une clé de PREMIER niveau hors des sections
    # admises est refusée (« Section de réglages inconnue ») : le corps publié
    # le dit (additionalProperties false sur la liste du modèle).
    @extend_schema(request=_forme_reglages('CalepinageParametresRequete',
                                           partielle=True),
                   extensions={EXTENSION_CORPS_RESSERRE: {
                       'properties': {s: {} for s in ParametresCalepinage.SECTIONS},
                       'additionalProperties': False}},
                   responses={200: _forme_reglages(
                       'CalepinageParametresEcrite')})
    def put(self, request, *args, **kwargs):
        if request.META.get('CONTENT_LENGTH') in (None, '', '0'):
            # Corps absent : le schéma le déclare obligatoire.
            return Response(
                {'detail': "Corps de requête manquant : envoyez un objet "
                           "« section : réglages »."},
                status=status.HTTP_400_BAD_REQUEST)
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
            if isinstance(refus, CaractereInterditEnCle):
                # ENF11 — clé d'objet interdite : inexprimable au schéma → 409.
                return Response({refus.champ or 'detail': str(refus)},
                                status=status.HTTP_409_CONFLICT)
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
    roof_layout=inline_serializer('CalepinageSuggestionPenteDocument', dict(
        # ``min_length=1`` PUBLIE ``minItems: 1`` (``allow_empty=False`` seul ne
        # l'écrit pas au schéma) : le serveur refuse un document sans pan.
        zones=serializers.ListField(
            child=serializers.DictField(), allow_empty=False, min_length=1),
    )),
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
    # Corps JSON SEUL : ``roof_layout`` est un objet imbriqué (liste de pans) que
    # ni multipart (part texte, lue comme un document sans pan) ni urlencoded
    # ne portent — le schéma publié ne déclare que ``application/json``.
    parser_classes = [JSONParser]
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
        # UN prédicat avec le schéma publié : ``zones`` est une liste NON VIDE
        # de pans (objets). Une valeur d'un autre type n'est jamais « lue vide »
        # par le service (société en France : 200 à tort).
        zones = document.get('zones') if isinstance(document, dict) else None
        if not (isinstance(zones, list) and zones
                and all(isinstance(zone, dict) for zone in zones)):
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
