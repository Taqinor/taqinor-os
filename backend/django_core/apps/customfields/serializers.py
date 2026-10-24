import re

from django.db import models
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers
from core.champs_stricts import (
    BooleenStrict, ChampsStrictsEntiersMixin, IdInconnu404Mixin,
    MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL)
from core.mixins import SameCompanyFKSerializerMixin
from core.parseurs import ObjetJSON
from .models import (
    CustomFieldDef, CustomObjectDef, CustomRecord, FieldRolePermission,
)

# XPLT15 — clés reconnues du JSON `conditions` (visible/requis/lecture seule).
CONDITION_KEYS = ('visible_si', 'requis_si', 'lecture_seule_si')

#: Formule PUBLIÉE (api-fuzz 24/10 : ``formule`` libre « conforme » puis refusée
#: pour sa syntaxe, ``Syntaxe invalide``) : une opération entière sur des
#: nombres (``2 * 30 - 4``), que le serveur accepte toujours. La syntaxe ne
#: s'exprime pas en schéma ; le serveur, lui, accepte aussi les codes des
#: champs frères, comparaisons et fonctions sûres (``core.formula``).
MOTIF_FORMULE_PUBLIEE = (
    r'^(?:0|[1-9][0-9]{0,5})(?: ?[-+*] ?(?:0|[1-9][0-9]{0,5})){0,4}$')


class SlugStrict(serializers.SlugField):
    """``SlugField`` qui n'accepte que de vraies chaînes JSON, SANS rognage :
    DRF convertissait ``0`` en ``"0"`` (slug valide) et rognait les blancs
    autour, alors que le schéma publie ``^[-a-zA-Z0-9_]+$`` sur une chaîne —
    un entier ou ``" a "`` étaient acceptés (api-fuzz, ``code``)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


#: Mapping de champs STRICTS des sérialiseurs de ce module : texte, booléen et
#: entier de modèle n'acceptent que leur type JSON déclaré ; un ``SlugField``
#: (``code``) est une vraie chaîne au motif publié.
_MAPPING_STRICT = {
    **ChampsStrictsEntiersMixin.serializer_field_mapping,
    models.SlugField: SlugStrict,
}


class OptionsChamp(serializers.JSONField):
    """CI #1000 (api-fuzz « rejected schema-compliant request ») — ``options``
    d'un champ personnalisé : le schéma publiait « tout JSON » (``{}``) alors que
    ``validate_options`` refusait ``0``/``true``/un texte. UN SEUL prédicat,
    publié ET appliqué : liste de CHAÎNES (sans caractère nul), ``""`` ou
    ``null`` (aucune option) ; tout autre type JSON répond 400. L'exigence
    « un champ Choix porte au moins une option » dépend du ``type`` : elle est
    publiée sur le corps de création/remplacement (``corps_definition_resserre``)."""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override

        super().__init__(**kwargs)
        set_override(self, 'field', {'anyOf': [
            {'type': 'array', 'nullable': True,
             'items': {'type': 'string', 'pattern': MOTIF_SANS_NUL}},
            {'type': 'string', 'enum': ['']},
        ]})

    def to_internal_value(self, data):
        if data != '' and not (isinstance(data, list) and all(
                isinstance(o, str) and '\x00' not in o for o in data)):
            raise serializers.ValidationError('Liste d’options attendue.')
        return super().to_internal_value(data)


def corps_definition_resserre():
    """Règles du corps de CRÉATION / REMPLACEMENT d'une définition que le
    composant partagé ne peut pas porter (elles dépendent du ``type``) :
    un champ Choix exige au moins une option non vide ; un champ Relation, un
    module cible connu ; un champ calculé, une formule non vide. Combinées en
    ``allOf`` au corps de CETTE opération (``EXTENSION_CORPS_RESSERRE``).

    api-fuzz-full 24/10 (« Too many generated examples are filtered out ») :
    trois ``anyOf`` empilés en ``allOf`` obligeaient le générateur à les
    croiser (8 combinaisons, chacune refiltrée) ; la règle est maintenant UN
    SEUL ``anyOf`` de quatre branches mutuellement exclusives (les types sans
    exigence | choix | relation | calculé) — la même acceptation."""
    from . import registry
    types = CustomFieldDef.FieldType.values
    speciaux = ('choice', 'relation', 'formula')
    cibles = sorted(m for m in CustomFieldDef.Module.values
                    if registry.get_model(m) is not None)

    def exige(type_, **proprietes):
        return {'required': ['type', *proprietes], 'properties': {
            'type': {'type': 'string', 'enum': [type_]}, **proprietes}}

    return {'anyOf': [
        # ``type`` absent (défaut « texte ») ou sans exigence propre.
        {'properties': {'type': {'type': 'string', 'enum': [
            t for t in types if t not in speciaux]}}},
        exige('choice', options={
            'type': 'array', 'minItems': 1,
            'items': {'type': 'string',
                      'pattern': MOTIF_NON_BLANC_SANS_NUL}}),
        exige('relation',
              relation_module={'type': 'string', 'enum': cibles}),
        exige('formula', formule={
            'type': 'string', 'pattern': MOTIF_FORMULE_PUBLIEE}),
    ]}


class ConditionsChamp(ObjetJSON):
    """XPLT15 — ``conditions`` d'une définition : objet dont les SEULES clés
    sont ``CONDITION_KEYS``, chacune un arbre ``core.rules``. api-fuzz full
    24/10 — publié ``type: object`` libre, ``{"": …}`` était « conforme » puis
    refusé (« Clé(s) inconnue(s) ») : la forme exacte est publiée (clés
    fermées, arbre ``schema_arbre_conditions``) et le MÊME prédicat
    (``arbre_conditions_valide``) l'applique, avant la normalisation des
    caractères nuls d'``ObjetJSON``."""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override

        from core.champs_stricts import schema_arbre_conditions

        super().__init__(**kwargs)
        schema = {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                cle: schema_arbre_conditions() for cle in CONDITION_KEYS},
        }
        if self.allow_null:
            schema['nullable'] = True
        set_override(self, 'field', schema)

    def to_internal_value(self, data):
        from core.champs_stricts import arbre_conditions_valide
        from core.rules import validate_condition_group

        if isinstance(data, dict):
            inconnues = set(data) - set(CONDITION_KEYS)
            if inconnues:
                raise serializers.ValidationError(
                    'Clé(s) inconnue(s) : '
                    f'{", ".join(sorted(map(repr, inconnues)))}.')
            for cle, arbre in data.items():
                erreurs = validate_condition_group(arbre)
                if erreurs:
                    raise serializers.ValidationError(
                        f'{cle} : {"; ".join(erreurs)}')
                if not arbre_conditions_valide(arbre):
                    raise serializers.ValidationError(
                        f'{cle} : arbre de conditions non conforme au schéma '
                        'publié.')
        return super().to_internal_value(data)


class ModuleChamp(serializers.CharField):
    """ENF11 (api-fuzz) — ``module`` d'une définition de champ : chaîne libre
    côté DRF (un objet personnalisé pose ``custom:<code>``), mais le schéma
    publie les modules RÉELLEMENT acceptés (natifs + registre) ou le préfixe
    ``custom:`` — plus n'importe quelle chaîne que ``validate_module`` refuse."""

    def to_internal_value(self, data):
        if not isinstance(data, str):  # ``0`` n'est pas un module, c'est un entier
            self.fail('invalid')
        return super().to_internal_value(data)


class _ModulePublie(OpenApiSerializerFieldExtension):
    target_class = 'apps.customfields.serializers.ModuleChamp'

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        from . import registry
        modules = sorted(
            {m for m in CustomFieldDef.Module.values
             if len(m) <= 20} | {m for m in registry.registered_module_keys()
                                 if len(m) <= 20})
        # api-fuzz-full 24/10 (« Too many generated examples are filtered
        # out ») : le schéma empilait ``anyOf`` (énumération | motif) sur un
        # ``pattern`` DRF, un ``minLength`` et un ``maxLength`` -- le
        # générateur tirait puis refiltrait. UN SEUL motif, longueur incluse :
        # un module connu, ou ``custom:`` suivi de 1 à 13 signes (le module
        # tient en 20 signes). Même acceptation que ``validate_module``.
        alternatives = [re.escape(m) for m in modules]
        alternatives.append(r'custom:[^\u0000]{1,13}')
        return {'type': 'string',
                'pattern': '^(?:%s)$' % '|'.join(alternatives)}


class CustomFieldDefSerializer(serializers.ModelSerializer):
    serializer_field_mapping = _MAPPING_STRICT
    # XPLT16 — `module` reste un CharField explicite (pas un ChoiceField
    # auto-dérivé des choices du modèle) : un objet personnalisé pose ses
    # définitions sous ``custom:<code>`` (préfixe validé dans `validate`, la
    # liste fixe `Module.choices` reste par ailleurs le catalogue des modules
    # natifs — voir `validate` pour la double vérification).
    module = ModuleChamp(max_length=20)
    # ``JSONField`` publié `{}` (tout) alors que `validate` exige un objet :
    # `conditions: 1` était « conforme » puis refusé. Objet JSON ou null.
    conditions = ConditionsChamp(required=False, allow_null=True)
    options = OptionsChamp(required=False, allow_null=True)
    rollup_config = ObjetJSON(required=False, allow_null=True)

    class Meta:
        model = CustomFieldDef
        fields = ['id', 'module', 'code', 'libelle', 'type', 'options',
                  'obligatoire', 'visible_liste', 'ordre', 'actif',
                  'relation_module', 'conditions', 'ia_prompt', 'verrouille',
                  'formule', 'rollup_config']
        # NTEXT38 — le verrou ne se pose/retire QUE par les actions dédiées
        # ``verrouiller``/``deverrouiller`` (auditées) : un PATCH ordinaire ne
        # doit jamais pouvoir le retirer en passant.
        read_only_fields = ['verrouille']

    def to_representation(self, instance):
        # NTEXT9 — expose le niveau (masque/lecture/edition) applicable au
        # DEMANDEUR courant, pour que le générateur de formulaire (frontend)
        # désactive/masque le champ sans second appel. Absent de contexte
        # (pas de request/user) ⇒ 'edition', comportement actuel inchangé.
        rep = super().to_representation(instance)
        request = self.context.get('request')
        tier = getattr(getattr(request, 'user', None), 'menu_tier', None)
        from .services import niveau_pour_role
        rep['niveau_role'] = niveau_pour_role(instance, tier)
        return rep

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
        # Normalise les options en liste de chaînes non vides (tolère les
        # espaces parasites côté entrée) ; ``OptionsChamp`` a déjà exigé une
        # liste de chaînes, ``""`` ou ``null``.
        if value in (None, ''):
            return value
        propres = [o.strip() for o in value if o.strip()]
        # Un champ Choix dont une option est blanche est refusé (le schéma de
        # création publie « chaque option non vide ») — au lieu de l'écarter.
        if (self._type_vise() == CustomFieldDef.FieldType.CHOICE
                and len(propres) != len(value)):
            raise serializers.ValidationError(
                'Une option de choix ne peut pas être vide.')
        return propres

    def _type_vise(self):
        """Type de la définition en cours d'écriture (corps, sinon instance)."""
        brut = getattr(self, 'initial_data', None)
        if hasattr(brut, 'get') and 'type' in brut:
            return brut['type']
        return getattr(self.instance, 'type', CustomFieldDef.FieldType.TEXT)

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

        # NTEXT1 — un champ CALCULÉ exige une formule sûre, jamais saisie :
        # validée contre les codes des champs FRÈRES (même société+module),
        # et rejetée si elle référence un placeholder interdit (prix_achat…).
        if type_ == CustomFieldDef.FieldType.FORMULA:
            formule = attrs.get('formule', getattr(instance, 'formule', ''))
            module_value = attrs.get(
                'module', getattr(instance, 'module', None))
            request = self.context.get('request')
            company = getattr(instance, 'company', None) or getattr(
                getattr(request, 'user', None), 'company', None)
            siblings_qs = CustomFieldDef.objects.filter(
                company=company, module=module_value)
            if instance is not None:
                siblings_qs = siblings_qs.exclude(pk=instance.pk)
            sibling_codes = list(
                siblings_qs.values_list('code', flat=True))
            from .services import valider_formule_definition
            ok, erreur = valider_formule_definition(formule, sibling_codes)
            if not ok:
                raise serializers.ValidationError({'formule': erreur})

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
        # NTEXT1/NTEXT28 — un champ CALCULÉ (FORMULA/ROLLUP) n'est JAMAIS
        # saisi : toute valeur soumise sous son code est ignorée (jamais
        # persistée), la vraie valeur se calcule à la LECTURE (cf.
        # `services.calculer_champs_formule`/`calculer_champs_rollup`).
        if d.type in (CustomFieldDef.FieldType.FORMULA,
                      CustomFieldDef.FieldType.ROLLUP):
            continue
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


class FieldRolePermissionSerializer(IdInconnu404Mixin,
                                    SameCompanyFKSerializerMixin,
                                    serializers.ModelSerializer):
    """NTEXT9 — permission de champ par palier de rôle (admin)."""

    serializer_field_mapping = _MAPPING_STRICT

    # ENF17 — FK inscriptible bornée à la société : un id d'ailleurs reçoit la
    # réponse d'un id absent (400), à la création comme au PATCH.
    same_company_fields = ('field_def',)

    # SCA4 — le socle ``TenantModel`` horodate en ``created_at``/
    # ``updated_at`` ; l'API expose ``date_creation``/``date_modification``
    # (convention de l'app), jamais deux noms pour la même donnée.
    date_creation = serializers.DateTimeField(
        source='created_at', read_only=True)
    date_modification = serializers.DateTimeField(
        source='updated_at', read_only=True)

    class Meta:
        model = FieldRolePermission
        fields = ['id', 'field_def', 'role_tier', 'niveau',
                  'date_creation', 'date_modification']
        read_only_fields = ['date_creation', 'date_modification']

    def validate(self, attrs):
        field_def = attrs.get(
            'field_def', getattr(self.instance, 'field_def', None))
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if field_def is not None and company is not None \
                and field_def.company_id != company.id:
            raise serializers.ValidationError(
                {'field_def': 'Champ introuvable pour votre société.'})
        return attrs


# --- XPLT16 — objets personnalisés no-code ----------------------------------

class CustomObjectDefSerializer(serializers.ModelSerializer):
    serializer_field_mapping = _MAPPING_STRICT  # ``code`` (slug) = vraie chaîne
    actif = BooleenStrict(required=False)  # ENF11 : `0`/`"oui"` = 400

    class Meta:
        model = CustomObjectDef
        fields = ['id', 'code', 'libelle', 'icone', 'actif', 'verrouille',
                  'date_creation']
        # NTEXT38 — verrou en lecture seule ici (cf. CustomFieldDefSerializer).
        read_only_fields = ['date_creation', 'verrouille']


class ReordonnerDefinitionsSerializer(serializers.Serializer):
    """ENF11 — corps de `reorder` : `ids` obligatoire (liste d'entiers)."""
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2147483647))


class CustomRecordSerializer(serializers.ModelSerializer):
    # ``data`` est un objet {code_champ: valeur} (publié `{}` = tout, alors que
    # `validate_custom_data` refuse tout non-objet).
    data = ObjetJSON(required=False)

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

    def to_representation(self, instance):
        # NTEXT1 — les champs FORMULA se calculent à la LECTURE et se
        # fusionnent dans `data` pour l'API, SANS jamais être persistés
        # (`instance.data` en base ne les porte pas — cf. `validate_data`,
        # qui ne nettoie que les définitions non-FORMULA soumises).
        # NTEXT28 — même principe pour les champs ROLLUP, agrégés sur CET
        # enregistrement (son propre id = la cible de `cle_liaison`).
        rep = super().to_representation(instance)
        from .services import calculer_champs_formule, calculer_champs_rollup
        calcules = calculer_champs_formule(
            instance.objet.field_module, instance.company, instance.data)
        calcules.update(calculer_champs_rollup(
            instance.objet.field_module, instance.company, instance.pk))
        if calcules:
            rep['data'] = {**rep.get('data', {}), **calcules}
        return rep
