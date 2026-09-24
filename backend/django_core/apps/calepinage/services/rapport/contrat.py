"""Le CONTRAT du rapport d'étude — sa déclaration de sections et son refus.

POURQUOI UNE FEUILLE À PART (fix CI #714, contrat import-linter CAL5)
=====================================================================
``ParametresCalepinage.clean()`` (``models.py``, CALX307) valide la sélection
de sections d'une société : il lui faut ``RapportRefuse`` et la liste
déclarée par ``rapport_etude.json`` — RIEN d'autre. Or ces deux noms vivaient
dans ``services/rapport/__init__.py``, l'ASSEMBLEUR, dont les imports
(même fonction-locaux : import-linter les compte) atteignent ``selectors``,
``services/electrique`` et ``services/documents`` — donc, de proche en
proche, ``apps.stock.models`` et ``apps.ventes.models``. Le contrat
« Calepinage models never import a business-core domain's models » (CAL5)
cassait dès que ``models.py`` touchait le paquet.

Ce module est une FEUILLE : bibliothèque standard seule, aucun import du
projet. ``models.py`` et ``sections_societe.py`` l'importent directement ;
``services/rapport/__init__.py`` en RÉEXPORTE les noms, si bien que
``from ..services.rapport import RapportRefuse`` reste valable partout (même
classe, même identité — ``except RapportRefuse`` inchangé).
"""
from __future__ import annotations

import functools
import json
import pathlib

__all__ = ['CODE_DOCUMENT', 'CHEMIN_CONTRAT', 'RapportRefuse',
           'sections_declarees']

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'rapport_etude'

#: La déclaration des sections (CALX292) — lue, jamais recopiée ici.
CHEMIN_CONTRAT = (pathlib.Path(__file__).resolve().parents[2]
                  / 'contract_samples' / 'rapport_etude.json')


class RapportRefuse(ValueError):
    """Le rapport refuse de sortir, et il NOMME la donnée en cause."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ── La déclaration des sections (CALX292) ───────────────────────────────────

@functools.lru_cache(maxsize=1)
def _contrat():
    return json.loads(CHEMIN_CONTRAT.read_text(encoding='utf-8'))


def sections_declarees():
    """Les sections du contrat, dans l'ordre d'impression (copies détachées)."""
    sections = _contrat()['exemple']['sections']
    return [dict(section, entrees_exigees=list(section['entrees_exigees']))
            for section in sorted(sections, key=lambda s: s['ordre'])]
