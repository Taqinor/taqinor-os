"""NTPLT61 — Import d'un tenant exporté (NTPLT60) dans une société VIDE.

Symétrique de ``core.dsr.export_tenant`` : consomme le zip
``taqinor-tenant-export/1`` et recrée les lignes dans une company CIBLE vide,
en REMAPPANT tous les identifiants (nouveaux PK auto-assignés) et en
réécrivant la FK ``company`` vers la cible. Combiné à l'anonymisation YHARD10,
c'est la reproduction fidèle d'un bug client sur staging SANS données réelles.

``core`` reste FONDATION : aucun import statique d'app métier. Les modèles sont
résolus dynamiquement (``django.apps.apps.get_model`` / introspection
``_meta``), exactement comme ``core.dsr``. Jamais exposé par API — seulement en
management command (opération d'exploitation).

Séparation testable : le PLAN de remap (tri topologique des modèles par
dépendances FK + réécriture des FK) est une fonction PURE
(``build_import_plan`` / ``_toposort``) testable sans base ; l'application en
base vit dans ``apply_import``.
"""
from __future__ import annotations

import json
import zipfile

EXPORT_FORMAT = 'taqinor-tenant-export/1'


class TenantImportError(Exception):
    """Erreur d'import de tenant (format invalide, cible non vide, …)."""


def read_export(zip_path):
    """Lit le zip d'export → ``(manifest, records, minio_manifest)``.

    ``records`` = liste de dicts Django-serializer ``{model, pk, fields}``
    agrégée sur tous les ``data/*.json``. Lève ``TenantImportError`` si le
    format du manifeste est inconnu.
    """
    records = []
    minio_manifest = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = set(zf.namelist())
        if 'manifest.json' not in names:
            raise TenantImportError('Zip invalide : manifest.json absent.')
        manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
        if manifest.get('format') != EXPORT_FORMAT:
            raise TenantImportError(
                f"Format d'export inconnu : {manifest.get('format')!r} "
                f"(attendu {EXPORT_FORMAT!r}).")
        if 'minio-manifest.json' in names:
            minio_manifest = json.loads(
                zf.read('minio-manifest.json').decode('utf-8'))
        for name in sorted(names):
            if name.startswith('data/') and name.endswith('.json'):
                payload = zf.read(name).decode('utf-8')
                for obj in json.loads(payload):
                    records.append(obj)
    return manifest, records, minio_manifest


def _toposort(labels, deps):
    """Tri topologique STABLE des ``labels`` selon ``deps`` (label -> set des
    labels dont il dépend, restreints à ``labels``).

    Les arêtes vers un label absent de l'ensemble sont ignorées. Les cycles
    (et self-refs) n'empêchent pas le tri : les labels encore bloqués en fin de
    parcours sont émis dans l'ordre d'origine (leurs FK cycliques seront
    résolues en seconde passe). Renvoie la liste ordonnée.
    """
    labels = list(labels)
    label_set = set(labels)
    remaining = {la: {d for d in deps.get(la, ()) if d in label_set and d != la}
                 for la in labels}
    ordered = []
    placed = set()
    progressed = True
    while remaining and progressed:
        progressed = False
        for la in labels:
            if la in placed:
                continue
            if remaining[la] <= placed:
                ordered.append(la)
                placed.add(la)
                progressed = True
        # recompute done implicitly via `placed`
    # Reliquat (cycles) : ordre d'origine.
    for la in labels:
        if la not in placed:
            ordered.append(la)
    return ordered


def build_import_plan(records, fk_map):
    """Plan PUR d'import (aucune base touchée).

    ``fk_map`` : ``{model_label: {field_attname: target_label}}`` décrivant les
    FK de chaque modèle vers un AUTRE modèle scopé (renseigné par l'appelant
    via l'introspection ``_meta``). Renvoie ``(ordre, deps)`` où ``ordre`` est
    la liste des labels triée topologiquement et ``deps`` le graphe utilisé.
    """
    labels = []
    for obj in records:
        if obj['model'] not in labels:
            labels.append(obj['model'])
    deps = {}
    for la in labels:
        targets = set(fk_map.get(la, {}).values())
        deps[la] = {t for t in targets if t in labels}
    return _toposort(labels, deps), deps


def _introspect_fk_map(labels):
    """Construit ``{label: {attname: target_label}}`` pour les FK pointant vers
    un AUTRE modèle présent dans ``labels`` (via ``_meta``). Renvoie aussi
    ``{label: company_attname|None}``. Aucun import d'app métier."""
    from django.apps import apps as django_apps

    fk_map = {}
    company_attr = {}
    for label in labels:
        model = django_apps.get_model(label)
        fields = {}
        comp = None
        for field in model._meta.get_fields():
            if not getattr(field, 'is_relation', False):
                continue
            if not (field.many_to_one or field.one_to_one):
                continue
            if not getattr(field, 'concrete', False):
                continue
            target = field.related_model
            tlabel = f'{target._meta.app_label}.{target._meta.model_name}'
            if field.name == 'company' or tlabel == 'authentication.company':
                comp = field.attname
                continue
            if tlabel in labels:
                fields[field.attname] = tlabel
        fk_map[label] = fields
        company_attr[label] = comp
    return fk_map, company_attr


def _is_nullable(model, attname):
    """True si la FK d'attname donné est nullable (autorise None en phase 1)."""
    for field in model._meta.get_fields():
        if getattr(field, 'attname', None) == attname:
            return bool(getattr(field, 'null', False))
    return False


def target_is_empty(company_id):
    """True si la société cible ne détient AUCUNE ligne scopée (import refusé
    sinon — on n'écrase jamais une company existante)."""
    from . import dsr
    for model in dsr._company_scoped_models():
        try:
            if model.objects.filter(company_id=company_id).exists():
                return False
        except Exception:  # noqa: BLE001 — modèle sans company_id → ignore
            continue
    return True


def apply_import(company_id, zip_path, *, with_files=False, dry_run=False):
    """Importe le tenant du zip dans la société ``company_id`` (VIDE).

    Remap complet des PK (auto-assignés) + FK ``company`` réécrite vers la
    cible. Deux passes : insertion en ordre topologique (FK déjà mappées
    résolues, FK cycliques nullables différées), puis patch des FK différées.
    Transaction unique : tout ou rien. Renvoie un résumé.
    """
    from django.core import serializers as dj_serializers
    from django.db import transaction

    manifest, records, minio_manifest = read_export(zip_path)

    # Regroupe par label en préservant l'ordre d'apparition.
    labels = []
    by_label = {}
    for obj in records:
        by_label.setdefault(obj['model'], []).append(obj)
        if obj['model'] not in labels:
            labels.append(obj['model'])

    fk_map, company_attr = _introspect_fk_map(labels)
    order, _deps = build_import_plan(records, fk_map)

    if dry_run:
        return {
            'company_id': company_id,
            'dry_run': True,
            'models': len(labels),
            'rows': len(records),
            'order': order,
            'minio_files': len(minio_manifest),
        }

    from django.apps import apps as django_apps

    pk_maps = {la: {} for la in labels}       # label -> {old_pk: new_pk}
    deferred = []       # (model, new_pk, attname, old_target_pk, target_label)
    inserted = 0

    with transaction.atomic():
        for label in order:
            model = django_apps.get_model(label)
            comp_attr = company_attr.get(label)
            scoped_fks = fk_map.get(label, {})
            for raw in by_label.get(label, []):
                dobj = next(iter(dj_serializers.deserialize(
                    'json', json.dumps([raw]))))
                inst = dobj.object
                old_pk = inst.pk
                inst.pk = None
                if hasattr(inst, 'id'):
                    inst.id = None
                if comp_attr:
                    setattr(inst, comp_attr, company_id)
                row_deferred = []
                for attname, tlabel in scoped_fks.items():
                    old = getattr(inst, attname, None)
                    if old is None:
                        continue
                    new = pk_maps[tlabel].get(old)
                    if new is not None:
                        setattr(inst, attname, new)
                    elif _is_nullable(model, attname):
                        setattr(inst, attname, None)
                        row_deferred.append((attname, old, tlabel))
                    else:
                        raise TenantImportError(
                            f"FK cyclique non-nullable {label}.{attname} → "
                            f"{tlabel} : import impossible en une passe.")
                inst.save()
                pk_maps[label][old_pk] = inst.pk
                inserted += 1
                for attname, old, tlabel in row_deferred:
                    deferred.append((model, inst.pk, attname, old, tlabel))

        # Seconde passe : patch des FK cycliques/self nullables différées, une
        # fois toutes les lignes insérées (donc toutes les cibles mappées).
        patched = 0
        for model, new_pk, attname, old, tlabel in deferred:
            new_target = pk_maps.get(tlabel, {}).get(old)
            if new_target is None:
                continue
            model.objects.filter(pk=new_pk).update(**{attname: new_target})
            patched += 1

    return {
        'company_id': company_id,
        'models': len(labels),
        'rows': inserted,
        'deferred_fk_patched': patched,
        'order': order,
        'minio_files': len(minio_manifest),
        'with_files': bool(with_files),
    }
