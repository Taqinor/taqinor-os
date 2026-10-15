"""Sérialiseur du répertoire ``Tiers`` (ARC17).

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Le tenant ne peut donc pas être
usurpé depuis le corps de requête.
"""
from django.db import models
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChaineStricte, DecimalStricte

from .models import Tiers


class EmailTiers(ChaineStricte, serializers.EmailField):
    """E-mail facultatif d'une fiche : ``""`` quand il n'est pas renseigné.

    ENF11 — le schéma déclare « e-mail valide OU chaîne vide » dans les deux
    sens (la valeur servie est ``""`` pour une fiche sans e-mail, et le
    formulaire envoie ``""``).
    """


class EmailTiersExtension(OpenApiSerializerFieldExtension):
    target_class = 'apps.tiers.serializers.EmailTiers'
    # Priorité > 0 : sans elle, l'extension générique des chaînes strictes
    # (``core.champs_stricts._ChaineSansNul``, ``match_subclasses``, enregistrée
    # avant celle-ci) gagnait à égalité et publiait ``format: email`` aussi en
    # réponse — l'e-mail vide servi violait alors le schéma.
    priority = 1

    def map_serializer_field(self, auto_schema, direction):
        # « e-mail valide OU chaîne vide », dans les DEUX sens (CI #1001 fuzz :
        # la réponse ``{'type': 'string'}`` recevait ``format: email`` de
        # drf-spectacular, qui rejoue les validateurs du champ sur tout schéma
        # de type ``string`` — l'e-mail vide servi violait alors le schéma). Un
        # ``anyOf`` n'a pas de ``type`` : la rejouée ne s'y applique plus.
        schema = {'anyOf': [
            {'type': 'string', 'format': 'email', 'maxLength': 254},
            {'type': 'string', 'maxLength': 0}]}
        if direction == 'response':
            schema['description'] = "Vide quand l'e-mail n'est pas renseigné."
        return schema


class TiersSerializer(serializers.ModelSerializer):
    # ENF11 — aucune coercition silencieuse (0 -> "0", 1 -> True) : la requête
    # que le schéma déclare invalide répond 400.
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.EmailField: EmailTiers,
        models.BooleanField: BooleenStrict,
        models.DecimalField: DecimalStricte,
    }

    type_tiers_display = serializers.CharField(
        source='get_type_tiers_display', read_only=True)
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Tiers
        fields = [
            'id', 'type_tiers', 'type_tiers_display',
            'nom', 'prenom', 'raison_sociale', 'nom_complet',
            'telephone', 'whatsapp', 'email', 'adresse', 'ville',
            'gps_lat', 'gps_lng',
            'ice', 'rc', 'identifiant_fiscal', 'cin', 'rib',
            'is_client', 'is_fournisseur', 'is_partenaire', 'is_soustraitant',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'id', 'date_creation', 'date_modification',
        ]
