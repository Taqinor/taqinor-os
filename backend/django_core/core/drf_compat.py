"""ADCG61 — contrat API de DRF 3.15 conservé sous DRF 3.18.

La montée 3.15.2 → 3.18.2 est une montée de SÉCURITÉ (avis HIGH corrigés en
3.18.2) : elle ne doit changer AUCUNE réponse servie. Trois changements de
comportement des notes de version 3.16 → 3.18 la changeaient ; deux se
neutralisent ici, en un seul endroit, appelé par ``CoreConfig.ready()`` (le
troisième — erreurs de ``ListSerializer`` en dict indexé — se règle par
``REST_FRAMEWORK['LIST_SERIALIZER_ERRORS_AS_DICT'] = False``) :

1. ``models.BigAutoField`` / ``models.BigIntegerField`` ne sont plus mappés
   sur ``IntegerField`` mais sur le nouveau ``BigIntegerField`` — dont le
   message d'erreur « A valid biginteger is required. » n'a AUCUNE traduction
   française (l'API servirait de l'anglais) et qui change la classe de chaque
   ``id``. 24 mixins du projet COPIENT ``serializer_field_mapping`` au chargement
   de leur module : on corrige donc à la sortie de ``build_standard_field``
   (résolu à l'appel, hérité par tous) plutôt que dans le dict.

2. Unicité. ``get_uniqueness_extra_kwargs`` donne désormais ``default=None``
   (champ ``null``) ou ``default=''`` (texte ``blank``) aux champs d'une
   contrainte d'unicité, et compte les champs de la CONDITION d'une
   ``UniqueConstraint``. Effet mesuré : ``company`` (FK ``null=True``, LECTURE
   SEULE) reçoit un défaut, entre donc dans la carte des sources, et DRF génère
   des ``UniqueTogetherValidator`` qui EXIGENT ``sku`` / ``code_barres`` à la
   création d'un produit (400 « Ce champ est obligatoire. ») ; un
   ``HiddenField(default=None)`` peut même être AJOUTÉ pour un ``company``
   absent du sérialiseur (un PUT l'écrirait à NULL). Et
   ``get_unique_together_validators`` SAUTE une ``UniqueConstraint``
   conditionnelle dont un champ de condition n'est pas au sérialiseur (ex.
   ``Facture`` (devis, cle_tranche) hors annulées : doublon → IntegrityError au
   lieu du 400). On reprend les règles 3.15 : seuls les champs des
   ``unique_together`` / ``UniqueConstraint`` à plusieurs champs entièrement
   présents au sérialiseur reçoivent une option, le défaut ne vient que de
   ``auto_now(_add)`` ou d'un ``default`` du modèle, et chaque validateur porte
   les seuls champs de la contrainte sur un queryset filtré par sa condition.
"""
from collections import defaultdict

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.validators import UniqueTogetherValidator

_DEJA_APPLIQUE = '_taqinor_drf315_compat'


def _contraintes_315(model):
    """``get_unique_together_constraints`` de DRF 3.15 : (champs, queryset)."""
    for parent in [model] + list(model._meta.parents):
        for ensemble in parent._meta.unique_together:
            yield ensemble, model._default_manager
        for contrainte in parent._meta.constraints:
            if (isinstance(contrainte, models.UniqueConstraint)
                    and len(contrainte.fields) > 1):
                yield (contrainte.fields,
                       model._default_manager if contrainte.condition is None
                       else model._default_manager.filter(contrainte.condition))


def _noms_unicite_315(model, field_names):
    """Champs qu'une contrainte d'unicité marquait sous DRF 3.15 (avant la
    prise en compte des conditions et des défauts null/blank)."""
    noms = set()
    for ensemble, _queryset in _contraintes_315(model):
        if set(field_names).issuperset(ensemble):
            noms |= set(ensemble)
    for nom in field_names:
        try:
            champ = model._meta.get_field(nom)
        except FieldDoesNotExist:
            continue
        noms |= {getattr(champ, attr, None) for attr in (
            'unique_for_date', 'unique_for_month', 'unique_for_year')}
    noms.discard(None)
    return noms


def _a_un_defaut_315(champ):
    """Vrai si DRF 3.15 donnait un défaut à ce champ d'unicité (sinon il le
    rendait ``required``)."""
    return bool(getattr(champ, 'auto_now_add', None)
                or getattr(champ, 'auto_now', None)
                or champ.has_default())


def _envelopper_unicite(origine):
    def get_uniqueness_extra_kwargs(self, field_names, declared_fields, extra_kwargs):
        avant = {nom: dict(kw) for nom, kw in extra_kwargs.items()}
        extra_kwargs, hidden_fields = origine(
            self, field_names, declared_fields, extra_kwargs)
        model = getattr(self.Meta, 'model')
        noms_315 = _noms_unicite_315(model, field_names)

        for nom in list(hidden_fields):
            try:
                champ = model._meta.get_field(nom)
            except FieldDoesNotExist:
                continue
            if nom not in noms_315 or not _a_un_defaut_315(champ):
                del hidden_fields[nom]

        for nom in list(extra_kwargs):
            kw = extra_kwargs[nom]
            if kw == avant.get(nom):
                continue  # option non touchée par l'unicité
            try:
                champ = model._meta.get_field(nom)
            except FieldDoesNotExist:
                continue
            if nom not in noms_315:
                # DRF 3.15 ne touchait pas ce champ (champ de condition) :
                # options de l'appelant seules.
                if nom in avant:
                    extra_kwargs[nom] = avant[nom]
                else:
                    del extra_kwargs[nom]
            elif not _a_un_defaut_315(champ) and 'default' not in avant.get(nom, {}):
                # Défaut null/blank ajouté par DRF ≥ 3.16 : retour au
                # « required » de 3.15 (l'appelant garde le dernier mot).
                kw.pop('default', None)
                kw.setdefault('required', True)
                kw.update(avant.get(nom, {}))
        return extra_kwargs, hidden_fields

    get_uniqueness_extra_kwargs.__wrapped__ = origine
    return get_uniqueness_extra_kwargs


def get_unique_together_validators(self):
    """Port de ``ModelSerializer.get_unique_together_validators`` de DRF 3.15
    (le ``UniqueTogetherValidator`` de 3.18 sans condition se comporte comme
    celui de 3.15)."""
    sources = {
        champ.field_name: champ.source for champ in self._writable_fields
        if champ.source != '*' and '.' not in champ.source}
    sources.update({
        champ.field_name: champ.source for champ in self.fields.values()
        if champ.read_only and champ.default is not empty
        and champ.source != '*' and '.' not in champ.source})
    carte = defaultdict(list)
    for nom, source in sources.items():
        carte[source].append(nom)
    validateurs = []
    for ensemble, queryset in _contraintes_315(self.Meta.model):
        if not set(carte).issuperset(ensemble):
            continue
        for source in ensemble:
            assert len(carte[source]) == 1, (
                f"Unable to create `UniqueTogetherValidator` for "
                f"`{self.Meta.model.__name__}.{source}` as "
                f"`{self.__class__.__name__}` has multiple fields "
                f"({', '.join(carte[source])}) that map to this model field.")
        validateurs.append(UniqueTogetherValidator(
            queryset=queryset, fields=tuple(carte[f][0] for f in ensemble)))
    return validateurs


def _envelopper_entiers(origine):
    def build_standard_field(self, field_name, model_field):
        classe, kwargs = origine(self, field_name, model_field)
        if classe is getattr(serializers, 'BigIntegerField', None):
            classe = serializers.IntegerField  # mapping DRF 3.15
        return classe, kwargs

    build_standard_field.__wrapped__ = origine
    return build_standard_field


def appliquer():
    """Idempotent : n'enveloppe qu'une fois, même si ``ready()`` se rejoue."""
    modele = serializers.ModelSerializer
    if getattr(modele, _DEJA_APPLIQUE, False):
        return
    modele.build_standard_field = _envelopper_entiers(modele.build_standard_field)
    modele.get_uniqueness_extra_kwargs = _envelopper_unicite(
        modele.get_uniqueness_extra_kwargs)
    modele.get_unique_together_validators = get_unique_together_validators
    setattr(modele, _DEJA_APPLIQUE, True)
