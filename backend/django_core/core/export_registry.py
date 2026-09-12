"""NTOBS6 — registre des datasets exportables pour l'export de réversibilité.

Réutilise en SOURCE PRINCIPALE le registre déjà peuplé de l'explorateur de
données (``core.data_explorer`` — crm/ventes/stock/sav/installations
s'enregistrent DÉJÀ dans leur ``ready()``, cf. ``apps/*/bi_datasets.py``) :
mêmes garanties de scoping société (``queryset_provider(company, user)``) et
de masquage des champs sous permission. Appelé avec ``user=None`` (extrait
planifié, sans acteur), ``core.data_explorer.champs_interdits`` retire
TOUJOURS les champs ``gated_fields`` (``prix_achat``/``cout``…) — jamais une
seconde liste d'exclusion à maintenir ici.

``register_export_dataset(app_label, queryset_fn, to_csv_fn)`` reste
disponible pour un export BESPOKE hors ``data_explorer`` (ex. un dataset qui
doit joindre des fichiers binaires) — même pattern additif que
``core.retention.register_retention_policy`` : chaque app s'enregistre dans
son ``ready()``, ``core`` ne connaît que le nom et les callables.

``core`` reste fondation (contrat import-linter
``core-foundation-is-a-base-layer``) : ``core.data_explorer`` est déjà une
app-soeur de fondation, jamais un import d'app domaine ici.
"""
from __future__ import annotations

import csv
import io
import logging

from django.conf import settings
from django.db import models
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .models import TenantModel

logger = logging.getLogger(__name__)


class ExportReversibiliteRun(TenantModel):
    """NTOBS7 — historique des exports de réversibilité d'une société.

    Une ligne par déclenchement (``core.tasks.export_reversibilite_tenant``
    la crée ``en_cours`` puis la fait progresser). ``company`` (obligatoire,
    imposée côté serveur) vient de ``core.models.TenantModel``."""

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        PRET = 'pret', 'Prêt'
        EXPIRE = 'expire', 'Expiré'
        ECHEC = 'echec', 'Échec'

    statut = models.CharField(
        'Statut', max_length=10, choices=Statut.choices,
        default=Statut.EN_COURS)
    fichier_key = models.CharField(
        'Clé objet MinIO', max_length=500, blank=True, default='')
    taille_octets = models.BigIntegerField(
        'Taille (octets)', null=True, blank=True)
    token = models.CharField(
        'Jeton de téléchargement', max_length=64, blank=True, default='')
    expire_le = models.DateTimeField('Expire le', null=True, blank=True)
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Demandé par')

    class Meta:
        verbose_name = 'Export de réversibilité'
        verbose_name_plural = 'Exports de réversibilité'
        ordering = ['-created_at']

    def __str__(self):
        return f'Export réversibilité société {self.company_id} ({self.statut})'

    @property
    def expire(self):
        return bool(self.expire_le and timezone.now() >= self.expire_le)


# Registre BESPOKE en mémoire (process-local, repeuplé à chaque ``ready()``).
_CUSTOM_REGISTRY: dict = {}

# Borne défensive par dataset — PAS le plafond de 5000 lignes de
# ``data_explorer.run_query`` (pensé pour une requête BI interactive, pas un
# export complet) : un export de réversibilité doit couvrir un tenant réel.
EXPORT_ROW_LIMIT_PER_DATASET = 200_000


def register_export_dataset(app_label, queryset_fn, to_csv_fn):
    """Enregistre un export BESPOKE.

    ``queryset_fn(company)`` -> QuerySet déjà scopé société.
    ``to_csv_fn(queryset)`` -> ``bytes`` CSV (l'app reste responsable
    d'exclure ELLE-MÊME tout champ interne-only, ex. ``prix_achat``).
    Idempotent : ré-enregistrer le même ``app_label`` REMPLACE l'entrée."""
    if not app_label or not callable(queryset_fn) or not callable(to_csv_fn):
        raise ValueError(
            'register_export_dataset : app_label + 2 callables requis.')
    _CUSTOM_REGISTRY[app_label] = {
        'queryset_fn': queryset_fn, 'to_csv_fn': to_csv_fn,
    }


def unregister_export_dataset(app_label):
    """Retire un dataset bespoke (surtout utile en test)."""
    _CUSTOM_REGISTRY.pop(app_label, None)


def clear_custom_registry():
    """Vide le registre bespoke (test uniquement)."""
    _CUSTOM_REGISTRY.clear()


def _rows_to_csv_bytes(rows, fieldnames):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ('' if v is None else v) for k, v in row.items()})
    return buf.getvalue().encode('utf-8')


def _data_explorer_dataset_names():
    from . import data_explorer
    # ``list_datasets()`` sans ``user`` sert ICI seulement à énumérer les NOMS
    # enregistrés (métadonnée) — le contenu réel de chaque dataset est
    # toujours relu via ``champs_interdits(dataset, None)`` plus bas, qui
    # retire TOUJOURS les champs gated (jamais via cette liste de noms).
    return sorted(d['name'] for d in data_explorer.list_datasets())


def _export_data_explorer_dataset(name, company):
    """CSV bytes + nombre de lignes d'UN dataset ``data_explorer``, scopé
    société, JAMAIS un champ ``gated_fields`` (appel avec ``user=None`` —
    ``champs_interdits`` retire alors TOUS les champs sous permission)."""
    from . import data_explorer

    dataset = data_explorer.get_dataset(name)
    interdits = data_explorer.champs_interdits(dataset, None)
    fields = [f for f in dataset['fields'] if f not in interdits]
    if not fields:
        fields = ['id']

    qs = data_explorer.analytics_queryset(dataset['provider'](company, None))
    rows_iter = qs.values(*fields).iterator(chunk_size=1000)
    rows = []
    for i, row in enumerate(rows_iter):
        if i >= EXPORT_ROW_LIMIT_PER_DATASET:
            logger.warning(
                'export_registry: dataset %r tronqué à %d lignes '
                '(société %s).', name, EXPORT_ROW_LIMIT_PER_DATASET, company.id)
            break
        rows.append(row)
    return _rows_to_csv_bytes(rows, fields), len(rows)


def export_all_datasets(company):
    """NTOBS6 — exporte TOUS les datasets enregistrés (``data_explorer`` +
    bespoke) pour ``company``. Renvoie ``{nom_fichier: bytes_csv}`` +
    ``{nom: nb_lignes}`` (pour le manifeste). Best-effort par dataset : un
    dataset en échec n'empêche pas les autres."""
    fichiers = {}
    comptes = {}

    for name in _data_explorer_dataset_names():
        try:
            csv_bytes, n = _export_data_explorer_dataset(name, company)
            fichiers[f'{name}.csv'] = csv_bytes
            comptes[name] = n
        except Exception:  # noqa: BLE001 — un dataset KO n'en bloque pas d'autres
            logger.exception(
                'export_registry: échec export dataset %r (société %s).',
                name, company.id)

    for app_label, entry in _CUSTOM_REGISTRY.items():
        try:
            qs = entry['queryset_fn'](company)
            csv_bytes = entry['to_csv_fn'](qs)
            fichiers[f'{app_label}.csv'] = csv_bytes
            comptes[app_label] = len(qs) if hasattr(qs, '__len__') else None
        except Exception:  # noqa: BLE001
            logger.exception(
                'export_registry: échec export bespoke %r (société %s).',
                app_label, company.id)

    return fichiers, comptes


def datasets_disponibles():
    """Noms de TOUS les datasets exportables (``data_explorer`` + bespoke) —
    pour vérifier « au moins 4 datasets enregistrés » et pour l'écran de
    sélection (NTOBS20, hors périmètre de ce lot)."""
    return sorted(set(_data_explorer_dataset_names()) | set(_CUSTOM_REGISTRY.keys()))


# ── API HTTP ─────────────────────────────────────────────────────────────
#
# NTOBS6 — POST déclenche l'export ASYNCHRONE (Celery, ``core.tasks.
# export_reversibilite_tenant``) ; GET telecharger/<token>/ sert l'OBJET
# MinIO via le jeton (comme ``ged.PartageGed`` : le jeton EST l'accès, sans
# authentification — un lien transféré doit fonctionner pour son
# destinataire). Throttle strict : action lourde, Directeur uniquement pour
# le déclenchement.

def _is_directeur_or_admin(user):
    if not (user and user.is_authenticated):
        return False
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_admin_role', False):
        return True
    role = getattr(user, 'role', None)
    return bool(role and role.nom in ('Directeur', 'Administrateur'))


class ExportReversibiliteThrottle(UserRateThrottle):
    # Action lourde — un déclenchement toutes les 20 min suffit largement à
    # un usage légitime (self-service, jamais un batch automatisé).
    scope = 'export_reversibilite'
    rate = '3/hour'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExportReversibiliteThrottle])
def declencher_export_reversibilite(request):
    """POST /api/django/core/export-reversibilite/ — Directeur/Administrateur
    uniquement. Crée la ligne d'historique (NTOBS7, ``en_cours``) puis lance
    la tâche Celery et renvoie 202 immédiatement (l'export complet d'un gros
    tenant peut prendre plusieurs minutes)."""
    if not _is_directeur_or_admin(request.user):
        return Response(status=status.HTTP_403_FORBIDDEN)
    from . import tasks as core_tasks

    run = ExportReversibiliteRun.objects.create(
        company=request.user.company, demande_par=request.user,
        statut=ExportReversibiliteRun.Statut.EN_COURS)
    datasets = request.data.get('datasets') or None
    core_tasks.export_reversibilite_tenant.delay(
        request.user.company_id, demande_par_id=request.user.id,
        datasets=datasets, run_id=run.id)
    return Response(
        ExportReversibiliteRunSerializer(run).data,
        status=status.HTTP_202_ACCEPTED)


class ExportReversibiliteRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportReversibiliteRun
        fields = [
            'id', 'statut', 'taille_octets', 'token', 'expire_le',
            'created_at',
        ]


class ExportReversibiliteHistoriqueView(generics.ListAPIView):
    """GET /api/django/core/export-reversibilite/historique/ — scopé société."""

    serializer_class = ExportReversibiliteRunSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return (
            ExportReversibiliteRun.objects
            .filter(company=self.request.user.company)
            .order_by('-created_at')[:50]
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def telecharger_export_reversibilite(request, token):
    """GET /api/django/core/export-reversibilite/telecharger/<token>/ —
    public (le jeton EST l'authentification), 404 si expiré/révoqué/inconnu
    (jamais de fuite d'information sur la raison)."""
    from . import signed_download

    try:
        resolu = signed_download.resoudre_lien(token)
    except Exception:  # noqa: BLE001 — jamais une 500 sur un jeton KO
        resolu = None
    if resolu is None:
        raise Http404
    bucket, object_key = resolu
    try:
        from .backup import _minio_client
        client = _minio_client()
        obj = client.get_object(Bucket=bucket, Key=object_key)
        contenu = obj['Body'].read()
    except Exception as exc:  # noqa: BLE001
        raise Http404 from exc
    response = HttpResponse(contenu, content_type='application/zip')
    response['Content-Disposition'] = (
        'attachment; filename="export-reversibilite.zip"')
    return response
