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
    ``core.numbering`` — JAMAIS un ``count()+1``. Le numéro est généré AVANT
    l'insertion (jamais posé après coup) : deux créations concurrentes ne
    peuvent jamais obtenir le même numéro.

    ``LotRecolte`` porte son numéro sur ``numero_lot`` (jamais ``reference``)
    : ``core.numbering.create_with_reference`` ne transmet pas de ``field``
    personnalisé à ``next_reference`` (il resterait sur son défaut
    ``'reference'``, absent de ce modèle), donc la boucle savepoint+retry est
    reproduite ICI avec ``next_reference(..., field='numero_lot')`` — même
    algorithme, jamais dupliqué en logique, seulement en câblage."""
    from django.db import IntegrityError, transaction

    from core.numbering import MAX_ATTEMPTS, next_reference

    from .models import LotRecolte

    last_exc = None
    for _ in range(MAX_ATTEMPTS):
        numero_lot = next_reference(
            LotRecolte, 'LOT', company, padding=4, period='monthly',
            field='numero_lot')
        try:
            with transaction.atomic():
                return LotRecolte.objects.create(
                    company=company, campagne=campagne,
                    date_recolte=date_recolte, quantite_qtl=quantite_qtl,
                    calibre=calibre, qualite=qualite,
                    stock_lot_id=stock_lot_id, numero_lot=numero_lot)
        except IntegrityError as exc:
            if 'numero_lot' not in str(exc).lower():
                raise
            last_exc = exc
    raise last_exc
