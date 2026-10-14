"""ERR-ENF11-FUZZ-GED — lecture SÛRE des identifiants, dates et textes d'un corps JSON
(``views.py`` est un fichier-mur : les aides vivent ici, importées par les vues)."""
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers as drf_serializers

from core.champs_stricts import ChaineStricte, EntierStrict


# Aucune clé primaire GED ne dépasse un entier PostgreSQL 32 bits : au-delà, la
# ligne n'existe pas (et la comparaison SQL, elle, déborderait).
_PK_MAX = 2147483647
ID_INEXISTANT = -1


def _borne_pk(n):
    return n if -_PK_MAX <= n <= _PK_MAX else ID_INEXISTANT


def _pk_ou_none(valeur):
    """Identifiant entier lu d'un corps JSON, ou ``None`` s'il n'en est pas un
    (bool, liste, objet, « abc », 2.5…). Ne lève jamais. Un entier hors de la
    plage 32 bits rend ``ID_INEXISTANT`` (aucune ligne : 404, jamais une 500)."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return _borne_pk(valeur)
    if isinstance(valeur, float) and valeur.is_integer():
        return _borne_pk(int(valeur))
    if isinstance(valeur, str) and valeur.strip().lstrip('-').isdigit():
        return _borne_pk(int(valeur.strip()))
    return None


def _pk(valeur, nom='detail'):
    """ERR-ENF11-FUZZ-GED — identifiant lu d'un CORPS JSON, rendu sûr pour
    ``.filter(pk=…)``.

    Absent (``None``, ``""``, ``"null"``) → ``None`` : l'appelant décide
    (« requis » 400 ou optionnel). MAL FORMÉ (``"abc"``, ``"{}"``, liste,
    objet, booléen, 2.5) → 400 nommant le champ : c'est une entrée invalide,
    pas un objet inconnu — le 404 « inconnu » reste réservé à un entier qui
    ne désigne aucune ligne visible (CI #956, core/tests/test_acal_500_journalise
    `test_fk_accolades_du_corps_400`). Avant : ``ValueError`` (500) ; puis
    ``None`` pour tout, qui confondait « mal formé » et « inconnu » en 404."""
    if valeur is None or (isinstance(valeur, str)
                          and valeur.strip() in ('', 'null')):
        return None
    pk = _pk_ou_none(valeur)
    if pk is None:
        raise drf_serializers.ValidationError(
            {nom: ['Identifiant entier attendu.']})
    return pk


def _pks(valeurs):
    """Liste d'identifiants sûrs (``pk__in``) : non-liste -> [] ; éléments
    invalides ignorés."""
    if not isinstance(valeurs, (list, tuple)):
        return []
    return [p for p in (_pk_ou_none(v) for v in valeurs) if p is not None]


def _date_iso(valeur):
    """Date ``AAAA-MM-JJ`` STRICTE (le schéma déclare ``format: date``) :
    ``parse_date`` acceptait ``2026-1-1`` ; un non-texte est refusé. ``None`` si
    invalide."""
    import re
    from django.utils.dateparse import parse_date
    if not isinstance(valeur, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}', valeur.strip()):
        return None
    try:
        return parse_date(valeur.strip())
    except ValueError:
        return None


def _txt(valeur, nom, max_length=None):
    """Texte optionnel lu d'un corps JSON, nettoyé : une valeur non chaîne
    (nombre, liste, objet) faisait lever ``AttributeError`` sur ``.strip()``
    (500) -> 400 nommant le champ. Le caractère NUL (refusé par PostgreSQL) et
    un texte plus long que la colonne cible (``max_length``) sont aussi un 400
    — c'étaient des 500 (``DataError``)."""
    if valeur is None:
        return ''
    if not isinstance(valeur, str):
        raise drf_serializers.ValidationError({nom: ['Chaîne attendue.']})
    if '\x00' in valeur:
        raise drf_serializers.ValidationError(
            {nom: ['Caractère nul interdit.']})
    valeur = valeur.strip()
    if max_length is not None and len(valeur) > max_length:
        raise drf_serializers.ValidationError(
            {nom: [f'{max_length} caractères au plus.']})
    return valeur


def _id_filtre(params, nom, *, null_ok=False):
    """Filtre de requête « identifiant » (``?folder=12``), STRICT : absent ->
    ``None`` ; ``null`` (si ``null_ok``) -> ``'null'`` ; entier -> ``int`` ;
    tout autre texte, VIDE compris, -> 400 nommant le paramètre (il était
    ignoré en silence). Hors plage 32 bits -> ``ID_INEXISTANT`` (liste vide)."""
    import re
    brut = params.get(nom)
    if brut is None:
        return None
    if null_ok and brut == 'null':
        return 'null'
    if re.fullmatch(r'-?[0-9]{1,30}', brut):
        return _borne_pk(int(brut))
    raise drf_serializers.ValidationError(
        {nom: ['Identifiant entier attendu.']})


def _entier_borne(params, nom, *, defaut, mini, maxi):
    """Paramètre de requête entier dans ``[mini, maxi]`` : absent -> ``defaut`` ;
    illisible, vide ou hors bornes -> 400 nommant le paramètre (il retombait
    sur le défaut ou était plafonné en silence)."""
    import re
    brut = params.get(nom)
    if brut is None:
        return defaut
    if re.fullmatch(r'-?[0-9]{1,30}', brut):
        n = int(brut)
        if mini <= n <= maxi:
            return n
    raise drf_serializers.ValidationError(
        {nom: [f'Entier entre {mini} et {maxi} attendu.']})


# ── Corps JSON VALIDÉS des actions lues à la main ────────────────────────────
# Ces serialiseurs sont aussi la déclaration OpenAPI : le composant garde le nom
# ``Ged…Corps`` de l'ancien ``inline_serializer`` (``openapi.py`` les ré-exporte).

def corps_valide(classe, request):
    """Valide ``request.data`` par ``classe`` (400 sinon) et rend les données."""
    serialiseur = classe(data=request.data)
    serialiseur.is_valid(raise_exception=True)
    return serialiseur.validated_data


def _id_corps(**kw):
    return EntierStrict(min_value=1, max_value=_PK_MAX, **kw)


def _non_vide(**kw):
    # Non blanc = ``allow_blank=False`` après rognage (DRF) : le motif publié
    # vient de ``ChaineStricte`` (non blanc ET sans NUL), pas d'un validateur.
    return ChaineStricte(**kw)


class _CourrielStrict(drf_serializers.EmailField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


@extend_schema_field(OpenApiTypes.DATE)
class _DateIsoStricte(drf_serializers.Field):
    """Date ``AAAA-MM-JJ`` stricte (le schéma dit ``format: date``)."""

    default_error_messages = {
        'invalid': 'Date invalide (format attendu : AAAA-MM-JJ).'}

    def to_internal_value(self, data):
        valeur = _date_iso(data)
        if valeur is None:
            self.fail('invalid')
        return valeur

    def to_representation(self, value):
        return value.isoformat()


class GedDemandeSignatureCorps(drf_serializers.Serializer):
    document = _id_corps()
    signataire_nom = _non_vide(max_length=255)
    signataire_email = _CourrielStrict(max_length=254)


class GedLegalHoldCorps(drf_serializers.Serializer):
    document = _id_corps()
    motif = ChaineStricte(required=False, allow_blank=True)


class GedMotifCorps(drf_serializers.Serializer):
    motif = ChaineStricte(required=False, allow_blank=True)


class GedArchiverLegalementCorps(drf_serializers.Serializer):
    motif = ChaineStricte(required=False, allow_blank=True)
    retain_until = _DateIsoStricte(required=False, allow_null=True)


class GedDemandeDispositionCorps(drf_serializers.Serializer):
    libelle = _non_vide(max_length=200)
    action = drf_serializers.ChoiceField(
        choices=['detruire', 'archiver'], required=False)
    documents = drf_serializers.ListField(
        child=_id_corps(), allow_empty=False, min_length=1)


class _ParamsTag(drf_serializers.Serializer):
    tag = _id_corps()


class _ParamsDossier(drf_serializers.Serializer):
    folder = _id_corps()


class _ParamsSignature(drf_serializers.Serializer):
    signataire_nom = ChaineStricte(
        required=False, allow_blank=True, max_length=255)
    signataire_email = _CourrielStrict(
        required=False, allow_blank=True, max_length=254)


_PARAMS_PAR_OPERATION = {
    'tagger': _ParamsTag, 'detaguer': _ParamsTag, 'deplacer': _ParamsDossier,
    'demander_signature': _ParamsSignature,
}


class GedOperationsLotCorps(drf_serializers.Serializer):
    # ERR-ENF11-FUZZ-GED : ``min_length`` publie ``minItems: 1`` (``[]``
    # était « conforme » puis refusé « liste vide »).
    documents = drf_serializers.ListField(
        child=_id_corps(), allow_empty=False, min_length=1)
    operation = drf_serializers.ChoiceField(choices=[
        'tagger', 'detaguer', 'deplacer', 'corbeille', 'telecharger_zip',
        'partager', 'demander_signature', 'demander_revue'])
    params = drf_serializers.DictField(required=False)

    def validate(self, attrs):
        classe = _PARAMS_PAR_OPERATION.get(attrs['operation'])
        if classe is not None:
            sous = classe(data=attrs.get('params') or {})
            sous.is_valid(raise_exception=True)
            attrs['params'] = dict(sous.validated_data)
        return attrs


def conflit_archivage(document):
    """Conflit d'ÉTAT de l'archivage légal (409), ou ``None`` : un document en
    corbeille ou déjà archivé ne s'archive pas — la saisie, elle, est valide."""
    from .models import ArchivageLegal
    if document.supprime_le is not None:
        return "Un document en corbeille ne peut pas être archivé légalement."
    if ArchivageLegal.objects.filter(document=document).exists():
        return "Ce document est déjà archivé légalement."
    return None


def lignes_csv_invalides(lignes):
    """Lignes d'un CSV d'import que la base refuserait (``nom`` plus long que la
    colonne, caractère NUL) : ``{n° de ligne: détail}``. Le ``nom`` de ces lignes
    est vidé pour que le service les rapporte en erreur de ligne SANS arrêter
    l'import (c'étaient des ``DataError`` = 500)."""
    invalides = {}
    for idx, ligne in enumerate(lignes or [], start=1):
        nul = any(chr(0) in str(v) for v in ligne.values() if v is not None)
        if nul:
            invalides[idx] = 'Caractère nul interdit.'
        elif len((ligne.get('nom') or '').strip()) > 255:
            invalides[idx] = 'Nom : 255 caractères au plus.'
        else:
            continue
        ligne['nom'] = ''
    return invalides


def refus_cycle_vie(exc, cible):
    """ERR-ENF11-FUZZ-GED — refus de ``change_lifecycle_status`` : 400 si
    ``cible`` n'est pas un statut du cycle (entrée invalide), 409 sinon (la
    transition est refusée par l'ÉTAT du document : déjà à ce statut,
    transition non permise)."""
    from rest_framework import status
    from rest_framework.response import Response

    from .models import LIFECYCLE_CHOICES
    connu = cible in {code for code, _ in LIFECYCLE_CHOICES}
    return Response({'detail': str(exc)}, status=(
        status.HTTP_409_CONFLICT if connu else status.HTTP_400_BAD_REQUEST))


def schema_groupe_conditions(profondeur=3):
    """ERR-ENF11-FUZZ-GED — l'arbre ``core.rules`` tel que
    ``validate_condition_group`` l'accepte, publié en REQUÊTE (il l'était en
    objet libre : ``{}``, le défaut, était « conforme » puis refusé en 400).
    Groupe ET/OU (``op`` facultatif seulement sans ``operator``), groupe NON
    (une seule condition) ou feuille (``field`` non vide + opérateur connu) ;
    déplié sur ``profondeur`` niveaux, sans référence récursive."""
    from core.rules import GROUP_OPERATORS, LEAF_OPERATORS
    feuille = {'type': 'object', 'required': ['field', 'operator'], 'properties': {
        'field': {'type': 'string', 'minLength': 1},
        'operator': {'type': 'string', 'enum': list(LEAF_OPERATORS)},
        'op': {'not': {'enum': list(GROUP_OPERATORS)}}}}
    if profondeur <= 0:
        return feuille
    enfants = schema_groupe_conditions(profondeur - 1)
    et_ou = {'type': 'object', 'required': ['conditions'],
             'anyOf': [{'required': ['op']}, {'not': {'required': ['operator']}}],
             'properties': {'op': {'type': 'string', 'enum': ['and', 'or']},
                            'conditions': {'type': 'array', 'minItems': 1,
                                           'items': enfants}}}
    non = {'type': 'object', 'required': ['op', 'conditions'], 'properties': {
        'op': {'type': 'string', 'enum': ['not']},
        'conditions': {'type': 'array', 'minItems': 1, 'maxItems': 1,
                       'items': enfants}}}
    return {'anyOf': [et_ou, non, feuille]}


class GroupeConditionsField(drf_serializers.JSONField):
    """Arbre de conditions ``core.rules`` validé AU CHAMP (création ET mise à
    jour : un PATCH posait ``{}`` sans contrôle) ; erreurs de
    ``validate_condition_group`` rendues sous le nom du champ (400)."""

    def to_internal_value(self, data):
        from core.rules import validate_condition_group
        valeur = super().to_internal_value(data)
        erreurs = validate_condition_group(valeur)
        if erreurs:
            raise drf_serializers.ValidationError(erreurs)
        return valeur


class _GroupeConditionsSchema(OpenApiSerializerFieldExtension):
    target_class = 'apps.ged.corps_requete.GroupeConditionsField'

    def map_serializer_field(self, auto_schema, direction):
        if direction == 'request':
            return schema_groupe_conditions()
        return auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
