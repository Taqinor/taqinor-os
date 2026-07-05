"""Services (écriture) du module ``apps.litiges``.

Comme ``selectors.py`` (lecture), destiné à être importé PAR D'AUTRES APPS
(import local, jamais au niveau module) pour créer/faire évoluer une
réclamation sans jamais importer ``apps.ventes``/``apps.crm``/etc. — toute
référence à un document d'une autre app passe par le couple souple
``source_type``/``source_id``, jamais par un import de modèle.
"""
from decimal import Decimal


def creer_reclamation(*, company, type_reclamation, source_type, source_id,
                      objet, description='', montant_conteste=None,
                      gravite=None, bloque_relances=True, user=None):
    """XFAC27 — Ouvre une ``Reclamation`` générique (type au choix de
    l'appelant, contrairement à ``creer_dossier_recouvrement`` qui est figé
    sur ``RECOUVREMENT``). Utilisé par le pont portail client « contester une
    facture » (``apps.compta`` — jamais un import de ``apps.litiges.models``
    en dehors de ce module). ``bloque_relances`` (défaut True, LITIGE3)
    suspend les relances automatiques de la facture liée tant que le litige
    est ouvert. Renvoie l'instance ``Reclamation`` créée."""
    from .models import Reclamation

    return Reclamation.objects.create(
        company=company,
        type_reclamation=type_reclamation,
        gravite=gravite or Reclamation.Gravite.MOYENNE,
        objet=objet,
        description=description or '',
        source_type=source_type or '',
        source_id=source_id,
        montant_conteste=Decimal(montant_conteste or 0),
        bloque_relances=bloque_relances,
        created_by=user if (
            user and getattr(user, 'is_authenticated', False)) else None,
    )


def creer_dossier_recouvrement(*, company, source_type, source_id, objet,
                               montant_conteste=None, description='',
                               user=None):
    """XFAC21 — ouvre un dossier contentieux / recouvrement externe.

    Crée une ``Reclamation`` de type ``recouvrement`` (bloque les relances
    ordinaires par défaut, comme tout litige financier). ``company`` est
    TOUJOURS fournie par l'appelant (jamais dérivée du corps de requête côté
    ventes). Idempotent côté appelant : cette fonction crée systématiquement
    une nouvelle réclamation (l'appelant décide s'il réutilise un dossier
    existant — voir ``apps.ventes.services.ouvrir_dossier_contentieux``, qui
    réutilise un dossier de recouvrement déjà ouvert pour le même client).
    Renvoie l'instance ``Reclamation`` créée."""
    from .models import Reclamation

    return Reclamation.objects.create(
        company=company,
        type_reclamation=Reclamation.TypeReclamation.RECOUVREMENT,
        gravite=Reclamation.Gravite.ELEVEE,
        objet=objet,
        description=description or '',
        source_type=source_type or '',
        source_id=source_id,
        montant_conteste=Decimal(montant_conteste or 0),
        bloque_relances=True,
        created_by=user if (
            user and getattr(user, 'is_authenticated', False)) else None,
    )
