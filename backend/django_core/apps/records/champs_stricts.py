"""ERR-ENF11-FUZZ (2e tour) — champs de sérialiseur à la forme EXACTE du schéma.

Complète ``core.champs_stricts`` (texte / booléen stricts) sur deux points que le
fuzz API relève comme « API accepted schema-violating request » :

* ``ChaineBornee`` — ``CharField`` mesure ``max_length`` APRÈS avoir retiré les
  blancs de bord : une chaîne plus longue que le ``maxLength`` publié, dont le
  excédent est fait de blancs de bord, était acceptée. La longueur BRUTE est
  contrôlée d'abord.
* ``DecimalLitteral`` — ``Decimal()`` lit ``"1e1"``, ``" 8"``, ``"+8"``,
  ``"8_0"`` ou des chiffres non latins, que le motif publié refuse : seule la
  forme littérale ASCII (``-?[0-9]+(.[0-9]+)?``) passe.

Ces briques vivent sous ``apps/records`` (app fondation, importable partout)
et non sous ``core/``.
"""
import re

from django.db import models
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChaineStricte, DecimalStricte

_DECIMAL_LITTERAL = re.compile(r'^-?[0-9]+(\.[0-9]+)?\Z')


class ChaineBornee(ChaineStricte):
    """Chaîne stricte dont la longueur BRUTE respecte ``max_length``."""

    def to_internal_value(self, data):
        if (isinstance(data, str) and self.max_length is not None
                and len(data) > self.max_length):
            self.fail('max_length', max_length=self.max_length)
        return super().to_internal_value(data)


class RegexStricte(ChaineStricte, serializers.RegexField):
    """``RegexField`` qui refuse les non-chaînes (400, pas de coercition) et
    publie son motif au schéma (``pattern``)."""


class DecimalLitteral(DecimalStricte):
    """Décimal-chaîne strict dont la forme est exactement celle du schéma."""

    def to_internal_value(self, data):
        if isinstance(data, str) and not _DECIMAL_LITTERAL.match(data):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsStrictsBornesMixin:
    """Mixin de ``ModelSerializer`` (à placer AVANT lui) : textes bornés sur la
    longueur brute et booléens stricts (décimaux inchangés)."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineBornee,
        models.TextField: ChaineBornee,
        models.BooleanField: BooleenStrict,
    }


class ChampsStrictsLitterauxMixin(ChampsStrictsBornesMixin):
    """Idem + décimaux en chaîne de forme littérale (``DecimalLitteral``) — pour
    les sérialiseurs dont les clients envoient déjà des décimaux en chaîne."""

    serializer_field_mapping = {
        **ChampsStrictsBornesMixin.serializer_field_mapping,
        models.DecimalField: DecimalLitteral,
    }
