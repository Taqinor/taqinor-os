"""ENF11 — corps STRICTS des écritures en lot de Paramètres.

Les quatre points d'entrée « lot » (messages, modèles d'e-mail, statuts,
traductions) lisaient ``request.data`` à la main et IGNORAIENT ce qui ne
leur convenait pas (clé inconnue, type faux) : une requête que le schéma
publié déclare invalide répondait 200. Ces sérialiseurs sont la SOURCE du
schéma ET de la validation — le contrat et le serveur ne peuvent plus
diverger. Les noms de classe (suffixe « Serializer » retiré) restent ceux des
composants OpenAPI d'avant.
"""
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChaineStricte, EntierStrict

from .models import MessageTemplate
from .statuses_defaults import VALID_DOMAINES


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
    ordre = EntierStrict(required=False, allow_null=True)
    actif = BooleenStrict(required=False)


class StatutsBulkRequestSerializer(serializers.Serializer):
    domaine = serializers.ChoiceField(choices=list(VALID_DOMAINES))
    statuts = StatutsBulkLigneSerializer(many=True, required=False)


class TraductionsBulkLigneSerializer(serializers.Serializer):
    # Une ligne de locale inconnue est IGNORÉE par design : texte libre au
    # schéma (le comportement tolérant est documenté, pas déguisé).
    locale = ChaineStricte()
    key = ChaineStricte()
    value = ChaineStricte(required=False, allow_null=True, allow_blank=True)


class TraductionsBulkRequestSerializer(serializers.Serializer):
    items = TraductionsBulkLigneSerializer(many=True)
