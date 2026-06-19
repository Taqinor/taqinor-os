from rest_framework import serializers
from .models import CustomFieldDef


class CustomFieldDefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldDef
        fields = ['id', 'module', 'code', 'libelle', 'type', 'options',
                  'obligatoire', 'visible_liste', 'ordre', 'actif']

    def validate_options(self, value):
        # Normalise les options en liste de chaînes non vides (tolère un dict
        # ou des espaces parasites côté entrée).
        if value in (None, ''):
            return value
        if isinstance(value, dict):
            value = list(value.values())
        if not isinstance(value, list):
            raise serializers.ValidationError('Liste d’options attendue.')
        return [str(o).strip() for o in value if str(o).strip()]

    def validate(self, attrs):
        # L816 — un champ de type « choice » exige au moins une option : un
        # select sans options est inutilisable. On évalue le type et les
        # options résultants (création comme mise à jour partielle).
        instance = self.instance
        type_ = attrs.get('type', getattr(instance, 'type', None))
        if 'options' in attrs:
            options = attrs.get('options')
        else:
            options = getattr(instance, 'options', None)
        if type_ == 'choice' and not options:
            raise serializers.ValidationError(
                {'options': 'Un champ « Choix » exige au moins une option.'})

        # L814 — interdire le renommage de `code` (la clé JSON) dès qu'un
        # enregistrement porte une valeur custom_data pour ce champ : seules
        # les modifications de libellé/type/options sont permises ensuite.
        if instance is not None and 'code' in attrs \
                and attrs['code'] != instance.code:
            if _code_has_data(instance):
                raise serializers.ValidationError(
                    {'code': 'Code non modifiable : des enregistrements '
                             'portent déjà ce champ.'})
        return attrs


def _code_has_data(instance):
    """True si au moins un enregistrement du module porte une valeur non vide
    pour ``instance.code`` dans son ``custom_data`` (company-scopé). Sert à
    verrouiller le renommage du code (L814) sans migration destructive."""
    module = instance.module
    company = instance.company
    code = instance.code
    model = _module_model(module)
    if model is None:
        return False
    qs = model.objects.filter(company=company) \
        .filter(custom_data__has_key=code)
    for row in qs.values_list('custom_data', flat=True).iterator():
        if row and row.get(code) not in (None, ''):
            return True
    return False


def _module_model(module):
    """Modèle Django porteur du custom_data pour un module donné."""
    if module == 'lead':
        from apps.crm.models import Lead
        return Lead
    if module == 'client':
        from apps.crm.models import Client
        return Client
    if module == 'produit':
        from apps.stock.models import Produit
        return Produit
    return None


def validate_custom_data(module, company, data):
    """Valide un dict custom_data contre les définitions actives du module.

    Renvoie le dict nettoyé (clés connues uniquement). Lève ValidationError si
    un champ obligatoire manque ou si un type est incohérent."""
    from datetime import date, datetime
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
        elif d.type == 'date':
            # L815 — la date doit être au format ISO (AAAA-MM-JJ). On
            # tolère un objet date/datetime déjà typé.
            if isinstance(val, (date, datetime)):
                val = val.date().isoformat() if isinstance(val, datetime) \
                    else val.isoformat()
            else:
                try:
                    val = date.fromisoformat(str(val)[:10]).isoformat()
                except (TypeError, ValueError):
                    raise ValidationError({code: 'Date invalide.'})
        clean[code] = val
    return clean
