"""ENF10 — champ à choix fermé documenté par un ``pattern`` plutôt qu'un ``enum``.

Pourquoi : le post-traitement des énumérations de drf-spectacular regroupe TOUS
les ``enum`` du schéma par nom de champ ; deux champs homonymes (``decision``,
``format``, ``metric``…) portant des jeux de valeurs différents produisent des
avertissements de collision. Le ``pattern`` exprime exactement la même contrainte
(la validation serveur reste celle d'un ``ChoiceField``) sans entrer dans cette
mécanique de nommage.
"""
import re

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


def champ_choix(valeurs, **kwargs):
    valeurs = [str(v) for v in valeurs]
    motif = '^(?:%s)$' % '|'.join(re.escape(v) for v in valeurs)

    @extend_schema_field({'type': 'string', 'pattern': motif})
    class ChampChoix(serializers.ChoiceField):
        pass

    return ChampChoix(choices=valeurs, **kwargs)
