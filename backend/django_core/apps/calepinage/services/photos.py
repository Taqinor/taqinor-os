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

__all__ = ['PhotoRefusee', 'ajouter_photo_site', 'calage_photo_site',
           'modifier_photo_site', 'supprimer_photo_site',
           'photo_en_ligne', 'lire_octets_piece', 'MAX_OCTETS']


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


def calage_photo_site(photo, calage):
    """CAL53 — pose ou efface le calage (4 coins ``[lat, lng]``) d'une photo.

    ``calage`` vaut ``None`` pour EFFACER (photo non calée), ou un objet
    ``{"coins": [[lat, lng] × 4]}``. ACAL202 : la forme est jugée par LE
    validateur unique du noyau (``core.calepinage.calage.valider_quatre_coins``,
    partagé avec ``apps.visites``) — un quadrilatère confondu, aligné ou croisé
    est refusé. Chaque refus NOMME le champ ``calage``.

    Args:
        photo: la ``PhotoSite`` — sa société fait foi (bornée par l'appelant).
        calage: ``None``, ou ``{"coins": [...]}``.

    Raises:
        PhotoRefusee: forme invalide ou quadrilatère dégénéré — champ
            ``calage``.
    """
    from core.calepinage.calage import CalageInvalide, valider_quatre_coins

    if calage is None:
        photo.calage = None
        photo.save(update_fields=['calage'])
        return photo
    try:
        photo.calage = valider_quatre_coins(calage)
    except CalageInvalide as refus:
        raise PhotoRefusee(str(refus), champ='calage') from None
    photo.save(update_fields=['calage'])
    return photo


#: ACAL202 — les seuls champs qu'un PATCH de photo peut changer. Le fichier,
#: la société, l'auteur, la provenance et le calage (route dédiée) n'en sont
#: jamais.
CHAMPS_MODIFIABLES = ('genre', 'prise_le', 'legende')


def modifier_photo_site(photo, donnees):
    """ACAL202 — corrige le genre, la date de prise de vue et/ou la légende.

    Seules les clés PRÉSENTES changent ; chacune est validée comme à la
    création (date saisie, jamais future ; genre parmi les choix). Une clé
    hors ``CHAMPS_MODIFIABLES`` est ignorée.

    Raises:
        PhotoRefusee: date absente/illisible/future, genre inconnu — le champ
            fautif est nommé.
    """
    donnees = donnees if hasattr(donnees, 'keys') else {}
    champs = []
    if 'prise_le' in donnees:
        photo.prise_le = _date_saisie(donnees.get('prise_le'))
        champs.append('prise_le')
    if 'genre' in donnees:
        photo.genre = _genre_saisi(donnees.get('genre'))
        champs.append('genre')
    if 'legende' in donnees:
        legende = donnees.get('legende')
        photo.legende = (legende if isinstance(legende, str) else '')[:200]
        champs.append('legende')
    if champs:
        photo.save(update_fields=champs)
    return photo


def supprimer_photo_site(photo):
    """ACAL202 — retire la photo ET sa pièce jointe propre.

    La pièce d'une photo DÉPOSÉE ici (rattachée au calepinage) part avec elle.
    Une photo REPRISE d'une visite (CALX364) partage la pièce de la visite :
    seule la fiche photo du calepinage est retirée, la preuve de la visite
    reste intacte.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    piece = photo.attachment
    calepinage = photo.calepinage
    propre = (
        piece.content_type_id
        == ContentType.objects.get_for_model(type(calepinage)).pk
        and piece.object_id == calepinage.pk)
    with transaction.atomic():
        photo.delete()
        if propre and not piece.photos_site_calepinage.exists():
            cle = piece.file_key
            piece.delete()
            # ACAL300 — l'OBJET stocké part aussi (effacement loi 09-08),
            # une fois la suppression en base VALIDÉE (jamais un fichier
            # perdu sous une ligne restaurée par un rollback).
            transaction.on_commit(lambda: _supprimer_objet(cle))


def _supprimer_objet(cle):
    """Supprime l'objet stocké d'une pièce PROPRE au calepinage — dans LE
    bon magasin (``roofs/…`` : ventes ; ``attachments/…`` : records).
    Best-effort journalisé : un magasin muet ne fait pas échouer le geste."""
    try:
        if str(cle or '').startswith(PREFIXE_TELEVERSEMENTS):
            from apps.records.storage import delete_attachment

            delete_attachment(cle)
        elif cle:
            from apps.ventes import services as ventes_services

            ventes_services.supprimer_fichier_toiture(cle)
    except Exception:  # noqa: BLE001 — journalisé, jamais propagé
        import logging

        logging.getLogger(__name__).exception(
            'ACAL300 : objet stocké non supprimé (%s)', cle)


#: Les pièces jointes générales (``records.store_attachment``) vivent dans le
#: bucket des téléversements ; tout le reste (rendus de toiture, photos du
#: module, plans) dans le bucket PDF, sous ``roofs/…``.
PREFIXE_TELEVERSEMENTS = 'attachments/'


def lire_octets_piece(file_key):
    """ACAL200 — les OCTETS d'une pièce, lus dans LE BON bucket, ou ``None``.

    Une photo DÉPOSÉE dans le module a une clé ``roofs/…`` (bucket PDF) ; une
    photo REPRISE d'une visite réutilise l'``Attachment`` de la visite, clé
    ``attachments/…`` (bucket des téléversements). Lire l'une dans le bucket de
    l'autre rendait une image vide : le bucket se résout donc ICI, une seule
    fois, par le préfixe de la clé. Absence ou magasin muet ⇒ ``None``.
    """
    if not file_key:
        return None
    if str(file_key).startswith(PREFIXE_TELEVERSEMENTS):
        from apps.records.storage import fetch_attachment

        octets, erreur = fetch_attachment(file_key)
        return None if erreur else octets
    from apps.ventes import services as ventes_services

    return ventes_services.lire_fichier_toiture(file_key)


def photo_en_ligne(photo):
    """La photo telle que l'écran l'affiche — clés TOUJOURS présentes.

    ``url`` est un chemin RELATIF même origine servi par Django (ACAL200 :
    jamais l'hôte interne de MinIO) ; ``calage`` vaut ``null`` tant que CAL53
    n'a pas posé de calage — jamais un objet vide qui laisserait croire à un
    calage neutre.
    """
    from .presentation import url_fichier_photo

    piece = photo.attachment
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
        'url': url_fichier_photo(photo.calepinage_id, photo.pk),
        'ajoutee_par': getattr(photo.ajoutee_par, 'username', '') or '',
        'created_at': photo.created_at.isoformat() if photo.created_at
        else None,
    }
