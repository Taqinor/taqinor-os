"""ENF11 — sérialiseurs de modèle dont les champs texte/booléens/entiers
refusent la coercition silencieuse (``5`` → ``"5"``, ``"yes"`` → ``True``).

Cause PARTAGÉE des constats api-fuzz « API accepted schema-violating
request » sur les ``ModelSerializer`` : DRF convertit un type JSON voisin au
lieu de répondre 400, alors que le schéma OpenAPI déclare ``string`` /
``boolean`` / ``integer``. ``ChampsStrictsMixin`` redirige les champs
``CharField``/``TextField``/``BooleanField`` du modèle vers leurs variantes
strictes (``core.champs_stricts``) ; une requête valide est inchangée.
"""
from django.db import models
from rest_framework import serializers

from .champs_stricts import BooleenStrict, ChaineStricte


class EntierStrict(serializers.IntegerField):
    """Entier JSON réel : ``"5"``, ``5.0`` et ``true`` sont refusés (400)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsStrictsMixin:
    """À placer AVANT ``ModelSerializer`` dans les bases du sérialiseur."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.BooleanField: BooleenStrict,
    }
