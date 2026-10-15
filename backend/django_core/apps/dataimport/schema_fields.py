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


class BooleenFormulaire(serializers.BooleanField):
    """Drapeau d'un corps ``multipart`` (toujours reçu en TEXTE) : seules les
    valeurs ``true`` / ``false`` (casse libre) sont des booléens. DRF lit aussi
    ``1``, ``on``, ``yes``… — un entier ou un objet JSON sérialisé en formulaire
    (``{}``) n'est PAS un booléen au schéma et était pris pour « faux » en
    silence (api-fuzz, ``ecraser`` / ``rollback_on_error``).

    Une valeur blanche (``ecraser=``) est lue comme une valeur — donc refusée —
    et non comme une absence (le comportement « formulaire HTML » de DRF est
    désactivé ; la désérialisation se fait sur un dict simple, voir
    ``views._options_import``)."""

    def get_value(self, dictionary):
        return dictionary.get(self.field_name, serializers.empty)

    def to_internal_value(self, data):
        if isinstance(data, bool):
            return data
        if isinstance(data, str) and data.lower() in ('true', 'false'):
            return data.lower() == 'true'
        self.fail('invalid', input=data)
