from rest_framework import serializers
from .models import CustomFieldDef


class CustomFieldDefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldDef
        fields = ['id', 'module', 'code', 'libelle', 'type', 'options',
                  'obligatoire', 'visible_liste', 'ordre', 'actif']


def validate_custom_data(module, company, data):
    """Valide un dict custom_data contre les définitions actives du module.

    Renvoie le dict nettoyé (clés connues uniquement). Lève ValidationError si
    un champ obligatoire manque ou si un type est incohérent."""
    from rest_framework.exceptions import ValidationError
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValidationError({'custom_data': 'Format invalide.'})
    defs = {d.code: d for d in CustomFieldDef.objects.filter(
        company=company, module=module, actif=True)}
    clean = {}
    for code, d in defs.items():
        val = data.get(code)
        if val in (None, ''):
            if d.obligatoire:
                raise ValidationError(
                    {code: f'Le champ « {d.libelle} » est obligatoire.'})
            continue
        if d.type == 'number':
            try:
                val = float(val)
            except (TypeError, ValueError):
                raise ValidationError({code: 'Nombre attendu.'})
        elif d.type == 'boolean':
            val = bool(val) if isinstance(val, bool) else str(val).lower() in ('1', 'true', 'oui')
        elif d.type == 'choice':
            opts = d.options or []
            if opts and val not in opts:
                raise ValidationError({code: 'Choix invalide.'})
        clean[code] = val
    return clean
