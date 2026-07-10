from rest_framework import serializers
from .models import CustomFieldDef, CustomObjectDef, CustomRecord

# XPLT15 — clés reconnues du JSON `conditions` (visible/requis/lecture seule).
CONDITION_KEYS = ('visible_si', 'requis_si', 'lecture_seule_si')


class CustomFieldDefSerializer(serializers.ModelSerializer):
    # XPLT16 — `module` reste un CharField explicite (pas un ChoiceField
    # auto-dérivé des choices du modèle) : un objet personnalisé pose ses
    # définitions sous ``custom:<code>`` (préfixe validé dans `validate`, la
    # liste fixe `Module.choices` reste par ailleurs le catalogue des modules
    # natifs — voir `validate` pour la double vérification).
    module = serializers.CharField(max_length=20)

    class Meta:
        model = CustomFieldDef
        fields = ['id', 'module', 'code', 'libelle', 'type', 'options',
                  'obligatoire', 'visible_liste', 'ordre', 'actif',
                  'relation_module', 'conditions', 'ia_prompt']

    def validate_module(self, value):
        from .models import CustomFieldDef as _CFD
        from . import registry
        if value.startswith('custom:'):
            return value
        # ARC14 — un module est valide s'il fait partie de la liste NATIVE
        # historique (Module.values, catalogue informatif du modèle) OU s'il
        # a été enregistré dynamiquement par une app pilote via
        # ``registry.register`` (ex. contrats.contrat, flotte.vehicule).
        if value in _CFD.Module.values or registry.is_registered(value):
            return value
        raise serializers.ValidationError('Module inconnu.')

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

        # XPLT14 — un champ de type « relation » exige un module cible connu
        # (celui vers lequel pointe le lien) : sans quoi il est impossible de
        # résoudre id → libellé côté validation/affichage.
        if 'relation_module' in attrs:
            relation_module = attrs.get('relation_module')
        else:
            relation_module = getattr(instance, 'relation_module', None)
        if type_ == 'relation':
            if not relation_module:
                raise serializers.ValidationError(
                    {'relation_module': 'Un champ « Relation » exige un '
                                        'module cible.'})
            if _module_model(relation_module) is None:
                raise serializers.ValidationError(
                    {'relation_module': 'Module cible inconnu.'})

        # XPLT17 — un champ IA ne peut RÉFÉRENCER aucun placeholder interne
        # sensible (prix_achat/marge…) — validé à la DÉFINITION, pas
        # seulement à la génération, pour refuser tôt un prompt mal conçu.
        if type_ == 'ia':
            ia_prompt = attrs.get('ia_prompt', getattr(instance, 'ia_prompt', ''))
            from .services import validate_ia_prompt
            errors = validate_ia_prompt(ia_prompt)
            if errors:
                raise serializers.ValidationError({'ia_prompt': errors})

        # L814 — interdire le renommage de `code` (la clé JSON) dès qu'un
        # enregistrement porte une valeur custom_data pour ce champ : seules
        # les modifications de libellé/type/options sont permises ensuite.
        if instance is not None and 'code' in attrs \
                and attrs['code'] != instance.code:
            if _code_has_data(instance):
                raise serializers.ValidationError(
                    {'code': 'Code non modifiable : des enregistrements '
                             'portent déjà ce champ.'})

        # XPLT15 — valide la STRUCTURE des arbres de conditions à la
        # définition (jamais évaluée ici — juste refusée si mal formée).
        if 'conditions' in attrs:
            conditions = attrs.get('conditions')
            if conditions not in (None, ''):
                if not isinstance(conditions, dict):
                    raise serializers.ValidationError(
                        {'conditions': 'Objet attendu.'})
                unknown = set(conditions) - set(CONDITION_KEYS)
                if unknown:
                    raise serializers.ValidationError(
                        {'conditions': f'Clé(s) inconnue(s) : '
                                       f'{", ".join(sorted(unknown))}.'})
                from core.rules import validate_condition_group
                for key, tree in conditions.items():
                    errors = validate_condition_group(tree)
                    if errors:
                        raise serializers.ValidationError(
                            {'conditions': f'{key} : {"; ".join(errors)}'})
        return attrs


def _code_has_data(instance):
    """True si au moins un enregistrement du module porte une valeur non vide
    pour ``instance.code`` dans son ``custom_data`` (company-scopé). Sert à
    verrouiller le renommage du code (L814) sans migration destructive."""
    module = instance.module
    company = instance.company
    code = instance.code
    # XPLT16 — un objet personnalisé n'a pas de custom_data par modèle : ses
    # données vivent une ligne par enregistrement dans CustomRecord.data.
    if module.startswith('custom:'):
        from .models import CustomRecord
        object_code = module.split(':', 1)[1]
        qs = CustomRecord.objects.filter(
            company=company, objet__code=object_code, data__has_key=code)
        for row in qs.values_list('data', flat=True).iterator():
            if row and row.get(code) not in (None, ''):
                return True
        return False
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
    """Modèle Django porteur du custom_data pour un module donné.

    ARC14 — résout désormais via ``registry.get_model`` (registre
    data-driven : app_label/model_name déclarés par ``registry.register``,
    soit les 8 clés natives pré-enregistrées dans ``registry.py`` lui-même,
    soit une app pilote qui s'enregistre depuis son ``AppConfig.ready()``,
    ex. ``contrats.contrat``/``flotte.vehicule``). Renvoie ``None`` pour tout
    module inconnu — comportement inchangé pour les appelants existants.
    """
    from . import registry
    return registry.get_model(module)


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
            required = d.obligatoire
            # XPLT15 — requis_si : re-évalué CÔTÉ SERVEUR contre les valeurs
            # soumises (le masquage front n'est jamais fait confiance seul).
            requis_si = (d.conditions or {}).get('requis_si') \
                if isinstance(d.conditions, dict) else None
            if requis_si and not required:
                from core.rules import evaluate_condition_group
                required = evaluate_condition_group(requis_si, data)
            if required:
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
        elif d.type == 'relation':
            val = _validate_relation_value(d, company, val)
        elif d.type == 'fichier':
            val = _validate_fichier_value(d, val)
        clean[code] = val
    return clean


def _validate_relation_value(field_def, company, val):
    """XPLT14 — valide/normalise la valeur d'un champ type=relation.

    Accepte soit un id brut (int/str numérique), soit un dict déjà résolu
    ``{'id': ..., 'label': ...}`` (renvoyé par une saisie précédente). Résout
    toujours l'id CONTRE le module cible (company-scopé, jamais cross-tenant)
    et dénormalise le libellé au moment de la validation — le libellé stocké
    peut donc devenir périmé si l'enregistrement cible est renommé plus tard
    (comportement documenté, cohérent avec une dénormalisation en lecture
    rapide ; re-valider re-synchronise)."""
    from rest_framework.exceptions import ValidationError
    target_module = field_def.relation_module
    model = _module_model(target_module)
    if model is None:
        raise ValidationError(
            {field_def.code: 'Module cible du lien introuvable.'})
    raw_id = val.get('id') if isinstance(val, dict) else val
    try:
        raw_id = int(raw_id)
    except (TypeError, ValueError):
        raise ValidationError({field_def.code: 'Identifiant de lien invalide.'})
    obj = model.objects.filter(company=company, pk=raw_id).first()
    if obj is None:
        raise ValidationError(
            {field_def.code: 'Enregistrement lié introuvable.'})
    return {'id': obj.pk, 'label': _relation_label(obj)}


def _relation_label(obj):
    """Libellé lisible dénormalisé pour un enregistrement lié.

    La plupart des modèles cibles (Lead/Client/Produit/Fournisseur) n'ont pas
    de ``__str__`` personnalisé (le défaut Django serait « ClassName object
    (pk) », inutilisable en UI) : on préfère un champ nom/libellé usuel s'il
    existe, sinon ``str(obj)``."""
    for attr in ('nom', 'libelle', 'titre', 'reference', 'numero'):
        value = getattr(obj, attr, None)
        if value:
            prenom = getattr(obj, 'prenom', '') or ''
            return f'{value} {prenom}'.strip() if attr == 'nom' and prenom \
                else str(value)
    return str(obj)


def _validate_fichier_value(field_def, val):
    """XPLT14 — valide/normalise la valeur d'un champ type=fichier.

    Accepte soit un objet fichier brut (upload multipart — passé par
    ``store_attachment``), soit un dict déjà téléversé
    ``{'file_key', 'filename', 'size', 'mime'}`` (réédition sans re-upload)."""
    from rest_framework.exceptions import ValidationError
    if isinstance(val, dict):
        if not val.get('file_key'):
            raise ValidationError({field_def.code: 'Fichier invalide.'})
        return val
    if hasattr(val, 'read'):
        from apps.records.storage import store_attachment
        stored, error = store_attachment(val)
        if error:
            raise ValidationError({field_def.code: error})
        return stored
    raise ValidationError({field_def.code: 'Fichier attendu.'})


# --- XPLT16 — objets personnalisés no-code ----------------------------------

class CustomObjectDefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomObjectDef
        fields = ['id', 'code', 'libelle', 'icone', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class CustomRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomRecord
        fields = ['id', 'objet', 'data', 'created_by',
                  'date_creation', 'date_modification']
        read_only_fields = ['objet', 'created_by',
                            'date_creation', 'date_modification']

    def validate_data(self, value):
        # Valide/nettoie `data` contre les CustomFieldDef de l'objet (même
        # chemin que custom_data sur les modules natifs) — le module cible est
        # posé par la vue (objet résolu par l'URL), pas par le corps.
        objet = self.context.get('objet')
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if objet is None or company is None:
            return value
        return validate_custom_data(objet.field_module, company, value)
