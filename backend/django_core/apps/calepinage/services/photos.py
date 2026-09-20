"""CAL52 — recevoir et ranger une photo drone / oblique du site.

LE CONSTAT
----------
La seule photo réelle acceptée était celle de la visite terrain
(``VisiteTerrain.photo_toit_key``) : rien ne permettait d'importer une photo
drone dans un calepinage SANS devis. Parité marché : la mesure de toiture
depuis imagerie oblique/drone.

LES QUATRE DÉCISIONS
--------------------
* **UN SEUL MAGASIN.** Les octets partent au MÊME endroit que ``roof-image``
  (CAL19) — MinIO, validation magic-bytes, URL pré-signée — par les fonctions
  minces ``apps.ventes.services.type_image_toiture`` /
  ``stocker_image_toiture`` / ``url_image_toiture``. Ce module n'importe ni
  une vue ni un modèle ventes, et n'ouvre AUCUN second chemin de stockage.
* **AUCUN CHAMP FICHIER.** La ligne de fichier est un ``records.Attachment``
  (primitive plateforme, ARC26), rattaché au calepinage par le mécanisme
  générique ``ContentType`` — la cible est déjà déclarée dans
  ``apps/calepinage/platform.py`` (``record_targets``).
* **LA CLÉ EST DÉRIVÉE CÔTÉ SERVEUR** et porte la société
  (``roofs/<company_id>/calepinage-<pk>-photo-<uuid>.<ext>``, SCA42) : rien
  n'est lu du corps hors le fichier, le genre, la date et la légende.
* **LA DATE DE PRISE DE VUE EST SAISIE.** Jamais la date d'import : une photo
  versée six mois après le vol daterait le toit du mauvais jour. Sans date,
  la photo est REFUSÉE en nommant le champ.

AUCUNE PHOTOGRAMMÉTRIE SERVEUR : on range une photo, on ne la mesure pas. Le
calage (CAL53) a sa colonne, vide.
"""
from __future__ import annotations

from uuid import uuid4

#: Taille maximale acceptée (octets) — même ordre que les pièces jointes
#: génériques (``records.storage``). Une photo drone brute dépasse rarement
#: cette borne ; au-delà, le refus NOMME le champ plutôt que de faire tomber
#: la requête en 500.
MAX_OCTETS = 15 * 1024 * 1024

__all__ = ['PhotoRefusee', 'ajouter_photo_site', 'photo_en_ligne',
           'MAX_OCTETS']


class PhotoRefusee(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _date_saisie(valeur):
    """La date de prise de vue SAISIE, ou un refus qui nomme le champ."""
    from datetime import date

    from django.utils import timezone
    from django.utils.dateparse import parse_date

    if isinstance(valeur, date):
        prise_le = valeur
    else:
        texte = (valeur or '').strip() if isinstance(valeur, str) else ''
        if not texte:
            raise PhotoRefusee(
                "La date de prise de vue est obligatoire : elle est SAISIE, "
                "jamais déduite de la date d'import.", champ='prise_le')
        prise_le = parse_date(texte)
        if prise_le is None:
            raise PhotoRefusee(
                "Date de prise de vue illisible : attendu AAAA-MM-JJ "
                f"(reçu : « {texte} »).", champ='prise_le')
    if prise_le > timezone.localdate():
        raise PhotoRefusee(
            "La date de prise de vue ne peut pas être dans le futur "
            f"(reçu : {prise_le:%d/%m/%Y}).", champ='prise_le')
    return prise_le


def _genre_saisi(valeur):
    from ..models import PhotoSite

    texte = (valeur or '').strip().lower() if isinstance(valeur, str) else ''
    if not texte:
        return PhotoSite.Genre.DRONE
    admis = {choix.value for choix in PhotoSite.Genre}
    if texte not in admis:
        raise PhotoRefusee(
            f"Genre de photo inconnu : « {texte} ». Genres admis : "
            f"{', '.join(sorted(admis))}.", champ='genre')
    return texte


def ajouter_photo_site(calepinage, fichier, *, genre=None, prise_le=None,
                       legende='', user=None):
    """Range UNE photo de site et rend la ``PhotoSite`` créée.

    Args:
        calepinage: le pivot — sa société fait foi (posée côté serveur).
        fichier: le fichier téléversé (objet à ``.read()`` / ``.name``).
        genre: ``drone`` / ``oblique`` / ``sol``. Vide ⇒ ``drone``.
        prise_le: date SAISIE (``date`` ou ``AAAA-MM-JJ``). OBLIGATOIRE.
        legende: texte libre, facultatif.
        user: l'auteur — posé côté serveur.

    Raises:
        PhotoRefusee: fichier manquant, trop gros, non-image, date manquante
            ou illisible, genre inconnu. Le champ fautif est toujours nommé.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from apps.records.models import Attachment
    from apps.ventes import services as ventes_services

    from ..models import PhotoSite

    if fichier is None:
        raise PhotoRefusee("Fichier photo manquant (champ « photo »).",
                           champ='photo')

    # L'ordre compte : la date et le genre sont validés AVANT le téléversement,
    # pour ne jamais laisser un objet orphelin dans MinIO derrière un refus de
    # formulaire.
    prise_le = _date_saisie(prise_le)
    genre = _genre_saisi(genre)

    donnees = fichier.read()
    if not donnees:
        raise PhotoRefusee("Le fichier photo est vide.", champ='photo')
    if len(donnees) > MAX_OCTETS:
        raise PhotoRefusee(
            "Photo trop volumineuse : "
            f"{len(donnees) // (1024 * 1024)} Mo pour un maximum de "
            f"{MAX_OCTETS // (1024 * 1024)} Mo.", champ='photo')

    extension, mime = ventes_services.type_image_toiture(donnees)
    if extension is None:
        raise PhotoRefusee(
            "Ce fichier n'est pas une image (PNG ou JPEG attendu).",
            champ='photo')

    cle = (f'roofs/{calepinage.company_id or 0}/'
           f'calepinage-{calepinage.pk}-photo-{uuid4().hex}.{extension}')
    ventes_services.stocker_image_toiture(donnees, cle, content_type=mime)

    with transaction.atomic():
        piece = Attachment.objects.create(
            company=calepinage.company,
            content_type=ContentType.objects.get_for_model(type(calepinage)),
            object_id=calepinage.pk,
            file_key=cle,
            filename=(getattr(fichier, 'name', '') or f'photo.{extension}')[:255],
            size=len(donnees),
            mime=mime or '',
            uploaded_by=user if getattr(user, 'pk', None) else None,
        )
        photo = PhotoSite(
            company=calepinage.company,
            calepinage=calepinage,
            attachment=piece,
            genre=genre,
            prise_le=prise_le,
            legende=(legende or '')[:200],
            ajoutee_par=user if getattr(user, 'pk', None) else None,
        )
        photo.full_clean(exclude=['company', 'calepinage', 'attachment',
                                  'ajoutee_par'])
        photo.save()
    return photo


def photo_en_ligne(photo):
    """La photo telle que l'écran l'affiche — clés TOUJOURS présentes.

    ``url`` est PRÉ-SIGNÉE (même chemin que ``roof-image``) et vaut ``''``
    quand le stockage ne répond pas : une URL absente est une URL absente,
    jamais un lien mort présenté comme valide. ``calage`` vaut ``null`` tant
    que CAL53 n'a pas posé de calage — jamais un objet vide qui laisserait
    croire à un calage neutre.
    """
    from apps.ventes import services as ventes_services

    piece = photo.attachment
    try:
        url = ventes_services.url_image_toiture(piece.file_key) or ''
    except Exception:       # pragma: no cover - dépend du stockage
        url = ''
    return {
        'id': photo.pk,
        'genre': photo.genre,
        'prise_le': photo.prise_le.isoformat() if photo.prise_le else None,
        'legende': photo.legende or '',
        'calage': photo.calage,
        'file_key': piece.file_key,
        'filename': piece.filename,
        'mime': piece.mime or '',
        'size': piece.size,
        'url': url,
        'ajoutee_par': getattr(photo.ajoutee_par, 'username', '') or '',
        'created_at': photo.created_at.isoformat() if photo.created_at
        else None,
    }
