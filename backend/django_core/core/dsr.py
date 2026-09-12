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

# NTGRC8 — GARDES D'EFFACEMENT (registre en mémoire, même idiome que les
# fournisseurs). Une app peut refuser un effacement AVANT qu'il ne commence —
# typiquement une mise sous séquestre (legal hold) : anonymiser un dossier
# gelé pour contentieux détruirait une preuve. La garde est consultée UNE
# fois, avant tout appel de fournisseur : un effacement à moitié fait serait
# pire que pas d'effacement du tout.
# ``core`` reste fondation : il ne connaît que le NOM et le CALLABLE.
_ERASURE_GUARDS: dict[str, object] = {}


class EffacementBloque(Exception):
    """Un effacement est refusé par une garde (ex. legal hold).

    Traduite en 409 (conflit d'état) par la vue — jamais en 500, et jamais en
    échec silencieux : le demandeur doit savoir POURQUOI sa demande n'a pas
    été exécutée.
    """


def register_erasure_guard(name, fn):
    """Enregistre une garde d'effacement (idempotent, appelée en ``ready()``).

    ``fn(company, subject_identifier)`` renvoie un MOTIF (str) pour bloquer,
    ou une valeur fausse pour laisser passer.
    """
    if not name or fn is None:
        raise ValueError("Garde d'effacement : nom + callable requis.")
    _ERASURE_GUARDS[name] = fn


def unregister_erasure_guard(name):
    """Retire une garde (surtout utile en test pour isoler le registre)."""
    _ERASURE_GUARDS.pop(name, None)


def list_erasure_guards():
    """Noms des gardes d'effacement enregistrées (rendu stable)."""
    return sorted(_ERASURE_GUARDS.keys())


def verifier_gardes_effacement(company, subject_identifier):
    """Lève ``EffacementBloque`` si UNE garde refuse l'effacement.

    Une garde qui lève une exception technique n'est PAS interprétée comme un
    refus (on ne bloque pas un droit légal sur un bug) : elle est ignorée,
    comme le registre isole déjà chaque fournisseur.
    """
    for name in sorted(_ERASURE_GUARDS.keys()):
        try:
            motif = _ERASURE_GUARDS[name](company, subject_identifier)
        except EffacementBloque:
            raise
        except Exception:  # noqa: BLE001 - une garde en échec ne bloque pas
            continue
        if motif:
            raise EffacementBloque(str(motif))


def register_dsr_provider(name, *, export=None, erase=None, erase_order=0):
    """Enregistre un fournisseur DSR pour une app (idempotent).

    Au moins un de ``export`` / ``erase`` doit être fourni.

    ``erase_order`` (défaut 0) ordonne l'EFFACEMENT, jamais l'export. Un
    fournisseur qui DÉTRUIT la clé de résolution des autres (l'app qui porte
    l'identité de la personne : email, téléphone) doit passer EN DERNIER,
    sinon les apps qui résolvent PAR ELLE ne trouvent plus rien à
    pseudonymiser et l'effacement est silencieusement partiel. À ordre égal
    l'ordre reste alphabétique (comportement historique).
    """
    if not name or (export is None and erase is None):
        raise ValueError('Fournisseur DSR : nom + export et/ou erase requis.')
    _PROVIDERS[name] = {
        'export': export, 'erase': erase, 'erase_order': int(erase_order)}


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

    ORDRE : ``erase_order`` puis le nom. L'app qui porte l'IDENTITÉ (le CRM :
    email / téléphone) s'efface en DERNIER — les fournisseurs qui résolvent
    leurs documents PAR cet identifiant (ventes → ``crm.selectors.
    client_ids_par_identifiant``) doivent tourner tant que la clé existe
    encore. C'est une DÉPENDANCE RÉELLE, pas une préférence : en ordre
    alphabétique (``crm`` avant ``ventes``) l'effacement des Ventes ne
    trouvait plus aucun devis et repartait à zéro, en silence.
    """
    out = {}
    for name, prov in sorted(
            _PROVIDERS.items(),
            key=lambda item: (item[1].get('erase_order', 0) or 0, item[0])):
        fn = prov.get('erase')
        if fn is None:
            continue
        try:
            out[name] = fn(company, subject_identifier)
        except Exception as exc:  # noqa: BLE001 - isolation par fournisseur
            out[name] = {'erreur': str(exc)}
    return out


# ===========================================================================
# NTGRC3 — machine à états de la demande + échéance légale 30 jours.
#
# Le cycle de vie légal est : reçue → (vérification d'identité) → traitée ou
# refusée. On ne livre jamais les données d'une personne sans s'être assuré
# que le demandeur est bien elle ; et une demande CLOSE (traitée/refusée) ne
# se rouvre pas — elle donnerait un second export sans nouvelle demande.
# Couche de statut DOCUMENTAIRE permanente, sans aucun rapport avec le funnel
# commercial de STAGES.py.
# ===========================================================================


class TransitionInterdite(ValueError):
    """Transition de statut illégale sur une ``DataSubjectRequest``.

    Traduite en 400 par la vue (jamais 500) : le message NOMME le statut
    courant et le statut visé, en français.
    """


def transitions_autorisees(statut):
    """Statuts atteignables depuis ``statut`` (jamais None)."""
    from .models import DataSubjectRequest

    table = {
        DataSubjectRequest.STATUT_RECUE: {
            DataSubjectRequest.STATUT_EN_VERIFICATION,
            DataSubjectRequest.STATUT_TRAITEE,
            DataSubjectRequest.STATUT_REFUSEE,
        },
        DataSubjectRequest.STATUT_EN_VERIFICATION: {
            DataSubjectRequest.STATUT_TRAITEE,
            DataSubjectRequest.STATUT_REFUSEE,
        },
        # Statuts TERMINAUX : une demande close ne se rouvre pas.
        DataSubjectRequest.STATUT_TRAITEE: set(),
        DataSubjectRequest.STATUT_REFUSEE: set(),
    }
    return table.get(statut, set())


def verifier_transition(request, cible):
    """Lève ``TransitionInterdite`` si ``request`` ne peut pas passer à
    ``cible``. Ne modifie rien."""
    from .models import DataSubjectRequest

    libelles = dict(DataSubjectRequest.STATUT_CHOICES)
    if cible not in libelles:
        raise TransitionInterdite(
            f'Statut « {cible} » inconnu pour une demande de droit.')
    if cible not in transitions_autorisees(request.statut):
        raise TransitionInterdite(
            f'Transition impossible : une demande « '
            f'{libelles.get(request.statut, request.statut)} » ne peut pas '
            f'passer à « {libelles[cible]} ».')


def prendre_en_charge(request):
    """Passe la demande en VÉRIFICATION D'IDENTITÉ (reçue → en_verification).

    Lève ``TransitionInterdite`` si la demande n'est plus au statut « reçue ».
    """
    from .models import DataSubjectRequest

    verifier_transition(request, DataSubjectRequest.STATUT_EN_VERIFICATION)
    request.statut = DataSubjectRequest.STATUT_EN_VERIFICATION
    request.save(update_fields=['statut', 'updated_at'])
    return request


def refuser_demande(request, motif=''):
    """Refuse la demande (motif obligatoire pour rester traçable)."""
    from .models import DataSubjectRequest

    verifier_transition(request, DataSubjectRequest.STATUT_REFUSEE)
    request.statut = DataSubjectRequest.STATUT_REFUSEE
    request.resultat = {'refus': True, 'motif': motif or ''}
    request.traitee_le = timezone.now()
    request.save(update_fields=['statut', 'resultat', 'traitee_le',
                                'updated_at'])
    return request


def demandes_en_retard(company, now=None):
    """Demandes de ``company`` dont l'échéance légale est DÉPASSÉE.

    « En retard » = échéance passée ET demande encore ouverte (ni traitée ni
    refusée). Bornée à la société — jamais de lecture cross-société.
    """
    from .models import DataSubjectRequest

    now = now or timezone.now()
    return (DataSubjectRequest.objects
            .filter(company=company, date_echeance__lt=now)
            .exclude(statut__in=[DataSubjectRequest.STATUT_TRAITEE,
                                 DataSubjectRequest.STATUT_REFUSEE])
            .order_by('date_echeance', 'id'))


def demandes_proches_echeance(company, within_days=7, now=None):
    """NTGRC34 — demandes OUVERTES dont l'échéance approche ou est dépassée.

    Pendant « préventif » de :func:`demandes_en_retard` : un rappel qui ne
    part qu'une fois le délai légal DÉPASSÉ arrive toujours trop tard. La
    fenêtre inclut donc le retard (échéance déjà passée) ET l'imminence
    (échéance dans ``within_days`` jours) — c'est la même file de travail.

    Bornée à la société ; triée par échéance la plus proche d'abord.
    """
    from .models import DataSubjectRequest

    now = now or timezone.now()
    limite = now + timezone.timedelta(days=max(0, int(within_days or 0)))
    return (DataSubjectRequest.objects
            .filter(company=company, date_echeance__isnull=False,
                    date_echeance__lte=limite)
            .exclude(statut__in=[DataSubjectRequest.STATUT_TRAITEE,
                                 DataSubjectRequest.STATUT_REFUSEE])
            .order_by('date_echeance', 'id'))


def traiter_demande(request):
    """Exécute une ``DataSubjectRequest`` (accès → export, effacement → erase).

    Met à jour ``resultat`` / ``statut`` / ``traitee_le``. Multi-tenant : la
    société de la demande borne tous les fournisseurs.
    """
    from .models import DataSubjectRequest

    # NTGRC3 — garde de transition : une demande déjà CLOSE (traitée/refusée)
    # ne se re-traite pas ; sinon un second export partirait sans qu'aucune
    # nouvelle demande n'ait été déposée.
    verifier_transition(request, DataSubjectRequest.STATUT_TRAITEE)

    company = request.company
    subject = request.subject_identifier
    if request.kind == DataSubjectRequest.KIND_ACCESS:
        request.resultat = exporter(company, subject)
    elif request.kind == DataSubjectRequest.KIND_ERASURE:
        # NTGRC8 — les gardes passent AVANT le premier fournisseur : un
        # effacement à moitié fait (CRM anonymisé, stock refusé) serait pire
        # que pas d'effacement du tout. Rien n'est modifié si une garde refuse.
        verifier_gardes_effacement(company, subject)
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
