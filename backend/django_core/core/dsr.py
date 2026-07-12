"""FG394 — Consentement & DSR (loi 09-08 / CNDP), orchestration.

Couche de FONDATION : orchestre les demandes de personnes concernées (accès =
export, effacement) SANS que ``core`` n'importe une app métier (contrat
import-linter ``core-foundation-is-a-base-layer``). Chaque app détenant des
données personnelles ENREGISTRE un « fournisseur DSR » :

    register_dsr_provider(name, export=fn_export, erase=fn_erase)

où ``fn_export(company, subject_identifier) -> dict`` renvoie les données de la
personne pour cette app (déjà scopées société), et ``fn_erase(company,
subject_identifier) -> int`` efface/anonymise et renvoie le nombre d'éléments
traités. ``core`` agrège simplement les fournisseurs — il ne sait RIEN des
modèles métier.
"""
from __future__ import annotations

from django.utils import timezone

# Registre en mémoire : { name: {export: fn|None, erase: fn|None} }.
_PROVIDERS: dict[str, dict] = {}


def register_dsr_provider(name, *, export=None, erase=None):
    """Enregistre un fournisseur DSR pour une app (idempotent).

    Au moins un de ``export`` / ``erase`` doit être fourni.
    """
    if not name or (export is None and erase is None):
        raise ValueError('Fournisseur DSR : nom + export et/ou erase requis.')
    _PROVIDERS[name] = {'export': export, 'erase': erase}


def list_dsr_providers():
    """Noms des fournisseurs DSR enregistrés (rendu stable)."""
    return sorted(_PROVIDERS.keys())


def exporter(company, subject_identifier):
    """Agrège l'export de tous les fournisseurs pour une personne concernée.

    Renvoie ``{provider_name: data}``. Un fournisseur qui lève est isolé
    (``{'erreur': ...}``) pour ne pas faire échouer tout l'export.
    """
    out = {}
    for name, prov in sorted(_PROVIDERS.items()):
        fn = prov.get('export')
        if fn is None:
            continue
        try:
            out[name] = fn(company, subject_identifier)
        except Exception as exc:  # noqa: BLE001 - isolation par fournisseur
            out[name] = {'erreur': str(exc)}
    return out


def effacer(company, subject_identifier):
    """Déclenche l'effacement chez tous les fournisseurs pour une personne.

    Renvoie ``{provider_name: nb_traite}``. Un fournisseur qui lève est isolé.
    """
    out = {}
    for name, prov in sorted(_PROVIDERS.items()):
        fn = prov.get('erase')
        if fn is None:
            continue
        try:
            out[name] = fn(company, subject_identifier)
        except Exception as exc:  # noqa: BLE001 - isolation par fournisseur
            out[name] = {'erreur': str(exc)}
    return out


def traiter_demande(request):
    """Exécute une ``DataSubjectRequest`` (accès → export, effacement → erase).

    Met à jour ``resultat`` / ``statut`` / ``traitee_le``. Multi-tenant : la
    société de la demande borne tous les fournisseurs.
    """
    from .models import DataSubjectRequest

    company = request.company
    subject = request.subject_identifier
    if request.kind == DataSubjectRequest.KIND_ACCESS:
        request.resultat = exporter(company, subject)
    elif request.kind == DataSubjectRequest.KIND_ERASURE:
        request.resultat = effacer(company, subject)
    else:
        # XPLT23 — rectification : workflow MANUEL. On n'exécute aucune
        # opération automatique ; on renvoie l'export des données actuelles
        # comme contexte de correction et on laisse le traitement au responsable
        # (champs demandés + trace). La demande reste « traitée » (contexte
        # fourni) mais aucune donnée n'est modifiée automatiquement.
        request.resultat = {
            'rectification': True,
            'donnees_actuelles': exporter(company, subject),
            'note': 'Correction à traiter manuellement par le responsable.',
        }
    request.statut = DataSubjectRequest.STATUT_TRAITEE
    request.traitee_le = timezone.now()
    request.save(update_fields=['resultat', 'statut', 'traitee_le',
                                'updated_at'])
    return request


# ===========================================================================
# NTPLT60 — Export INTÉGRAL d'un tenant (portabilité SOCIÉTÉ entière).
#
# Complète l'export DSR INDIVIDUEL (ci-dessus) par la portabilité de TOUTE la
# société : la réponse standard aux DSI qui demandent « et si on part ? ».
# Produit un zip = un JSON par modèle company-scopé (via les serializers Django
# — générique, aucun import d'app métier, ``core`` reste fondation) + un
# manifeste des fichiers MinIO de la société + des checksums SHA-256.
# ===========================================================================


def _company_scoped_models():
    """Modèles portant une FK ``company`` (réutilise la découverte RLS)."""
    from django.apps import apps as django_apps
    from . import rls
    tables = {e.table for e in rls.discover_company_scoped_tables()}
    out = []
    for model in django_apps.get_models():
        meta = getattr(model, '_meta', None)
        if meta is None or meta.abstract or meta.proxy:
            continue
        if meta.db_table in tables:
            out.append(model)
    return out


def _minio_manifest(company_id):
    """Liste (best-effort) les objets MinIO sous le préfixe société.

    Renvoie ``[{'bucket', 'key', 'size'}]`` — vide si le stockage est
    indisponible (jamais d'exception propagée)."""
    from django.conf import settings
    prefix = f'company/{company_id}/'
    buckets = [
        getattr(settings, 'MINIO_BUCKET_UPLOADS', 'erp-uploads'),
        getattr(settings, 'MINIO_BUCKET_PDF', 'erp-pdf'),
    ]
    entries = []
    try:
        from .backup import _minio_client
        client = _minio_client()
    except Exception:  # noqa: BLE001 — stockage indisponible → manifeste vide
        return entries
    for bucket in buckets:
        try:
            paginator = client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []) or []:
                    entries.append({
                        'bucket': bucket, 'key': obj.get('Key'),
                        'size': int(obj.get('Size', 0) or 0)})
        except Exception:  # noqa: BLE001 — bucket absent/erreur → ignore
            continue
    return entries


def export_tenant(company_id, out_path):
    """Écrit un zip d'export intégral de la société ``company_id`` dans
    ``out_path``.

    Contenu du zip :
      * ``data/<app>.<model>.json`` — sérialisation Django de toutes les lignes
        company-scopées de ce modèle (filtrées par société) ;
      * ``minio-manifest.json`` — liste des fichiers MinIO du tenant ;
      * ``checksums.sha256`` — SHA-256 de chaque entrée ``data/*`` ;
      * ``manifest.json`` — métadonnées (société, date, modèles, compte de
        lignes).
    Renvoie un résumé ``{company_id, models, rows, files, out}``.
    """
    import hashlib
    import json
    import zipfile

    from django.core import serializers as dj_serializers

    models_exported = {}
    total_rows = 0
    checksums = {}

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for model in _company_scoped_models():
            meta = model._meta
            label = f'{meta.app_label}.{meta.model_name}'
            try:
                qs = model.objects.filter(company_id=company_id)
                payload = dj_serializers.serialize('json', qs.iterator())
            except Exception:  # noqa: BLE001 — un modèle KO ne bloque pas tout
                continue
            count = payload.count('"model":') if payload else 0
            arcname = f'data/{label}.json'
            zf.writestr(arcname, payload)
            digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            checksums[arcname] = digest
            models_exported[label] = count
            total_rows += count

        minio_files = _minio_manifest(company_id)
        zf.writestr('minio-manifest.json',
                    json.dumps(minio_files, ensure_ascii=False, indent=2))
        zf.writestr('checksums.sha256',
                    '\n'.join(f'{v}  {k}' for k, v in sorted(
                        checksums.items())))
        manifest = {
            'company_id': company_id,
            'exported_at': timezone.now().isoformat(),
            'models': models_exported,
            'rows': total_rows,
            'minio_files': len(minio_files),
            'format': 'taqinor-tenant-export/1',
        }
        zf.writestr('manifest.json',
                    json.dumps(manifest, ensure_ascii=False, indent=2))

    return {
        'company_id': company_id,
        'models': len(models_exported),
        'rows': total_rows,
        'files': len(minio_files),
        'out': str(out_path),
    }
