"""CAL208 — archiver un calepinage, RÉVERSIBLE, par la corbeille plateforme.

AUCUNE SECONDE CORBEILLE, AUCUNE SUPPRESSION DURE
-----------------------------------------------------
``apps.trash`` (NTUX7) est DÉJÀ la primitive corbeille transverse de tout le
dépôt (``ElementSupprime``, générique par ``ContentType``). Ce module ne
crée RIEN : il journalise une suppression LOGIQUE (``apps.trash.services.
journaliser_suppression``) et restaure via ``apps.trash.services.restaurer``
— jamais un ``.delete()`` sur ``Calepinage``, jamais un second modèle
d'archive.

L'ÉTAT EST SUR LE MODÈLE (ACAL118, C-ACAL-099)
------------------------------------------------
La purge de rétention de la corbeille (``purger_expires``) EFFACE l'entrée :
un état archivé porté par la corbeille « ressuscitait » à J+31. L'état vit
donc dans ``Calepinage.archive_le`` ; la corbeille reste le JOURNAL du geste
(et garde le devis détaché pour la restauration). Le lecteur unique des
actifs est ``selectors.calepinages_actifs``.

Un calepinage qui PORTE un devis non brouillon ne s'archive pas (refus nommé,
champ ``devis``) ; lié à un brouillon, il est archivé ET détaché. Le statut
du devis n'est jamais écrit (règle #4).
"""
from __future__ import annotations

from rest_framework.exceptions import APIException

#: Clé de registre / ContentType, DANS ``apps.trash`` (``cle_modele``).
CLE_MODELE = 'calepinage.calepinage'

#: ACAL148 — clé de registre d'une PIÈCE JOINTE mise à la corbeille (fichier
#: météo retiré ou remplacé). ``records.Attachment`` ne porte aucun drapeau de
#: soft-delete : sans restaurateur dédié, le repli générique de ``apps.trash``
#: lèverait ``RestaurationImpossible``.
CLE_PIECE_JOINTE = 'records.attachment'

__all__ = ['ArchivageInvalide', 'CLE_MODELE', 'CLE_PIECE_JOINTE',
           'EcritureArchiveRefusee', 'MESSAGE_ARCHIVE', 'est_archive',
           'archiver', 'raison_refus_archivage',
           'refuser_ecriture_si_archive', 'restaurer',
           'RestaurationEnConflit',
           'restaurateur_calepinage', 'restaurateur_piece_jointe']


class ArchivageInvalide(ValueError):
    """Erreur métier, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


#: ACAL118 — le refus d'ÉCRITURE sur un archivé (verrou, garde d'écriture).
MESSAGE_ARCHIVE = ('Calepinage archivé : restaurez-le avant toute '
                   'modification.')

#: ACAL118 — le statut de devis qui laisse archiver (et détacher) : seul un
#: BROUILLON se détache ; un devis envoyé/accepté porte la conception.
_STATUT_DETACHABLE = 'brouillon'


def est_archive(calepinage):
    """``True`` si ``calepinage`` est archivé — ACAL118 : lu sur le MODÈLE
    (``archive_le``), jamais sur la corbeille dont la purge efface l'entrée.
    Lecture pure."""
    return getattr(calepinage, 'archive_le', None) is not None


class EcritureArchiveRefusee(APIException):
    """ACAL119 (D-ACAL-25) — 409 ``{detail}`` : une écriture visant un
    calepinage ARCHIVÉ. ``APIException`` : l'enveloppe globale respecte le
    statut sans toucher un seul ``except`` de vue."""

    status_code = 409
    default_code = 'calepinage_archive'
    default_detail = MESSAGE_ARCHIVE


def refuser_ecriture_si_archive(calepinage):
    """ACAL119 — LA garde d'écriture d'un archivé (une seule) : appelée par
    le point commun des méthodes non sûres du module
    (``CalepinageViewSet.get_object``), sauf « Restaurer ». No-op pour un
    calepinage actif."""
    if est_archive(calepinage):
        raise EcritureArchiveRefusee(MESSAGE_ARCHIVE)


def raison_refus_archivage(calepinage):
    """ACAL120 — le motif pour lequel ``archiver`` refuserait (``''`` s'il
    accepte) : LE prédicat de ``permissions.peut_supprimer`` du détail
    (« supprimer » = archiver ; DELETE est 405)."""
    refus = _refus_devis_porte(calepinage)
    return str(refus) if refus is not None else ''


def _refus_devis_porte(calepinage):
    """ACAL118 — un calepinage qui PORTE un devis non brouillon ne s'archive
    pas : refus nommé (champ ``devis``) — ``None`` sinon."""
    devis = getattr(calepinage, 'devis', None)
    if devis is None or getattr(devis, 'statut', None) == _STATUT_DETACHABLE:
        return None
    reference = ((getattr(devis, 'reference', '') or '').strip()
                 or f'#{devis.pk}')
    if hasattr(devis, 'get_statut_display'):
        statut = devis.get_statut_display()
    else:
        statut = str(getattr(devis, 'statut', ''))
    return ArchivageInvalide(
        f'Ce calepinage porte le devis {reference} ({statut}) : '
        "détachez-le d'abord", champ='devis')


def archiver(calepinage, *, user=None):
    """Archive ``calepinage`` — réversible, journalisé (ACAL118).

    * lié à un devis NON brouillon ⇒ refus nommé (champ ``devis``), rien
      n'est écrit ;
    * lié à un devis BROUILLON ⇒ archivé ET détaché (``devis=None``,
      journalisé) ; le devis détaché est gardé dans l'entrée de corbeille
      pour être rattaché à la restauration s'il est libre ;
    * ``archive_le`` est posé sur le MODÈLE (survit à la purge) ; la
      corbeille reste le journal du geste.

    Idempotent : archiver un archivé ne crée pas de seconde entrée.

    Raises:
        ArchivageInvalide: calepinage non enregistré, ou devis non brouillon
            lié.
    """
    from django.db import transaction
    from django.utils import timezone

    from apps.trash.services import journaliser_suppression

    from .journal import journaliser_lien_devis, noter

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ArchivageInvalide(
            "Impossible d'archiver un calepinage non enregistré.",
            champ='calepinage')
    if est_archive(calepinage):
        # Idempotent : l'entrée existante (et le devis détaché qu'elle garde)
        # n'est jamais réécrite par un second clic.
        from apps.trash.selectors import entree_active

        return entree_active(calepinage)
    refus = _refus_devis_porte(calepinage)
    if refus is not None:
        raise refus

    with transaction.atomic():
        devis_detache = calepinage.devis_id
        champs = []
        if devis_detache:
            calepinage.devis = None
            champs.append('devis')
        if calepinage.archive_le is None:
            calepinage.archive_le = timezone.now()
            champs.append('archive_le')
        if champs:
            calepinage.save(update_fields=champs + ['updated_at'])
        element = journaliser_suppression(
            instance=calepinage, company=calepinage.company, user=user,
            type_libelle='Calepinage', libelle=str(calepinage),
            donnees=({'devis_id': devis_detache} if devis_detache else None),
            now=calepinage.archive_le)

    if devis_detache:
        journaliser_lien_devis(calepinage, ancien=devis_detache,
                               nouveau=None, user=user)
    noter(calepinage, 'Calepinage archivé (corbeille).', user=user)
    return element


def restaurer(calepinage, *, user=None):
    """Restaure ``calepinage`` — à l'identique, tracé (ACAL118).

    L'entrée de corbeille ACTIVE est fermée par ``apps.trash`` (qui appelle
    ``restaurateur_calepinage``) ; une entrée déjà purgée n'empêche pas la
    restauration : ``archive_le`` est alors simplement remis à ``None``.

    Raises:
        ArchivageInvalide: calepinage non enregistré, ou pas archivé (rien à
            restaurer).
    """
    from apps.trash.selectors import entree_active
    from apps.trash.services import restaurer as restaurer_element

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ArchivageInvalide(
            "Impossible de restaurer un calepinage non enregistré.",
            champ='calepinage')
    if not est_archive(calepinage):
        raise ArchivageInvalide(
            "Ce calepinage n'est pas archivé : rien à restaurer.",
            champ='calepinage')

    element = entree_active(calepinage)
    if element is not None:
        # Lot 2 critique #13 — le désarchivage (et le re-rattachement du
        # devis) est journalisé au nom de QUI RESTAURE : fait ici avec
        # ``user`` ; le restaurateur appelé ensuite par ``apps.trash`` n'a
        # plus rien à faire (idempotent) et ferme l'entrée.
        donnees = element.donnees_snapshot if isinstance(
            element.donnees_snapshot, dict) else {}
        _desarchiver(calepinage, devis_id=donnees.get('devis_id'), user=user)
        restaurer_element(element, user=user)
    else:
        _desarchiver(calepinage, devis_id=None, user=user)
    calepinage.refresh_from_db()

    from .journal import noter

    noter(calepinage, 'Calepinage restauré depuis la corbeille.', user=user)
    return calepinage


class RestaurationEnConflit(APIException):
    """Lot 2 critique #12 (D-ACAL-12) — 409 NOMMÉ : restaurer ce calepinage
    ferait un SECOND calepinage ouvert sur son lead. ``APIException`` : la
    porte calepinage ET l'écran corbeille (``apps.trash``) répondent 409 sans
    toucher un seul ``except``."""

    status_code = 409
    default_code = 'calepinage_restauration_conflit'


def _refuser_si_le_lead_a_deja_un_ouvert(calepinage, user=None):
    """Un calepinage restauré ne peut pas devenir le SECOND ouvert de son
    lead ; un MODÈLE n'est jamais « l'ouvert » de son lead (ACAL187)."""
    if not getattr(calepinage, 'lead_id', None):
        return
    from ..selectors import calepinage_ouvert_du_lead
    from .creation import corps_conflit
    from .modeles import est_modele

    if est_modele(calepinage):
        return
    existant = calepinage_ouvert_du_lead(calepinage.company,
                                         calepinage.lead_id)
    if existant is not None and existant.pk != calepinage.pk:
        raise RestaurationEnConflit(corps_conflit(existant, user))


def _desarchiver(calepinage, *, devis_id=None, user=None):
    """ACAL118 — remet ``archive_le`` à ``None`` et rattache le devis
    détaché à l'archivage S'IL EST LIBRE (``liens.lier_devis`` refuse un
    devis déjà pris : il reste alors détaché, sans erreur).

    Lot 2 critique #12 — refus 409 nommé (``RestaurationEnConflit``) quand
    le lead a déjà un AUTRE calepinage ouvert (D-ACAL-12)."""
    if calepinage.archive_le is not None:
        _refuser_si_le_lead_a_deja_un_ouvert(calepinage, user)
        calepinage.archive_le = None
        calepinage.save(update_fields=['archive_le', 'updated_at'])
    if devis_id and not calepinage.devis_id:
        from .liens import LiaisonRefusee, lier_devis

        try:
            lier_devis(calepinage, devis_id, user=user)
        except LiaisonRefusee:
            pass
    return calepinage


def restaurateur_calepinage(element):
    """Restaurateur enregistré dans ``apps.py`` ``ready()`` — signature
    imposée par ``apps.trash.registry`` (reçoit l'``ElementSupprime``, rend
    l'objet restauré). ACAL118 : remet ``archive_le`` à ``None`` et rattache
    le devis détaché (``donnees_snapshot['devis_id']``) s'il est libre —
    même chemin depuis l'écran corbeille et depuis ``restaurer``."""
    from ..models import Calepinage

    calepinage = Calepinage.objects.filter(pk=element.object_id).first()
    if calepinage is None:
        return None
    donnees = element.donnees_snapshot if isinstance(
        element.donnees_snapshot, dict) else {}
    # Lot 2 critique #13 — la signature imposée par ``apps.trash`` ne porte
    # pas QUI restaure : aucun auteur plutôt que celui qui avait SUPPRIMÉ
    # (``supprime_par``). La porte calepinage (``restaurer``) désarchive
    # elle-même avec l'auteur réel avant d'appeler la corbeille.
    return _desarchiver(calepinage, devis_id=donnees.get('devis_id'),
                        user=None)


def restaurateur_piece_jointe(element):
    """ACAL148 — restaurateur d'une pièce jointe mise à la corbeille (fichier
    météo retiré/remplacé). Comme ``restaurateur_calepinage`` il ne modifie
    RIEN : l'état « retirée » est porté par l'entrée de corbeille ACTIVE
    (``simulation.lire_piece_meteo`` l'exclut) ; fermer l'entrée suffit à
    rendre la pièce de nouveau retenue."""
    from apps.records.models import Attachment

    return Attachment.objects.filter(pk=element.object_id).first()
