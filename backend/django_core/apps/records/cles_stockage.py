"""ADOC193 (C-ADOC-VER4-010) — registre des DÉTENTEURS d'une clé de stockage
objet : ``(label de modèle, champ, bucket)``, rempli par chaque ``apps.py``
(append-only). Une clé encore tenue par un détenteur n'est jamais effacée
(``records.storage.delete_attachment``). Nouveau fichier car : registre, pas
client MinIO. ``records`` est une fondation : les modèles des détenteurs sont
résolus par ``django.apps.apps.get_model`` à l'appel, jamais importés."""
import logging

logger = logging.getLogger(__name__)

_DETENTEURS = []


def enregistrer_detenteur(label, champ, bucket):
    """Déclare ``<app_label.Modele>.<champ>`` détenteur de clés du ``bucket``
    (nom du bucket, ex. ``settings.MINIO_BUCKET_UPLOADS``). Idempotent."""
    entree = (label, champ, bucket)
    if entree not in _DETENTEURS:
        _DETENTEURS.append(entree)


def detenteurs(bucket=None):
    """Entrées du registre (toutes, ou celles du ``bucket``)."""
    return [e for e in _DETENTEURS if bucket is None or e[2] == bucket]


def cle_detenue(cle, bucket, sauf=()):
    """True si une ligne d'un détenteur du ``bucket`` porte encore ``cle``,
    hors les instances ``sauf`` (celles qui libèrent la clé). Toutes sociétés :
    une clé est un identifiant physique, le doute conserve le fichier."""
    from django.apps import apps
    cle = (cle or '').strip()
    if not cle:
        return False
    exclus = {(o._meta.label, o.pk) for o in sauf}
    for label, champ, _ in detenteurs(bucket):
        try:
            modele = apps.get_model(label)
        except LookupError:
            continue
        pks = [pk for lab, pk in exclus if lab == modele._meta.label]
        if modele._base_manager.filter(**{champ: cle}).exclude(
                pk__in=pks).exists():
            return True
    return False
