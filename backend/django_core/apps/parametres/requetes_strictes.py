"""ENF11 — corps STRICTS des écritures en lot de Paramètres.

Les quatre points d'entrée « lot » (messages, modèles d'e-mail, statuts,
traductions) lisaient ``request.data`` à la main et IGNORAIENT ce qui ne
leur convenait pas (clé inconnue, type faux) : une requête que le schéma
publié déclare invalide répondait 200. Ces sérialiseurs sont la SOURCE du
schéma ET de la validation — le contrat et le serveur ne peuvent plus
diverger. Les noms de classe (suffixe « Serializer » retiré) restent ceux des
composants OpenAPI d'avant.
"""
from django.db import models as django_models
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import (
    BooleenStrict, ChaineStricte, DecimalSouple, DecimalStricte, EntierStrict,
    TypageStrictMixin,
)

from .models import MessageTemplate
from .statuses_defaults import VALID_DOMAINES


# ENF11 (api-fuzz « accepted schema-violating request ») — à poser en premier
# sur un ``ModelSerializer`` de Paramètres : textes (``CharField`` ET
# ``TextField``), booléens, entiers ET décimaux sont générés en version
# STRICTE. ``TypageStrictMixin`` (core) laisse ``TextField`` et décimaux passer
# par la coercition DRF : ``corps: 0`` ou ``taux: 20`` (nombre JSON pour un
# décimal publié « chaîne ») répondait 200 au lieu de 400. (Commentaire et non
# docstring : une docstring ici fuiterait dans la description OpenAPI de chaque
# sérialiseur qui n'en porte pas.)
class TypageStrictParametres(TypageStrictMixin):
    serializer_field_mapping = {
        **TypageStrictMixin.serializer_field_mapping,
        django_models.TextField: ChaineStricte,
        django_models.DecimalField: DecimalStricte,
    }


class DecimalSoupleReglages(DecimalSouple):
    """``DecimalSouple`` des réglages société : acceptation inchangée ; sa
    borne basse ``>= 0`` est publiée AUSSI sur la branche chaîne (voir
    ``_DecimalSoupleReglagesBorne``) — et appliquée telle quelle : ``"-0"``,
    que le motif sans signe refuse, est refusé aussi."""

    def to_internal_value(self, data):
        if (isinstance(data, str) and data.startswith('-')
                and self.min_value is not None and self.min_value >= 0):
            self.fail('min_value', min_value=self.min_value)
        return super().to_internal_value(data)


class _DecimalSoupleReglagesBorne(OpenApiSerializerFieldExtension):
    """api-fuzz full (24/10, ``PUT/PATCH parametres/update/``) — la branche
    NOMBRE publiait ``minimum: 0`` mais la branche CHAÎNE gardait un motif
    signé : ``"-.52"`` était conforme au schéma puis refusé en 400
    (« supérieure ou égale à 0 »). Borne ``>= 0`` → motif sans signe."""
    target_class = 'apps.parametres.requetes_strictes.DecimalSoupleReglages'
    priority = 1

    def map_serializer_field(self, auto_schema, direction):
        from core.champs_stricts import _DecimalChaineNonVide
        champ = self.target
        schema = _DecimalChaineNonVide(champ).map_serializer_field(
            auto_schema, direction)
        if (direction != 'request' or champ.min_value is None
                or champ.min_value < 0):
            return schema
        motif_plafond = _motif_plafond_puissance_dix(champ)
        for branche in schema.get('anyOf', ()):
            motif = branche.get('pattern')
            if motif and motif.startswith('^-?'):
                branche['pattern'] = motif_plafond or '^' + motif[3:]
        return schema


def _motif_plafond_puissance_dix(champ):
    """Motif non signé EXACT d'un décimal borné à ``[0, 10^k]`` (pourcentage
    ``[0, 100]``) : partie entière d'au plus ``k`` chiffres, ou ``10^k`` sans
    décimale non nulle — ``"150"`` passait le motif puis était refusé (400).
    ``None`` si le plafond n'est pas une puissance de dix."""
    plafond, decimales = champ.max_value, champ.decimal_places
    if plafond is None or decimales is None:
        return None
    texte = format(plafond, 'f')  # int 100 → "100.000000", Decimal → "100"
    if '.' in texte:
        texte = texte.rstrip('0').rstrip('.')
    if not (texte.startswith('1') and set(texte[1:]) == {'0'}):
        return None
    k = len(texte) - 1
    # Zéros de tête permis tant que la partie entière tient dans les
    # ``max_whole_digits`` signes du motif de ``core`` (``"099"`` passe).
    entiers = champ.max_whole_digits or k + 1
    zeros, zeros_plafond = max(entiers - k, 0), max(entiers - k - 1, 0)
    return (fr'^(?:0{{0,{zeros}}}\d{{1,{k}}}(?:\.\d{{0,{decimales}}})?'
            fr'|\.\d{{1,{decimales}}}'
            fr'|0{{0,{zeros_plafond}}}{texte}(?:\.0{{0,{decimales}}})?)$')


# ENF11 (api-fuzz « accepted schema-violating request ») — variante des écrans de
# RÉGLAGES société (profil, tarification, modèles de documents) : textes
# (``CharField`` ET ``TextField``) et booléens STRICTS, décimaux acceptés en
# CHAÎNE ou en NOMBRE JSON (l'écran en envoie des deux, la lecture sert des
# chaînes) et publiés ainsi (``DecimalSouple``) ; les entiers gardent la
# lecture souple de DRF (l'écran peut taper « 30 »). Un ``0`` pour un texte ou
# un booléen, une chaîne hors motif pour un décimal répondaient 200.
class TypageStrictReglages:
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        django_models.CharField: ChaineStricte,
        django_models.TextField: ChaineStricte,
        django_models.BooleanField: BooleenStrict,
        django_models.DecimalField: DecimalSoupleReglages,
    }


class FlottantStrict(serializers.FloatField):
    """Nombre JSON réel (entier ou flottant) : ``"12"``, ``true`` et ``null``
    déguisé sont refusés (400) au lieu d'être convertis ou remplacés par un
    défaut en silence."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        try:
            return super().to_internal_value(data)
        except OverflowError:  # entier JSON > 1e308 : ``float()`` déborde
            self.fail('invalid')


def valider_corps(serializer_class, request):
    """Corps validé (``ValidationError`` 400 sinon) — ``request.data`` reste
    la source des valeurs, déjà conformes."""
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class MessageTemplateEcritRequestSerializer(serializers.Serializer):
    cle = serializers.ChoiceField(
        choices=[c for c, _ in MessageTemplate.Cle.choices])
    corps_fr = ChaineStricte(
        required=False, allow_null=True, allow_blank=True)
    corps_darija = ChaineStricte(
        required=False, allow_null=True, allow_blank=True)
    reset = BooleenStrict(required=False)


class EmailTemplatesBulkLigneSerializer(serializers.Serializer):
    # Une clé retirée côté source est IGNORÉE par design (robustesse au
    # déploiement) : le schéma la déclare donc texte libre, pas énumération.
    cle = ChaineStricte()
    sujet = ChaineStricte(required=False, allow_null=True, allow_blank=True)
    corps = ChaineStricte(required=False, allow_null=True, allow_blank=True)


class EmailTemplatesBulkRequestSerializer(serializers.Serializer):
    templates = EmailTemplatesBulkLigneSerializer(many=True)


class StatutsBulkLigneSerializer(serializers.Serializer):
    cle = ChaineStricte()
    libelle = ChaineStricte(required=False, allow_null=True, allow_blank=True)
    # Plafond = borne d'un entier SQL : au-delà, l'écriture levait une erreur de
    # base (500) ; la borne est publiée au schéma. Un négatif reste ramené à 0
    # par la vue (comportement historique).
    ordre = EntierStrict(required=False, allow_null=True,
                         max_value=2147483647)
    actif = BooleenStrict(required=False)


class StatutsBulkRequestSerializer(serializers.Serializer):
    domaine = serializers.ChoiceField(choices=list(VALID_DOMAINES))
    statuts = StatutsBulkLigneSerializer(many=True, required=False)


class TraductionsBulkLigneSerializer(serializers.Serializer):
    # Une ligne de locale inconnue est IGNORÉE par design : texte libre au
    # schéma (le comportement tolérant est documenté, pas déguisé).
    locale = ChaineStricte()
    # 120 = longueur de la colonne ``TranslationOverride.key`` (une clé plus
    # longue levait une erreur de base — 500 — à l'écriture).
    key = ChaineStricte(max_length=120)
    value = ChaineStricte(required=False, allow_null=True, allow_blank=True)


class TraductionsBulkRequestSerializer(serializers.Serializer):
    items = TraductionsBulkLigneSerializer(many=True)
