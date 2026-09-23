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
