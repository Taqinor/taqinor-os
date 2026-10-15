"""T9 — endpoints d'import réutilisable (dry-run + commit). Multi-tenant :
la société vient toujours du serveur, jamais du corps."""
import copy
import csv
import io
import logging

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, parser_classes
from core.champs_stricts import MOTIF_SANS_NUL, ChaineStricte
from core.parametres_requete import choix_ou_400
from core.conflit_etat import ConflitEtat
from core.parseurs import PARSEURS_JSON, ChoixDocumente, corps_valide
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser

from django.http import Http404

from authentication.permissions import (
    IsResponsableOrAdmin, HasPermissionAndRole,
)
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.selectors import get_company_object

from . import services
from .models import ImportJob
from .schema_fields import BooleenFormulaire
from .holidays_import import exporter_feries_csv, importer_feries_csv
from .translations_i18n import exporter_traductions_csv, importer_traductions_csv
from rest_framework import serializers as drf_serializers

logger = logging.getLogger(__name__)

# NTI18N29 — import de traductions : forme réelle du corps (multipart, un seul
# champ ``file``) et de la réponse (résumé de l'``ImportJob`` créé).
IMPORT_TRADUCTIONS_REQUEST = inline_serializer(
    'ImporterTraductionsRequest', {'file': serializers.FileField()})
IMPORT_TRADUCTIONS_RESPONSE = inline_serializer('ImporterTraductionsRapport', {
    'job': serializers.IntegerField(),
    'statut': serializers.CharField(),
    'total_lignes': serializers.IntegerField(),
    'created_count': serializers.IntegerField(),
    'updated_count': serializers.IntegerField(),
    'error_count': serializers.IntegerField(),
})

# NTI18N45 — import de fériés : même forme de corps/réponse que les
# traductions ci-dessus, mais déclarée séparément (composants uniques par
# usage — jamais la même instance de champ/serializer partagée entre deux
# schémas).
IMPORT_FERIES_REQUEST = inline_serializer(
    'ImporterFeriesRequest', {'file': serializers.FileField()})
IMPORT_FERIES_RESPONSE = inline_serializer('ImporterFeriesRapport', {
    'job': serializers.IntegerField(),
    'statut': serializers.CharField(),
    'total_lignes': serializers.IntegerField(),
    'created_count': serializers.IntegerField(),
    'updated_count': serializers.IntegerField(),
    'error_count': serializers.IntegerField(),
})

# QG4 — la CRÉATION de produits est restreinte partout (REST, import de
# données, OCR) aux rôles Directeur et Commercial responsable. Le commit
# d'import `products` porte donc la même garde que ProduitViewSet.create ;
# les autres cibles (leads, clients, fournisseurs, équipements…) gardent la
# règle historique (responsable/admin).
PRODUIT_CREATE_PERMISSION = HasPermissionAndRole(
    'stock_creer', 'Directeur', 'Commercial responsable')

_CIBLES = sorted(services.TARGETS)
_MODES = ['creer', 'maj', 'upsert']


class _OptionsImport(serializers.Serializer):
    """Champs FACULTATIFS du corps multipart de dry-run/commit : LE prédicat,
    à la fois publié au schéma (``_corps_import``) et appliqué par la vue
    (``_options_import``). ``file`` et ``target`` restent lus par ``_read``."""
    mapping = ChaineStricte(required=False, allow_blank=True)
    mode = serializers.ChoiceField(choices=_MODES, required=False)
    ecraser = BooleenFormulaire(required=False)
    external_system = ChaineStricte(required=False, allow_blank=True)


class _OptionsCommit(_OptionsImport):
    rollback_on_error = BooleenFormulaire(required=False)


def _corps_import(nom, options=_OptionsImport):
    """Corps multipart de dry-run/commit (``file`` + ``target`` obligatoires)."""
    champs = {
        'file': serializers.FileField(),
        'target': serializers.ChoiceField(choices=_CIBLES),
        **{cle: copy.deepcopy(champ)
           for cle, champ in options._declared_fields.items()},
    }
    return {'multipart/form-data': inline_serializer(nom, champs)}


def _options_import(request, options):
    """Options du formulaire validées par le serializer publié : ``mode`` hors
    liste, drapeau autre que ``true``/``false`` (``{}``, ``1``…) ou texte à
    caractère nul → 400 nommant le champ, jamais pris pour une valeur par
    défaut. Le corps multipart est lu en dict SIMPLE (dernière valeur d'une clé
    répétée) pour que ``ecraser=`` vide soit une valeur et non une absence."""
    serializer = options(data=request.data.dict(), context={'request': request})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


# ERR53 — Bornes anti-DoS : un upload trop gros (en octets) ou un fichier de
# trop de lignes est rejeté AVANT toute lecture/parsing intégral en mémoire,
# avec un 400 clair plutôt qu'une erreur générique avalée.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Mo
MAX_ROWS = 10000


def _read(request):
    f = request.FILES.get('file')
    target = request.data.get('target')
    if f is None:
        return None, None, Response({'detail': 'Aucun fichier fourni.'}, status=400)
    if target not in services.TARGETS:
        cibles = ', '.join(sorted(services.TARGETS))
        return None, None, Response(
            {'detail': f'Cible invalide (valeurs possibles : {cibles}).'},
            status=400)
    size = getattr(f, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        return None, None, Response(
            {'detail': 'Fichier trop volumineux : '
                       f'{size} octets (max {MAX_UPLOAD_BYTES}).'},
            status=400)
    return f, target, None


_VIEWS_DRY_RUN_REPONSE = inline_serializer('ViewsDryRunReponse', {
    'target': drf_serializers.JSONField(allow_null=True),
    'colonnes': drf_serializers.JSONField(allow_null=True),
    'mapping': drf_serializers.JSONField(allow_null=True),
    'non_mappees': drf_serializers.JSONField(allow_null=True),
    'apercu': drf_serializers.JSONField(allow_null=True),
    'total_lignes': drf_serializers.JSONField(allow_null=True),
    'mode': drf_serializers.JSONField(required=False, allow_null=True),
    'ecraser': drf_serializers.JSONField(required=False, allow_null=True),
})


@extend_schema(request=_corps_import('ImportDryRunRequete'),
               responses=_VIEWS_DRY_RUN_REPONSE)
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def dry_run(request):
    """Aperçu d'import (10 lignes + mapping colonne→champ) AVANT validation.

    XPLT2 — ``mapping`` (nom d'un ``ImportMapping`` sauvegardé) réapplique un
    mapping colonne→champ mémorisé au lieu du mapping automatique par en-tête.

    ``mode``/``ecraser``/``external_system`` sont ceux qui seront envoyés au
    commit : l'aperçu rejoue le MÊME rapprochement sans rien écrire et liste,
    champ par champ, les valeurs déjà saisies que le fichier remplacerait. La
    société reste TOUJOURS celle du serveur (jamais le corps de la requête).
    """
    f, target, err = _read(request)
    if err:
        return err
    options = _options_import(request, _OptionsImport)
    mapping_name = options.get('mapping') or None
    mode = options.get('mode', 'creer')
    ecraser = options.get('ecraser', False)
    external_system = options.get('external_system') or None
    try:
        result = services.dry_run(
            f.read(), f.name, target, company=request.user.company,
            mapping_name=mapping_name, mode=mode, ecraser=ecraser,
            external_system=external_system)
    except services.ModeNonSupporte as exc:
        # Couple cible/mode inexprimable dans le corps publié : 409.
        raise ConflitEtat(str(exc))
    except ValueError as exc:
        # Erreur attendue (cible inconnue, plafond de lignes…) : message clair.
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        # ERR53 — diagnostic : on journalise la cause réelle côté serveur sans
        # la divulguer au client, et on renvoie un 400 générique.
        logger.warning('Import dry-run échoué (target=%s)', target, exc_info=True)
        return Response(
            {'detail': 'Lecture du fichier impossible (format invalide ?).'},
            status=400)
    return Response(result)


_VIEWS_COMMIT_REPONSE = inline_serializer('ViewsCommitReponse', {
    'ok': drf_serializers.JSONField(allow_null=True),
    'target': drf_serializers.JSONField(allow_null=True),
    'mode': drf_serializers.JSONField(allow_null=True),
    'ecraser': drf_serializers.JSONField(allow_null=True),
    'created': drf_serializers.JSONField(allow_null=True),
    'updated': drf_serializers.JSONField(allow_null=True),
    'skipped': drf_serializers.JSONField(allow_null=True),
    'total': drf_serializers.JSONField(allow_null=True),
    'job_id': drf_serializers.JSONField(allow_null=True),
    'statut': drf_serializers.JSONField(allow_null=True),
    'ecrasements': drf_serializers.JSONField(allow_null=True),
    'refuses': drf_serializers.JSONField(allow_null=True),
})


@extend_schema(
    request=_corps_import('ImportCommitRequete', _OptionsCommit),
    responses=_VIEWS_COMMIT_REPONSE)
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def commit(request):
    """Import effectif. ``creer`` (défaut) : création seule, doublons ignorés,
    origine marquée. ``maj``/``upsert`` : mise à jour en REMPLISSAGE SEUL — un
    champ déjà rempli n'est remplacé que si l'appelant envoie ``ecraser=true``,
    et chaque remplacement laisse sa valeur précédente sur l'``ImportJob``."""
    f, target, err = _read(request)
    if err:
        return err
    # QG4 — l'import de PRODUITS crée des produits : même restriction que le
    # create REST (Directeur + Commercial responsable uniquement).
    if target == 'products' and not PRODUIT_CREATE_PERMISSION().has_permission(
            request, None):
        return Response(
            {'detail': 'La création de produits est réservée aux rôles '
                       'Directeur et Commercial responsable.'},
            status=403)
    # XPLT1 — mode d'import optionnel (creer=défaut, maj, upsert), jamais lu
    # ailleurs que le body du formulaire (la société, elle, reste forcée
    # côté serveur via request.user.company).
    options = _options_import(request, _OptionsCommit)
    mode = options.get('mode', 'creer')
    external_system = options.get('external_system') or None
    # XPLT2 — mapping sauvegardé optionnel + choix commit partiel (défaut,
    # comportement historique) vs rollback atomique total si une ligne échoue.
    mapping_name = options.get('mapping') or None
    rollback_on_error = options.get('rollback_on_error', False)
    # Garde-fou : sans ``ecraser=true`` explicite, un import ne peut que
    # RENSEIGNER un champ vide — jamais remplacer une valeur déjà saisie. Le
    # défaut sûr est donc l'absence du drapeau.
    ecraser = options.get('ecraser', False)
    try:
        result = services.commit(
            f.read(), f.name, target, request.user.company, request.user,
            mode=mode, external_system=external_system,
            mapping_name=mapping_name, rollback_on_error=rollback_on_error,
            ecraser=ecraser)
    except services.ModeNonSupporte as exc:
        raise ConflitEtat(str(exc))
    except ValueError as exc:
        # Erreur attendue (cible inconnue, plafond de lignes…) : message clair.
        return Response({'detail': str(exc)}, status=400)
    except Exception:
        # ERR53 — diagnostic : on journalise la cause réelle côté serveur sans
        # la divulguer au client, et on renvoie un 400 générique. Le commit est
        # atomique (ERR51) : rien n'est créé en cas d'échec.
        logger.warning('Import commit échoué (target=%s)', target, exc_info=True)
        return Response(
            {'detail': 'Import impossible (vérifiez le fichier).'},
            status=400)
    return Response(result)


@extend_schema(
    parameters=[OpenApiParameter('target', OpenApiTypes.STR, required=False,
                                 enum=_CIBLES)],
    responses=inline_serializer('ImportMappingLigne', {
        'id': serializers.IntegerField(),
        'target': serializers.CharField(),
        'nom': serializers.CharField(),
        'mapping': serializers.DictField()}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def list_mappings(request):
    """XPLT2 — mappings sauvegardés de la société courante (sélecteur), filtrés
    optionnellement par cible (``?target=leads``)."""
    # ``?target=`` vide ou hors liste → 400 (l'énumération est publiée).
    target = choix_ou_400(request, 'target', _CIBLES)
    mappings = services.list_mappings(request.user.company, target=target)
    return Response([
        {'id': m.pk, 'target': m.entity, 'nom': m.nom, 'mapping': m.mapping}
        for m in mappings
    ])


NOM_MAPPING_MAX = 150  # ``ImportMapping.nom`` (varchar 150)

#: Champs qu'une cible QUELCONQUE sait écrire (``FIELD_MAPS``) : une valeur hors
#: de cette liste (``company_id``…) est refusée en 400 par le corps publié ; le
#: couple colonne→champ propre à UNE cible reste vérifié par ``save_mapping``.
_CHAMPS_IMPORTABLES = sorted(
    {champ for carte in services.FIELD_MAPS.values()
     for champ in carte.values()})

#: Corps de ``POST mapping/`` : LE prédicat publié ET appliqué (``corps_valide``).
#: ``nom`` : texte strict (un nombre n'est plus « converti » en texte), plafond
#: de la colonne ; valeurs : un champ importable.
_MAPPING_REQUETE = inline_serializer('ImportMappingRequete', {
    'target': serializers.ChoiceField(choices=_CIBLES),
    'nom': ChaineStricte(max_length=NOM_MAPPING_MAX),
    'mapping': serializers.DictField(
        child=ChoixDocumente(choices=_CHAMPS_IMPORTABLES))})


@extend_schema(
    # ENF11 (api-fuzz) : un mapping vide est refusé (400) — le corps publié exige
    # au moins une paire colonne→champ, de texte à texte.
    # Une colonne ne porte pas de caractère nul (jsonb le refuse).
    extensions={EXTENSION_CORPS_RESSERRE: {
        'type': 'object', 'properties': {'mapping': {
            'minProperties': 1,
            'propertyNames': {'pattern': MOTIF_SANS_NUL}}}}},
    request=_MAPPING_REQUETE,
    responses=inline_serializer('ImportMappingEnregistre', {
        'id': serializers.IntegerField(),
        'target': serializers.CharField(),
        'nom': serializers.CharField(),
        'mapping': serializers.DictField()}))
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes(PARSEURS_JSON)
def save_mapping(request):
    """XPLT2 — sauvegarde (ou remplace) un mapping colonne→champ nommé pour une
    cible, réapplicable au prochain dry-run/commit via ``mapping=<nom>``."""
    # ENF11 — le corps est validé par le serializer PUBLIÉ : un corps non objet
    # (``[null, null]``), un type faux ou un ``nom`` trop long répondent 400
    # (la lecture à la main levait AttributeError → 500).
    corps = corps_valide(request, _MAPPING_REQUETE)
    target, nom, mapping = corps['target'], corps['nom'], corps['mapping']
    if not mapping:
        return Response(
            {'detail': 'Mapping invalide (dict colonne→champ attendu).'},
            status=400)
    # Une colonne portant un caractère nul ne peut pas être stockée en JSON
    # (jsonb le refuse → 500) et ne correspond à aucun en-tête de fichier.
    if any('\x00' in colonne for colonne in mapping):
        return Response(
            {'mapping': ['Nom de colonne invalide (caractère nul).']},
            status=400)
    # AANA9 — un champ hors ``FIELD_MAPS[target]`` (company_id, owner_id…)
    # est refusé en 400 lisible, jamais enregistré.
    try:
        obj = services.save_mapping(request.user.company, target, nom, mapping)
    except ValueError as exc:
        # Champ valide pour une autre cible mais pas pour celle-ci : le couple
        # cible/champ est inexprimable dans le corps publié (409).
        raise ConflitEtat(str(exc))
    return Response({
        'id': obj.pk, 'target': obj.entity, 'nom': obj.nom, 'mapping': obj.mapping,
    })


@extend_schema(responses={(200, 'text/csv'): OpenApiTypes.STR})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def job_erreurs_csv(request, job_id):
    """XPLT2 — CSV des seules lignes en échec d'un ``ImportJob``, directement
    ré-importables (mêmes en-têtes que le fichier d'origine + ``_motif``).
    Isolation tenant stricte : un job d'une autre société → 404 (YRBAC11 —
    helper canonique ``core.selectors.get_company_object``)."""
    try:
        job = get_company_object(ImportJob, job_id, request.user)
    except Http404:
        return Response({'detail': 'Import introuvable.'}, status=404)
    fieldnames, rows = services.erreurs_csv_rows(job)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames or ['_motif'])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="import_{job.pk}_erreurs.csv"'
    return resp


@extend_schema(responses={(200, 'text/csv'): OpenApiTypes.STR})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_traductions(request):
    """NTI18N29 — ``GET traductions/export.csv`` : CSV des surcharges de
    traduction de la société (colonnes ``cle|fr|en|ar|statut_traduction``),
    pour relecture par un traducteur externe hors-ligne."""
    contenu = exporter_traductions_csv(request.user.company)
    resp = HttpResponse(contenu, content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="traductions.csv"'
    return resp


@extend_schema(request={'multipart/form-data': IMPORT_TRADUCTIONS_REQUEST},
               responses={200: IMPORT_TRADUCTIONS_RESPONSE})
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def import_traductions(request):
    """NTI18N29 — ``POST traductions/import/`` (multipart ``file``) : réimporte
    un CSV corrigé, upsert des seules colonnes de locale FOURNIES et non
    vides (jamais un effacement silencieux). Journalisé via
    ``dataimport.ImportJob`` (``target='traductions'``)."""
    f = request.FILES.get('file')
    if f is None:
        return Response({'detail': 'Aucun fichier fourni.'}, status=400)
    size = getattr(f, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        return Response(
            {'detail': 'Fichier trop volumineux : '
                       f'{size} octets (max {MAX_UPLOAD_BYTES}).'},
            status=400)
    try:
        job = importer_traductions_csv(
            f.read(), f.name, request.user.company, user=request.user)
    except Exception:
        logger.warning('Import de traductions échoué', exc_info=True)
        return Response(
            {'detail': 'Lecture du fichier impossible (format invalide ?).'},
            status=400)
    return Response({
        'job': job.pk, 'statut': job.statut, 'total_lignes': job.total_lignes,
        'created_count': job.created_count, 'updated_count': job.updated_count,
        'error_count': job.error_count,
    })


@extend_schema(responses={(200, 'text/csv'): OpenApiTypes.STR})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_feries(request):
    """NTI18N45 — ``GET feries/export.csv`` : CSV du calendrier de jours
    fériés de la société (colonnes ``pays|date|libelle|recurrent_annuel``),
    pour préparation hors-ligne dans un tableur."""
    contenu = exporter_feries_csv(request.user.company)
    resp = HttpResponse(contenu, content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="feries.csv"'
    return resp


@extend_schema(request={'multipart/form-data': IMPORT_FERIES_REQUEST},
               responses={200: IMPORT_FERIES_RESPONSE})
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
@parser_classes([MultiPartParser, FormParser])
def import_feries(request):
    """NTI18N45 — ``POST feries/import/`` (multipart ``file``) : importe en
    masse un calendrier de jours fériés, upsert IDEMPOTENT par
    ``(pays, date)``. Journalisé via ``dataimport.ImportJob``
    (``target='feries'``)."""
    f = request.FILES.get('file')
    if f is None:
        return Response({'detail': 'Aucun fichier fourni.'}, status=400)
    size = getattr(f, 'size', None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        return Response(
            {'detail': 'Fichier trop volumineux : '
                       f'{size} octets (max {MAX_UPLOAD_BYTES}).'},
            status=400)
    try:
        job = importer_feries_csv(
            f.read(), f.name, request.user.company, user=request.user)
    except Exception:
        logger.warning('Import de fériés échoué', exc_info=True)
        return Response(
            {'detail': 'Lecture du fichier impossible (format invalide ?).'},
            status=400)
    return Response({
        'job': job.pk, 'statut': job.statut, 'total_lignes': job.total_lignes,
        'created_count': job.created_count, 'updated_count': job.updated_count,
        'error_count': job.error_count,
    })
