"""Sérialiseur des modèles de documents éditables — D2/N60/N67/N26/N59.

Expose les portions de texte éditables du devis. ``company``, ``version`` et
``date_modification`` sont posés/gérés CÔTÉ SERVEUR — jamais lus du corps de la
requête. Les champs vides → repli moteur sur le littéral historique (le PDF reste
byte-identique tant que rien n'est édité)."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.champs_stricts import MOTIF_SANS_NUL

from .models_documents import DocumentTemplates
from .requetes_strictes import TypageStrictReglages

#: ENF11 (api-fuzz « rejected schema-compliant request ») — formes JSON des deux
#: champs libres du modèle, PUBLIÉES au schéma ET tenues par ``validate_*``
#: ci-dessous (une seule règle) : le schéma disait « n'importe quel JSON », le
#: serveur refusait ``true`` ou ``null`` (400) sur un corps « conforme ».
#: api-fuzz full 24/10 — une puce porteuse d'un caractère nul faisait lever la
#: base (JSONB, 500) : le motif ``MOTIF_SANS_NUL`` est publié ET appliqué.
TEXTE_PUCE = {'type': 'string', 'pattern': MOTIF_SANS_NUL}
SCHEMA_PUCES = {'type': 'array', 'items': TEXTE_PUCE, 'nullable': True}
SCHEMA_VARIANTE_CGV = {
    'type': 'object', 'nullable': True,
    'properties': {
        'titre': {**TEXTE_PUCE, 'nullable': True},
        'bullets': {'type': 'array', 'items': TEXTE_PUCE, 'nullable': True},
    },
}
SCHEMA_CGV_PAR_MODE = {
    'type': 'object',
    'properties': {'commercial': SCHEMA_VARIANTE_CGV,
                   'industriel': SCHEMA_VARIANTE_CGV},
    'additionalProperties': False,
}


def _texte_sans_nul(valeur):
    """Vrai si ``valeur`` est une chaîne sans caractère nul (``TEXTE_PUCE``)."""
    return isinstance(valeur, str) and chr(0) not in valeur


@extend_schema_field(SCHEMA_PUCES)
class PucesField(serializers.JSONField):
    """Liste de puces (textes) ou ``null``."""


@extend_schema_field(SCHEMA_CGV_PAR_MODE)
class CgvParModeField(serializers.JSONField):
    """Objet ``{commercial|industriel: {titre, bullets[]}}``."""


class DocumentTemplatesSerializer(TypageStrictReglages, serializers.ModelSerializer):
    cgv_bullets = PucesField(required=False, allow_null=True)
    cgv_par_mode = CgvParModeField(required=False)

    class Meta:
        model = DocumentTemplates
        fields = [
            'validite_badge_p1',
            'validite_onepage',
            'cgv_titre',
            'cgv_bullets',
            'cgv_par_mode',
            'garantie_titre',
            'garantie_detail',
            'garantie_perf_label',
            'bpa_titre',
            'bpa_mention',
            'acceptance_stamp',
            'version',
            'date_modification',
        ]
        # version/date posés serveur ; company jamais exposée ni acceptée.
        read_only_fields = ['version', 'date_modification']

    def validate_cgv_bullets(self, value):
        """Liste de chaînes (puces CGV) ou NULL. Refuse tout autre type."""
        if value is None:
            return None
        if not isinstance(value, list) or not all(
                _texte_sans_nul(x) for x in value):
            raise serializers.ValidationError(
                'Les puces des conditions générales doivent être une liste '
                'de textes.')
        return list(value)

    #: CIQ218 — les deux modes C&I qui portent leurs propres conditions.
    MODES_CGV_CI = ('commercial', 'industriel')

    def validate_cgv_par_mode(self, value):
        """CIQ218 — ``{commercial|industriel: {titre, bullets[]}}`` ou ``{}``.
        Refuse un autre mode ou une forme inattendue (message français)."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les conditions générales par mode doivent être un objet '
                '{commercial: {titre, bullets}, industriel: {…}}.')
        propre = {}
        for mode, variante in value.items():
            if mode not in self.MODES_CGV_CI:
                raise serializers.ValidationError(
                    f'Mode « {mode} » inconnu : seuls commercial et '
                    'industriel portent des conditions générales C&I.')
            if variante is None:
                continue
            titre = puces = None
            if isinstance(variante, dict):
                titre, puces = variante.get('titre'), variante.get('bullets')
            if (not isinstance(variante, dict)
                    or not (titre is None or _texte_sans_nul(titre))
                    or not (puces is None or (isinstance(puces, list) and all(
                        _texte_sans_nul(x) for x in puces)))):
                raise serializers.ValidationError(
                    f'cgv_par_mode.{mode} : attendu {{titre, bullets: [...]}} '
                    'avec des textes.')
            puces = [x for x in puces or [] if x.strip()]
            titre = (titre or '').strip()
            if puces or titre:
                propre[mode] = {'titre': titre, 'bullets': puces}
        return propre
