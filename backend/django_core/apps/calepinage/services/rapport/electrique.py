"""CALX303 — la section « Électrique » du rapport, schéma unifilaire inclus.

Le constat
==========
Le schéma unifilaire est un SVG produit HORS du module et servi à un seul
panneau (``apps/calepinage/views/schema.py:55-102`` →
``apps.ventes.selectors.schema_unifilaire_svg``), et le dossier
réglementaire sait déjà l'encapsuler pour l'impression
(``services/reglementaire.py::_rendus_du_module``, via
``planche.html_de_planche``) : c'est une pièce SÉPARÉE, fusionnée en PDF, pas
un fragment HTML embarqué. Aucune pièce d'étude ne porte chaînage, verdicts
et schéma ensemble.

DEUX SURFACES, POUR DEUX RAISONS (même discipline que ``systeme.py``,
CALX299)
=========================================================================
* ``html_de_section(contexte)`` — la forme APPELÉE par l'assembleur
  (``services/rapport/__init__.py``) : PURE, elle ne lit QUE
  ``contexte['resultat']['electrique']`` — chaînage, table des onduleurs
  (ratio DC/AC compris) et table des verdicts, servis TELS QUELS, sans rien
  recalculer ;
* ``bloc_schema_unifilaire(calepinage, …)``/``rendre_rapport_avec_schema`` —
  la jonction du schéma exige la base (le devis LIÉ porte l'électrique
  chiffrée : ``apps.ventes.selectors.schema_unifilaire_svg(devis)``) : ces
  fonctions prennent le CALEPINAGE directement, exactement comme
  ``reglementaire._rendus_du_module``. Elles ne sont PAS encore appelées par
  ``rendre_rapport`` — crochet de phase 2 (voir la docstring de
  ``services/rapport/__init__.py``).

Le motif MOT POUR MOT
======================
``MOTIF_SCHEMA_INDISPONIBLE`` reprend, caractère pour caractère, la phrase
de ``services/reglementaire.py::_rendus_du_module`` (sa fermeture
``_schema()``) : un lecteur qui compare le dossier réglementaire et ce
rapport ne doit jamais lire deux formulations différentes pour la même
absence.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = [
    'CSS_SECTION', 'MOTIF_SCHEMA_INDISPONIBLE', 'MENTION_NON_VERIFIABLE',
    'html_de_section', 'html_table_verdicts', 'bloc_schema_unifilaire',
    'rendre_rapport_avec_schema',
]

#: La feuille de la section — hachure d'un verdict non vérifiable, mêmes gris
#: que la charte d'impression du rapport (voir ``pertes.CSS_SECTION``).
CSS_SECTION = (
    '.electrique-onduleurs td.num,.electrique-onduleurs th.num,'
    '.electrique-chainage td.num{text-align:right;}'
    '.electrique-verdicts tr.non-verifiable td{background:'
    'repeating-linear-gradient(45deg,#f2f2f2 0,#f2f2f2 1.2mm,#999 1.2mm,'
    '#999 1.5mm);}'
    '.electrique-verdicts tr.non-conforme td{font-weight:bold;}'
    '.electrique-verdicts .detail{display:block;font-size:7.5pt;color:#555;}'
    '.schema-unifilaire{margin-top:4mm;}'
)

#: Le vocabulaire du MOTEUR (``core/electrique/chaines.py::_borne_texte``) —
#: jamais « OK », jamais une valeur devinée.
MENTION_NON_VERIFIABLE = 'non vérifiable'

#: MOT POUR MOT ``services/reglementaire.py::_rendus_du_module`` (fonction
#: ``_schema``) — voir la docstring du module.
MOTIF_SCHEMA_INDISPONIBLE = (
    "Aucun schéma unifilaire n'est disponible pour ce calepinage : il se "
    "produit depuis le devis lié.")


def _table_chainage(chainage, langue):
    if not isinstance(chainage, dict) or not chainage:
        return ''
    lignes = (
        ('Modules chaînés', chainage.get('modules')),
        ('Modules par chaîne', chainage.get('modules_par_chaine')),
        ('Nombre de chaînes', chainage.get('chaines')),
        ('Modules hors chaîne', chainage.get('reste')),
    )
    corps = ''.join(
        '<tr><th>%s</th><td class="num">%s</td></tr>'
        % (escape(libelle), nombre_tel_que_servi(valeur, langue))
        for libelle, valeur in lignes)
    return '<table class="electrique-chainage">%s</table>' % corps


def _table_onduleurs(onduleurs, langue):
    if not onduleurs:
        return ''
    entete = (
        '<tr><th>Onduleur</th><th class="num">Nombre</th>'
        '<th class="num">DC (kWc)</th><th class="num">Ratio DC/AC</th>'
        '<th>Conforme</th></tr>')
    lignes = []
    for onduleur in onduleurs:
        if not isinstance(onduleur, dict):
            continue
        conforme = onduleur.get('conforme')
        texte = (MENTION_NON_VERIFIABLE if conforme is None
                 else ('oui' if conforme else 'non'))
        if onduleur.get('motif'):
            texte += '<span class="detail">%s</span>' % escape(
                str(onduleur['motif']))
        lignes.append(
            '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td>%s</td></tr>'
            % (escape(str(onduleur.get('reference') or '')),
               nombre_tel_que_servi(onduleur.get('nombre'), langue),
               nombre_tel_que_servi(onduleur.get('puissance_dc_kwc'),
                                    langue),
               nombre_tel_que_servi(onduleur.get('ratio_dc_ac'), langue),
               texte))
    return '<table class="electrique-onduleurs">%s%s</table>' % (
        entete, ''.join(lignes))


def html_table_verdicts(verdicts, langue='fr'):
    """La table des verdicts, ``bloquant``/``conforme``/``source``/``detail``
    SERVIS TELS QUELS — un ``conforme: null`` imprime ``« non vérifiable »``,
    jamais « OK » et jamais une valeur devinée (vocabulaire du moteur,
    ``core/electrique/chaines.py``). PURE — aucune base, aucun recalcul.
    """
    verdicts = [v for v in verdicts or () if isinstance(v, dict)]
    if not verdicts:
        return ''
    entete = ('<tr><th>Contrôle</th><th>Verdict</th><th>Bloquant</th>'
              '<th>Source</th><th>Détail</th></tr>')
    lignes = []
    for verdict in verdicts:
        conforme = verdict.get('conforme')
        if conforme is None:
            texte, classe = MENTION_NON_VERIFIABLE, 'non-verifiable'
        elif conforme:
            texte, classe = 'conforme', ''
        else:
            texte, classe = 'non conforme', 'non-conforme'
        bloquant = verdict.get('bloquant')
        texte_bloquant = ('oui' if bloquant else 'non'
                          if bloquant is not None else '—')
        detail = str(verdict.get('detail') or '')
        mention_temp = str(verdict.get('temperature_mention') or '')
        if mention_temp:
            detail = (detail + ' — ' + mention_temp) if detail \
                else mention_temp
        lignes.append(
            '<tr%s><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
            '<td>%s</td></tr>'
            % (' class="%s"' % classe if classe else '',
               escape(str(verdict.get('libelle') or verdict.get('code')
                          or '')),
               texte, texte_bloquant,
               escape(str(verdict.get('source') or '—')),
               escape(detail) if detail else '—'))
    return '<table class="electrique-verdicts">%s%s</table>' % (
        entete, ''.join(lignes))


def html_de_section(contexte):
    """Le corps de la section ``electrique`` (le titre est posé par
    l'assembleur). PUR — ne lit que ``contexte['resultat']['electrique']``.
    """
    resultat = contexte.get('resultat') or {}
    langue = contexte.get('langue') or 'fr'
    electrique = resultat.get('electrique') or {}

    blocs = [_table_chainage(electrique.get('chainage'), langue)]
    onduleurs = [o for o in electrique.get('onduleurs') or ()
                 if isinstance(o, dict)]
    if onduleurs:
        blocs.append('<h3>Onduleurs</h3>')
        blocs.append(_table_onduleurs(onduleurs, langue))
    verdicts = electrique.get('verdicts')
    table_verdicts = html_table_verdicts(verdicts, langue)
    if table_verdicts:
        blocs.append('<h3>Verdicts</h3>')
        blocs.append(table_verdicts)
    return ''.join(b for b in blocs if b)


# ── Le schéma unifilaire — lit la base, prend le calepinage ─────────────────

def bloc_schema_unifilaire(calepinage, *, company=None):
    """``(octets_pdf, motif)`` — le schéma unifilaire, encapsulé comme le fait
    ``reglementaire._rendus_du_module`` (``html_de_planche`` + ``render_pdf``),
    ou ``(None, MOTIF_SCHEMA_INDISPONIBLE)`` MOT POUR MOT quand aucun devis
    n'est lié ou que le devis ne publie aucun schéma.
    """
    from apps.ventes.selectors import schema_unifilaire_svg
    from core.pdf import render_pdf

    from ..planche import html_de_planche

    # ``schema_unifilaire_svg`` est keyword-only (``*, devis=None, …`` —
    # ``apps/ventes/selectors.py:449``) : l'appel positionnel de
    # ``services/reglementaire.py::_rendus_du_module`` (``:522``) lèverait un
    # ``TypeError`` s'il s'exécutait — défaut PRÉEXISTANT, hors du fichier de
    # cette tâche, signalé sans être corrigé ici.
    devis_id = getattr(calepinage, 'devis_id', None)
    svg = schema_unifilaire_svg(devis=calepinage.devis) if devis_id else ''
    if not svg:
        return None, MOTIF_SCHEMA_INDISPONIBLE
    octets = render_pdf(
        html=html_de_planche(svg),
        company=company or getattr(calepinage, 'company', None))
    return octets, None


def rendre_rapport_avec_schema(calepinage, octets_rapport, *, company=None,
                               construire_bloc=None):
    """Le rapport + le schéma unifilaire — SANS AUCUNE PAGE VIDE quand il
    n'est pas disponible (rend ``octets_rapport`` inchangé, avec le motif).

    Rend ``(octets, motif)`` — ``motif`` est ``''`` quand le schéma a été
    joint. ``construire_bloc`` — point d'injection pour les essais (par
    défaut ``bloc_schema_unifilaire``, qui parle à la base).
    """
    from .systeme import fusionner_octets_pdf

    construire_bloc = construire_bloc or bloc_schema_unifilaire
    octets_schema, motif = construire_bloc(calepinage, company=company)
    if not octets_schema:
        return octets_rapport, motif or ''
    return fusionner_octets_pdf([octets_rapport, octets_schema]), ''
