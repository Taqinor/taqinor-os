"""Lectures cross-app du module Notes de frais (``apps.frais``) — ODX15.

Point d'entrée ``selectors.py`` exigé par CLAUDE.md : un appelant d'une autre
app (``apps.paie`` pour le remboursement via bulletin, XPAI25) lit les frais
d'ici, sans importer ``apps.frais.models`` ni — surtout — ``apps.compta.models``.

Les implémentations restent celles de ``apps.compta.selectors`` (elles agrègent
des données comptables : montants postés, statuts de remboursement) — ré-export,
pas duplication.
"""

from apps.compta.selectors import (  # noqa: F401
    analyse_notes_frais,
    indemnites_chantier_remboursables_par_paie,
)

__all__ = [
    'analyse_notes_frais',
    'indemnites_chantier_remboursables_par_paie',
    'note_frais_par_id',
]


def note_frais_par_id(company, note_id):
    """NTMOB7 — une ``NoteFrais`` par id, scopée société (``None`` si absente
    ou hors société). Point d'entrée en LECTURE pour un appelant externe (ex.
    ``reporting.approbations``, décision via jeton de notification push) qui
    ne doit importer ni ``apps.frais.models`` ni — surtout — jamais
    ``apps.compta.models`` directement (frontière ODX15)."""
    if company is None or not note_id:
        return None
    from apps.frais.models import NoteFrais
    return NoteFrais.objects.filter(company=company, id=note_id).first()
