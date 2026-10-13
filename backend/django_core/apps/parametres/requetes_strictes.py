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
from rest_framework import serializers

from core.champs_stricts import (
    BooleenStrict, ChaineStricte, DecimalStricte, EntierStrict,
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
