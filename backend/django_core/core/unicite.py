"""ENF2 (C6) — unicité PAR SOCIÉTÉ validée AVANT l'écriture en base.

Le problème (api-fuzz du 07/10/2026, ~40 routes) : la plupart des modèles
scopés société portent une contrainte ``UniqueConstraint(fields=['company',
'nom'])`` (ou ``unique_together``). DRF sait générer un
``UniqueTogetherValidator`` — mais SEULEMENT quand tous les champs de la
contrainte sont des champs du serializer. Or ``company`` n'y est JAMAIS (règle
multi-tenant : la société est posée côté serveur par ``perform_create``, jamais
lue du corps). Résultat : aucun contrôle avant l'INSERT, et un doublon
(``POST {"nom": "0"}`` deux fois) remontait en ``IntegrityError`` → 500
« Une erreur inattendue s'est produite ».

La correction, générique (aucun serializer à modifier un par un) :

* ``brancher_unicite_societe(serializer, request)`` — appelé par
  ``core.mixins.TenantMixin.get_serializer`` — enchaîne, APRÈS le
  ``validate()`` du serializer, un ``UniciteSocieteValidator`` qui, pour chaque contrainte
  d'unicité du modèle contenant ``company``, cherche une ligne existante de la
  MÊME société portant les mêmes valeurs. Trouvée → ``ConflitUnicite`` (409,
  code ``unique_conflict``, ``fields`` nomme les champs en cause) AVANT tout
  effet de bord.
* le filet de sécurité (course entre deux requêtes, vue hors ``TenantMixin``)
  reste la contrainte en base : ``core.exceptions`` traduit une violation
  d'unicité Postgres (SQLSTATE 23505) en ce MÊME 409 — jamais un 500.

Sémantique alignée sur Postgres pour ne JAMAIS refuser ce que la base
accepterait : les contraintes CONDITIONNELLES ou à EXPRESSIONS sont ignorées
(le filet en base les couvre), une valeur ``NULL`` désactive le contrôle
(``NULL`` ≠ ``NULL`` en unicité), et la recherche passe par
``_base_manager`` (les lignes « archivées »/supprimées en douceur occupent
aussi la contrainte).

``core`` reste FONDATION : aucun import d'app domaine — les modèles sont lus
réflexivement via le registre d'applications Django.
"""
from __future__ import annotations

import functools
import re

from rest_framework import serializers, status
from rest_framework.exceptions import APIException

CHAMP_SOCIETE = 'company'


class ConflitUnicite(APIException):
    """409 — l'enregistrement demandé existe déjà pour cette société.

    ``detail`` est le message humain ; ``champs`` (liste) nomme les champs de
    la contrainte (hors ``company``), repris par ``core.exceptions`` dans la
    clé ``fields`` de l'enveloppe d'erreur."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Un enregistrement identique existe déjà.'
    default_code = 'unique_conflict'

    def __init__(self, detail=None, champs=None):
        super().__init__(detail=detail or self.default_detail,
                         code=self.default_code)
        self.champs = list(champs or [])


def message_conflit(model, champs) -> str:
    """Message FR stable : « <verbose_name> existe déjà (champ, champ). »"""
    libelle = str(getattr(model._meta, 'verbose_name', '') or 'Enregistrement')
    libelle = libelle[:1].upper() + libelle[1:]
    if champs:
        return (f'{libelle} : un enregistrement avec la même valeur '
                f'({", ".join(champs)}) existe déjà.')
    return f'{libelle} : un enregistrement identique existe déjà.'


@functools.lru_cache(maxsize=None)
def contraintes_societe(model) -> tuple[tuple[str, ...], ...]:
    """Tuples de NOMS de champs des contraintes d'unicité du modèle qui
    contiennent ``company`` — inconditionnelles et sans expression seulement."""
    try:
        model._meta.get_field(CHAMP_SOCIETE)
    except Exception:  # noqa: BLE001 — modèle sans champ company
        return ()
    groupes: list[tuple[str, ...]] = []
    for groupe in model._meta.unique_together or ():
        groupes.append(tuple(groupe))
    for contrainte in model._meta.constraints:
        champs = tuple(getattr(contrainte, 'fields', ()) or ())
        if not champs or getattr(contrainte, 'condition', None) is not None:
            continue
        if getattr(contrainte, 'expressions', ()):
            continue
        if getattr(contrainte, 'nulls_distinct', None) is False:
            continue
        # UniqueConstraint seulement (CheckConstraint n'a pas de `fields`).
        groupes.append(champs)
    vus: list[tuple[str, ...]] = []
    for groupe in groupes:
        if CHAMP_SOCIETE in groupe and len(groupe) > 1 and groupe not in vus:
            vus.append(groupe)
    return tuple(vus)


@functools.lru_cache(maxsize=1)
def _index_contraintes() -> dict:
    """Nom de contrainte Postgres → (modèle, champs hors société)."""
    from django.apps import apps as django_apps
    index = {}
    for model in django_apps.get_models():
        for contrainte in model._meta.constraints:
            nom = getattr(contrainte, 'name', None)
            champs = tuple(getattr(contrainte, 'fields', ()) or ())
            if nom and champs:
                index[nom] = (model, tuple(
                    c for c in champs if c != CHAMP_SOCIETE))
    return index


@functools.lru_cache(maxsize=1)
def _index_tables() -> dict:
    """Nom de table → modèle concret (non proxy)."""
    from django.apps import apps as django_apps
    return {m._meta.db_table: m for m in django_apps.get_models()
            if not m._meta.proxy}


_CLE_DETAIL = re.compile(r'Key \((?P<colonnes>[^)]*)\)=')


def decrire_contrainte(nom_contrainte, table=None, detail=None):
    """(modèle, champs hors société) d'une violation d'unicité.

    D'abord par le NOM de la contrainte (``UniqueConstraint`` nommée) ; sinon
    (``unique_together`` porte un nom généré, index unique brut) par la table
    et les colonnes que Postgres cite dans son DETAIL (« Key (company_id,
    nom)=(…) already exists. ») — jamais les VALEURS, seulement les noms de
    colonnes. (None, ()) si rien n'est reconnu."""
    if nom_contrainte and nom_contrainte in _index_contraintes():
        return _index_contraintes()[nom_contrainte]
    model = _index_tables().get(table) if table else None
    if model is None:
        return None, ()
    champs = []
    trouve = _CLE_DETAIL.search(detail or '')
    if trouve:
        par_colonne = {f.column: f.name for f in model._meta.concrete_fields}
        for colonne in trouve.group('colonnes').split(','):
            nom = par_colonne.get(colonne.strip().strip('"'))
            if nom and nom != CHAMP_SOCIETE:
                champs.append(nom)
    return model, tuple(champs)


class UniciteSocieteValidator:
    """Validateur de serializer : refuse (409) un doublon par société."""

    requires_context = True

    def __init__(self, model, company_id):
        self.model = model
        self.company_id = company_id

    def __call__(self, attrs, serializer):
        instance = getattr(serializer, 'instance', None)
        company_id = self.company_id
        if company_id is None and instance is not None:
            company_id = getattr(instance, 'company_id', None)
        if company_id is None or not isinstance(attrs, dict):
            return
        for groupe in contraintes_societe(self.model):
            filtre = self._filtre(groupe, attrs, instance)
            if filtre is None:
                continue
            qs = self.model._base_manager.filter(
                company_id=company_id, **filtre)
            if instance is not None and getattr(instance, 'pk', None):
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                champs = [c for c in groupe if c != CHAMP_SOCIETE]
                raise ConflitUnicite(
                    message_conflit(self.model, champs), champs=champs)

    def _filtre(self, groupe, attrs, instance):
        filtre = {}
        for nom in groupe:
            if nom == CHAMP_SOCIETE:
                continue
            champ = self.model._meta.get_field(nom)
            if nom in attrs:
                valeur = attrs[nom]
                cle = nom
            elif instance is not None:
                cle = getattr(champ, 'attname', nom)
                valeur = getattr(instance, cle, None)
            else:
                # Valeur inconnue avant l'écriture (défaut de modèle, champ
                # posé par la vue) : le filet en base reste le juge.
                return None
            if valeur is None:
                return None
            filtre[cle] = valeur
        return filtre or None


def brancher_unicite_societe(serializer, request) -> None:
    """Branche ``UniciteSocieteValidator`` sur un ModelSerializer d'écriture.

    Sans effet pour une lecture (pas de ``data``), un ``many=True``, un
    serializer non-modèle ou un modèle sans contrainte « par société »."""
    if not isinstance(serializer, serializers.ModelSerializer):
        return
    if not hasattr(serializer, 'initial_data'):
        return
    model = getattr(getattr(serializer, 'Meta', None), 'model', None)
    if model is None or not contraintes_societe(model):
        return
    if getattr(serializer, '_unicite_societe_branchee', False):
        return
    user = getattr(request, 'user', None)
    company_id = getattr(user, 'company_id', None) if user is not None else None
    validateur = UniciteSocieteValidator(model, company_id)
    validate_origine = serializer.validate

    # Branché APRÈS le ``validate()`` propre du serializer (et non dans
    # ``validators``, qui passent AVANT lui) : un contrôle de doublon métier
    # déjà écrit par l'app garde la main et son 400 inchangé ; ce filet ne
    # répond que pour ce que l'app ne contrôlait pas.
    def validate(attrs):
        attrs = validate_origine(attrs)
        validateur(attrs, serializer)
        return attrs

    serializer.validate = validate
    serializer._unicite_societe_branchee = True
