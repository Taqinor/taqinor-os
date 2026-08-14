"""Groupe NTWMS — services ÉCRITURE/orchestration de la couche entrepôt.

Ré-exporté par ``apps/stock/services.py`` (fin de fichier) : les appelants
continuent d'écrire ``from apps.stock.services import …``.

FRONTIÈRE INTER-APPS. Les casiers (``BinLocation``, FG319) et les règles de
rangement (``RegleRangement``/``CategorieStockage``, ZSTK9) vivent dans
``installations`` : ce module les LIT via ``apps.installations.selectors``
(jamais un import de ses modèles, jamais un modèle parallèle dans ``stock``).
"""
import logging

logger = logging.getLogger('stock.wms')


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS2 — Rangement guidé (put-away) proposé à la confirmation d'une réception
# ═══════════════════════════════════════════════════════════════════════════

def suggestions_rangement_reception(reception):
    """Casier SUGGÉRÉ pour chaque ligne d'une réception, AVANT validation.

    Une ligne = ``{ligne_id, produit_id, produit_nom, quantite,
    emplacement_id, emplacement_nom, bin_id, bin_code, bin_zone,
    source}`` — ``source`` vaut ``'regle'`` quand une règle de rangement
    (ZSTK9) ou un casier déjà affecté a tranché, ``'aucun'`` quand aucun
    casier n'est proposable (le magasinier range librement : comportement
    historique). Le casier reste MODIFIABLE côté client : cette fonction
    PROPOSE, elle n'écrit rien.

    La suggestion réutilise ``installations.selectors.suggerer_bin_putaway``
    (FG320/ZSTK9) : règle active → casier déjà affecté au produit → premier
    casier libre par ordre de parcours, chacun sous garde de capacité.
    """
    from apps.installations.selectors import suggerer_bin_putaway

    if reception is None:
        return []
    company = reception.company
    bon = reception.bon_commande
    emplacement = getattr(bon, 'emplacement_destination', None)
    emplacement_id = getattr(bon, 'emplacement_destination_id', None)

    lignes = (reception.lignes
              .select_related('produit')
              .order_by('id'))
    out = []
    for ligne in lignes:
        produit = ligne.produit
        entree = {
            'ligne_id': ligne.id,
            'produit_id': ligne.produit_id,
            'produit_nom': getattr(produit, 'nom', '') or '',
            'quantite': ligne.quantite,
            'emplacement_id': emplacement_id,
            'emplacement_nom': getattr(emplacement, 'nom', '') or '',
            'bin_id': None,
            'bin_code': '',
            'bin_zone': '',
            'source': 'aucun',
        }
        if ligne.produit_id:
            bin_loc = suggerer_bin_putaway(
                company, ligne.produit_id, emplacement_id,
                ligne.quantite or 0)
            if bin_loc is not None:
                entree.update({
                    'bin_id': bin_loc.id,
                    'bin_code': bin_loc.code,
                    'bin_zone': bin_loc.zone or '',
                    'source': 'regle',
                })
        out.append(entree)
    return out
