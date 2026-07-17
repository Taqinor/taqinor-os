"""Orchestration ÉCRITURE cross-app du domaine Agriculture.

Réservé aux tâches du groupe NTAGR nécessitant une orchestration d'écriture
(ex. NTAGR15 numérotation de lot, futures NTAGR26 préparation d'audit qhse,
NTAGR29 export coopérative) qui appelleront ``paie.services``/
``qhse.services`` par nom de fonction, jamais par import de modèle
(CLAUDE.md, frontière cross-app)."""


def creer_lot_recolte(
        *, company, campagne, date_recolte, quantite_qtl,
        calibre='', qualite='', stock_lot_id=''):
    """NTAGR15 — Crée un ``LotRecolte`` avec un ``numero_lot`` unique par
    société, race-safe (plus-haut-utilisé+1, savepoint+retry) via
    ``core.numbering.create_with_reference`` — JAMAIS un ``count()+1``. Le
    numéro est généré AVANT l'insertion (jamais posé après coup) : deux
    créations concurrentes ne peuvent jamais obtenir le même numéro."""
    from core.numbering import create_with_reference

    from .models import LotRecolte

    def _save(reference):
        return LotRecolte.objects.create(
            company=company, campagne=campagne, date_recolte=date_recolte,
            quantite_qtl=quantite_qtl, calibre=calibre, qualite=qualite,
            stock_lot_id=stock_lot_id, numero_lot=reference)

    return create_with_reference(
        LotRecolte, 'LOT', company, _save, padding=4, period='monthly')
