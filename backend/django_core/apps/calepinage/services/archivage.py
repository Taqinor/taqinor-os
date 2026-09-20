"""CAL208 — archiver un calepinage, RÉVERSIBLE, par la corbeille plateforme.

AUCUNE SECONDE CORBEILLE, AUCUNE SUPPRESSION DURE
-----------------------------------------------------
``apps.trash`` (NTUX7) est DÉJÀ la primitive corbeille transverse de tout le
dépôt (``ElementSupprime``, générique par ``ContentType``). Ce module ne
crée RIEN : il journalise une suppression LOGIQUE (``apps.trash.services.
journaliser_suppression``) et restaure via ``apps.trash.services.restaurer``
— jamais un ``.delete()`` sur ``Calepinage``, jamais un second modèle
d'archive.

AUCUN NOUVEAU CHAMP
-----------------------
``Calepinage`` ne porte ni ``is_archived`` ni ``is_deleted`` : l'état
archivé/actif est ENTIÈREMENT porté par la présence (ou l'absence) d'une
entrée ACTIVE dans ``ElementSupprime`` (``apps.trash.selectors.
entree_active`` / ``ids_dans_corbeille`` — jamais un import direct
d'``ElementSupprime``). Le restaurateur enregistré dans ``apps.py``
``ready()`` (``apps.trash.registry``) ne modifie donc rien sur l'objet
lui-même — il le renvoie tel quel, l'état vit dans la corbeille.

``selectors.appliquer_filtres_liste`` exclut les calepinages archivés de la
liste PAR DÉFAUT (CAL208, ``inclure_archives=False``) — un calepinage lié à
un devis envoyé s'archive sans jamais toucher au devis (règle #4).
"""
from __future__ import annotations

#: Clé de registre / ContentType, DANS ``apps.trash`` (``cle_modele``).
CLE_MODELE = 'calepinage.calepinage'

__all__ = ['ArchivageInvalide', 'CLE_MODELE', 'est_archive', 'archiver',
           'restaurer', 'restaurateur_calepinage']


class ArchivageInvalide(ValueError):
    """Erreur métier, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def est_archive(calepinage):
    """``True`` si ``calepinage`` a une entrée ACTIVE dans la corbeille —
    lecture pure."""
    from apps.trash.selectors import entree_active

    return entree_active(calepinage) is not None


def archiver(calepinage, *, user=None):
    """Archive ``calepinage`` par la corbeille — réversible, journalisé.

    Idempotent : archiver un calepinage déjà archivé ne crée pas de seconde
    entrée (``journaliser_suppression`` l'est déjà côté ``apps.trash``).

    Raises:
        ArchivageInvalide: calepinage non enregistré.
    """
    from apps.trash.services import journaliser_suppression

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ArchivageInvalide(
            "Impossible d'archiver un calepinage non enregistré.",
            champ='calepinage')

    element = journaliser_suppression(
        instance=calepinage, company=calepinage.company, user=user,
        type_libelle='Calepinage', libelle=str(calepinage))

    from .journal import noter

    noter(calepinage, 'Calepinage archivé (corbeille).', user=user)
    return element


def restaurer(calepinage, *, user=None):
    """Restaure ``calepinage`` DEPUIS la corbeille — à l'identique, tracé.

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
    element = entree_active(calepinage)
    if element is None:
        raise ArchivageInvalide(
            "Ce calepinage n'est pas archivé : rien à restaurer.",
            champ='calepinage')

    restaurer_element(element, user=user)

    from .journal import noter

    noter(calepinage, 'Calepinage restauré depuis la corbeille.', user=user)
    return calepinage


def restaurateur_calepinage(element):
    """Restaurateur enregistré dans ``apps.py`` ``ready()`` — signature
    imposée par ``apps.trash.registry`` (reçoit l'``ElementSupprime``, rend
    l'objet restauré). Ne modifie RIEN sur ``Calepinage`` : l'état
    archivé/actif est entièrement porté par la corbeille elle-même."""
    from ..models import Calepinage

    return Calepinage.objects.filter(pk=element.object_id).first()
