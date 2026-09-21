"""ZPRJ9 — Rapport « Point d'avancement projet » (PDF INTERNE).

Rendu via le MÊME pipeline que les PDF legacy (factures, compte-rendu
d'intervention F19) : ``apps.ventes.utils.pdf`` (identité société + template
Jinja2/Django + WeasyPrint). CE N'EST PAS le moteur premium ``/proposal``
réservé aux devis client (règle #4 CLAUDE.md) — ce document est strictement
INTERNE et peut exposer budget/coûts/marge, jamais transmis au client par ce
chemin.

Agrège les sélecteurs déjà existants (lecture seule, aucune écriture) :
``rollup_avancement``, ``jalons_for_projet``, ``retards_projet``,
``evm_projet``, ``synthese_temps_projet``. Un projet sans données
(jalons/risques/temps) dégrade proprement — jamais de crash.
"""
from apps.ventes.utils.pdf import _company_context, _html_to_pdf, _render_html

from .models import Jalon
from . import selectors


def _jalons_payload(projet):
    return [
        {
            'libelle': j.libelle,
            'date_prevue': j.date_prevue,
            'statut': j.get_statut_display(),
            'atteint': j.statut == Jalon.Statut.ATTEINT,
        }
        for j in selectors.jalons_for_projet(projet)
    ]


def rapport_avancement_pdf(projet):
    """Génère le PDF INTERNE « Point d'avancement projet » (ZPRJ9).

    Entête projet, % avancement (rollup), jalons atteints/à venir, retards,
    EVM (SPI/CPI/EAC) et synthèse des temps. Document strictement INTERNE :
    peut exposer des données de coût — jamais transmis au client via ce
    chemin (le seul chemin client-facing pour un PDF de devis reste
    ``/proposal``, règle #4).
    """
    company = projet.company
    context = _company_context(company=company)

    avancement = selectors.rollup_avancement(projet)
    retards = selectors.retards_projet(projet)

    try:
        evm = selectors.evm_projet(company, projet)
    except Exception:
        evm = None

    try:
        synthese_temps = selectors.synthese_temps_projet(projet)
    except Exception:
        synthese_temps = None

    jalons = _jalons_payload(projet)
    jalons_atteints = [j for j in jalons if j['atteint']]
    jalons_a_venir = [j for j in jalons if not j['atteint']]

    context.update({
        'projet': projet,
        'avancement': avancement,
        'jalons_atteints': jalons_atteints,
        'jalons_a_venir': jalons_a_venir,
        'retards': retards,
        'evm': evm,
        'synthese_temps': synthese_temps,
    })
    html = _render_html('rapport_avancement_projet.html', context)
    return _html_to_pdf(html)
