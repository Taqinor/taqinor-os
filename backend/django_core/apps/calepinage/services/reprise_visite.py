"""CALX364 — reprendre les mesures et les photos d'une visite technique.

LE CONSTAT
----------
``ReleveTerrain`` et ``services/releve.py::enregistrer_releve`` n'acceptaient
qu'une saisie manuelle de chaînes de cotes, ``services/photos.py::
ajouter_photo_site`` exigeait un fichier téléversé : rien ne savait reprendre
ce qu'une visite technique avait DÉJÀ capturé sur le toit, et aucun champ ne
disait d'où venait une mesure. Le concepteur ressaisissait.

LA PORTE, ET SES QUATRE RÈGLES (contrat ``calepinage_releve_visite.json``)
---------------------------------------------------------------------------
* **La lecture passe par la porte de ``visites``.** Le lead vient de
  ``apps.crm.selectors.get_company_lead`` (borné à la société du calepinage),
  le relevé de ``apps.visites.selectors.releve_pour_calepinage`` (CALX363) —
  JAMAIS ``apps.visites.models`` : ce module ne connaît ni ``VisiteTerrain``
  ni ``VisiteMedia``.
* **Rien n'est converti ni complété (D7).** Les mesures sont rangées TELLES
  QUE SAISIES dans ``ReleveTerrain.mesures`` : une longueur n'est pas une
  chaîne de cotes, une orientation « sud » n'est pas un azimut. Les photos
  sont rattachées à la pièce jointe EXISTANTE de la visite
  (``records.Attachment``) — aucun octet n'est recopié, aucune seconde pièce
  jointe n'est créée.
* **Une reprise par visite.** Un second « Reprendre » ne crée rien : il rend
  ``deja_repris: true`` et le relevé DÉJÀ créé. La garantie tient en base
  (contrainte partielle ``uniq_releve_reprise_par_visite``) ET sous verrou de
  ligne du calepinage, pour deux clics simultanés.
* **La provenance est écrite.** Le relevé et chaque photo reprise portent
  ``provenance='visite'`` ; tout le reste garde ``'saisie'`` (D12).

LES DEUX DATES, DITES TELLES QU'ELLES SONT
------------------------------------------
* ``releve_le`` du relevé repris est le jour de la REPRISE (le bandeau de
  l'onglet affiche « repris le … par … ») : la porte de ``visites`` ne publie
  pas la date de réalisation de la visite, et aucune autre date n'est
  présentée à sa place. La visite d'origine reste tracée par ``visite_id``.
* ``prise_le`` d'une photo reprise est la date d'enregistrement de SA pièce
  jointe (``records.Attachment.created_at``, en heure locale) : la photo d'une
  visite est versée depuis le terrain, dans la checklist, au moment où elle
  est prise — c'est la seule date réellement stockée pour elle.

La société et l'auteur viennent TOUJOURS du serveur. Aucun statut ne bouge.
"""
from __future__ import annotations

#: Le motif publié quand le calepinage n'a AUCUN lead : il n'y a pas de
#: visite technique à chercher. Recopié tel quel par l'onglet (CALX365).
MOTIF_SANS_LEAD = (
    "Ce calepinage n'est rattaché à aucun lead : il n'y a pas de visite "
    "technique à reprendre.")

__all__ = ['MOTIF_SANS_LEAD', 'RepriseRefusee', 'etat_reprise',
           'reprendre_visite']


class RepriseRefusee(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé."""

    def __init__(self, message, champ='visite_id'):
        super().__init__(message)
        self.champ = champ

    def corps(self):
        return {self.champ or 'detail': str(self)}


def _lecture_visite(calepinage):
    """Ce que la porte de ``visites`` sert pour le lead du calepinage.

    Les cinq clés ``{visite_id, validee_le, mesures, photos, motif_absence}``
    — mêmes clés à ``None`` et motif NOMMÉ quand rien n'est à reprendre.
    """
    from apps.crm.selectors import get_company_lead
    from apps.visites.selectors import releve_pour_calepinage

    lead_id = getattr(calepinage, 'lead_id', None)
    if not lead_id:
        return {'visite_id': None, 'validee_le': None, 'mesures': None,
                'photos': None, 'motif_absence': MOTIF_SANS_LEAD}
    lead = get_company_lead(getattr(calepinage, 'company', None), lead_id)
    return releve_pour_calepinage(lead)


def _composer_reponse(lecture, bloc_releve):
    """La réponse de ``releve-visite/`` — UNE forme, GET comme POST.

    Fonction PURE : ``lecture`` est le dictionnaire de la porte ``visites``,
    ``bloc_releve`` le relevé déjà repris (``_releve_en_ligne``) ou ``None``.
    """
    return {
        'visite_id': lecture.get('visite_id'),
        'validee_le': lecture.get('validee_le'),
        'mesures': lecture.get('mesures'),
        'photos': lecture.get('photos'),
        'motif_absence': lecture.get('motif_absence'),
        'deja_repris': bloc_releve is not None,
        'releve': bloc_releve,
    }


def _horodatage(moment):
    return moment.isoformat() if moment is not None else None


def _photo_en_ligne(photo):
    return {
        'id': photo.pk,
        'attachment_id': photo.attachment_id,
        'slot_code': photo.slot_code or '',
        'provenance': photo.provenance,
    }


def _releve_en_ligne(releve, photos):
    """Le bloc ``releve`` du contrat : date et auteur de la reprise."""
    return {
        'id': releve.pk,
        'provenance': releve.provenance,
        'releve_le': (releve.releve_le.isoformat()
                      if releve.releve_le else None),
        'releve_par': getattr(releve.releve_par, 'username', '') or '',
        'created_at': _horodatage(releve.created_at),
        'photos': [_photo_en_ligne(photo) for photo in photos],
    }


def _releve_repris(calepinage, visite_id):
    """Le relevé de CE calepinage déjà repris de CETTE visite, ou ``None``."""
    from ..models import ProvenanceTerrain, ReleveTerrain

    if visite_id is None or not getattr(calepinage, 'pk', None):
        return None
    return (ReleveTerrain.objects
            .select_related('releve_par')
            .filter(calepinage=calepinage, company_id=calepinage.company_id,
                    provenance=ProvenanceTerrain.VISITE, visite_id=visite_id)
            .first())


def _bloc(releve):
    if releve is None:
        return None
    photos = releve.photos.order_by('id')
    return _releve_en_ligne(releve, photos)


def etat_reprise(calepinage):
    """GET — la dernière visite VALIDÉE du lead, et si elle est déjà reprise.

    Lecture PURE : rien n'est écrit, ni ici ni côté visite.
    """
    lecture = _lecture_visite(calepinage)
    return _composer_reponse(
        lecture, _bloc(_releve_repris(calepinage, lecture.get('visite_id'))))


def _entiers_uniques(photos):
    """Les photos servies, une par pièce jointe (ordre servi conservé)."""
    vues, gardees = set(), []
    for photo in photos or []:
        if not isinstance(photo, dict):
            continue
        piece = photo.get('attachment_id')
        if isinstance(piece, bool) or not isinstance(piece, int):
            continue
        if piece in vues:
            continue
        vues.add(piece)
        gardees.append(photo)
    return gardees


def _rattacher_photos(calepinage, releve, photos, user):
    """Rattache chaque photo reprise à SA pièce jointe existante.

    Bornage : une pièce jointe d'une autre société (ligne corrompue) ou
    disparue depuis la lecture n'est simplement pas rattachée. Une pièce déjà
    rangée dans CE calepinage n'est jamais redupliquée : sa fiche photo est
    rattachée au relevé si elle ne l'était à aucun.
    """
    from django.utils import timezone

    from apps.records.models import Attachment

    from ..models import PhotoSite, ProvenanceTerrain

    retenues = _entiers_uniques(photos)
    ids = [photo['attachment_id'] for photo in retenues]
    if not ids:
        return
    pieces = {piece.pk: piece for piece in Attachment.objects.filter(
        pk__in=ids, company_id=calepinage.company_id)}
    deja = {photo.attachment_id: photo for photo in PhotoSite.objects.filter(
        calepinage=calepinage, attachment_id__in=ids)}
    auteur = user if getattr(user, 'pk', None) else None
    for photo in retenues:
        piece = pieces.get(photo['attachment_id'])
        if piece is None:
            continue
        existante = deja.get(piece.pk)
        if existante is not None:
            if existante.releve_id is None:
                existante.releve = releve
                existante.save(update_fields=['releve', 'updated_at'])
            continue
        PhotoSite.objects.create(
            company=calepinage.company,
            calepinage=calepinage,
            attachment=piece,
            genre=PhotoSite.Genre.SOL,
            prise_le=timezone.localtime(piece.created_at).date(),
            legende=str(photo.get('libelle') or '')[:200],
            releve=releve,
            provenance=ProvenanceTerrain.VISITE,
            slot_code=str(photo.get('slot_code') or '')[:80],
            ajoutee_par=auteur,
        )


def reprendre_visite(calepinage, user=None):
    """POST — reprend la dernière visite validée dans ce calepinage.

    Returns:
        ``(reponse, cree)`` — la réponse du contrat (``deja_repris: true``,
        ``releve`` rempli) et ``True`` si un relevé vient d'être créé,
        ``False`` s'il existait déjà (rien n'est recréé).

    Raises:
        RepriseRefusee: aucune visite validée à reprendre — le message est le
            motif NOMMÉ par la porte de ``visites`` (champ ``visite_id``).
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils import timezone

    from ..models import Calepinage, ProvenanceTerrain, ReleveTerrain
    from .releve import resoudre_chaines

    lecture = _lecture_visite(calepinage)
    visite_id = lecture.get('visite_id')
    if visite_id is None:
        raise RepriseRefusee(lecture.get('motif_absence') or MOTIF_SANS_LEAD)

    with transaction.atomic():
        # Deux « Reprendre » simultanés sur le MÊME calepinage passent l'un
        # après l'autre : le second trouve le relevé du premier. ``list``
        # évalue la requête — c'est ICI que le verrou de ligne est pris.
        list(Calepinage.objects.select_for_update()
             .filter(pk=calepinage.pk).values_list('pk', flat=True))
        existant = _releve_repris(calepinage, visite_id)
        if existant is not None:
            return _composer_reponse(lecture, _bloc(existant)), False

        releve = ReleveTerrain(
            company=calepinage.company,
            calepinage=calepinage,
            chaines=[],
            # Le MÊME chemin de résolution que toute saisie : aucune chaîne,
            # donc aucune cote — la géométrie le dit, elle n'invente rien.
            geometrie=resoudre_chaines([]),
            releve_le=timezone.localdate(),
            notes=f'Repris de la visite technique n° {visite_id}.',
            releve_par=user if getattr(user, 'pk', None) else None,
            provenance=ProvenanceTerrain.VISITE,
            visite_id=visite_id,
            mesures=list(lecture.get('mesures') or []),
        )
        try:
            releve.full_clean(exclude=['company', 'calepinage', 'releve_par'])
        except ValidationError as erreur:
            champ, messages = sorted(erreur.message_dict.items())[0]
            raise RepriseRefusee(messages[0], champ)
        releve.save()
        _rattacher_photos(calepinage, releve, lecture.get('photos'), user)
    return _composer_reponse(lecture, _bloc(releve)), True
