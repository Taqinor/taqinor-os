"""Les DOCUMENTS imprimables du module calepinage (lot 6 — CALX291-CALX330).

Un paquet, pas un module : le gabarit société (``gabarit_document``), les
libellés FR/EN (``libelles_document``) et chaque pièce du lot 6 y posent LEUR
fichier, et ce ``__init__`` reste une surface APPEND-ONLY (une section par
tâche, ajoutée EN FIN, jamais réordonnée) — deux lanes du même lot ne se
disputent ainsi jamais le même fichier.

AUCUN IMPORT AU CHARGEMENT : importer ``services.documents.gabarit_document``
exécute d'abord ce fichier ; un import lourd ici (WeasyPrint, modèles) se
paierait à chaque lecture d'un libellé. Les sections ci-dessous importent
FONCTION-LOCALEMENT.

Rien ici n'est un devis client : ``/proposal`` reste le seul PDF de devis
(règle #4) et aucune pièce du module ne porte de montant (D5).
"""
from __future__ import annotations


# ── CALX297 — le rapport d'étude ────────────────────────────────────────────
#: ``code du document -> chemin de SA fonction de mise en page`` : UNE seule
#: fonction HTML par document, que le rendu PDF et l'aperçu (CALX323)
#: partagent. Les pièces suivantes du lot AJOUTENT leur ligne ici.
MISES_EN_PAGE = {
    'rapport_etude': 'apps.calepinage.services.rapport:html_du_rapport',
}


def mise_en_page(code):
    """La fonction de mise en page HTML du document ``code`` (import tardif).

    Lève ``KeyError`` en nommant le code quand le document n'en a pas.
    """
    from importlib import import_module

    try:
        chemin = MISES_EN_PAGE[code]
    except KeyError:
        raise KeyError('Document sans mise en page déclarée : « %s ».'
                       % code) from None
    module, _, fonction = chemin.partition(':')
    return getattr(import_module(module), fonction)


# ── CALX310 — le plan de câblage des chaînes ────────────────────────────────
MISES_EN_PAGE['plan_cablage'] = (
    'apps.calepinage.services.documents.plan_cablage:html_du_plan_cablage')
