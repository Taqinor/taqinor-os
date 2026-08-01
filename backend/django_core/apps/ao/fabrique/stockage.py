"""AOF150 — archivage MinIO IMMUABLE + manifeste de pack.

Trois règles, toutes structurelles :

1. **Rien ne s'écrase.** La clé porte l'indice ET l'empreinte —
   ``ao/<company>/<dossier>/<code>/<indice>-<empreinte8>.<ext>`` — et
   l'unicité est en BASE. Ré-écrire la même clé lève ``EcrasementRefuse``.
2. **Le pack courant est un MANIFESTE de clés, pas un répertoire.** Un
   répertoire accumule les versions et laisse le dépôt choisir ; le dépôt réel
   contient encore aujourd'hui deux bordereaux homonymes divergents.
3. **Mémoire BORNÉE.** L'écriture se fait pièce par pièce EN FLUX : les octets
   passent par morceaux, jamais tous en mémoire (un worker Celery sature
   sinon). ``ecrire_artefact`` consomme un ITÉRABLE de morceaux.

Aucun nouveau ``FileField`` : les octets vivent dans MinIO, référencés par
``records.Attachment``.
"""
from __future__ import annotations

import hashlib

__all__ = [
    'EcrasementRefuse',
    'TAILLE_MORCEAU',
    'cle_artefact',
    'construire_manifeste',
    'ecrire_artefact',
    'manifeste_courant',
]

#: Taille d'un morceau de flux (64 Kio) — le plafond mémoire d'une écriture.
TAILLE_MORCEAU = 64 * 1024


class EcrasementRefuse(Exception):
    """Levée quand une clé d'artefact existe déjà (jamais d'écrasement)."""


def cle_artefact(company_id, dossier_id, code, indice, empreinte,
                 extension='pdf'):
    """``ao/<company>/<dossier>/<code>/<indice>-<empreinte8>.<ext>``.

    Le préfixe société est obligatoire (isolation multi-tenant du stockage
    objet, motif SCA42) ; l'indice et l'empreinte rendent la clé UNIQUE par
    version, ce qui est exactement ce qui empêche l'écrasement.
    """
    empreinte8 = (empreinte or '')[:8] or '00000000'
    extension = (extension or 'bin').lstrip('.')
    return (f'ao/{company_id}/{dossier_id}/{code}/'
            f'{indice}-{empreinte8}.{extension}')


def _televerser_en_flux(cle, morceaux, mime):
    """Téléverse un flux de morceaux vers MinIO — mémoire bornée.

    Chaque morceau est écrit puis relâché : la fonction ne conserve jamais
    plus d'un morceau à la fois. Renvoie ``(taille, empreinte_contenu)``.
    """
    import tempfile

    from django.conf import settings

    from apps.ventes.utils.minio_client import (
        ensure_uploads_bucket, get_minio_client,
    )

    taille = 0
    digest = hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=TAILLE_MORCEAU * 4) as tampon:
        for morceau in morceaux:
            if not morceau:
                continue
            taille += len(morceau)
            digest.update(morceau)
            tampon.write(morceau)
        tampon.seek(0)
        client = get_minio_client()
        ensure_uploads_bucket()
        client.upload_fileobj(
            tampon, settings.MINIO_BUCKET_UPLOADS, cle,
            ExtraArgs={'ContentType': mime or 'application/octet-stream'})
    return taille, digest.hexdigest()


def ecrire_artefact(dossier, *, code, indice, empreinte, morceaux,
                    extension='pdf', mime='application/pdf',
                    televerseur=None):
    """Archive UN artefact, en flux, sans jamais écraser (AOF150).

    Args:
        dossier: le ``DossierAO`` propriétaire.
        code / indice: identifient la pièce et sa version.
        empreinte: empreinte du CONTEXTE au moment de la production.
        morceaux: ITÉRABLE d'``bytes`` — consommé morceau par morceau, jamais
            matérialisé en entier (contrainte mémoire d'AOF150).
        televerseur: injection de test — ``(cle, morceaux, mime) ->
            (taille, empreinte_contenu)``. Par défaut, l'écriture MinIO.

    Raises:
        EcrasementRefuse: la clé existe déjà — un artefact est IMMUABLE.
    """
    from ..models import ArtefactAO

    cle = cle_artefact(dossier.company_id, dossier.pk, code, indice,
                       empreinte, extension)
    if ArtefactAO.objects.filter(
            company=dossier.company, cle=cle).exists():
        raise EcrasementRefuse(
            f'La clé « {cle} » existe déjà : un artefact archivé est IMMUABLE. '
            f'Produire un indice supérieur, jamais réécrire le même.')
    ecrire = televerseur or _televerser_en_flux
    taille, _ = ecrire(cle, morceaux, mime)
    return ArtefactAO.objects.create(
        company=dossier.company, dossier=dossier, code=code, indice=indice,
        empreinte=empreinte or '', cle=cle, taille=taille, mime=mime or '')


def manifeste_courant(dossier):
    """Le manifeste COURANT du dossier, ou None."""
    return dossier.manifestes.filter(courant=True).first()


def construire_manifeste(dossier, *, empreinte=None):
    """Construit le manifeste du pack COURANT (AOF150).

    N'y entrent QUE les artefacts produits sous l'empreinte courante du
    dossier : un indice antérieur est structurellement exclu, il ne « risque »
    pas d'y entrer, il ne le PEUT pas. Le manifeste précédent est démis de son
    statut de courant mais reste consultable en historique.
    """
    from django.db import transaction

    from ..models import ArtefactAO, ManifestePack
    from .coherence import empreinte_dossier

    empreinte = empreinte or empreinte_dossier(dossier)
    eligibles = ArtefactAO.objects.filter(
        company=dossier.company, dossier=dossier, empreinte=empreinte)
    with transaction.atomic():
        ManifestePack.objects.filter(
            dossier=dossier, courant=True).update(courant=False)
        manifeste = ManifestePack.objects.create(
            company=dossier.company, dossier=dossier, empreinte=empreinte,
            courant=True)
        manifeste.artefacts.set(eligibles)
    return manifeste
