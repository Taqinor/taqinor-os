"""FG17 — sérialiseur des modèles d'e-mail éditables (``EmailTemplate``)."""
import re

from rest_framework import serializers

from .models_email import EMAIL_TEMPLATE_PLACEHOLDERS, EmailTemplate


# Repère tout token de la forme {foo} dans un sujet/corps.
_PLACEHOLDER_RE = re.compile(r'\{[^{}]*\}')


def _unknown_placeholders(text, cle):
    """Tokens {…} présents dans ``text`` mais NON autorisés pour cette clé.

    Renvoie la liste, dans l'ordre et dédoublonnée, des tokens inconnus pour
    pouvoir nommer le fautif dans l'erreur FR.
    """
    allowed = set(EMAIL_TEMPLATE_PLACEHOLDERS.get(cle, []))
    seen = []
    for tok in _PLACEHOLDER_RE.findall(text or ''):
        if tok not in allowed and tok not in seen:
            seen.append(tok)
    return seen


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ['id', 'cle', 'sujet', 'corps']
        # company posée côté serveur (TenantMixin) — jamais depuis le corps.

    def _check_placeholders(self, attrs):
        # La clé effective (création : du corps ; mise à jour : conservée).
        cle = attrs.get('cle') or getattr(self.instance, 'cle', None)
        if not cle:
            return
        for champ, libelle in (('sujet', 'sujet'), ('corps', 'corps')):
            if champ not in attrs:
                continue
            inconnus = _unknown_placeholders(attrs.get(champ) or '', cle)
            if inconnus:
                autorises = ' '.join(
                    EMAIL_TEMPLATE_PLACEHOLDERS.get(cle, [])) or 'aucun'
                raise serializers.ValidationError({
                    champ: (
                        f'Placeholder non supporté dans le {libelle} : '
                        f'{", ".join(inconnus)}. '
                        f'Placeholders autorisés : {autorises}.'),
                })

    def validate(self, attrs):
        self._check_placeholders(attrs)
        # La clé d'un modèle existant ne se réaffecte pas (créer une autre ligne).
        if self.instance is not None:
            new_cle = attrs.get('cle')
            if new_cle and new_cle != self.instance.cle:
                raise serializers.ValidationError(
                    {'cle': "La clé d'un modèle d'e-mail ne peut pas changer — "
                            "créez-en un autre."})
        return attrs
